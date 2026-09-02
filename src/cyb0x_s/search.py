"""Unified search engine for CYB0X-S across all notebook entities."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel

from cyb0x_s.db.store import NotebookStore
from cyb0x_s.models import (
    ChecklistItem,
    CommandRecord,
    Credential,
    Evidence,
    Finding,
    Lead,
    Note,
    Service,
    Target,
)


class SearchMatch(BaseModel):
    """Normalized search match representation."""
    entity_type: str
    entity_id: Optional[int]
    target_id: Optional[int]
    target_ip: Optional[str] = None
    title: str
    snippet: str


def search_notebook(
    store: NotebookStore,
    query: str,
    workspace_id: Optional[int] = None,
) -> List[SearchMatch]:
    """Execute case-insensitive keyword search across all notebook tables."""
    q = query.strip().lower()
    if not q:
        return []

    ws_id = workspace_id or store.get_active_workspace().id
    targets = store.list_targets(workspace_id=ws_id)
    target_map = {t.id: t.ip for t in targets if t.id is not None}
    matches: List[SearchMatch] = []

    # 1. Targets
    for t in targets:
        if (
            q in t.ip.lower()
            or q in t.hostname.lower()
            or q in t.os.lower()
            or q in t.notes.lower()
        ):
            matches.append(
                SearchMatch(
                    entity_type="target",
                    entity_id=t.id,
                    target_id=t.id,
                    target_ip=t.ip,
                    title=f"Target: {t.ip} ({t.hostname or 'no host'})",
                    snippet=f"OS: {t.os} | Notes: {t.notes}",
                )
            )

    # 2. Services
    for s in store.list_services():
        target_ip = target_map.get(s.target_id)
        port_str = f"{s.port}/{s.protocol}"
        if (
            q in port_str.lower()
            or q in s.service.lower()
            or q in s.version.lower()
            or q in s.notes.lower()
            or q in s.status.value.lower()
        ):
            matches.append(
                SearchMatch(
                    entity_type="service",
                    entity_id=s.id,
                    target_id=s.target_id,
                    target_ip=target_ip,
                    title=f"Service: {port_str} {s.service}",
                    snippet=f"Version: {s.version} [{s.status.value}] {s.notes}",
                )
            )

    # 3. Findings
    for f in store.list_findings():
        target_ip = target_map.get(f.target_id)
        if (
            q in f.title.lower()
            or q in f.description.lower()
            or q in f.notes.lower()
            or (f.severity and q in f.severity.lower())
        ):
            matches.append(
                SearchMatch(
                    entity_type="finding",
                    entity_id=f.id,
                    target_id=f.target_id,
                    target_ip=target_ip,
                    title=f"Finding{' (Global)' if f.target_id is None else ''}: {f.title}",
                    snippet=f"Sev: {f.severity or 'manual'} | {f.description or f.notes}",
                )
            )

    # 4. Credentials
    for c in store.list_credentials():
        target_ip = target_map.get(c.target_id)
        if (
            q in c.username.lower()
            or q in c.source.lower()
            or q in c.service_scope.lower()
            or q in c.notes.lower()
            or q in c.status.lower()
        ):
            matches.append(
                SearchMatch(
                    entity_type="credential",
                    entity_id=c.id,
                    target_id=c.target_id,
                    target_ip=target_ip,
                    title=f"Credential: {c.username} : ********",
                    snippet=f"Scope: {c.service_scope} | Source: {c.source} [{c.status}]",
                )
            )

    # 5. Notes
    for n in store.list_notes():
        target_ip = target_map.get(n.target_id)
        if q in n.content.lower():
            matches.append(
                SearchMatch(
                    entity_type="note",
                    entity_id=n.id,
                    target_id=n.target_id,
                    target_ip=target_ip,
                    title="Field Note",
                    snippet=n.content[:120] + ("..." if len(n.content) > 120 else ""),
                )
            )

    # 6. Checklist
    for item in store.list_checklist_items():
        target_ip = target_map.get(item.target_id)
        if (
            q in item.title.lower()
            or q in item.category.lower()
            or q in item.status.value.lower()
            or q in item.notes.lower()
        ):
            matches.append(
                SearchMatch(
                    entity_type="checklist",
                    entity_id=item.id,
                    target_id=item.target_id,
                    target_ip=target_ip,
                    title=f"Checklist [{item.status.value}]: {item.title}",
                    snippet=f"Category: {item.category} {item.notes}",
                )
            )

    # 7. Evidence
    for ev in store.list_evidence():
        target_ip = target_map.get(ev.target_id)
        if (
            q in ev.path_or_ref.lower()
            or q in ev.description.lower()
            or q in ev.evidence_type.lower()
        ):
            matches.append(
                SearchMatch(
                    entity_type="evidence",
                    entity_id=ev.id,
                    target_id=ev.target_id,
                    target_ip=target_ip,
                    title=f"Evidence ({ev.evidence_type}): {ev.path_or_ref}",
                    snippet=ev.description,
                )
            )

    # 8. Leads
    for ld in store.list_leads():
        target_ip = target_map.get(ld.target_id)
        if q in ld.title.lower() or q in ld.notes.lower():
            matches.append(
                SearchMatch(
                    entity_type="lead",
                    entity_id=ld.id,
                    target_id=ld.target_id,
                    target_ip=target_ip,
                    title=f"Lead: {ld.title}",
                    snippet=f"Status: {ld.status} | {ld.notes}",
                )
            )

    # 9. Commands
    for cmd in store.list_commands():
        target_ip = target_map.get(cmd.target_id)
        if q in cmd.command.lower() or q in cmd.notes.lower():
            matches.append(
                SearchMatch(
                    entity_type="command",
                    entity_id=cmd.id,
                    target_id=cmd.target_id,
                    target_ip=target_ip,
                    title=f"Command: {cmd.command}",
                    snippet=cmd.notes,
                )
            )

    return matches
