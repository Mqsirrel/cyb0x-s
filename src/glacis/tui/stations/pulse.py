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
from glacis.tui.theme import GLYPHS, current_palette
from glacis.tui.widgets.chrome import set_border_text
from glacis.tui.widgets.lists import DataListItem, elide, sync_data_list

_PHASE_STYLE = {
    HostPhase.UNTOUCHED: (GLYPHS["host_untouched"], "warn"),
    HostPhase.RECON: (GLYPHS["host_recon"], "accent"),
    HostPhase.FOOTHOLD: (GLYPHS["host_foothold"], "warn"),
    HostPhase.USER: (GLYPHS["host_user"], "ok"),
    HostPhase.ROOT: (GLYPHS["host_root"], "ok"),
    HostPhase.COMPLETE: (GLYPHS["host_complete"], "ok"),
}

_SEV_STYLE = {
    AdvisorySeverity.CRIT: (GLYPHS["dead_end"], "danger"),
    AdvisorySeverity.WARN: (GLYPHS["warn"], "warn"),
    AdvisorySeverity.HINT: (GLYPHS["hint"], "accent"),
    AdvisorySeverity.INFO: (GLYPHS["info"], "muted"),
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
        margin-left: 1;
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
        width: 48%;
        height: 100%;
    }
    #pulse-advisories-panel {
        width: 52%;
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
                yield Static(id="pulse-hosts-legend", classes="panel-legend")
            with Vertical(id="pulse-advisories-panel", classes="panel-box"):
                yield ListView(id="pulse-advisories", classes="panel-list")
                yield Static(id="pulse-advisories-legend", classes="panel-legend")

    def on_mount(self) -> None:
        P_ = current_palette()
        try:
            set_border_text(
                self.query_one("#pulse-hosts-panel"),
                title=" HOST TRIAGE BOARD ",
                subtitle=" [Enter: Focus host] ",
            )
            set_border_text(
                self.query_one("#pulse-advisories-panel"),
                title=" EXPLAINABLE NEXT-FOCUS SIGNALS ",
                subtitle=" [Enter: Jump] ",
            )
            self.query_one("#pulse-hosts-legend", Static).update(
                Text.assemble(
                    (f"{GLYPHS['host_untouched']} UNTOUCHED   ", "bold " + P_.accent),
                    (f"{GLYPHS['host_recon']} RECON   ", "bold " + P_.accent),
                    (f"{GLYPHS['host_foothold']} FOOTHOLD   ", "bold " + P_.accent),
                    (f"{GLYPHS['host_user']} USER   ", "bold " + P_.accent),
                    (f"{GLYPHS['host_root']} ROOT   ", "bold " + P_.accent),
                    (f"{GLYPHS['host_complete']} COMPLETE\n", "bold " + P_.accent),
                    ("svc services · todo untested · cred creds · ev evidence · ", P_.muted),
                    (f"{GLYPHS['dead_end_count']} dead ends", P_.muted),
                )
            )
            self.query_one("#pulse-advisories-legend", Static).update(
                Text.assemble(
                    (f"{GLYPHS['dead_end']} CRITICAL   ", "bold " + P_.danger),
                    (f"{GLYPHS['warn']} ATTENTION   ", "bold " + P_.warn),
                    (f"{GLYPHS['hint']} HINT   ", "bold " + P_.accent),
                    (f"{GLYPHS['info']} INFO      ", P_.muted),
                    ("Enter opens the station the signal points at", P_.muted),
                )
            )
        except Exception:
            pass

    # ------------------------------------------------------------------
    def _hosts_panel_width(self) -> int:
        """Usable row width of the host board (minus padding and scrollbar)."""
        try:
            width = self.query_one("#pulse-hosts", ListView).size.width - 3
        except Exception:
            width = 0
        return width if width > 24 else 70

    def _host_row(self, h: Any) -> Text:
        """One host, answerable in one glance.

        Order is deliberate: identity → progress → phase → *what is left*.
        ``s1/u1`` needed the manual; ``todo 1`` does not, and the untested
        count is the only number that changes what you do next, so it is the
        only one painted in warning colour.
        """
        P = current_palette()
        icon, colour = _PHASE_STYLE.get(h.phase, (GLYPHS["host_untouched"], "muted"))

        # Budgets are derived from the *panel* width, not the station width, so
        # the row stays inside its frame on a 100-column terminal as well as a
        # 250-column one.  Everything after the identity block is optional and
        # dropped in priority order when there is no room.
        panel_width = self._hosts_panel_width()
        host_budget = max(min(panel_width // 4, 18), 8)

        t = Text()
        t.append(f"{icon} ", style=f"bold {getattr(P, colour)}")
        t.append(f"{h.ip:<15}", style="bold " + P.text)
        if h.hostname:
            t.append(f"  {elide(h.hostname, host_budget):<{host_budget}}", style=P.text_soft)
        t.append("  ")
        t.append(h.progress_bar, style=f"bold {P.ok}")
        t.append(f" {h.completion_pct:3.0f}% ", style=P.text_soft)
        t.append(f"[{h.phase.value:<8}]", style=f"bold {getattr(P, colour)}")

        dead = h.services_dead_end + h.failure_count
        # Line 2 is the *inventory*: it is what turns a phase badge into a
        # decision, and it is also what stops a two-host board from being 25
        # rows of dead space.
        t.append("\n  ")
        t.append(h.progress_bar, style=f"bold {P.ok}")
        t.append("  ", style="")
        counters = [
            (f"svc {h.services_total}", P.muted if h.services_total else f"dim {P.muted}"),
            (f"todo {h.services_untested}", f"bold {P.warn}" if h.services_untested else f"dim {P.muted}"),
            (f"cred {h.creds_count}", P.accent if h.creds_count else f"dim {P.muted}"),
            (f"ev {h.evidence_count}", P.ok if h.evidence_count else f"dim {P.muted}"),
        ]
        if dead:
            counters.append((f"{GLYPHS['dead_end']}{dead} dead", f"bold {P.danger}"))
        used = 2 + 10 + 2
        for i, (label, style) in enumerate(counters):
            if used + len(label) + 3 > panel_width:
                break
            if i:
                t.append(" · ", style=f"dim {P.muted}")
            t.append(label, style=style)
            used += len(label) + 3
        if not h.is_in_scope:
            t.append("  OUT-OF-SCOPE", style=f"bold {P.danger}")
        if h.is_pivot:
            t.append(f" {GLYPHS['pivot']}", style=f"bold {P.warn}")
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
            t.append(f"\n    {GLYPHS['next']} {a.action_text}", style=f"bold {getattr(P, colour)}")
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
            empty.append(" press ", style=f"bold {P.text}")
            empty.append("t", style=f"bold {P.bg} on {P.accent}")
            empty.append(" and name the first box you are attacking", style=f"bold {P.text}")
            empty.append("\n  Nothing else on this station means anything until a target exists.",
                        style=f"{P.muted}")
            host_list.append(DataListItem(data_obj=None, display_text=empty, is_placeholder=True))

        adv_list = self.query_one("#pulse-advisories", ListView)
        sync_data_list(
            adv_list,
            report.advisories,
            self._advisory_row,
            key_fn=lambda a: ("TriageAdvisory",) + a.key(),
        )
        if report.advisories:
            # A short list that simply stops reads as a rendering bug. One
            # terminal marker says "that is everything" without inventing data.
            P = current_palette()
            tail = Text()
            tail.append(f" {GLYPHS['info']} end of signals", style=f"dim {P.muted}")
            adv_list.append(DataListItem(data_obj=None, display_text=tail, is_placeholder=True))
        if not report.advisories:
            P = current_palette()
            adv_list.clear()
            calm = Text()
            calm.append(f"  {GLYPHS['done']} NOTHING OUTSTANDING ", style=f"bold {P.bg} on {P.ok}")
            calm.append("\n  Every host is mapped with no open state gaps. Keep recording.",
                        style=f"bold {P.text}")
            adv_list.append(DataListItem(data_obj=None, display_text=calm, is_placeholder=True))

        try:
            untested = sum(h.services_untested for h in report.hosts)
            stuck = sum(h.services_dead_end + h.failure_count for h in report.hosts)
            hosts_sub = f" {len(report.hosts)} hosts "
            if untested:
                hosts_sub += f"· {untested} untested "
            if stuck:
                hosts_sub += f"· {stuck} dead "
            set_border_text(self.query_one("#pulse-hosts-panel"), subtitle=hosts_sub)
            set_border_text(
                self.query_one("#pulse-advisories-panel"),
                subtitle=f" {len(report.advisories)} signals · [Enter: Jump] ",
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
