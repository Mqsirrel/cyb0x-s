"""Offline scan ingestion engine for GLACIS Field Notebook.

Strictly passive and manual:
- Parses local scan output files (Nmap XML, normal text, Gnmap, NetExec).
- Operates 100% offline: zero network interaction, zero automated scanning.
- Human-in-the-loop review: extracts candidates for user confirmation.
- Preserves raw output files in workspace `scans/` folder as immutable evidence.
- Tracks SHA-256 file hashes to prevent redundant duplicates.
"""

from __future__ import annotations

import hashlib
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from glacis.db.store import NotebookStore
from glacis.models import Lead, ScanImport, Target
from glacis.parsers import parse_nmap_text, parse_scan_file


def compute_file_hash(file_path: Union[str, Path]) -> str:
    """Compute SHA-256 checksum of a file for import deduplication."""
    p = Path(file_path).expanduser().resolve()
    hasher = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def inspect_scan_file(file_path: Union[str, Path]) -> List[Dict[str, Any]]:
    """Parse a scan file offline for user review without committing to database.

    Handles complete or truncated files gracefully (e.g. interrupted Nmap scans).
    """
    p = Path(file_path).expanduser().resolve()
    if not p.is_file():
        raise FileNotFoundError(f"Scan file not found: {file_path}")

    # Detect truncated XML and fallback safely
    try:
        return parse_scan_file(p)
    except ET.ParseError:
        # Interrupted XML scan: salvage what was discovered before interruption
        salvaged = _salvage_truncated_xml(p)
        if salvaged:
            return salvaged
        return parse_nmap_text(p)


def _salvage_truncated_xml(file_path: Path) -> List[Dict[str, Any]]:
    """Emergency regex parser to salvage open ports from an interrupted/malformed Nmap XML."""
    import re

    raw = file_path.read_text(encoding="utf-8", errors="replace")
    results: List[Dict[str, Any]] = []

    # Find host blocks even if </host> or </nmaprun> is missing
    host_raw_blocks = re.split(r"<host[\s>]", raw)
    for chunk in host_raw_blocks[1:]:
        if "</host>" in chunk:
            chunk = chunk.split("</host>")[0]

        # IP
        ip_m = re.search(r'<address\s+[^>]*addr="([0-9a-fA-F.:]+)"', chunk)
        if not ip_m:
            continue
        ip = ip_m.group(1)

        # Hostname
        hn_m = re.search(r'<hostname\s+[^>]*name="([^"]+)"', chunk)
        hostname = hn_m.group(1) if hn_m else ""

        # OS
        os_m = re.search(r'<osmatch\s+[^>]*name="([^"]+)"', chunk)
        os_name = os_m.group(1) if os_m else "Unknown"

        # Ports (handling flexible attribute order between protocol and portid)
        services = []
        port_matches = re.finditer(r'<port\s+([^>]+)>(.*?)(?:</port>|(?=<port[\s>]|\Z))', chunk, re.DOTALL)
        for pm in port_matches:
            port_attrs = pm.group(1)
            inner = pm.group(2)
            if 'state="open"' in inner:
                port_id_m = re.search(r'portid="(\d+)"', port_attrs)
                if not port_id_m:
                    continue
                port_id = int(port_id_m.group(1))

                proto_m = re.search(r'protocol="([^"]+)"', port_attrs)
                proto = proto_m.group(1) if proto_m else "tcp"

                svc_m = re.search(r'<service\s+[^>]*name="([^"]+)"', inner)
                svc_name = svc_m.group(1) if svc_m else "unknown"
                prod_m = re.search(r'<service\s+[^>]*product="([^"]+)"', inner)
                prod = prod_m.group(1) if prod_m else ""
                ver_m = re.search(r'<service\s+[^>]*version="([^"]+)"', inner)
                ver = ver_m.group(1) if ver_m else ""
                banner = f"{prod} {ver}".strip()

                services.append({
                    "port": port_id,
                    "protocol": proto,
                    "service": svc_name,
                    "name": svc_name,
                    "version": banner,
                    "access_potential": "",
                    "next_action": "",
                })

        results.append({
            "ip": ip,
            "hostname": hostname,
            "os": os_name,
            "services": services,
        })

    return results


def check_scan_already_imported(
    store: NotebookStore,
    file_path: Union[str, Path],
    workspace_id: Optional[int] = None,
) -> Optional[ScanImport]:
    """Check if this scan file was already imported into the given workspace."""
    ws = store.get_workspace(workspace_id) if workspace_id else store.get_active_workspace()
    if not ws or not ws.id:
        return None
    file_hash = compute_file_hash(file_path)
    return store.get_scan_import(workspace_id=ws.id, file_hash=file_hash)


def commit_scan_results(
    store: NotebookStore,
    file_path: Union[str, Path],
    targets_data: List[Dict[str, Any]],
    workspace_id: Optional[int] = None,
    copy_to_scans: bool = True,
    preserve_status: bool = True,
) -> Dict[str, Any]:
    """Commit reviewed scan results into the database and archive raw output as Evidence.

    Returns summary metrics: targets count, services count, evidence path, and SHA-256 hash.
    """
    src_file = Path(file_path).expanduser().resolve()
    if not src_file.is_file():
        raise FileNotFoundError(f"Source scan file does not exist: {file_path}")

    file_hash = compute_file_hash(src_file)
    ws = store.get_workspace(workspace_id) if workspace_id else store.get_active_workspace()
    if not ws or not ws.id:
        ws = store.get_or_create_workspace("default")

    # Determine destination evidence path
    ws_root = store.get_workspace_root(ws)
    scans_dir = ws_root / "scans"
    scans_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Check if source file is already inside workspace root
        rel = src_file.resolve().relative_to(ws_root.resolve())
        evidence_rel_path = str(rel)
    except ValueError:
        # Source file is outside the workspace
        if copy_to_scans:
            dest_file = scans_dir / src_file.name
            if dest_file.exists() and dest_file.resolve() != src_file.resolve():
                # If destination exists and has different content, preserve unique filename
                dest_hash = compute_file_hash(dest_file)
                if dest_hash != file_hash:
                    dest_file = scans_dir / f"{src_file.stem}_{file_hash[:8]}{src_file.suffix}"
            if not dest_file.exists() or dest_file.resolve() != src_file.resolve():
                shutil.copy2(src_file, dest_file)
            evidence_rel_path = f"scans/{dest_file.name}"
        else:
            evidence_rel_path = store.relativize_path(str(src_file), workspace=ws)

    targets_saved: List[Target] = []
    total_services_saved = 0

    for item in targets_data:
        ip = item.get("ip", "").strip()
        if not ip:
            continue

        hostname = item.get("hostname", "") or ""
        os_name = item.get("os", "Unknown") or "Unknown"

        # Upsert target in workspace
        target = store.add_target(
            ip=ip,
            hostname=hostname,
            os_name=os_name,
            workspace_id=ws.id,
        )
        targets_saved.append(target)

        # Attach raw scan file as evidence
        store.add_evidence(
            path_or_ref=evidence_rel_path,
            target_id=target.id,
            evidence_type="scan",
            description=f"Nmap scan output: {src_file.name} (SHA256: {file_hash[:12]}...)",
        )

        # Record scan import deduplication entry
        store.record_scan_import(
            workspace_id=ws.id,
            file_path=evidence_rel_path,
            file_hash=file_hash,
            target_id=target.id,
            scan_type="nmap",
        )

        # Upsert all selected services
        services = item.get("services", [])
        for svc in services:
            port = int(svc.get("port", 0))
            if port <= 0:
                continue
            proto = svc.get("protocol", "tcp") or "tcp"
            name = svc.get("service", "unknown") or "unknown"
            version = svc.get("version", "") or ""
            access_pot = svc.get("access_potential", "") or ""
            next_act = svc.get("next_action", "") or ""
            status = svc.get("status", "CHECKED") or "CHECKED"

            store.add_service(
                target_id=target.id,  # type: ignore
                port=port,
                protocol=proto,
                service=name,
                version=version,
                access_potential=access_pot,
                next_action=next_act,
                status=status,
                preserve_status=preserve_status,
            )
            total_services_saved += 1

    return {
        "workspace_name": ws.name,
        "workspace_id": ws.id,
        "targets_count": len(targets_saved),
        "services_count": total_services_saved,
        "evidence_path": evidence_rel_path,
        "file_hash": file_hash,
        "targets": targets_saved,
    }


def commit_web_enum_results(
    store: NotebookStore,
    file_path: Union[str, Path],
    endpoints: List[Dict[str, Any]],
    target_id: Optional[int] = None,
    workspace_id: Optional[int] = None,
    copy_to_enum: bool = True,
) -> Dict[str, Any]:
    """Commit reviewed web enumeration endpoints into the database and archive raw output as Evidence.

    Copies file to <workspace_root>/enum/<filename>, records an Evidence row,
    and creates a Lead for each selected endpoint.
    """
    src_file = Path(file_path).expanduser().resolve()
    if not src_file.is_file():
        raise FileNotFoundError(f"Web enum file does not exist: {file_path}")

    file_hash = compute_file_hash(src_file)
    ws = store.get_workspace(workspace_id) if workspace_id else store.get_active_workspace()
    if not ws or not ws.id:
        ws = store.get_or_create_workspace("default")

    if target_id is None:
        active_target = store.get_active_target()
        if active_target and active_target.id:
            target_id = active_target.id
        else:
            targets = store.list_targets(workspace_id=ws.id)
            if targets:
                target_id = targets[0].id

    # Determine destination evidence path in workspace/enum/
    ws_root = store.get_workspace_root(ws)
    enum_dir = ws_root / "enum"
    enum_dir.mkdir(parents=True, exist_ok=True)
    try:
        rel = src_file.resolve().relative_to(ws_root.resolve())
        evidence_rel_path = str(rel)
    except ValueError:
        if copy_to_enum:
            dest_file = enum_dir / src_file.name
            if dest_file.exists() and dest_file.resolve() != src_file.resolve():
                dest_hash = compute_file_hash(dest_file)
                if dest_hash != file_hash:
                    dest_file = enum_dir / f"{src_file.stem}_{file_hash[:8]}{src_file.suffix}"
            if not dest_file.exists() or dest_file.resolve() != src_file.resolve():
                shutil.copy2(src_file, dest_file)
            evidence_rel_path = f"enum/{dest_file.name}"
        else:
            evidence_rel_path = store.relativize_path(str(src_file), workspace=ws)

    # Attach raw enum file as evidence
    store.add_evidence(
        path_or_ref=evidence_rel_path,
        target_id=target_id,
        evidence_type="enum",
        description=f"Web enumeration output: {src_file.name} (SHA256: {file_hash[:12]}...)",
    )

    # Record scan import deduplication entry
    store.record_scan_import(
        workspace_id=ws.id,
        file_path=evidence_rel_path,
        file_hash=file_hash,
        target_id=target_id,
        scan_type="web_enum",
    )

    saved_leads: List[Lead] = []
    for ep in endpoints:
        path_str = ep.get("path", "").strip()
        if not path_str:
            continue
        status = ep.get("status", 200)
        tool = ep.get("tool", "web_enum")
        size = ep.get("size", 0)
        redirect = ep.get("redirect", "")
        lead_title = f"{status} {path_str}"
        notes_str = f"Found via {tool} (Size: {size})"
        if redirect:
            notes_str += f" -> {redirect}"

        lead = store.add_lead(
            title=lead_title,
            target_id=target_id,
            notes=notes_str,
            status="open",
        )
        saved_leads.append(lead)

    return {
        "workspace_name": ws.name,
        "workspace_id": ws.id,
        "target_id": target_id,
        "endpoints_count": len(saved_leads),
        "evidence_path": evidence_rel_path,
        "file_hash": file_hash,
        "leads": saved_leads,
    }

