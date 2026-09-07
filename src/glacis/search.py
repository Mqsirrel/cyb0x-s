"""Unified search engine for GLACIS across all notebook entities.

Powered by SQLite FTS5 with Okapi BM25 ranking, prefix completion,
automatic trigger synchronization, and graceful fallback.
"""

from __future__ import annotations

import sqlite3
from typing import List, Optional

from pydantic import BaseModel

from glacis.db.store import NotebookStore


class SearchMatch(BaseModel):
    """Normalized search match representation."""
    entity_type: str
    entity_id: Optional[int]
    target_id: Optional[int]
    target_ip: Optional[str] = None
    title: str
    snippet: str
    score: Optional[float] = None


def _sanitize_fts_query(raw_query: str) -> str:
    """Format raw query string into safe SQLite FTS5 query with prefix and phrase support."""
    cleaned = raw_query.strip()
    if not cleaned:
        return ""
    if cleaned.startswith('"') and cleaned.endswith('"'):
        return cleaned

    parts = cleaned.split()
    tokens: List[str] = []
    for p in parts:
        upper_p = p.upper()
        if upper_p in ("AND", "OR", "NOT"):
            tokens.append(upper_p)
            continue
        safe_p = p.replace('"', "").replace("'", "")
        if not safe_p:
            continue

        has_wildcard = safe_p.endswith("*")
        base = safe_p[:-1] if has_wildcard else safe_p
        if not base:
            continue

        # Dotted/special character strings (IPs, domains, ports, paths) need quotes in FTS5
        if any(c in base for c in ".:/-_@$"):
            tokens.append(f'"{base}"')
        else:
            tokens.append(f"{base}*")

    final_tokens: List[str] = []
    for i, token in enumerate(tokens):
        final_tokens.append(token)
        if (
            i < len(tokens) - 1
            and token not in ("AND", "OR", "NOT")
            and tokens[i + 1] not in ("AND", "OR")
        ):
            final_tokens.append("AND")

    return " ".join(final_tokens)


def search_notebook(
    store: NotebookStore,
    query: str,
    workspace_id: Optional[int] = None,
    target_id: Optional[int] = None,
    entity_type: Optional[str] = None,
) -> List[SearchMatch]:
    """Execute Okapi BM25 ranked full-text search across all notebook tables.

    Uses the native SQLite FTS5 virtual table `notebook_fts`. Automatically
    falls back to case-insensitive substring search if FTS syntax is invalid.
    """
    raw_q = query.strip()
    if not raw_q:
        return []

    ws_id = workspace_id or store.get_active_workspace().id
    targets = store.list_targets(workspace_id=ws_id)
    target_map = {t.id: t.ip for t in targets if t.id is not None}

    # Attempt SQLite FTS5 BM25 search
    fts_q = _sanitize_fts_query(raw_q)
    if fts_q:
        try:
            cur = store.conn.cursor()
            sql = """
                SELECT entity_type, entity_id, target_id, title, content, tags,
                       snippet(notebook_fts, -1, '', '', '...', 15) as matched_snippet,
                       bm25(notebook_fts) as rank_score
                FROM notebook_fts
                WHERE notebook_fts MATCH ?
                ORDER BY rank_score ASC
            """
            cur.execute(sql, (fts_q,))
            rows = cur.fetchall()

            matches: List[SearchMatch] = []
            for r in rows:
                t_id = r["target_id"]
                # Enforce workspace isolation: if entity belongs to a target, target must be in active workspace
                if t_id is not None and t_id not in target_map:
                    continue

                if target_id is not None and t_id != target_id:
                    continue

                e_type = r["entity_type"]
                if entity_type is not None and e_type != entity_type:
                    continue

                snip = (r["matched_snippet"] or "").strip()
                content = (r["content"] or "").strip()
                if not snip or snip == r["title"]:
                    snippet_text = content[:120] + ("..." if len(content) > 120 else "")
                else:
                    snippet_text = snip

                matches.append(
                    SearchMatch(
                        entity_type=e_type,
                        entity_id=r["entity_id"],
                        target_id=t_id,
                        target_ip=target_map.get(t_id),
                        title=r["title"],
                        snippet=snippet_text,
                        score=float(r["rank_score"]) if r["rank_score"] is not None else None,
                    )
                )

            return matches
        except sqlite3.OperationalError:
            # Fallback on malformed FTS syntax or missing virtual table
            pass

    return _fallback_substring_search(store, raw_q, target_map, target_id, entity_type)


def _fallback_substring_search(
    store: NotebookStore,
    query: str,
    target_map: dict[int, str],
    target_id: Optional[int] = None,
    entity_type: Optional[str] = None,
) -> List[SearchMatch]:
    """Fallback Python-level substring search in case FTS is unavailable or syntax fails."""
    q = query.strip().lower()
    if not q:
        return []

    matches: List[SearchMatch] = []

    # 1. Targets
    if entity_type is None or entity_type == "target":
        for t in store.list_targets():
            if t.id is not None and t.id not in target_map:
                continue
            if target_id is not None and t.id != target_id:
                continue
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
    if entity_type is None or entity_type == "service":
        for s in store.list_services():
            if s.target_id not in target_map:
                continue
            if target_id is not None and s.target_id != target_id:
                continue
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
                        target_ip=target_map.get(s.target_id),
                        title=f"Service: {port_str} {s.service}",
                        snippet=f"Version: {s.version} [{s.status.value}] {s.notes}",
                    )
                )

    # 3. Findings
    if entity_type is None or entity_type == "finding":
        for f in store.list_findings():
            if f.target_id is not None and f.target_id not in target_map:
                continue
            if target_id is not None and f.target_id != target_id:
                continue
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
                        target_ip=target_map.get(f.target_id),
                        title=f"Finding{' (Global)' if f.target_id is None else ''}: {f.title}",
                        snippet=f"Sev: {f.severity or 'manual'} | {f.description or f.notes}",
                    )
                )

    # 4. Credentials
    if entity_type is None or entity_type == "credential":
        for c in store.list_credentials():
            if c.target_id not in target_map:
                continue
            if target_id is not None and c.target_id != target_id:
                continue
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
                        target_ip=target_map.get(c.target_id),
                        title=f"Credential: {c.username} : ********",
                        snippet=f"Scope: {c.service_scope} | Source: {c.source} [{c.status}]",
                    )
                )

    # 5. Notes
    if entity_type is None or entity_type == "note":
        for n in store.list_notes():
            if n.target_id is not None and n.target_id not in target_map:
                continue
            if target_id is not None and n.target_id != target_id:
                continue
            if q in n.content.lower():
                matches.append(
                    SearchMatch(
                        entity_type="note",
                        entity_id=n.id,
                        target_id=n.target_id,
                        target_ip=target_map.get(n.target_id),
                        title="Field Note",
                        snippet=n.content[:120] + ("..." if len(n.content) > 120 else ""),
                    )
                )

    # 6. Checklist
    if entity_type is None or entity_type == "checklist":
        for item in store.list_checklist_items():
            if item.target_id is not None and item.target_id not in target_map:
                continue
            if target_id is not None and item.target_id != target_id:
                continue
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
                        target_ip=target_map.get(item.target_id),
                        title=f"Checklist [{item.status.value}]: {item.title}",
                        snippet=f"Category: {item.category} {item.notes}",
                    )
                )

    # 7. Evidence
    if entity_type is None or entity_type == "evidence":
        for ev in store.list_evidence():
            if ev.target_id is not None and ev.target_id not in target_map:
                continue
            if target_id is not None and ev.target_id != target_id:
                continue
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
                        target_ip=target_map.get(ev.target_id),
                        title=f"Evidence ({ev.evidence_type}): {ev.path_or_ref}",
                        snippet=ev.description,
                    )
                )

    # 8. Leads
    if entity_type is None or entity_type == "lead":
        for ld in store.list_leads():
            if ld.target_id is not None and ld.target_id not in target_map:
                continue
            if target_id is not None and ld.target_id != target_id:
                continue
            if q in ld.title.lower() or q in ld.notes.lower():
                matches.append(
                    SearchMatch(
                        entity_type="lead",
                        entity_id=ld.id,
                        target_id=ld.target_id,
                        target_ip=target_map.get(ld.target_id),
                        title=f"Lead: {ld.title}",
                        snippet=f"Status: {ld.status} | {ld.notes}",
                    )
                )

    # 9. Commands
    if entity_type is None or entity_type == "command":
        for cmd in store.list_commands():
            if cmd.target_id is not None and cmd.target_id not in target_map:
                continue
            if target_id is not None and cmd.target_id != target_id:
                continue
            if q in cmd.command.lower() or q in cmd.notes.lower():
                matches.append(
                    SearchMatch(
                        entity_type="command",
                        entity_id=cmd.id,
                        target_id=cmd.target_id,
                        target_ip=target_map.get(cmd.target_id),
                        title=f"Command: {cmd.command}",
                        snippet=cmd.notes,
                    )
                )

    return matches
