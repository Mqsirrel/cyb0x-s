"""Station 0 — Pulse: deterministic situation-awareness board.

Left panel: one row per host showing its kill-chain phase, transparent
progress arithmetic, service/cred/evidence counts and dead-end heat.

Right panel: explainable, rule-named advisories. Every line is derived from
recorded data only; Enter navigates to the station the advisory points at.
No timers, no animations, no background work — the report is computed when
the station is opened and when the notebook changes.
"""

from __future__ import annotations

from typing import Any, Optional

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import ListView, Static

from glacis.triage import (
    AdvisoryKind,
    AdvisorySeverity,
    HostPhase,
    TriageAdvisory,
    TriageReport,
    phase_counts,
)
from glacis.tui.theme import current_palette
from glacis.tui.widgets.lists import DataListItem, sync_data_list

_PHASE_STYLE = {
    HostPhase.UNTOUCHED: ("◇", "warn"),
    HostPhase.RECON: ("◐", "accent"),
    HostPhase.FOOTHOLD: ("▸", "warn"),
    HostPhase.USER: ("◆", "ok"),
    HostPhase.ROOT: ("★", "ok"),
    HostPhase.COMPLETE: ("✔", "ok"),
}

_SEV_STYLE = {
    AdvisorySeverity.CRIT: ("✖", "danger"),
    AdvisorySeverity.WARN: ("▲", "warn"),
    AdvisorySeverity.HINT: ("•", "accent"),
    AdvisorySeverity.INFO: ("·", "muted"),
}


class PulseStation(Static):
    """The operator's mission-control triage board."""

    DEFAULT_CSS = """
    PulseStation {
        height: 1fr;
        layout: vertical;
        padding: 0 1;
    }
    #pulse-kpi-band {
        height: 3;
        layout: horizontal;
        margin-bottom: 1;
    }
    #pulse-kpis {
        width: 1fr;
        height: 3;
        border: solid $border;
        background: $surface;
        padding: 0 1;
    }
    #pulse-mode {
        width: auto;
        height: 3;
        border: solid $border;
        background: $surface;
        padding: 0 1;
        color: $text-muted;
    }
    #pulse-body {
        height: 1fr;
        layout: horizontal;
    }
    #pulse-hosts-panel {
        width: 46%;
        height: 100%;
    }
    #pulse-advisories-panel {
        width: 54%;
        height: 100%;
        margin-left: 1;
    }
    PulseStation .panel-box {
        border: solid $border;
        border-title-color: $text-soft;
        border-title-style: bold;
        border-subtitle-color: $text-muted;
        border-subtitle-align: right;
        background: $surface;
        padding: 0;
    }
    PulseStation .panel-box:focus-within {
        border: double $accent;
        border-title-color: $accent;
        border-subtitle-color: $accent;
    }
    #pulse-hosts, #pulse-advisories {
        height: 1fr;
        background: transparent;
    }
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.report: Optional[TriageReport] = None

    def compose(self) -> ComposeResult:
        with Horizontal(id="pulse-kpi-band"):
            yield Static(id="pulse-kpis")
            yield Static(id="pulse-mode")
        with Horizontal(id="pulse-body"):
            with Vertical(id="pulse-hosts-panel", classes="panel-box"):
                yield ListView(id="pulse-hosts", classes="panel-list")
            with Vertical(id="pulse-advisories-panel", classes="panel-box"):
                yield ListView(id="pulse-advisories", classes="panel-list")

    def on_mount(self) -> None:
        try:
            self.query_one("#pulse-hosts-panel").border_title = " HOST TRIAGE BOARD "
            self.query_one("#pulse-advisories-panel").border_title = " EXPLAINABLE NEXT-FOCUS SIGNALS "
            self.query_one("#pulse-hosts-panel").border_subtitle = " [Enter: Focus host] "
            self.query_one("#pulse-advisories-panel").border_subtitle = " [Enter: Jump] "
        except Exception:
            pass

    # ------------------------------------------------------------------
    def _host_row(self, h: Any) -> Text:
        P = current_palette()
        icon, colour = _PHASE_STYLE.get(h.phase, ("◇", "muted"))
        t = Text()
        t.append(f"{icon} ", style=f"bold {getattr(P, colour)}")
        t.append(f"{h.ip:<15}", style="bold " + P.text)
        if h.hostname:
            host = h.hostname if len(h.hostname) <= 12 else h.hostname[:11] + "…"
            t.append(f" {host:<12}", style=P.text_soft)
        t.append(" ")
        t.append(h.progress_bar, style=f"bold {P.ok}")
        t.append(f" {h.completion_pct:5.1f}% ", style=P.text_soft)
        t.append(f"[{h.phase.value:<9}]", style=f"bold {getattr(P, colour)}")
        t.append(f" s{h.services_total}", style=P.muted)
        if h.services_untested:
            t.append(f"/u{h.services_untested}", style=f"bold {P.warn}")
        if h.creds_count:
            t.append(f" k{h.creds_count}", style=P.accent)
        if h.evidence_count:
            t.append(f" e{h.evidence_count}", style=P.ok)
        dead = h.services_dead_end + h.failure_count
        if dead:
            t.append(f" ✖{dead}", style=f"bold {P.danger}")
        if not h.is_in_scope:
            t.append(" OUT-OF-SCOPE", style=f"bold {P.danger}")
        if h.is_pivot:
            t.append(" ⇄", style=f"bold {P.warn}")
        return t

    def _advisory_row(self, a: TriageAdvisory) -> Text:
        P = current_palette()
        icon, colour = _SEV_STYLE.get(a.severity, ("·", "muted"))
        t = Text()
        t.append(f"{icon} ", style=f"bold {getattr(P, colour)}")
        t.append(f"[{a.rule_id}] ", style=f"{P.muted}")
        t.append(a.title, style=f"bold {P.text}")
        if a.detail:
            t.append(f"\n    {a.detail}", style=P.text_soft)
        if a.action_text:
            t.append(f"\n    ▸ {a.action_text}", style=f"bold {getattr(P, colour)}")
        if a.kind == AdvisoryKind.DIRECTION:
            t.append("  (opt-in)", style=f"dim {P.muted}")
        return t

    def _render_kpis(self, report: TriageReport) -> None:
        P = current_palette()
        counts = phase_counts(report)
        t = Text()
        t.append(f" OVERALL {report.overall_pct:5.1f}%  ", style=f"bold {P.accent}")
        for phase in HostPhase:
            n = counts.get(phase.value, 0)
            if n:
                _, colour = _PHASE_STYLE[phase]
                t.append(f"{phase.value:<10} {n}  ", style=f"bold {getattr(P, colour)}")
        tot = report.totals
        t.append(f"| svc {tot.get('services', 0)} ", style=P.muted)
        t.append(f"creds {tot.get('credentials', 0)} ", style=P.muted)
        t.append(f"proofs {tot.get('proofs', 0)} ", style=P.muted)
        t.append(f"dead {tot.get('dead_ends', 0)}", style=f"bold {P.danger}" if tot.get("dead_ends") else P.muted)
        self.query_one("#pulse-kpis", Static).update(t)

        mode = Text()
        if report.direction_enabled:
            mode.append(" DIRECTION: ON ", style=f"bold {P.bg} on {P.ok}")
            mode.append(" (G toggles)", style=P.muted)
        else:
            mode.append(" STATE ONLY ", style=f"bold {P.bg} on {P.muted}")
            mode.append(" press G for focus-shift hints", style=P.muted)
        self.query_one("#pulse-mode", Static).update(mode)

    def update_report(self, report: TriageReport) -> None:
        self.report = report
        self._render_kpis(report)
        host_list = self.query_one("#pulse-hosts", ListView)
        sync_data_list(
            host_list,
            report.hosts,
            self._host_row,
            key_fn=lambda h: ("HostTriage", h.target_id),
        )
        if not report.hosts:
            P = current_palette()
            host_list.clear()
            empty = Text()
            empty.append("  [+ ADD TARGET] ", style=f"bold {P.bg} on {P.accent}")
            empty.append(" Press 't' or :t 10.10.10.10", style=f"bold {P.text}")
            host_list.append(DataListItem(data_obj=None, display_text=empty, is_placeholder=True))

        adv_list = self.query_one("#pulse-advisories", ListView)
        sync_data_list(
            adv_list,
            report.advisories,
            self._advisory_row,
            key_fn=lambda a: ("TriageAdvisory",) + a.key(),
        )
        if not report.advisories:
            P = current_palette()
            adv_list.clear()
            calm = Text()
            calm.append("  ✔ NOTHING OUTSTANDING ", style=f"bold {P.bg} on {P.ok}")
            calm.append("\n  Every host is mapped with no open state gaps. Keep recording.",
                        style=f"bold {P.text}")
            adv_list.append(DataListItem(data_obj=None, display_text=calm, is_placeholder=True))

        try:
            self.query_one("#pulse-hosts-panel").border_subtitle = f" {len(report.hosts)} hosts "
            self.query_one("#pulse-advisories-panel").border_subtitle = (
                f" {len(report.advisories)} signals "
            )
        except Exception:
            pass

    # ------------------------------------------------------------------
    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.list_view.id == "pulse-hosts" and isinstance(event.item, DataListItem):
            host = event.item.data_obj
            if host is None or not hasattr(self.app, "focus_triage_host"):
                return
            self.app.focus_triage_host(host)
        elif event.list_view.id == "pulse-advisories" and isinstance(event.item, DataListItem):
            advisory = event.item.data_obj
            if isinstance(advisory, TriageAdvisory) and hasattr(self.app, "focus_advisory"):
                self.app.focus_advisory(advisory)
