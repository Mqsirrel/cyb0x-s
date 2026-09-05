"""Export and import engines for CYB0X-S.

Produces clean, standalone Markdown, JSON backups, and plain text notes.
Allows lossless round-trip workspace migration.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from cyb0x_s.db.store import NotebookStore
from cyb0x_s.models import ChecklistStatus, Workspace


def export_markdown(
    store: NotebookStore,
    workspace_id: Optional[int] = None,
    reveal_creds: bool = False,
) -> str:
    """Export notebook to human-readable standalone Markdown.

    Designed to be clear and useful without CYB0X-S installed.
    """
    ws = store.get_workspace(workspace_id) if workspace_id else store.get_active_workspace()
    if not ws:
        return "# Empty Workspace\n"

    lines: List[str] = []
    lines.append(f"# Assessment Workspace: {ws.name}")
    if ws.description:
        lines.append(f"> {ws.description}\n")
    else:
        lines.append("")

    targets = store.list_targets(workspace_id=ws.id)

    if not targets:
        lines.append("*No targets recorded in this workspace.*\n")

    for target in targets:
        lines.append(f"# Target: {target.ip}")
        scope_tag = "IN-SCOPE" if target.is_in_scope else "OUT-OF-SCOPE"
        meta_parts: List[str] = [f"`IP:` `{target.ip}`", f"`Scope:` `{scope_tag}`"]
        if target.hostname:
            meta_parts.append(f"`Hostname:` `{target.hostname}`")
        if target.os and target.os != "Unknown":
            meta_parts.append(f"`OS:` `{target.os}`")
        lines.append(f"> **Target Scope:** {' | '.join(meta_parts)}")
        if target.notes:
            lines.append(f"> **Notes:** {target.notes}")
        lines.append("")

        # 01 — Services & Ports
        services = store.list_services(target_id=target.id)
        if services:
            lines.append("## 01 — Open Ports & Discovered Services (Services)")
            lines.append("## Services")
            for s in services:
                version_str = f" — {s.version}" if s.version else ""
                status_str = f" [{s.status.value}]" if s.status.value != "CHECKED" else ""
                pot_str = f" [{s.access_potential}]" if s.access_potential else ""
                act_str = f" -> Next: `{s.next_action}`" if s.next_action else ""
                notes_str = f" ({s.notes})" if s.notes else ""
                lines.append(f"- {s.port}/{s.protocol} — {s.service}{version_str}{pot_str}{status_str}{act_str}{notes_str}")
            lines.append("")

        # 02 — Credentials
        creds = store.list_credentials(target_id=target.id)
        if creds:
            lines.append("## 02 — Discovered Credentials (Credentials)")
            lines.append("## Credentials")
            for c in creds:
                secret_display = c.secret if reveal_creds else c.masked_secret
                meta = []
                if c.source:
                    meta.append(f"Source: {c.source}")
                if c.service_scope:
                    meta.append(f"Scope: {c.service_scope}")
                if c.status and c.status != "untested":
                    meta.append(f"Status: {c.status}")
                meta_str = f" ({', '.join(meta)})" if meta else ""
                lines.append(f"- {c.username} : {secret_display}{meta_str}")
            lines.append("")

        # 03 — Exploitation & Initial Foothold
        if target.initial_access_vuln or target.foothold_cmd or target.foothold_context:
            lines.append("## 03 — Exploitation & Initial Foothold")
            if target.initial_access_vuln:
                lines.append(f"- **Attack Vector / CVE:** {target.initial_access_vuln}")
            if target.foothold_cmd:
                lines.append(f"- **Exploit Command / Tool:**\n```bash\n{target.foothold_cmd}\n```")
            if target.foothold_context:
                lines.append(f"- **Foothold Context:** `{target.foothold_context}`")
            lines.append("")

        # 04 — Privilege Escalation
        if target.privesc_vector or target.root_proof:
            lines.append("## 04 — Privilege Escalation")
            if target.privesc_vector:
                lines.append(f"- **PrivEsc Vector:** {target.privesc_vector}")
            if target.root_proof:
                lines.append(f"- **Root Shell Proof:**\n```bash\n{target.root_proof}\n```")
            lines.append("")

        # 05 — Captured Flags & Evidence
        if target.user_flag or target.root_flag:
            lines.append("## 05 — Captured Flags & Evidence")
            if target.user_flag:
                lines.append(f"- **User Flag (`user.txt`):** `{target.user_flag}`")
            if target.root_flag:
                lines.append(f"- **Root Flag (`root.txt`):** `{target.root_flag}`")
            lines.append("")

        # Findings
        findings = store.list_findings(target_id=target.id)
        if findings:
            lines.append("## Findings")
            for f in findings:
                sev_prefix = f"[{f.severity}] " if f.severity else ""
                lines.append(f"- {sev_prefix}{f.title}")
                if f.description:
                    lines.append(f"  {f.description}")
                if f.notes:
                    lines.append(f"  Note: {f.notes}")
            lines.append("")

        # Checklist
        checklist = store.list_checklist_items(target_id=target.id)
        if checklist:
            lines.append("## Checklist")
            for item in checklist:
                if item.status == ChecklistStatus.CHECKED:
                    box = "[x]"
                elif item.status == ChecklistStatus.DEFERRED:
                    box = "[-]"
                elif item.status == ChecklistStatus.DEAD_END:
                    box = "[!]"
                else:
                    box = "[ ]"
                status_suffix = (
                    f" ({item.status.value})"
                    if item.status in (ChecklistStatus.DEFERRED, ChecklistStatus.DEAD_END)
                    else ""
                )
                lines.append(f"- {box} {item.title}{status_suffix}")
            lines.append("")

        # Failure Log & Breakthroughs (Notion Section 06)
        failures = store.list_failure_logs(target_id=target.id)
        if failures:
            lines.append("## 🧠 06 — Rabbit Hole & Breakthrough Analysis (Failure Log)")
            for fl in failures:
                if fl.where_stuck:
                    lines.append(f"- **🕳️ Where I Got Stuck / Dead Ends:** {fl.where_stuck}")
                if fl.breakthrough_clue:
                    lines.append(f"- **🔑 Breakthrough Clue:** {fl.breakthrough_clue}")
                if fl.rule_for_next_time:
                    lines.append(f"- **📌 Permanent Rule for Next Time:** {fl.rule_for_next_time}")
            lines.append("")

        # Golden Reproduction Walkthrough
        golden_cmds = store.list_commands(target_id=target.id, golden_only=True)
        if golden_cmds:
            lines.append("## 🏆 Golden Reproduction Walkthrough")
            for idx, gc in enumerate(golden_cmds, start=1):
                step_tag = f"**[{gc.step.upper()}]** " if gc.step else ""
                lines.append(f"{idx}. {step_tag}`{gc.command}`")
                if gc.notes:
                    lines.append(f"   - *Note: {gc.notes}*")
            lines.append("")

        # Evidence
        evidence = store.list_evidence(target_id=target.id)
        if evidence:
            lines.append("## Evidence")
            for ev in evidence:
                desc_str = f" — {ev.description}" if ev.description else ""
                lines.append(f"- [{ev.evidence_type}] `{ev.path_or_ref}`{desc_str}")
            lines.append("")

        # Notes
        notes = store.list_notes(target_id=target.id)
        if notes:
            lines.append("## Notes")
            for n in notes:
                lines.append(f"- {n.content}")
            lines.append("")

        lines.append("---")
        lines.append("")

    # Global entries (target_id is None)
    global_findings = [f for f in store.list_findings() if f.target_id is None]
    global_creds = [c for c in store.list_credentials() if c.target_id is None]
    global_notes = [n for n in store.list_notes() if n.target_id is None]
    global_leads = store.list_leads()

    if global_findings or global_creds or global_notes or global_leads:
        lines.append("# Assessment General Notes")
        if global_findings:
            lines.append("## General Findings")
            for f in global_findings:
                lines.append(f"- {f.title}")
            lines.append("")
        if global_creds:
            lines.append("## General Credentials")
            for c in global_creds:
                secret_display = c.secret if reveal_creds else c.masked_secret
                lines.append(f"- {c.username} : {secret_display}")
            lines.append("")
        if global_leads:
            lines.append("## Open Leads")
            for ld in global_leads:
                lines.append(f"- [{ld.status.upper()}] {ld.title} ({ld.notes})")
            lines.append("")
        if global_notes:
            lines.append("## General Notes")
            for n in global_notes:
                lines.append(f"- {n.content}")
            lines.append("")

    # Exam Question Proofs Ledger (Station 4)
    all_proofs = store.list_exam_proofs()
    if all_proofs:
        lines.append("# Exam Evidence & Answer Submission Ledger (Q1–Q35)")
        lines.append("| Question | Target | Category | Proof / Answer Value | Notes |")
        lines.append("|---|---|---|---|---|")

        def sort_key(p: Any) -> tuple[int, str]:
            q = p.question_num.lstrip("Qq")
            return (int(q) if q.isdigit() else 9999, p.question_num)

        for p in sorted(all_proofs, key=sort_key):
            tgt = f"Host #{p.target_id}" if p.target_id else "Global"
            if p.target_id:
                t = store.get_target(p.target_id)
                if t:
                    tgt = t.ip
            lines.append(f"| **{p.question_num}** | `{tgt}` | `{p.category}` | `{p.answer_proof}` | {p.notes or '-'} |")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def export_txt(store: NotebookStore, workspace_id: Optional[int] = None) -> str:
    """Export notebook to plain text format."""
    ws = store.get_workspace(workspace_id) if workspace_id else store.get_active_workspace()
    if not ws:
        return "Empty Workspace\n"

    lines: List[str] = [
        "CYB0X-S SAFE FIELD NOTEBOOK",
        f"Workspace: {ws.name}",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "=" * 60,
        "",
    ]

    targets = store.list_targets(workspace_id=ws.id)
    for target in targets:
        lines.append(f"TARGET: {target.ip} ({target.hostname or 'no-host'}) [OS: {target.os}]")
        lines.append("-" * 40)

        services = store.list_services(target_id=target.id)
        if services:
            lines.append("SERVICES:")
            for s in services:
                lines.append(f"  * {s.port}/{s.protocol:<4} {s.service:<12} {s.version} [{s.status.value}]")

        findings = store.list_findings(target_id=target.id)
        if findings:
            lines.append("FINDINGS:")
            for f in findings:
                lines.append(f"  * {f.title} ({f.severity or 'manual'})")

        creds = store.list_credentials(target_id=target.id)
        if creds:
            lines.append("CREDENTIALS:")
            for c in creds:
                lines.append(f"  * {c.username} : {c.masked_secret} (Source: {c.source})")

        checklist = store.list_checklist_items(target_id=target.id)
        if checklist:
            lines.append("CHECKLIST:")
            for item in checklist:
                lines.append(f"  [{item.status.value:<8}] {item.title}")

        notes = store.list_notes(target_id=target.id)
        if notes:
            lines.append("NOTES:")
            for n in notes:
                lines.append(f"  > {n.content}")

        lines.append("")

    return "\n".join(lines)


def export_json(store: NotebookStore, workspace_id: Optional[int] = None) -> str:
    """Export complete workspace to JSON representation."""
    ws = store.get_workspace(workspace_id) if workspace_id else store.get_active_workspace()
    if not ws:
        return json.dumps({"error": "Workspace not found"})

    validations = store.get_cred_validations()
    cred_val_list = [
        {"credential_id": cid, "service_id": sid, "status": stat}
        for (cid, sid), stat in validations.items()
    ]

    data: Dict[str, Any] = {
        "version": "1.0",
        "format": "cyb0x-s-backup",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "workspace": ws.model_dump(mode="json"),
        "targets": [],
        "findings": [f.model_dump(mode="json") for f in store.list_findings() if f.target_id is None],
        "credentials": [c.model_dump(mode="json") for c in store.list_credentials() if c.target_id is None],
        "leads": [ld.model_dump(mode="json") for ld in store.list_leads()],
        "notes": [n.model_dump(mode="json") for n in store.list_notes() if n.target_id is None],
        "failure_logs": [fl.model_dump(mode="json") for fl in store.list_failure_logs() if fl.target_id is None],
        "exam_proofs": [ep.model_dump(mode="json") for ep in store.list_exam_proofs() if ep.target_id is None],
        "commands": [cmd.model_dump(mode="json") for cmd in store.list_commands(limit=500) if cmd.target_id is None],
        "cred_validations": cred_val_list,
    }

    targets = store.list_targets(workspace_id=ws.id)
    for t in targets:
        t_data = t.model_dump(mode="json")
        t_data["services"] = [s.model_dump(mode="json") for s in store.list_services(target_id=t.id)]
        t_data["findings"] = [f.model_dump(mode="json") for f in store.list_findings(target_id=t.id)]
        t_data["credentials"] = [c.model_dump(mode="json") for c in store.list_credentials(target_id=t.id)]
        t_data["checklist"] = [ci.model_dump(mode="json") for ci in store.list_checklist_items(target_id=t.id)]
        t_data["evidence"] = [ev.model_dump(mode="json") for ev in store.list_evidence(target_id=t.id)]
        t_data["field_notes"] = [n.model_dump(mode="json") for n in store.list_notes(target_id=t.id)]
        t_data["commands"] = [cmd.model_dump(mode="json") for cmd in store.list_commands(target_id=t.id, limit=500)]
        t_data["failure_logs"] = [fl.model_dump(mode="json") for fl in store.list_failure_logs(target_id=t.id)]
        t_data["exam_proofs"] = [ep.model_dump(mode="json") for ep in store.list_exam_proofs(target_id=t.id)]
        data["targets"].append(t_data)

    return json.dumps(data, indent=2, default=str)


def import_json(
    store: NotebookStore,
    json_content: Union[str, Dict[str, Any]],
    workspace_name: Optional[str] = None,
) -> Workspace:
    """Import workspace data from JSON structure."""
    if isinstance(json_content, str):
        payload = json.loads(json_content)
    else:
        payload = json_content

    ws_data = payload.get("workspace", {})
    name = workspace_name or ws_data.get("name") or "imported_workspace"
    desc = ws_data.get("description", "Imported assessment")

    ws = store.get_or_create_workspace(name=name, description=desc)
    store.set_active_workspace(ws.id)

    # Import targets and children
    for t_item in payload.get("targets", []):
        t_notes = t_item.get("notes", "")
        if not isinstance(t_notes, str):
            t_notes = ""

        target = store.add_target(
            ip=t_item["ip"],
            hostname=t_item.get("hostname", ""),
            os_name=t_item.get("os", "Unknown"),
            notes=t_notes,
            workspace_id=ws.id,
        )

        # Restore methodology, flags, scope, and network details
        store.update_target_details(
            target_id=target.id,
            hostname=t_item.get("hostname", ""),
            os_name=t_item.get("os", "Unknown"),
            initial_access_vuln=t_item.get("initial_access_vuln", ""),
            foothold_cmd=t_item.get("foothold_cmd", ""),
            foothold_context=t_item.get("foothold_context", ""),
            privesc_vector=t_item.get("privesc_vector", ""),
            root_proof=t_item.get("root_proof", ""),
            user_flag=t_item.get("user_flag", ""),
            root_flag=t_item.get("root_flag", ""),
            subnet=t_item.get("subnet", ""),
            is_pivot=bool(t_item.get("is_pivot", False)),
            pivot_route=t_item.get("pivot_route", ""),
            is_in_scope=bool(t_item.get("is_in_scope", True)),
        )

        for s in t_item.get("services", []):
            store.add_service(
                target_id=target.id,
                port=s["port"],
                protocol=s.get("protocol", "tcp"),
                service=s.get("service", "unknown"),
                version=s.get("version", ""),
                access_potential=s.get("access_potential", ""),
                next_action=s.get("next_action", ""),
                status=s.get("status", "CHECKED"),
                notes=s.get("notes", ""),
            )

        for f in t_item.get("findings", []):
            store.add_finding(
                title=f["title"],
                target_id=target.id,
                description=f.get("description", ""),
                notes=f.get("notes", ""),
                severity=f.get("severity"),
            )

        for c in t_item.get("credentials", []):
            store.add_credential(
                username=c["username"],
                secret=c["secret"],
                source=c.get("source", ""),
                target_id=target.id,
                service_scope=c.get("service_scope", ""),
                status=c.get("status", "untested"),
                notes=c.get("notes", ""),
            )

        for ci in t_item.get("checklist", []):
            store.add_checklist_item(
                title=ci["title"],
                category=ci.get("category", "ENUMERATION"),
                target_id=target.id,
                status=ci.get("status", "TODO"),
                notes=ci.get("notes", ""),
            )

        for ev in t_item.get("evidence", []):
            store.add_evidence(
                path_or_ref=ev["path_or_ref"],
                target_id=target.id,
                evidence_type=ev.get("evidence_type", "screenshot"),
                description=ev.get("description", ""),
            )

        # Field notes of target (supports both 'field_notes' and legacy 'notes' list)
        f_notes = t_item.get("field_notes", [])
        if not f_notes and isinstance(t_item.get("notes"), list):
            f_notes = t_item["notes"]
        for n in f_notes:
            store.add_note(
                content=n["content"],
                target_id=target.id,
            )

        for cmd in t_item.get("commands", []):
            store.add_command(
                command=cmd["command"],
                target_id=target.id,
                notes=cmd.get("notes", ""),
                is_golden=bool(cmd.get("is_golden", False)),
                step=cmd.get("step", ""),
            )

        for fl in t_item.get("failure_logs", []):
            store.add_failure_log(
                target_id=target.id,
                where_stuck=fl.get("where_stuck", ""),
                breakthrough_clue=fl.get("breakthrough_clue", ""),
                rule_for_next_time=fl.get("rule_for_next_time", ""),
            )

        for ep in t_item.get("exam_proofs", []):
            store.add_exam_proof(
                question_num=ep["question_num"],
                answer_proof=ep["answer_proof"],
                category=ep.get("category", "FLAG"),
                notes=ep.get("notes", ""),
                target_id=target.id,
            )

    # Global items
    for f in payload.get("findings", []):
        store.add_finding(
            title=f["title"],
            target_id=None,
            description=f.get("description", ""),
            notes=f.get("notes", ""),
            severity=f.get("severity"),
        )

    for c in payload.get("credentials", []):
        store.add_credential(
            username=c["username"],
            secret=c["secret"],
            source=c.get("source", ""),
            target_id=None,
            service_scope=c.get("service_scope", ""),
            status=c.get("status", "untested"),
            notes=c.get("notes", ""),
        )

    for ld in payload.get("leads", []):
        store.add_lead(
            title=ld["title"],
            target_id=None,
            notes=ld.get("notes", ""),
            status=ld.get("status", "open"),
        )

    for n in payload.get("notes", []):
        store.add_note(
            content=n["content"],
            target_id=None,
        )

    for fl in payload.get("failure_logs", []):
        store.add_failure_log(
            target_id=None,
            where_stuck=fl.get("where_stuck", ""),
            breakthrough_clue=fl.get("breakthrough_clue", ""),
            rule_for_next_time=fl.get("rule_for_next_time", ""),
        )

    for ep in payload.get("exam_proofs", []):
        store.add_exam_proof(
            question_num=ep["question_num"],
            answer_proof=ep["answer_proof"],
            category=ep.get("category", "FLAG"),
            notes=ep.get("notes", ""),
            target_id=None,
        )

    for cmd in payload.get("commands", []):
        store.add_command(
            command=cmd["command"],
            target_id=None,
            notes=cmd.get("notes", ""),
            is_golden=bool(cmd.get("is_golden", False)),
            step=cmd.get("step", ""),
        )

    for cv in payload.get("cred_validations", []):
        try:
            store.set_cred_validation(
                credential_id=cv["credential_id"],
                service_id=cv["service_id"],
                status=cv["status"],
            )
        except Exception:
            pass

    return ws
