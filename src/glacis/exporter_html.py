"""Self-contained, offline HTML report exporter.

The report is a *single* HTML document with inline CSS and **no** external
resources: no CDN links, no web fonts, no JavaScript, no analytics. It opens in
any browser and prints cleanly (``@media print``) for exam submission packets.
"""

from __future__ import annotations

import html
from datetime import datetime, timezone
from typing import Any, List, Optional

from glacis.db.store import NotebookStore
from glacis.models import ChecklistStatus
from glacis.routes import build_network_topology
from glacis.triage import evaluate_workspace, phase_counts


def _esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


# Inline stylesheet — deliberately simple, high-contrast, print friendly.
_STYLE = """
:root { color-scheme: light dark; }
* { box-sizing: border-box; }
body { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
       margin: 0; padding: 2rem; background: #f6f7f9; color: #16202a;
       line-height: 1.45; }
main { max-width: 980px; margin: 0 auto; }
h1 { font-size: 1.5rem; margin: 0 0 .25rem; }
h2 { font-size: 1.15rem; margin: 1.8rem 0 .5rem; border-bottom: 2px solid #33414f;
     padding-bottom: .2rem; }
h3 { font-size: 1rem; margin: 1.1rem 0 .35rem; }
.meta { color: #4a5a68; font-size: .85rem; margin-bottom: 1rem; }
.card { background: #fff; border: 1px solid #c9d2dc; border-radius: 6px;
        padding: .8rem 1rem; margin: .6rem 0; break-inside: avoid; }
.scope-in { color: #0b6b3a; font-weight: bold; }
.scope-out { color: #a02020; font-weight: bold; }
.phase { display: inline-block; min-width: 96px; font-weight: bold; }
table { border-collapse: collapse; width: 100%; margin: .4rem 0; font-size: .86rem; }
th, td { text-align: left; border: 1px solid #c9d2dc; padding: .28rem .45rem;
         vertical-align: top; }
th { background: #e7ecf1; }
code, pre { font-family: inherit; }
pre { background: #16202a; color: #d7e3ee; border-radius: 6px; padding: .7rem .9rem;
      overflow-x: auto; white-space: pre-wrap; word-break: break-word; }
.muted { color: #5a6a78; }
.pill { display: inline-block; border-radius: 999px; padding: 0 .6rem; font-size: .75rem;
        font-weight: bold; color: #fff; }
.pill-ok { background: #0b6b3a; } .pill-warn { background: #9a6200; }
.pill-bad { background: #a02020; } .pill-info { background: #31506b; }
.bar { letter-spacing: 1px; font-weight: bold; }
.kpis { display: flex; flex-wrap: wrap; gap: .5rem; margin: .5rem 0; }
.kpi { background: #e7ecf1; border-radius: 6px; padding: .4rem .7rem; font-size: .82rem; }
footer { margin-top: 2rem; color: #5a6a78; font-size: .78rem; border-top: 1px solid #c9d2dc;
        padding-top: .6rem; }
@media (prefers-color-scheme: dark) {
  body { background: #0e1418; color: #dde6ee; }
  .card { background: #151c22; border-color: #2a363f; }
  th { background: #1d262e; } th, td { border-color: #2a363f; }
  .kpi { background: #1d262e; }
  .meta, .muted, footer { color: #8698a8; }
  h2 { border-color: #3a4b58; }
}
@media print {
  body { background: #fff; color: #000; padding: 0; font-size: 10pt; }
  .card, pre, table { break-inside: avoid; }
  h2 { break-after: avoid; }
}
""".strip()


def _checklist_item(status: ChecklistStatus) -> str:
    marks = {
        ChecklistStatus.CHECKED: ("[x]", "checked"),
        ChecklistStatus.DEFERRED: ("[-]", "deferred"),
        ChecklistStatus.DEAD_END: ("[!]", "dead-end"),
    }
    mark, cls = marks.get(status, ("[ ]", "todo"))
    return f'<span class="pill pill-{"ok" if mark == "[x]" else "warn" if mark == "[-]" else "bad" if mark == "[!]" else "info"}">{_esc(mark)}</span>'


def _bar(pct: float, width: int = 10) -> str:
    filled = int(round(width * pct / 100.0))
    return "█" * filled + "░" * (width - filled)


def _target_section(store: NotebookStore, target: Any, reveal_creds: bool) -> str:
    tid = target.id
    parts: List[str] = []
    scope_cls = "scope-in" if target.is_in_scope else "scope-out"
    scope_txt = "IN-SCOPE" if target.is_in_scope else "OUT-OF-SCOPE"
    host_html = f'<span class="muted">({_esc(target.hostname)})</span>' if target.hostname else ""
    parts.append(
        f'<section class="card"><h3>{_esc(target.ip)} {host_html}'
        f' <span class="{scope_cls}">[{scope_txt}]</span></h3>'
    )
    meta = [f"OS: {_esc(target.os or 'Unknown')}"]
    if target.subnet:
        meta.append(f"Subnet: {_esc(target.subnet)}")
    if target.is_pivot:
        meta.append(f"Pivot: {_esc(target.pivot_route or 'yes')}")
    parts.append('<p class="meta">' + "  •  ".join(meta) + "</p>")

    services = store.list_services(target_id=tid)
    if services:
        rows = []
        for s in services:
            pot = f'<span class="pill pill-{"bad" if s.access_potential in ("HIGH", "CRITICAL") else "warn"}">{_esc(s.access_potential)}</span>' if s.access_potential else ""
            rows.append(
                "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
                    _esc(s.port), _esc(s.protocol), _esc(s.service), _esc(s.version),
                    _esc(s.status.value), pot,
                )
            )
        parts.append(
            "<table><thead><tr><th>Port</th><th>Proto</th><th>Service</th>"
            "<th>Version</th><th>Status</th><th>Potential</th></tr></thead><tbody>"
            + "".join(rows) + "</tbody></table>"
        )

    creds = store.list_credentials(target_id=tid)
    if creds:
        rows = []
        for c in creds:
            secret = _esc(c.secret) if reveal_creds else "********"
            rows.append(
                f"<tr><td>{_esc(c.username)}</td><td>{secret}</td>"
                f"<td>{_esc(c.service_scope or 'GLOBAL')}</td><td>{_esc(c.status)}</td>"
                f"<td>{_esc(c.source)}</td></tr>"
            )
        parts.append(
            "<table><thead><tr><th>User</th><th>Secret</th><th>Scope</th>"
            "<th>Status</th><th>Source</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
        )

    if target.initial_access_vuln or target.foothold_cmd:
        parts.append("<p><strong>Foothold:</strong> " + _esc(target.initial_access_vuln) + "</p>")
        if target.foothold_cmd:
            parts.append(f"<pre>{_esc(target.foothold_cmd)}</pre>")
        if target.foothold_context:
            parts.append(f"<p><strong>Context:</strong> {_esc(target.foothold_context)}</p>")
    if target.privesc_vector or target.root_proof:
        parts.append("<p><strong>Privesc:</strong> " + _esc(target.privesc_vector) + "</p>")
        if target.root_proof:
            parts.append(f"<pre>{_esc(target.root_proof)}</pre>")

    findings = store.list_findings(target_id=tid)
    if findings:
        rows = "".join(
            f"<tr><td>{_esc(f.severity or '-')}</td><td>{_esc(f.title)}</td>"
            f"<td>{_esc(f.description)}</td></tr>"
            for f in findings
        )
        parts.append(
            "<table><thead><tr><th>Severity</th><th>Finding</th><th>Detail</th></tr></thead><tbody>"
            + rows + "</tbody></table>"
        )

    checklist = store.list_checklist_items(target_id=tid)
    if checklist:
        items = []
        for item in checklist:
            items.append(
                f"<div>{_checklist_item(item.status)} {_esc(item.title)}"
                f' <span class="muted">[{_esc(item.category)}]</span></div>'
            )
        parts.append("<div>" + "".join(items) + "</div>")

    failures = store.list_failure_logs(target_id=tid)
    if failures:
        rows = []
        for fl in failures:
            rows.append(
                f"<tr><td>{_esc(fl.where_stuck)}</td><td>{_esc(fl.breakthrough_clue)}</td>"
                f"<td>{_esc(fl.rule_for_next_time)}</td></tr>"
            )
        parts.append(
            "<h3>Rabbit holes &amp; breakthroughs</h3><table><thead><tr>"
            "<th>Where stuck</th><th>Breakthrough clue</th><th>Rule for next time</th>"
            "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
        )

    golden = store.list_commands(target_id=tid, golden_only=True)
    if golden:
        parts.append("<h3>Golden reproduction chain</h3><ol>")
        for gc in golden:
            parts.append(f"<li><code>{_esc(gc.command)}</code></li>")
        parts.append("</ol>")

    evidence = store.list_evidence(target_id=tid)
    if evidence:
        rows = "".join(
            f"<tr><td>{_esc(e.evidence_type)}</td><td>{_esc(e.path_or_ref)}</td>"
            f"<td>{_esc(e.description)}</td></tr>"
            for e in evidence
        )
        parts.append(
            "<table><thead><tr><th>Type</th><th>Path / Reference</th><th>Description</th></tr></thead><tbody>"
            + rows + "</tbody></table>"
        )

    notes = store.list_notes(target_id=tid)
    if notes:
        parts.append("<h3>Field notes</h3><ul>" + "".join(f"<li>{_esc(n.content)}</li>" for n in notes) + "</ul>")

    flags: list[str] = []
    if target.user_flag:
        flags.append(f'<span class="pill pill-ok">user: {_esc(target.user_flag)}</span>')
    if target.root_flag:
        flags.append(f'<span class="pill pill-info">root: {_esc(target.root_flag)}</span>')
    if flags:
        parts.append("<p>" + " ".join(flags) + "</p>")

    parts.append("</section>")
    return "".join(parts)


def export_html(
    store: NotebookStore,
    workspace_id: Optional[int] = None,
    *,
    reveal_creds: bool = False,
    include_triage: bool = True,
) -> str:
    """Render the complete standalone HTML report."""
    ws = store.get_workspace(workspace_id) if workspace_id else store.get_active_workspace()
    ws_name = ws.name if ws else "default"
    ws_desc = ws.description if ws else ""
    targets = store.list_targets(workspace_id=ws.id if ws else None)
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    parts: List[str] = [
        "<!DOCTYPE html>",
        '<html lang="en"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>GLACIS report — {_esc(ws_name)}</title>",
        f"<style>{_STYLE}</style></head><body><main>",
        f"<h1>GLACIS Assessment Report — {_esc(ws_name)}</h1>",
        f'<p class="meta">Generated offline {generated} from local notebook records'
        + (f" — {_esc(ws_desc)}" if ws_desc else "")
        + "</p>",
    ]

    if include_triage:
        report = evaluate_workspace(store, ws.id if ws else None, include_direction=False)
        counts = phase_counts(report)
        kpis = [
            ("targets", report.totals.get("targets", 0)),
            ("services", report.totals.get("services", 0)),
            ("credentials", report.totals.get("credentials", 0)),
            ("evidence", report.totals.get("evidence", 0)),
            ("proofs", report.totals.get("proofs", 0)),
            ("untouched", report.totals.get("untouched", 0)),
            ("complete", report.totals.get("complete", 0)),
        ]
        for phase_name, phase_n in counts.items():
            if phase_n:
                kpis.append((f"phase {phase_name.lower()}", phase_n))
        parts.append('<h2>Engagement overview</h2><div class="kpis">')
        for label, val in kpis:
            parts.append(f'<span class="kpi"><strong>{val}</strong> {_esc(label)}</span>')
        parts.append("</div>")
        rows = []
        for h in report.hosts:
            rows.append(
                "<tr><td>{}</td><td>{}</td><td><span class='bar'>{}</span> {}%</td>"
                "<td>{}/{}</td><td>{}</td><td>{}</td></tr>".format(
                    _esc(h.ip),
                    f'<span class="phase">{_esc(h.phase.value)}</span>',
                    _bar(h.completion_pct),
                    f"{h.completion_pct:.0f}",
                    h.checklist_done,
                    h.checklist_total,
                    f"{h.services_total} svc",
                    _esc(h.phase_reason),
                )
            )
        if rows:
            parts.append(
                "<table><thead><tr><th>Host</th><th>Phase</th><th>Progress</th>"
                "<th>Checklist</th><th>Surface</th><th>Note</th></tr></thead><tbody>"
                + "".join(rows) + "</tbody></table>"
            )

    for target in targets:
        parts.append(f"<h2>Target: {_esc(target.ip)}</h2>")
        parts.append(_target_section(store, target, reveal_creds))

    # Network topology as preformatted text (no JS graph libraries).
    try:
        topology = build_network_topology(store, ws.id if ws else None)
        if topology.subnets:
            parts.append("<h2>Network topology</h2>")
            parts.append(f"<pre>{_esc(topology.ascii_map)}</pre>")
    except Exception:
        pass

    proofs = store.list_exam_proofs()
    if proofs:
        parts.append("<h2>Objective proof ledger</h2>")
        rows = []
        for p in sorted(proofs, key=lambda x: x.question_num):
            tgt = ""
            if p.target_id:
                t = store.get_target(p.target_id)
                tgt = t.ip if t else f"#{p.target_id}"
            rows.append(
                f"<tr><td>{_esc(p.question_num)}</td><td>{_esc(tgt)}</td>"
                f"<td>{_esc(p.category)}</td><td>{_esc(p.answer_proof)}</td>"
                f"<td>{_esc(p.notes)}</td></tr>"
            )
        parts.append(
            "<table><thead><tr><th>Objective</th><th>Target</th><th>Category</th>"
            "<th>Proof</th><th>Notes</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
        )

    parts.append(
        '<footer>Generated by GLACIS from local records only. This document contains no '
        "external resources, scripts, or tracking references. All testing actions were "
        "performed manually by the operator.</footer>"
    )
    parts.append("</main></body></html>")
    return "\n".join(parts)
