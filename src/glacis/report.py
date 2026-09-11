"""Standalone HTML report export for GLACIS.

Produces a single, fully self-contained ``.html`` file:

* zero external assets — no CDN fonts, no JavaScript bundles, no images;
  it renders identically offline, from a USB stick, or attached to a report.
* themed with the same design tokens as the TUI palettes (CSS custom
  properties generated from :mod:`glacis.tui.theme`).
* print-friendly: a dedicated ``@media print`` stylesheet turns it into a
  clean submission document.

100% passive: renders only data the user recorded.
"""

from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from typing import List, Optional

from glacis.db.store import NotebookStore
from glacis.models import ChecklistStatus
from glacis.pulse import (
    WorkspacePulse,
    build_timeline,
    compute_next_actions,
    compute_target_scorecards,
    compute_workspace_pulse,
)
from glacis.tui.theme import PALETTES

_SEVERITY_CLASS = {
    "CRITICAL": "crit",
    "HIGH": "high",
    "MEDIUM": "med",
    "LOW": "low",
    "INFO": "info",
    "UNRATED": "unrated",
}

_STATUS_CLASS = {
    "CHECKED": "ok",
    "DEAD-END": "danger",
    "DEFERRED": "warn",
    "TODO": "muted",
    "UNTESTED": "muted",
}


def _esc(value: object) -> str:
    return escape(str(value if value is not None else ""))


def _mask(secret: str, reveal: bool) -> str:
    return secret if reveal else "•" * max(8, min(len(secret), 24))


def _spans(series: List[int], accent: str) -> str:
    """Inline SVG sparkline (pure markup — no JS, no images)."""
    if not series:
        return ""
    peak = max(series) or 1
    w, h, pad = 140, 34, 3
    n = len(series)
    bw = (w - 2 * pad) / n
    parts: List[str] = []
    for i, v in enumerate(series):
        bh = max(1.5, (h - 2 * pad) * (v / peak)) if v else 1.5
        x = pad + i * bw
        y = h - pad - bh
        parts.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw * 0.68:.1f}" height="{bh:.1f}" rx="1.5" '
            f'fill="{accent}" opacity="{1.0 if v else 0.28}"/>'
        )
    return (
        f'<svg class="spark" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
        f'role="img" aria-label="activity, last {n} days">{"".join(parts)}</svg>'
    )


def _stat_card(label: str, value: str, sub: str = "", cls: str = "", raw_sub: bool = False) -> str:
    sub_html = f'<div class="card-sub">{sub if raw_sub else _esc(sub)}</div>' if sub else ""
    return (
        f'<div class="card {cls}"><div class="card-value">{_esc(value)}</div>'
        f'<div class="card-label">{_esc(label)}</div>{sub_html}</div>'
    )


def _bar(pct: int, cls: str = "") -> str:
    return (
        f'<div class="bar {cls}"><div class="bar-fill" style="width:{max(0, min(100, pct))}%"></div></div>'
    )


def _chip(text: str, cls: str) -> str:
    return f'<span class="chip {cls}">{_esc(text)}</span>'


def build_html_report(
    store: NotebookStore,
    workspace_id: Optional[int] = None,
    reveal_creds: bool = False,
    palette_name: str = "slate",
) -> str:
    """Render the workspace as a standalone themed HTML report."""
    ws = store.get_workspace(workspace_id) if workspace_id else store.get_active_workspace()
    if not ws:
        return "<!doctype html><title>GLACIS</title><h1>Empty workspace</h1>"

    pulse: WorkspacePulse = compute_workspace_pulse(store, ws.id)
    scorecards = compute_target_scorecards(store, ws.id)

    pal = PALETTES.get(palette_name, PALETTES["slate"])
    t = {
        "bg": pal.bg, "surface": pal.surface, "raised": pal.raised,
        "border": pal.border, "border_strong": pal.border_strong,
        "text": pal.text, "text_soft": pal.text_soft, "muted": pal.muted,
        "accent": pal.accent, "ok": pal.ok, "warn": pal.warn, "danger": pal.danger,
    }

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    targets = {x.id: x for x in store.list_targets(workspace_id=ws.id)}

    timeline_events = build_timeline(store, ws.id)
    actions = compute_next_actions(store, ws.id)

    # ------------------------------------------------------------------ header
    sev = pulse.severity_counts
    sev_badges = "".join(
        f'<span class="chip {_SEVERITY_CLASS.get(k, "unrated")}">{_esc(k)} {v}</span>'
        for k, v in sev.items()
        if v
    ) or '<span class="chip muted">no findings yet</span>'

    cards = "".join([
        _stat_card("Targets", str(pulse.targets), f"{pulse.in_scope_targets} in scope"),
        _stat_card("Services", str(pulse.services), f"{pulse.coverage_pct}% tested"),
        _stat_card("Findings", str(pulse.findings), sev_badges, "accent-card", raw_sub=True),
        _stat_card("Credentials", str(pulse.credentials), f"{pulse.evidence} evidence items"),
        _stat_card("Checklist", f"{pulse.checklist_pct}%", f"{pulse.checklist_checked}/{pulse.checklist_total} steps"),
        _stat_card("Momentum (7d)", str(pulse.momentum_7d), f"{pulse.momentum_24h} today"),
    ])

    # ------------------------------------------------------------- scorecards
    rows = []
    for c in scorecards:
        rows.append(
            "<tr>"
            f'<td class="mono">{_esc(c.ip)}<span class="muted">{_esc(" · " + c.hostname) if c.hostname else ""}</span></td>'
            f'<td>{_esc(c.os)}</td>'
            f'<td class="grade grade-{_esc(c.grade)}">{_esc(c.grade)}</td>'
            f'<td>{c.coverage_pct}%{_bar(c.coverage_pct)}</td>'
            f'<td>{c.checklist_pct}%{_bar(c.checklist_pct)}</td>'
            f'<td class="num">{c.services}</td><td class="num">{c.findings}</td>'
            f'<td class="num">{c.credentials}</td>'
            f'<td class="num flags">{c.flags_captured} ✦</td>'
            "</tr>"
        )
    score_rows = "".join(rows) or '<tr><td colspan="9" class="empty">No targets recorded.</td></tr>'

    # ------------------------------------------------------------ target details
    sections: List[str] = []
    for x in targets.values():
        services = store.list_services(target_id=x.id)
        findings = store.list_findings(target_id=x.id)
        creds = store.list_credentials(target_id=x.id)
        evidence = store.list_evidence(target_id=x.id)
        notes = store.list_notes(target_id=x.id)
        checklist = store.list_checklist_items(target_id=x.id)
        failures = store.list_failure_logs(target_id=x.id)

        svc_rows = "".join(
            "<tr>"
            f'<td class="mono">{s.port}/{_esc(s.protocol)}</td>'
            f'<td>{_esc(s.service)}</td><td class="mono">{_esc(s.version)}</td>'
            f'<td>{_chip(s.status.value if hasattr(s.status, "value") else str(s.status), _STATUS_CLASS.get(s.status.value if hasattr(s.status, "value") else str(s.status), "muted"))}</td>'
            f'<td class="muted">{_esc(s.notes[:90])}</td>'
            "</tr>"
            for s in services
        ) or '<tr><td colspan="5" class="empty">No services recorded.</td></tr>'

        find_items = "".join(
            f'<li class="finding"><span class="chip {_SEVERITY_CLASS.get((f.severity or "UNRATED").upper(), "unrated")}">{_esc((f.severity or "UNRATED").upper())}</span>'
            f'<div><strong>{_esc(f.title)}</strong>'
            f'{f"<p>{_esc(f.description)}</p>" if f.description else ""}'
            f'{f"<p class=muted>{_esc(f.notes)}</p>" if f.notes else ""}</div></li>'
            for f in findings
        ) or '<li class="empty">No findings recorded.</li>'

        cred_rows = []
        for c in creds:
            src_html = f'<span class="muted">{_esc(c.source)}</span>' if c.source else ""
            cred_rows.append(
                f'<li class="mono"><span class="cred-user">{_esc(c.username)}</span>'
                f'<span class="cred-secret">{_esc(_mask(c.secret, reveal_creds))}</span>'
                f"{src_html}"
                f'{_chip(c.status, "ok" if c.status == "valid" else "muted")}</li>'
            )
        cred_items = "".join(cred_rows) or '<li class="empty">No credentials recorded.</li>'

        check_items = "".join(
            f'<li><span class="tick {"tick-ok" if k.status == ChecklistStatus.CHECKED else "tick-" + _STATUS_CLASS.get(k.status.value, "muted")}">'
            f'{"✔" if k.status == ChecklistStatus.CHECKED else "·" if k.status == ChecklistStatus.TODO else "⤷" if k.status == ChecklistStatus.DEFERRED else "✗"}</span>'
            f'<span class="{"done" if k.status == ChecklistStatus.CHECKED else ""}">{_esc(k.title)}</span>'
            f'<span class="muted cat">{_esc(k.category)}</span></li>'
            for k in checklist
        ) or '<li class="empty">No checklist applied.</li>'

        ev_rows = []
        for e in evidence:
            desc_html = f'<span class="muted"> — {_esc(e.description)}</span>' if e.description else ""
            ev_rows.append(f'<li class="mono">❐ {_esc(e.path_or_ref)}{desc_html}</li>')
        ev_items = "".join(ev_rows) or '<li class="empty">No evidence recorded.</li>'

        note_items = "".join(f"<li>{_esc(n.content)}</li>" for n in notes) or '<li class="empty">No notes.</li>'
        fail_rows = []
        for fl in failures:
            clue_html = f'<br><strong>breakthrough:</strong> {_esc(fl.breakthrough_clue)}' if fl.breakthrough_clue else ""
            rule_html = f'<br><strong>rule:</strong> {_esc(fl.rule_for_next_time)}' if fl.rule_for_next_time else ""
            fail_rows.append(
                f"<li><strong>stuck:</strong> {_esc(fl.where_stuck)}{clue_html}{rule_html}</li>"
            )
        fail_items = "".join(fail_rows) or '<li class="empty">No failure logs.</li>'

        anchors = " ".join(filter(None, [
            'id="host-root"' if not sections else "",
            f'id="host-{_esc(x.ip)}"',
        ]))
        sections.append(f"""
<section class="host" {anchors}>
  <h2><span class="mono">{_esc(x.ip)}</span>
      {f'<span class="hostname">{_esc(x.hostname)}</span>' if x.hostname else ""}
      {_chip("IN-SCOPE", "ok") if x.is_in_scope else _chip("OUT-OF-SCOPE", "muted")}
      {f'{_chip("USER ✦", "ok")}' if x.user_flag else ""}
      {f'{_chip("ROOT ✦", "danger")}' if x.root_flag else ""}
  </h2>
  {'<p class="foothold mono">' + _esc(x.foothold_cmd) + "</p>" if x.foothold_cmd else ""}
  {'<p class="muted">' + _esc(x.notes) + "</p>" if x.notes else ""}
  <h3>Services</h3>
  <table><thead><tr><th>Port</th><th>Service</th><th>Version</th><th>Status</th><th>Notes</th></tr></thead>
  <tbody>{svc_rows}</tbody></table>
  <h3>Findings</h3><ul class="findings">{find_items}</ul>
  <h3>Credentials</h3><ul class="creds">{cred_items}</ul>
  <h3>Methodology</h3><ul class="checks">{check_items}</ul>
  <h3>Evidence</h3><ul class="evidence">{ev_items}</ul>
  <h3>Field notes</h3><ul class="notes">{note_items}</ul>
  <h3>Failure log</h3><ul class="failures">{fail_items}</ul>
</section>""")

    host_section = "".join(sections) or '<section class="host"><p class="empty">Nothing recorded yet.</p></section>'

    # --------------------------------------------------------------- timeline
    tl_rows = []
    for e in timeline_events[:120]:
        tgt_html = f'<span class="muted"> · {_esc(e.target_ip)}</span>' if e.target_ip else ""
        det_html = f'<span class="tl-detail muted">{_esc(e.detail)}</span>' if e.detail else ""
        tl_rows.append(
            f'<li class="tl"><span class="tl-when mono">{e.when_iso}</span>'
            f'<span class="tl-icon">{e.icon}</span>'
            f'<span class="tl-label">{_esc(e.label)}{tgt_html}</span>'
            f"{det_html}</li>"
        )
    tl_items = "".join(tl_rows) or '<li class="empty">Journal is empty.</li>'

    # ------------------------------------------------------------ next actions
    prio_cls = {"now": "danger", "next": "warn", "later": "muted"}
    act_rows = []
    for a in actions:
        tgt_html = f'<span class="muted"> · {_esc(a.target_ip)}</span>' if a.target_ip else ""
        reason_html = f'<div class="muted reason">{_esc(a.reason)}</div>' if a.reason else ""
        act_rows.append(
            f'<li class="act"><span class="chip {prio_cls.get(a.priority.value, "muted")}">{a.priority.value.upper()}</span>'
            f'<strong>{_esc(a.title)}</strong>{tgt_html}{reason_html}</li>'
        )
    act_items = "".join(act_rows) or '<li class="empty">Queue is clear — everything recorded is resolved.</li>'

    css_vars = " ".join(f"--c-{k}: {v};" for k, v in t.items())

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GLACIS Report — {_esc(pulse.workspace_name)}</title>
<style>
:root {{ {css_vars} }}
* {{ box-sizing: border-box; }}
html {{ scroll-behavior: smooth; }}
body {{
  margin: 0; background: var(--c-bg); color: var(--c-text);
  font: 15px/1.55 "SF Mono", "Cascadia Code", Consolas, "DejaVu Sans Mono", monospace;
  -webkit-font-smoothing: antialiased;
}}
a {{ color: var(--c-accent); text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
.layout {{ display: grid; grid-template-columns: 220px minmax(0, 1fr); max-width: 1180px; margin: 0 auto; }}
nav {{
  position: sticky; top: 0; align-self: start; padding: 26px 10px 26px 22px;
  font-size: 12.5px; max-height: 100vh; overflow-y: auto;
}}
nav .brand {{ font-weight: 700; letter-spacing: .14em; color: var(--c-accent); margin-bottom: 4px; }}
nav .brand-sub {{ color: var(--c-muted); font-size: 11px; margin-bottom: 18px; }}
nav a {{ display: block; padding: 3.5px 8px; color: var(--c-text-soft); border-left: 2px solid var(--c-border); }}
nav a:hover {{ border-left-color: var(--c-accent); color: var(--c-text); text-decoration: none; background: var(--c-surface); }}
main {{ padding: 26px 28px 90px; min-width: 0; }}
header.report {{ border: 1px solid var(--c-border_strong); background: var(--c-surface); border-radius: 10px; padding: 22px 24px 18px; }}
header.report h1 {{ margin: 0 0 2px; font-size: 21px; letter-spacing: .06em; }}
header.report .ws {{ color: var(--c-accent); }}
header.report .meta {{ color: var(--c-muted); font-size: 12px; margin-bottom: 14px; }}
.cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; }}
.card {{ background: var(--c-raised); border: 1px solid var(--c-border); border-radius: 8px; padding: 12px 14px; }}
.card-value {{ font-size: 23px; font-weight: 700; }}
.card-label {{ color: var(--c-muted); font-size: 11px; text-transform: uppercase; letter-spacing: .12em; margin-top: 2px; }}
.card-sub {{ color: var(--c-text-soft); font-size: 11.5px; margin-top: 5px; }}
.accent-card {{ border-color: var(--c-accent); }}
.accent-card .card-value {{ color: var(--c-accent); }}
.spark-row {{ display: flex; align-items: center; gap: 14px; margin-top: 14px; color: var(--c-muted); font-size: 12px; }}
.spark {{ display: block; }}
h2 {{ font-size: 16px; margin: 34px 0 10px; padding-bottom: 6px; border-bottom: 1px solid var(--c-border); letter-spacing: .04em; }}
h3 {{ font-size: 12.5px; text-transform: uppercase; letter-spacing: .14em; color: var(--c-muted); margin: 20px 0 8px; }}
table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
th {{ text-align: left; color: var(--c-muted); font-size: 11px; text-transform: uppercase; letter-spacing: .1em; border-bottom: 1px solid var(--c-border_strong); padding: 6px 8px; }}
td {{ padding: 6px 8px; border-bottom: 1px solid var(--c-border); vertical-align: top; }}
tr:hover td {{ background: var(--c-surface); }}
.num {{ text-align: right; }}
.mono {{ font-family: inherit; }}
.hostname {{ color: var(--c-text-soft); font-weight: 400; }}
.muted {{ color: var(--c-muted); }}
.empty {{ color: var(--c-muted); font-style: italic; list-style: none; }}
.grade {{ font-weight: 700; text-align: center; font-size: 15px; }}
.grade-A {{ color: var(--c-ok); }} .grade-B {{ color: var(--c-ok); }}
.grade-C {{ color: var(--c-warn); }} .grade-D {{ color: var(--c-warn); }}
.grade-E, .grade-F {{ color: var(--c-danger); }}
.flags {{ color: var(--c-warn); }}
.chip {{ display: inline-block; font-size: 10.5px; font-weight: 700; letter-spacing: .08em;
  border: 1px solid var(--c-border_strong); border-radius: 20px; padding: 1.5px 9px; vertical-align: middle; }}
.chip.ok {{ color: var(--c-ok); border-color: var(--c-ok); }}
.chip.warn {{ color: var(--c-warn); border-color: var(--c-warn); }}
.chip.danger {{ color: var(--c-danger); border-color: var(--c-danger); }}
.chip.muted {{ color: var(--c-muted); border-color: var(--c-border); }}
.chip.crit, .chip.high {{ color: var(--c-danger); border-color: var(--c-danger); }}
.chip.med {{ color: var(--c-warn); border-color: var(--c-warn); }}
.chip.low {{ color: var(--c-accent); border-color: var(--c-accent); }}
.chip.info, .chip.unrated {{ color: var(--c-muted); border-color: var(--c-border); }}
.bar {{ height: 4px; background: var(--c-border); border-radius: 3px; margin-top: 4px; width: 90px; }}
.bar-fill {{ height: 100%; border-radius: 3px; background: var(--c-accent); }}
.host {{ background: var(--c-surface); border: 1px solid var(--c-border); border-radius: 10px; padding: 4px 22px 16px; margin: 18px 0; }}
.host h2 {{ border-bottom: none; margin-top: 22px; }}
.foothold {{ background: var(--c-raised); border-left: 3px solid var(--c-ok); padding: 8px 12px; border-radius: 4px; }}
ul {{ padding-left: 18px; }}
ul li {{ margin: 5px 0; }}
.findings li {{ display: flex; gap: 10px; align-items: baseline; list-style: none; }}
.findings p {{ margin: 2px 0 0; }}
.creds li {{ list-style: none; display: flex; gap: 12px; align-items: baseline; }}
.cred-user {{ color: var(--c-accent); min-width: 110px; }}
.cred-secret {{ color: var(--c-warn); }}
.checks li {{ list-style: none; display: flex; gap: 8px; align-items: baseline; }}
.checks .cat {{ margin-left: auto; font-size: 10.5px; letter-spacing: .1em; }}
.tick {{ width: 1.2em; display: inline-block; text-align: center; font-weight: 700; }}
.tick-ok {{ color: var(--c-ok); }} .tick-warn {{ color: var(--c-warn); }}
.tick-danger {{ color: var(--c-danger); }} .tick-muted {{ color: var(--c-muted); }}
.done {{ color: var(--c-muted); text-decoration: line-through; }}
.evidence li, .notes li, .failures li {{ margin: 7px 0; }}
.tl {{ list-style: none; display: flex; gap: 10px; margin: 4px 0; align-items: baseline; }}
.tl-when {{ color: var(--c-muted); font-size: 12px; min-width: 118px; }}
.tl-icon {{ color: var(--c-accent); width: 1.1em; }}
.tl-label {{ min-width: 0; }}
.tl-detail {{ display: block; font-size: 12.5px; }}
.act {{ list-style: none; margin: 9px 0; }}
.act .reason {{ font-size: 12px; margin-top: 2px; }}
footer.foot {{ margin-top: 46px; color: var(--c-muted); font-size: 11.5px; border-top: 1px solid var(--c-border); padding-top: 12px; }}
@media (max-width: 860px) {{
  .layout {{ grid-template-columns: 1fr; }}
  nav {{ position: static; max-height: none; border-bottom: 1px solid var(--c-border); }}
}}
@media print {{
  body {{ background: #fff; color: #111; }}
  nav {{ display: none; }}
  .layout {{ grid-template-columns: 1fr; }}
  .host, header.report {{ border-color: #ccc; background: #fff; }}
  .bar {{ background: #ddd; }}
}}
</style>
</head>
<body>
<div class="layout">
<nav>
  <div class="brand">GLACIS</div>
  <div class="brand-sub">field worksheet report</div>
  <a href="#host-root">Overview</a>
  <a href="#pulse">Pulse</a>
  <a href="#queue">Next actions</a>
  <a href="#scorecards">Scorecards</a>
  <a href="#timeline">Timeline</a>
  {"".join(f'<a href="#host-{_esc(x.ip)}">{_esc(x.ip)}</a>' for x in targets.values())}
</nav>
<main>
<header class="report" id="host-root">
  <h1>GLACIS <span class="ws">{_esc(pulse.workspace_name)}</span></h1>
  <div class="meta">generated {now} · {pulse.targets} targets · {pulse.services} services · local/offline export</div>
  <div class="cards">{cards}</div>
  <div class="spark-row">
    {_spans(pulse.activity_14d, t["accent"])}
    <span>momentum — records per day, last 14 days</span>
  </div>
</header>

<h2 id="pulse">◈ Workspace pulse</h2>
<table>
<thead><tr><th>Metric</th><th>Value</th><th>Detail</th></tr></thead>
<tbody>
  <tr><td>Service coverage</td><td>{pulse.coverage_pct}%</td><td>{pulse.services_tested} of {pulse.services} services tested · {pulse.services_dead_ends} dead-ends</td></tr>
  <tr><td>Methodology progress</td><td>{pulse.checklist_pct}%</td><td>{pulse.checklist_checked} checked · {pulse.checklist_dead_ends} dead-ends · {pulse.checklist_total} total</td></tr>
  <tr><td>Open leads</td><td>{pulse.leads_open}</td><td>of {pulse.leads_total} recorded</td></tr>
  <tr><td>Command history</td><td>{pulse.commands_logged}</td><td>{pulse.failure_logs} failure logs (lessons learned)</td></tr>
  <tr><td>Busiest target</td><td class="mono">{_esc(pulse.busiest_target or "—")}</td><td>{pulse.busiest_target_count} recorded artefacts</td></tr>
  <tr><td>Stalest target</td><td class="mono">{_esc(pulse.stalest_target or "—")}</td><td>{pulse.stale_days} days since last update</td></tr>
</tbody></table>

<h2 id="queue">▲ Next actions</h2>
<p class="muted">Deterministic triage of your own open items — no inference, no scanning.</p>
<ul>{act_items}</ul>

<h2 id="scorecards">★ Target scorecards</h2>
<table>
<thead><tr><th>Target</th><th>OS</th><th>Grade</th><th>Coverage</th><th>Methodology</th><th>Svc</th><th>Find</th><th>Creds</th><th>Flags</th></tr></thead>
<tbody>{score_rows}</tbody>
</table>

<h2 id="timeline">⏱ Timeline</h2>
<ul>{tl_items}</ul>

{host_section}

<footer class="foot">
  Generated locally by GLACIS — zero network, zero telemetry. Credentials are masked
  unless the report was exported with <span class="mono">--reveal-creds</span>.
</footer>
</main>
</div>
</body>
</html>"""
