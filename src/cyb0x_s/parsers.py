"""Offline scan parsers for CYB0X-S.

Strictly passive: parses locally saved scan files (Nmap XML, Nmap normal text, Gnmap, NetExec).
Zero network activity: pure file reader.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from cyb0x_s.settings import derive_guidance_enabled


def derive_potential_and_next(
    service_name: str,
    port: int,
    target_ip: str = "",
    enabled: Optional[bool] = None,
) -> tuple[str, str]:
    """Derive initial access potential (HIGH/MED/LOW) and tactical next action.

    Derivation is **gated behind the settings switch**, which is off by default
    (see :mod:`cyb0x_s.settings`). ``enabled`` overrides the global switch for a
    single call/parse; when effectively disabled this returns ``("", "")`` so
    CYB0X-S never classifies a recorded service or proposes a next step on its
    own.
    """
    if not (derive_guidance_enabled() if enabled is None else enabled):
        return "", ""

    s = service_name.lower().strip()
    ip_str = target_ip or "<TARGET_IP>"

    if s in ("smb", "microsoft-ds", "netbios-ssn") or port in (139, 445):
        return "HIGH", f"smbmap -u guest -p '' -d . -H {ip_str}"
    elif s in ("http", "https", "http-proxy", "web", "apache", "nginx", "iis") or port in (80, 443, 8080, 8000, 8081, 8888, 5000):
        proto = "https" if port == 443 or "https" in s else "http"
        port_suffix = f":{port}" if port not in (80, 443) else ""
        return "HIGH", f"feroxbuster -u {proto}://{ip_str}{port_suffix}/ -w /usr/share/wordlists/dirb/common.txt"
    elif s in ("winrm", "wsman") or port in (5985, 5986):
        return "HIGH", f"evil-winrm -i {ip_str} -u <USER> -p '<PW>'"
    elif s in ("mssql", "ms-sql-s") or port == 1433:
        return "HIGH", f"nmap -p 1433 --script ms-sql-info,ms-sql-empty-password {ip_str}"
    elif s in ("mysql",) or port == 3306:
        return "MED", f"mysql -h {ip_str} -u root -p"
    elif s in ("ftp",) or port == 21:
        return "HIGH", f"ftp {ip_str} (test anonymous)"
    elif s in ("ssh",) or port == 22:
        return "MED", f"hydra -l <USER> -P /usr/share/wordlists/rockyou.txt ssh://{ip_str}"
    elif s in ("rdp", "ms-wbt-server") or port == 3389:
        return "MED", f"xfreerdp /u:<USER> /p:'<PW>' /v:{ip_str} /smart-sizing"
    elif s in ("snmp",) or port == 161:
        return "HIGH", f"onesixtyone -c /usr/share/seclists/Discovery/SNMP/snmp.txt {ip_str}"
    return "LOW", ""


def parse_nmap_xml(
    content_or_path: Union[str, Path], derive_guidance: Optional[bool] = None
) -> List[Dict[str, Any]]:
    """Parse Nmap XML output (-oX) into structured target data."""
    if isinstance(content_or_path, Path) or (
        isinstance(content_or_path, str)
        and not content_or_path.strip().startswith("<")
        and Path(content_or_path).exists()
    ):
        tree = ET.parse(content_or_path)
        root = tree.getroot()
    else:
        root = ET.fromstring(content_or_path)

    results: List[Dict[str, Any]] = []

    for host in root.findall("host"):
        status_elem = host.find("status")
        if status_elem is not None and status_elem.get("state") != "up":
            continue

        ip = None
        for addr in host.findall("address"):
            if addr.get("addrtype") in ("ipv4", "ipv6"):
                ip = addr.get("addr")
                break
        if not ip:
            continue

        hostname = ""
        hostnames_elem = host.find("hostnames")
        if hostnames_elem is not None:
            for hn in hostnames_elem.findall("hostname"):
                name = hn.get("name")
                if name:
                    hostname = name
                    break

        os_name = "Unknown"
        os_elem = host.find("os")
        if os_elem is not None:
            osmatch = os_elem.find("osmatch")
            if osmatch is not None:
                os_name = osmatch.get("name", "Unknown")

        services = []
        ports_elem = host.find("ports")
        if ports_elem is not None:
            for port_elem in ports_elem.findall("port"):
                state_elem = port_elem.find("state")
                if state_elem is None or state_elem.get("state") != "open":
                    continue

                port_id = int(port_elem.get("portid", 0))
                protocol = port_elem.get("protocol", "tcp")

                service_elem = port_elem.find("service")
                svc_name = "unknown"
                product = ""
                version = ""

                if service_elem is not None:
                    svc_name = service_elem.get("name", "unknown")
                    product = service_elem.get("product", "")
                    version = service_elem.get("version", "")

                banner = f"{product} {version}".strip()
                potential, next_act = derive_potential_and_next(
                    svc_name, port_id, target_ip=ip, enabled=derive_guidance
                )

                services.append({
                    "port": port_id,
                    "protocol": protocol,
                    "service": svc_name,
                    "name": svc_name,
                    "version": banner,
                    "access_potential": potential,
                    "next_action": next_act,
                })

        results.append({
            "ip": ip,
            "hostname": hostname,
            "os": os_name,
            "services": services,
        })

    return results


def parse_nmap_text(
    content_or_path: Union[str, Path], derive_guidance: Optional[bool] = None
) -> List[Dict[str, Any]]:
    """Parse standard Nmap normal text output (-oN) into structured targets."""
    if isinstance(content_or_path, Path) or (
        isinstance(content_or_path, str) and Path(content_or_path).exists()
    ):
        with open(content_or_path, "r", encoding="utf-8", errors="replace") as f:
            raw = f.read()
    else:
        raw = str(content_or_path)

    results: List[Dict[str, Any]] = []
    host_blocks = re.split(r"Nmap scan report for ", raw)

    for block in host_blocks[1:]:
        lines = block.splitlines()
        if not lines:
            continue

        header_line = lines[0].strip()
        # Header line: "10.10.10.10" or "hostname (10.10.10.10)"
        ip = ""
        hostname = ""
        ip_match = re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", header_line)
        if ip_match:
            ip = ip_match.group(0)
            if "(" in header_line:
                hostname = header_line.split("(")[0].strip()
        else:
            ip = header_line.split()[0]

        services = []
        for line in lines[1:]:
            line = line.strip()
            # Match: "80/tcp open http Apache httpd 2.4.41"
            m = re.match(r"^(\d+)/(tcp|udp)\s+open\s+(\S+)(?:\s+(.*))?$", line)
            if m:
                port = int(m.group(1))
                proto = m.group(2)
                svc_name = m.group(3)
                ver_info = (m.group(4) or "").strip()

                potential, next_act = derive_potential_and_next(
                    svc_name, port, target_ip=ip, enabled=derive_guidance
                )
                services.append({
                    "port": port,
                    "protocol": proto,
                    "service": svc_name,
                    "name": svc_name,
                    "version": ver_info,
                    "access_potential": potential,
                    "next_action": next_act,
                })

        if ip:
            results.append({
                "ip": ip,
                "hostname": hostname,
                "os": "Linux" if "linux" in block.lower() else ("Windows" if "windows" in block.lower() else "Unknown"),
                "services": services,
            })

    return results


def parse_nmap_gnmap(
    content_or_path: Union[str, Path], derive_guidance: Optional[bool] = None
) -> List[Dict[str, Any]]:
    """Parse Nmap Greppable output (-oG) into structured targets."""
    if isinstance(content_or_path, Path) or (
        isinstance(content_or_path, str) and Path(content_or_path).exists()
    ):
        with open(content_or_path, "r", encoding="utf-8", errors="replace") as f:
            raw = f.read()
    else:
        raw = str(content_or_path)

    results_map: Dict[str, Dict[str, Any]] = {}

    for line in raw.splitlines():
        line = line.strip()
        if not line.startswith("Host:"):
            continue

        ip_match = re.search(r"Host:\s+([0-9.]+)", line)
        if not ip_match:
            continue
        ip = ip_match.group(1)

        host_entry = results_map.setdefault(
            ip,
            {"ip": ip, "hostname": "", "os": "Unknown", "services": []},
        )

        host_match = re.search(r"Host:\s+[0-9.]+\s+\(([^)]+)\)", line)
        if host_match and not host_entry["hostname"]:
            host_entry["hostname"] = host_match.group(1).strip()

        ports_idx = line.find("Ports:")
        if ports_idx != -1:
            ports_str = line[ports_idx + 6 :].split("\t")[0].strip()
            for p_chunk in ports_str.split(","):
                p_chunk = p_chunk.strip()
                if not p_chunk:
                    continue
                parts = p_chunk.split("/")
                if len(parts) >= 5 and "open" in parts[1].lower():
                    port = int(parts[0])
                    proto = parts[2] if len(parts) > 2 and parts[2] else "tcp"
                    svc_name = parts[4] if len(parts) > 4 and parts[4] else "unknown"
                    version = parts[6] if len(parts) > 6 else ""
                    pot, nxt = derive_potential_and_next(
                        svc_name, port, target_ip=ip, enabled=derive_guidance
                    )
                    host_entry["services"].append({
                        "port": port,
                        "protocol": proto,
                        "service": svc_name,
                        "name": svc_name,
                        "version": version,
                        "access_potential": pot,
                        "next_action": nxt,
                    })

    return list(results_map.values())


def parse_netexec_output(
    content_or_path: Union[str, Path], derive_guidance: Optional[bool] = None
) -> List[Dict[str, Any]]:
    """Parse NetExec (nxc) CLI output into structured targets."""
    if isinstance(content_or_path, Path) or (
        isinstance(content_or_path, str) and Path(content_or_path).exists()
    ):
        with open(content_or_path, "r", encoding="utf-8", errors="replace") as f:
            raw = f.read()
    else:
        raw = str(content_or_path)

    results_map: Dict[str, Dict[str, Any]] = {}

    for line in raw.splitlines():
        line = line.strip()
        m = re.match(r"^([A-Z0-9_-]+)\s+([0-9.]+)\s+(\d+)\s+([A-Za-z0-9_-]+)?", line)
        if m:
            proto_svc = m.group(1).lower()
            ip = m.group(2)
            port = int(m.group(3))
            hostname = m.group(4) or ""

            entry = results_map.setdefault(
                ip,
                {"ip": ip, "hostname": hostname if hostname != "-" else "", "os": "Windows" if "windows" in line.lower() else "Unknown", "services": []},
            )
            if hostname and hostname != "-" and not entry["hostname"]:
                entry["hostname"] = hostname

            pot, nxt = derive_potential_and_next(
                proto_svc, port, target_ip=ip, enabled=derive_guidance
            )
            entry["services"].append({
                "port": port,
                "protocol": "tcp",
                "service": proto_svc,
                "name": proto_svc,
                "version": "",
                "access_potential": pot,
                "next_action": nxt,
            })

    return list(results_map.values())


def parse_scan_file(
    file_path: Union[str, Path], derive_guidance: Optional[bool] = None
) -> List[Dict[str, Any]]:
    """Auto-detect format (XML vs Text vs Gnmap vs NetExec) and parse scan file."""
    p = Path(file_path)
    if not p.exists():
        raise FileNotFoundError(f"Scan file not found: {file_path}")

    with open(p, "r", encoding="utf-8", errors="replace") as f:
        head = f.read(500)

    if "<nmaprun" in head or "<!DOCTYPE nmaprun" in head:
        return parse_nmap_xml(p, derive_guidance=derive_guidance)
    elif "# Nmap" in head and "Ports:" in head:
        return parse_nmap_gnmap(p, derive_guidance=derive_guidance)
    return parse_nmap_text(p, derive_guidance=derive_guidance)

