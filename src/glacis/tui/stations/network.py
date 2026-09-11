"""Station 5 — Network: documented subnets, pivots and SOCKS hop chains.

Pure documentation/visualization over the operator's own records (subnet
strings, ``is_pivot`` flags, ``pivot_route`` notes). Nothing here probes a
network: route math lives in :mod:`glacis.routes`. Enter on an action copies
its reference syntax for the human to run in their own terminal.
"""

from __future__ import annotations

from typing import Any, List, NamedTuple

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import ListView, Static

from glacis.routes import build_network_topology, generate_proxychains_config
from glacis.tui import widgets as _pkg
from glacis.tui.theme import GLYPHS, current_palette
from glacis.tui.widgets.chrome import set_border_text
from glacis.tui.widgets.lists import DataListItem, elide, sync_data_list


class ActionSpec(NamedTuple):
    """One copy-ready reference command in the Network action list."""

    label: str
    cmd: str


class NetworkStation(Static):
    """ASCII topology map plus copy-ready pivot/ProxyChains actions."""

    DEFAULT_CSS = """
    NetworkStation {
        height: 1fr;
        layout: vertical;
        padding: 0 1;
    }
    #network-body {
        height: 1fr;
        layout: horizontal;
    }
    #network-map-panel {
        width: 52%;
        height: 100%;
        border: solid $border;
        border-title-color: $text-soft;
        border-title-style: bold;
        background: $surface;
        padding: 0 1;
        margin-right: 1;
    }
    #network-map-panel:focus-within {
        border: double $accent;
        border-title-color: $accent;
    }
    #network-map {
        height: auto;
    }
    #network-actions-panel {
        width: 48%;
        height: 100%;
        border: solid $border;
        border-title-color: $text-soft;
        border-title-style: bold;
        border-subtitle-color: $accent;
        border-subtitle-align: right;
        background: $surface;
        padding: 0;
    }
    #network-actions-panel:focus-within {
        border: double $accent;
        border-title-color: $accent;
        border-subtitle-color: $accent;
    }
    #network-actions {
        height: 1fr;
        background: transparent;
    }
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._actions: List[ActionSpec] = []

    def compose(self) -> ComposeResult:
        with Horizontal(id="network-body"):
            with Vertical(id="network-map-panel"):
                with VerticalScroll():
                    yield Static(id="network-map")
                yield Static(id="network-map-legend", classes="panel-legend")
            with Vertical(id="network-actions-panel"):
                yield ListView(id="network-actions", classes="panel-list")

    def on_mount(self) -> None:
        P = current_palette()
        try:
            set_border_text(
                self.query_one("#network-map-panel"), title=" DOCUMENTED NETWORK TOPOLOGY "
            )
            panel = self.query_one("#network-actions-panel")
            set_border_text(panel, title=" TUNNEL & ROUTE ACTIONS ", subtitle=" [Enter: Copy] ")
            self.query_one("#network-map-legend", Static).update(
                Text.assemble(
                    (f"{GLYPHS['pivot']} ", "bold " + P.warn),
                    ("dual-homed pivot  ·  ", P.muted),
                    ("one box per documented subnet  ·  ", P.muted),
                    ("drawn only from targets you recorded (:t)", P.muted),
                    ("\n", ""),
                    (f"{GLYPHS['next']} ", "bold " + P.accent),
                    ("Enter copies the highlighted tunnel command — GLACIS sends nothing itself",
                     P.muted),
                )
            )
        except Exception:
            pass

    def update_topology(self, store: Any) -> None:
        P = current_palette()
        topo = build_network_topology(store)

        map_txt = Text(topo.ascii_map, style=f"bold {P.text_soft}")
        if not topo.subnets:
            map_txt = Text(
                "No targets recorded yet.\n\n"
                "Add targets (:t) and mark dual-homed hosts as pivots:\n"
                "  :pivot 192.168.1.0/24 via socks5:1080\n\n"
                "GLACIS calculates hop chains and ProxyChains syntax from\n"
                "your own notes — it never sends a packet itself.",
                style=f"bold {P.text}",
            )
        self.query_one("#network-map", Static).update(map_txt)
        try:
            set_border_text(
                self.query_one("#network-map-panel"),
                subtitle=(
                    f" {len(topo.subnets)} subnet(s) · {len(topo.pivots)} pivot(s) "
                    f"· {sum(len(v) for v in topo.subnets.values())} host(s) "
                ),
            )
        except Exception:
            pass

        actions: List[ActionSpec] = []

        # Scaffolding configs are always useful, pivoted or not; they never
        # touch the network — the human runs them in their own terminal.
        chain_hint = "all documented hops" if topo.pivots else "stock template (no pivots yet)"
        actions.append(
            ActionSpec(
                f"ProxyChains config — {chain_hint}",
                generate_proxychains_config(topo),
            )
        )
        actions.append(
            ActionSpec("Chisel server (attacker host)", "chisel server -p 8000 --reverse")
        )

        for ip, route in topo.routes_by_target.items():
            if route.is_direct:
                continue
            for hop in route.hops:
                actions.append(
                    ActionSpec(
                        f"Chisel client via pivot {hop.pivot_ip} → {hop.dest_subnet}",
                        f"chisel client {hop.pivot_ip}:8000 R:{hop.proxy_port}:socks",
                    )
                )
            if route.ssh_jump_cmd:
                actions.append(
                    ActionSpec(f"SSH ProxyJump to {route.destination}", route.ssh_jump_cmd)
                )
            if route.chisel_client_cmd:
                actions.append(
                    ActionSpec(f"Chisel client hop for {route.destination}", route.chisel_client_cmd)
                )
            actions.append(
                ActionSpec(
                    f"Proxied scan hint — {route.destination} ({route.hop_count} hop(s))",
                    f"proxychains -q nmap -sT -Pn -p- {route.destination}",
                )
            )

        for p in topo.pivots:
            port = p.get("port", 1080)
            actions.append(
                ActionSpec(
                    f"SSH SOCKS listener on pivot {p['ip']}",
                    f"ssh -N -D {port} user@{p['ip']}   # {p.get('pivot_route') or 'dual-homed'}",
                )
            )

        self._actions = actions

        action_list = self.query_one("#network-actions", ListView)

        avail = self._actions_panel_width()

        def _render(spec: ActionSpec) -> Text:
            t = Text()
            t.append(elide(spec.label, max(avail - 2, 12)) + "\n", style=f"bold {P.text}")
            t.append(f"  {GLYPHS['run']} ", style=f"bold {P.ok}")
            first, *rest = spec.cmd.splitlines() or [""]
            t.append(elide(first, max(avail - 6, 12)), style=f"bold {P.warn}")
            for extra in rest[:6]:
                t.append(f"\n     {elide(extra, max(avail - 7, 12))}", style=P.text_soft)
            if len(rest) > 6:
                t.append(f"\n     … (+{len(rest) - 6} lines)", style=P.muted)
            return t

        if actions:
            sync_data_list(
                action_list, actions, _render,
                key_fn=lambda s: ("ActionSpec", s.label),
            )
        else:
            t = Text(
                "\n  No targets recorded yet.\n\n"
                "  Add targets (:t) and mark dual-homed hosts as pivots:\n"
                "    :pivot 172.16.50.0/24 via socks5:1080\n",
                style=P.muted,
            )
            sync_data_list(action_list, [], _render, placeholder_text=t)

        try:
            set_border_text(
                self.query_one("#network-actions-panel"),
                subtitle=f" {len(actions)} action(s) · [Enter: Copy] ",
            )
        except Exception:
            pass

    def _actions_panel_width(self) -> int:
        """Usable row width of the action list (minus padding and scrollbar)."""
        try:
            width = self.query_one("#network-actions", ListView).size.width - 3
        except Exception:
            width = 0
        return width if width > 24 else 70

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.list_view.id == "network-actions" and isinstance(event.item, DataListItem):
            spec = event.item.data_obj
            if isinstance(spec, ActionSpec):
                _pkg.copy_to_clipboard(spec.cmd)
                if hasattr(self.app, "notify"):
                    self.app.notify(f"Copied: {spec.label}")
