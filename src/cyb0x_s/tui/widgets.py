"""Textual widgets and modal dialogs for CYB0X-S Worksheet."""

from __future__ import annotations

import shlex
import time
from datetime import timedelta
from typing import Any, Dict, List, Optional, Set

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import DataTable, Input, Label, ListItem, ListView, Static, Tree

from cyb0x_s.clipboard import copy_to_clipboard
from cyb0x_s.models import (
    Credential,
    Service,
    Target,
)
from cyb0x_s.templates import get_template_guidance_for_title
from cyb0x_s.tui.theme import (
    S,
    current_palette,
    mix,
    ramp,
)


def substitute_command_placeholders(command: str, target_ip: str = "") -> str:
    """Fill the static command templates with the active target context.

    Purely mechanical string substitution on human-curated reference text:
    no command is ever generated, inferred or suggested.
    """
    if not command:
        return ""
    res = command
    if target_ip:
        subnet = f"{target_ip.rsplit('.', 1)[0]}.0/24" if "." in target_ip else ""
        res = res.replace("<TARGET_IP>", target_ip).replace("<TARGET_SUBNET>", subnet)
    res = res.replace("<WORDLIST>", "/usr/share/wordlists/dirb/common.txt")
    return res


class TargetTreeWidget(Tree):
    """Sidebar Tree displaying targets and their listening services."""

    # The tree lives inside a bordered panel now, so it must not draw its
    # own frame — otherwise every sidebar panel gets a double border.
    DEFAULT_CSS = """
    TargetTreeWidget {
        background: transparent;
        padding: 0;
        height: 1fr;
        color: $foreground;
        overflow-x: hidden;
        scrollbar-size-horizontal: 0;
    }
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__("Target Roster", **kwargs)
        self.show_root = False

    def populate(
        self,
        targets: List[Target],
        services: List[Service],
        selected_target_id: Optional[int] = None,
    ) -> None:
        # Preserve user's collapsed node state across refreshes
        collapsed_keys: set[tuple[str, Any]] = set()

        def _collect_collapsed(node: Any) -> None:
            for child in getattr(node, "children", []):
                if getattr(child, "data", None) and isinstance(child.data, dict):
                    ntype = child.data.get("type")
                    nkey = child.data.get("subnet") if ntype == "subnet" else child.data.get("id")
                    if ntype and nkey is not None and not child.is_expanded:
                        collapsed_keys.add((ntype, nkey))
                _collect_collapsed(child)

        try:
            _collect_collapsed(self.root)
        except Exception:
            pass

        self.clear()
        root = self.root

        svc_map: dict[int, list[Service]] = {}
        for s in services:
            svc_map.setdefault(s.target_id, []).append(s)

        P = current_palette()

        def _get_subnet(t: Target) -> str:
            if t.subnet:
                return t.subnet
            octets = t.ip.split(".")
            if len(octets) == 4 and all(o.isdigit() for o in octets):
                return f"{octets[0]}.{octets[1]}.{octets[2]}.0/24"
            return "General / External"

        subnets_set = {_get_subnet(t) for t in targets}
        use_subnet_groups = len(subnets_set) > 1 or any(t.is_pivot or t.subnet for t in targets)

        def _add_target_to_node(parent_node: Any, target: Target) -> None:
            target_svcs = svc_map.get(target.id or 0, [])
            icon = "✔" if target.root_flag else ("★" if target.initial_access_vuln or target.user_flag else "○")
            safe_ip = target.ip
            host = target.hostname or ""
            if len(host) > 10:
                host = host[:9] + "…"
            safe_host = f" ({host})" if host else ""
            pivot_badge = f" [bold {P.warn}]⇄ [PIVOT][/]" if target.is_pivot else ""
            label = f"{icon} [bold]{safe_ip}[/bold]{safe_host}{pivot_badge} [{P.muted}]({len(target_svcs)})[/]"
            if not target.is_in_scope:
                label = f"[{P.muted} strike]{label} ⃠[/]"

            target_node = parent_node.add(
                label,
                data={
                    "type": "target",
                    "id": target.id,
                    "target": target,
                    "is_pivot": target.is_pivot,
                    "pivot_route": target.pivot_route,
                },
            )

            for svc in target_svcs:
                svc_icon = "✓" if svc.status.value == "CHECKED" else ("✗" if svc.status.value == "DEAD-END" else "→")
                pot_badge = (
                    f" [bold {P.danger}][{svc.access_potential}][/]"
                    if svc.access_potential in ("HIGH", "CRITICAL")
                    else ""
                )
                port_text = f"{svc.port}/{svc.protocol}"
                svc_label = (
                    f"{svc_icon} [bold {P.accent}]{port_text:<9}[/]"
                    f" [bold {P.text}]{svc.service}[/]{pot_badge}"
                )
                target_node.add_leaf(
                    svc_label,
                    data={"type": "service", "id": svc.id, "target_id": target.id, "service": svc, "target": target},
                )

            if ("target", target.id) in collapsed_keys:
                target_node.collapse()
            else:
                target_node.expand()

        if use_subnet_groups:
            subnet_map: dict[str, list[Target]] = {}
            for t in targets:
                subnet_map.setdefault(_get_subnet(t), []).append(t)

            for snet, t_list in subnet_map.items():
                has_pivot = any(t.is_pivot for t in t_list)
                pivot_lbl = f" [bold {P.warn}]⇄ [PIVOT SEGMENT][/]" if has_pivot else ""
                snet_label = f"[bold {P.accent}]{snet}[/]{pivot_lbl} [{P.muted}]({len(t_list)} host{'s' if len(t_list) != 1 else ''})[/]"
                snet_node = root.add(
                    snet_label,
                    data={"type": "subnet", "subnet": snet, "has_pivot": has_pivot},
                )
                for t in t_list:
                    _add_target_to_node(snet_node, t)
                if ("subnet", snet) in collapsed_keys:
                    snet_node.collapse()
                else:
                    snet_node.expand()
        else:
            for target in targets:
                _add_target_to_node(root, target)


class WorksheetHeader(Static):
    """One-row chrome: identity on the left, live counters on the right."""

    DEFAULT_CSS = """
    WorksheetHeader {
        height: 1;
        background: $background;
        color: $text-muted;
        padding: 0 2;
    }
    """

    def __init__(
        self,
        workspace_name: str = "default",
        active_station: str = "Cockpit",
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.workspace_name = workspace_name
        self.active_station = active_station
        self.counts: dict[str, int] = {}
        self.active_ip: str = ""

    def update_status(
        self,
        workspace_name: str = "",
        counts: Optional[dict[str, int]] = None,
        active_ip: str = "",
        active_station: str = "",
    ) -> None:
        """Refresh the header meta information (workspace, counters, target, station)."""
        if workspace_name:
            self.workspace_name = workspace_name
        if counts is not None:
            self.counts = counts
        if active_ip:
            self.active_ip = active_ip
        if active_station:
            self.active_station = active_station
        self.refresh()

    def render(self) -> Text:
        P = current_palette()
        t = Text()
        t.append("CYB0X-S ", style=f"bold {P.accent}")
        t.append("WORKSHEET", style=f"bold {P.text_soft}")
        t.append("  ›  ", style=f"{P.muted}")
        t.append(f"[ {self.workspace_name} ]", style=f"bold {P.accent}")
        if self.active_station:
            t.append("  ›  ", style=f"{P.muted}")
            t.append(f"[ {self.active_station} ]", style=f"bold {P.text}")

        if not (self.counts or self.active_ip):
            return t

        counter_text = "  ".join(f"{k} {v}" for k, v in self.counts.items())
        candidates = [
            f"{counter_text}",
            f"▸ {self.active_ip}" if self.active_ip else "",
        ]
        width = max(self.size.width - 2, 1)
        for meta in candidates:
            if not meta:
                continue
            padding = width - len(t.plain) - len(meta)
            if padding > 1:
                t.append(" " * padding)
                t.append(meta, style=f"bold {P.muted}")
                break
        return t


class MachineStatusStrip(Static):
    """At-a-glance machine state.

    Row 1 — who am I attacking and what have I captured.
    Row 2 — what should I do next, and what is blocking me.

    This is the "exam speed" panel: everything here is answerable in one glance.
    """

    DEFAULT_CSS = """
    MachineStatusStrip {
        height: 3;
        background: $surface;
        border-bottom: solid $border;
        padding: 0 2;
    }
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.target: Optional[Target] = None
        self.counts: dict[str, int] = {}
        self.next_step: str = ""
        self.progress: tuple[int, int, int] = (0, 0, 0)  # done, total, percent
        self.blockers: int = 0

        # Exam clock: a persisted start (store setting) wins; otherwise the
        # session clock counts from app launch. Offline and passive either way.
        self.session_start = time.monotonic()
        self.exam_start: Optional[float] = None

    def on_mount(self) -> None:
        """Restore a persisted exam start time; tick the clock every second."""
        try:
            store = getattr(self.app, "store", None)
            if store is not None and hasattr(store, "get_setting"):
                raw = store.get_setting("exam_started_at")
                if raw:
                    self.exam_start = float(raw)
        except Exception:
            self.exam_start = None
        self.set_interval(1, self.refresh)

    def update_status(
        self,
        target: Optional[Target] = None,
        counts: Optional[dict[str, int]] = None,
        next_step: Optional[str] = None,
        progress: Optional[tuple[int, int, int]] = None,
        blockers: Optional[int] = None,
        checklist_total: Optional[int] = None,
        checklist_done: Optional[int] = None,
    ) -> None:
        if target is not None:
            self.target = target
        if counts is not None:
            self.counts = counts
        if next_step is not None:
            self.next_step = next_step
        if progress is not None:
            self.progress = progress
        if blockers is not None:
            self.blockers = blockers
        if checklist_total is not None and checklist_done is not None:
            pct = int(checklist_done / checklist_total * 100) if checklist_total else 0
            self.progress = (checklist_done, checklist_total, pct)
        self.refresh()

    @staticmethod
    def _elide(value: str, width: int) -> str:
        if width <= 1:
            return ""
        if len(value) <= width:
            return value
        return value[: max(width - 1, 1)] + "…"

    def _tag(self, label: str, value: str, colour: str, t: Text) -> None:
        t.append(f" {label} ", style=f"{current_palette().muted}")
        t.append(value, style=f"bold {colour}")
        t.append("  ", style="")

    @staticmethod
    def _progress_bar(pct: int, width: int, P: Any) -> Text:
        """A rising gradient bar — brighter where you are, dim where you began."""
        filled = int(round(width * pct / 100))
        shades = ramp(P.ok, filled, dim_towards=P.surface, floor=0.35) if filled else []
        empty = mix(P.border, P.surface, 0.55)

        bar = Text()
        for i in range(filled):
            bar.append("\u2588", style=f"bold {shades[i]}")
        if filled < width:
            bar.append("\u2591" * (width - filled), style=empty)
        return bar

    def render(self) -> Text:
        P = current_palette()
        t = Text()
        width = max(self.size.width - 4, 20) if self.size.width > 0 else 120

        # ---- row 1: identity + loot ------------------------------------
        row1 = Text()
        if self.target:
            row1.append("◈ ", style=f"bold {P.accent}")
            row1.append(f"{self.target.ip} ", style=f"bold {P.text}")
            if self.target.hostname:
                row1.append(f"[ {self.target.hostname} ] ", style=f"bold {P.accent}")
            if self.target.os and self.target.os != "Unknown":
                row1.append(f"({self.target.os}) ", style=f"{P.muted}")

            scope_ok = self.target.is_in_scope
            scope_badge = "IN-SCOPE" if scope_ok else "OUT-OF-SCOPE"
            row1.append(f"[{scope_badge}] ", style=f"bold {P.ok if scope_ok else P.danger}")

            if self.exam_start is not None:
                elapsed_s = int(time.time() - self.exam_start)
            else:
                elapsed_s = int(time.monotonic() - self.session_start)
            row1.append(f"T+{timedelta(seconds=elapsed_s)} ", style=f"bold {P.muted}")

            # Clean Status Badges for User and Root Flags
            if self.target.user_flag:
                row1.append("[USER: ✔] ", style=f"bold {P.ok}")
            else:
                row1.append("[USER: ◯] ", style=f"{P.muted}")

            if self.target.root_flag:
                row1.append("[ROOT: ✔] ", style=f"bold {P.ok}")
            else:
                row1.append("[ROOT: ◯] ", style=f"{P.muted}")

            if self.target.initial_access_vuln:
                row1.append(f"[{self._elide(self.target.initial_access_vuln, 16)}] ", style=f"bold {P.warn}")
        else:
            row1.append("◇ TARGET ▸ ", style=f"bold {P.warn}")
            row1.append("no target selected  ·  press 't' to add one", style=f"{P.muted}")

        # right-hand counters
        placed_counters_row1 = False
        counts_text = ""
        if self.counts:
            counts_text = "   ".join(f"{v} {k}" for k, v in self.counts.items())
            pad = width - len(row1.plain) - len(counts_text)
            if pad >= 4:
                row1.append(" " * pad)
                row1.append(counts_text, style=f"bold {P.muted}")
                placed_counters_row1 = True

        if self.size.height < 2:
            # Short terminal: return single identity line without newline.
            return Text(self._elide(row1.plain, width)) if len(row1.plain) > width else row1

        if len(row1.plain) > width:
            t.append(self._elide(row1.plain, width))
        else:
            t.append_text(row1)
        t.append("\n")

        # ---- row 2: next step + progress + blockers ---------------------
        done, total, pct = self.progress

        # Tail of row 2: progress bar + counts (if not on row 1) + blockers
        tail2 = Text()
        if total:
            tail2.append_text(self._progress_bar(pct, 10, P))
            tail2.append(f" {pct:>3d}% ({done}/{total})  ", style=f"{P.text_soft}")

        if not placed_counters_row1 and counts_text:
            tail2.append(counts_text + "   ", style=f"bold {P.muted}")

        blocker_text = f"🕳 {self.blockers} dead end" + ("s" if self.blockers != 1 else "") if self.blockers else "no blockers"
        tail2.append(blocker_text, style=f"bold {P.danger}" if self.blockers else f"{P.muted}")

        # Left side of row 2: TODO or CHECKLIST
        left2 = Text()
        avail_left = max(width - len(tail2.plain) - 4, 16)
        if self.next_step:
            left2.append("TODO ▸ ", style=f"bold {P.warn}")
            step_room = max(avail_left - 7, 8)
            left2.append(self._elide(self.next_step, step_room), style=f"bold {P.text}")
        elif total:
            left2.append("CHECKLIST ▸ ", style=f"bold {P.ok}")
            left2.append(self._elide("methodology complete", max(avail_left - 12, 8)), style=f"bold {P.ok}")
        else:
            left2.append("CHECKLIST ▸ ", style=f"bold {P.muted}")
            left2.append(self._elide("press 'm' to load a methodology template", max(avail_left - 12, 8)), style=f"{P.muted}")

        pad2 = width - len(left2.plain) - len(tail2.plain)
        row2 = Text()
        row2.append_text(left2)
        if pad2 > 0:
            row2.append(" " * pad2)
        else:
            row2.append(" ")
        row2.append_text(tail2)

        if len(row2.plain) > width:
            t.append(self._elide(row2.plain, width))
        else:
            t.append_text(row2)
        return t


class ConsoleBar(Container):
    """Full-width bottom console: the highlighted command, its tip, and input.

    Replaces the old 4-row guidance drawer: the command now gets the full
    terminal width, so nothing worth copying is ever clipped.
    """

    DEFAULT_CSS = """
    ConsoleBar {
        height: 5;
        border: solid $border;
        border-top: solid $accent;
        border-title-color: $text-soft;
        border-title-style: bold;
        border-subtitle-color: $accent;
        border-subtitle-align: right;
        background: $surface;
        padding: 0;
        margin: 0 1;
    }
    ConsoleBar:focus-within {
        border: solid $accent;
    }
    #console-cmd {
        height: 1;
        padding: 0 1;
        color: $foreground;
    }
    #console-tip {
        height: 1;
        padding: 0 1;
        color: $text-muted;
    }
    #console-input-row {
        height: 1;
        padding: 0 1;
        background: $surface-darken-1;
        layout: horizontal;
    }
    #console-prompt {
        width: auto;
        color: $accent;
        text-style: bold;
    }
    #cmd-input {
        width: 1fr;
        height: 1;
        border: none;
        background: transparent;
        color: $foreground;
        padding: 0;
    }
    #cmd-input:focus {
        border: none;
    }
    #console-hotkeys {
        width: auto;
        color: $text-muted;
        text-align: right;
    }
    """

    AUTOCOMPLETE_PREFIXES: Dict[str, str] = {
        ":t": ":t ",
        ":target": ":t ",
        ":s": ":s ",
        ":service": ":s ",
        ":c": ":c ",
        ":cred": ":c ",
        ":n": ":n ",
        ":note": ":n ",
        ":f": ":f ",
        ":finding": ":f ",
        ":th": ":theme ",
        ":theme": ":theme ",
        ":ref": ":ref ",
        ":cheat": ":ref ",
        ":u": ":uflag ",
        ":uflag": ":uflag ",
        ":r": ":rflag ",
        ":rflag": ":rflag ",
        ":foot": ":foothold ",
        ":foothold": ":foothold ",
        ":priv": ":privesc ",
        ":privesc": ":privesc ",
        ":st": ":stuck ",
        ":stuck": ":stuck ",
        ":cl": ":clue ",
        ":clue": ":clue ",
        ":ev": ":ev ",
        ":m": ":m ",
        ":meth": ":m ",
        ":pivot": ":pivot ",
        ":proof": ":q ",
        ":subnet": ":subnet ",
        ":export": ":export exam",
        ":w": ":w ",
        ":wordlist": ":w ",
        ":q": ":q",
    }

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.command: str = ""
        self.tip: str = ""
        self.heading: str = "CMD"
        self.recipes: List[Dict[str, str]] = []
        self.recipe_index: int = 0
        self.recipe_target_ip: str = ""
        self.active_station: str = "tab-worksheet"

    def _build_hotkey_text(self) -> Text:
        P = current_palette()
        t = Text()
        t.append(" [w]", style=f"bold {P.warn}")
        t.append(" panels ", style=f"{P.muted}")
        t.append(" [1-4]", style=f"bold {P.warn}")
        t.append(" stations ", style=f"{P.muted}")
        t.append(" [?]", style=f"bold {P.warn}")
        t.append(" help ", style=f"{P.muted}")
        t.append(" [q]", style=f"bold {P.warn}")
        t.append(" quit", style=f"{P.muted}")
        return t

    def set_active_station(self, station_id: str) -> None:
        """Inform console of the currently active station so idle tips stay contextual."""
        self.active_station = station_id
        if not self.command and not self.tip:
            self._paint()

    def on_mount(self) -> None:
        try:
            self._cmd_static = self.query_one("#console-cmd", Static)
            self._tip_static = self.query_one("#console-tip", Static)
            self._hotkeys_lbl = self.query_one("#console-hotkeys", Label)
        except Exception:
            self._cmd_static = None
            self._tip_static = None
            self._hotkeys_lbl = None
        # Paint the idle hint straight away so the console is never blank.
        self.call_after_refresh(self._paint)

    def compose(self) -> ComposeResult:
        yield Static(id="console-cmd")
        yield Static(id="console-tip")
        with Horizontal(id="console-input-row"):
            yield Label(" [ : ] ❯ ", id="console-prompt")
            yield Input(
                placeholder="Type command (:t, :s, :c, :m, :w) or note... (: for menu, Tab to complete)",
                id="cmd-input",
            )
            yield Label(self._build_hotkey_text(), id="console-hotkeys")

    def update_input_hint(self, val: str) -> None:
        """Dynamically display live syntax guidance as the user types."""
        v = val.strip()
        if not v:
            self._paint()
            return

        self.border_title = " COMMAND RUNNER "
        self.border_subtitle = " [Enter: Run] · [Esc: Cancel] "

        P = current_palette()
        inner = max(self.size.width - 4, 16)
        cmd_line = Text()
        tip_line = Text()

        cmd_line.append("RUN ▸ ", style=f"bold {P.accent}")

        if v == ":":
            cmd_line.append("[COMMAND MENU] ", style=f"bold {P.warn}")
            cmd_line.append(":t target  :s svc  :c cred  :m tmpl  :w wordlist  :n note  :f finding  :theme  :1-:4  ? help", style=f"bold {P.text}")
            tip_line.append("TIP ▸ ", style=f"bold {P.muted}")
            tip_line.append("Press Tab to autocomplete or type a command name", style=f"{P.muted}")
        elif v.startswith(":w") or v.startswith("wordlist "):
            cmd_line.append("[WORDLIST ALIAS] ", style=f"bold {P.warn}")
            cmd_line.append(":w <rockyou|common|medium|raft-d|users>", style=f"bold {P.text}")
            tip_line.append("TIP ▸ ", style=f"bold {P.muted}")
            tip_line.append("Copies standard SecLists/Kali wordlist path to clipboard", style=f"{P.muted}")
        elif v.startswith(":m") or v.startswith(":template") or v.startswith(":methodology"):
            cmd_line.append("[METHODOLOGY CHECKLIST] ", style=f"bold {P.warn}")
            cmd_line.append(":m <name> [append]", style=f"bold {P.text}")
            tip_line.append("TIP ▸ ", style=f"bold {P.muted}")
            tip_line.append("e.g. :m web, :m smb, :m pivoting, :m ejpt (press 'm' for modal picker)", style=f"{P.muted}")
        elif v.startswith(":t") or v.startswith("target ") or v.startswith("add target"):
            cmd_line.append("[ADD TARGET] ", style=f"bold {P.warn}")
            cmd_line.append(":t <ip> [hostname] [os]", style=f"bold {P.text}")
            tip_line.append("TIP ▸ ", style=f"bold {P.muted}")
            tip_line.append("e.g. :t 10.10.11.10 dc01.corp.local Linux", style=f"{P.muted}")
        elif v.startswith(":s") or v.startswith("service ") or v.startswith("add service"):
            cmd_line.append("[ADD SERVICE] ", style=f"bold {P.warn}")
            cmd_line.append(":s <port/proto> <service_name>", style=f"bold {P.text}")
            tip_line.append("TIP ▸ ", style=f"bold {P.muted}")
            tip_line.append("e.g. :s 80/tcp http   or   :s 445 smb   or   :s 22/tcp ssh", style=f"{P.muted}")
        elif v.startswith(":c") or v.startswith("cred ") or v.startswith("add cred"):
            cmd_line.append("[ADD CREDENTIAL] ", style=f"bold {P.warn}")
            cmd_line.append(":c <username:password> [scope]", style=f"bold {P.text}")
            tip_line.append("TIP ▸ ", style=f"bold {P.muted}")
            tip_line.append("e.g. :c admin:Secret123! SMB   or   :c root:toor SSH", style=f"{P.muted}")
        elif v.startswith(":n") or v.startswith("note ") or v.startswith("add note"):
            cmd_line.append("[FIELD NOTE] ", style=f"bold {P.warn}")
            cmd_line.append(":n <your note observation>", style=f"bold {P.text}")
            tip_line.append("TIP ▸ ", style=f"bold {P.muted}")
            tip_line.append("Saves instant note under NOTES & FINDINGS (press Enter to save)", style=f"{P.muted}")
        elif v.startswith(":f") or v.startswith("finding ") or v.startswith("add finding"):
            cmd_line.append("[FINDING / VULN] ", style=f"bold {P.warn}")
            cmd_line.append(":f <vulnerability title>", style=f"bold {P.text}")
            tip_line.append("TIP ▸ ", style=f"bold {P.muted}")
            tip_line.append("e.g. :f Anonymous SMB Share Access (press Enter to save)", style=f"{P.muted}")
        elif v.startswith(":th") or v.startswith("theme"):
            cmd_line.append("[THEME / PALETTE] ", style=f"bold {P.warn}")
            cmd_line.append(":theme <1-7 or slate|midnight|ember|cyber|sugary|candy|caramel>", style=f"bold {P.text}")
            tip_line.append("TIP ▸ ", style=f"bold {P.muted}")
            tip_line.append("e.g. :theme cyber, :theme 3 (ember), or :theme alone to cycle", style=f"{P.muted}")
        elif v.startswith(":u") or v.startswith(":flag user"):
            cmd_line.append("[USER FLAG] ", style=f"bold {P.warn}")
            cmd_line.append(":uflag <hash_string>", style=f"bold {P.text}")
            tip_line.append("TIP ▸ ", style=f"bold {P.muted}")
            tip_line.append("Records captured user.txt flag hash for active target", style=f"{P.muted}")
        elif v.startswith(":r") or v.startswith(":flag root"):
            cmd_line.append("[ROOT FLAG] ", style=f"bold {P.warn}")
            cmd_line.append(":rflag <hash_string>", style=f"bold {P.text}")
            tip_line.append("TIP ▸ ", style=f"bold {P.muted}")
            tip_line.append("Records captured root.txt / proof.txt flag hash", style=f"{P.muted}")
        elif v.startswith(":ref") or v.startswith(":cheat"):
            cmd_line.append("[CHEAT SHEET] ", style=f"bold {P.warn}")
            cmd_line.append(":ref <search term>", style=f"bold {P.text}")
            tip_line.append("TIP ▸ ", style=f"bold {P.muted}")
            tip_line.append("e.g. :ref winrm, :ref smb, :ref pivoting (opens reference modal)", style=f"{P.muted}")
        elif v.startswith(":foot"):
            cmd_line.append("[FOOTHOLD] ", style=f"bold {P.warn}")
            cmd_line.append(":foothold <initial access vulnerability>", style=f"bold {P.text}")
            tip_line.append("TIP ▸ ", style=f"bold {P.muted}")
            tip_line.append("e.g. :foothold Apache Struts S2-045 RCE", style=f"{P.muted}")
        elif v.startswith(":priv"):
            cmd_line.append("[PRIVESC] ", style=f"bold {P.warn}")
            cmd_line.append(":privesc <privilege escalation vector>", style=f"bold {P.text}")
            tip_line.append("TIP ▸ ", style=f"bold {P.muted}")
            tip_line.append("e.g. :privesc Sudo NOPASSWD /usr/bin/find GTFOBins", style=f"{P.muted}")
        elif v.startswith(":stuck") or v.startswith(":dead"):
            cmd_line.append("[RABBIT HOLE] ", style=f"bold {P.warn}")
            cmd_line.append(":stuck <where you spent time>", style=f"bold {P.text}")
            tip_line.append("TIP ▸ ", style=f"bold {P.muted}")
            tip_line.append("e.g. :stuck Brute-forcing SSH for 45m with wrong user", style=f"{P.muted}")
        elif v.startswith(":clue"):
            cmd_line.append("[BREAKTHROUGH] ", style=f"bold {P.warn}")
            cmd_line.append(":clue <breakthrough observation>", style=f"bold {P.text}")
            tip_line.append("TIP ▸ ", style=f"bold {P.muted}")
            tip_line.append("e.g. :clue Found cleartext password in db_backup.sql", style=f"{P.muted}")
        elif v in (":1", ":2", ":3", ":4"):
            cmd_line.append("[SWITCH STATION] ", style=f"bold {P.warn}")
            names = {":1": "Cockpit (Workbench)", ":2": "Playbooks & Checklists", ":3": "Credential Vault", ":4": "Loot & Flags"}
            cmd_line.append(f"Switching to {names.get(v, '')}", style=f"bold {P.text}")
            tip_line.append("TIP ▸ ", style=f"bold {P.muted}")
            tip_line.append("Press Enter to switch screen", style=f"{P.muted}")
        elif v in ("?", "help", ":help", ":?"):
            cmd_line.append("[HELP & SHORTCUTS] ", style=f"bold {P.warn}")
            cmd_line.append("Press Enter to open full help reference guide", style=f"bold {P.text}")
            tip_line.append("TIP ▸ ", style=f"bold {P.muted}")
            tip_line.append("Shows all keyboard shortcuts and interactive guide", style=f"{P.muted}")
        elif v.startswith(":q"):
            cmd_line.append("[QUIT] ", style=f"bold {P.warn}")
            cmd_line.append("Press Enter to exit CYB0X-S", style=f"bold {P.text}")
            tip_line.append("TIP ▸ ", style=f"bold {P.muted}")
            tip_line.append("Exits the application", style=f"{P.muted}")
        else:
            cmd_line.append("[RAW NOTE] ", style=f"bold {P.warn}")
            cmd_line.append(ConsoleBar._elide(v, inner - 14), style=f"bold {P.text}")
            tip_line.append("TIP ▸ ", style=f"bold {P.muted}")
            tip_line.append("Free-form note — press Enter to save to Notes & Findings", style=f"{P.muted}")

        try:
            self.query_one("#console-cmd", Static).update(cmd_line)
            self.query_one("#console-tip", Static).update(tip_line)
        except Exception:
            pass

    def on_key(self, event: Any) -> None:
        if event.key == "tab":
            inp = self.query_one("#cmd-input", Input)
            v = inp.value.strip()
            # Autocomplete prefix
            for prefix, completed in self.AUTOCOMPLETE_PREFIXES.items():
                if v and prefix.startswith(v) and len(v) < len(completed):
                    inp.value = completed
                    inp.cursor_position = len(completed)
                    event.stop()
                    self.update_input_hint(inp.value)
                    return
        elif event.key == "escape":
            inp = self.query_one("#cmd-input", Input)
            if inp.has_focus:
                inp.value = ""
                self.reset()
                event.stop()
                if hasattr(self.app, "action_focus_workbench"):
                    getattr(self.app, "action_focus_workbench")()
                return

    def show_copied_feedback(self, cmd: str) -> None:
        """Display an immediate inline copy confirmation in the console preview."""
        P = current_palette()
        self.border_title = " COMMAND COPIED "
        self.border_subtitle = " [COPIED TO CLIPBOARD] "
        line = Text()
        line.append("✔ COPIED ▸ ", style=f"bold {P.ok}")
        inner = max(self.size.width - 16, 20)
        line.append(self._elide(cmd, inner), style=f"bold {P.text}")
        try:
            self.query_one("#console-cmd", Static).update(line)
            self.set_class(True, "copied-flash")
            self.set_timer(1.8, lambda: [self.set_class(False, "copied-flash"), self._paint()])
        except Exception:
            pass

    # -- state ------------------------------------------------------------
    def show_command(self, command: str, tip: str, target_ip: str = "", heading: str = "CMD") -> None:
        self.command = substitute_command_placeholders(command or "", target_ip)
        self.tip = tip or ""
        self.heading = heading
        self._paint()

    def show_step(self, title: str, target_ip: str = "") -> None:
        """Show guidance for a checklist step from the static templates."""
        self.heading = "CMD"
        self.command = ""
        self.tip = ""
        guidance = get_template_guidance_for_title(title)
        if guidance:
            self.command = substitute_command_placeholders(guidance.get("command", ""), target_ip)
            self.tip = guidance.get("tip", "")
        elif title:
            self.heading = "STEP"
            self.tip = title
        self._paint()

    def update_guidance(self, item_title: str, target_ip: str = "") -> None:
        """Backwards-compatible entry point for checklist steps."""
        self.show_step(item_title, target_ip)

    def show_recipes(
        self, recipes: List[Dict[str, str]], index: int = 0, target_ip: str = ""
    ) -> None:
        """Display a specific recipe from a multi-recipe collection for a service."""
        if not recipes:
            self.reset()
            return
        self.recipes = recipes
        self.recipe_index = max(0, min(index, len(recipes) - 1))
        self.recipe_target_ip = target_ip
        r = self.recipes[self.recipe_index]
        cmd = r.get("command", "")
        tip = r.get("tip", "")
        count = len(recipes)
        heading = f"RECIPE {self.recipe_index + 1}/{count}" if count > 1 else "RECIPE"
        self.show_command(cmd, tip, target_ip=target_ip, heading=heading)

    def cycle_recipe(self, delta: int) -> Optional[str]:
        """Cycle recipe index by delta (+1 or -1) and return the newly active command."""
        if not hasattr(self, "recipes") or not self.recipes:
            return None
        self.recipe_index = (self.recipe_index + delta) % len(self.recipes)
        self.show_recipes(self.recipes, self.recipe_index, getattr(self, "recipe_target_ip", ""))
        return self.command

    def reset(self) -> None:
        self.command = ""
        self.tip = ""
        self.heading = "CMD"
        self.recipes = []
        self.recipe_index = 0
        self._paint()

    # -- painting ---------------------------------------------------------
    def _paint(self) -> None:
        P = current_palette()
        inner = max(self.size.width - 4, 16)
        cmd_line = Text()
        tip_line = Text()

        if self.command:
            if len(self.recipes) > 1:
                self.border_title = f" ACTION RECIPE ({self.recipe_index + 1}/{len(self.recipes)}) "
                self.border_subtitle = f" [Enter: Copy] · [. Next ({self.recipe_index + 1}/{len(self.recipes)})] "
            else:
                self.border_title = " ACTION RECIPE & LIVE GUIDANCE "
                self.border_subtitle = " [Enter: Copy] "

            cmd_line.append("RUN ▸ ", style=f"bold {P.accent}")
            cmd_line.append(ConsoleBar._elide(self.command, inner - 8), style=f"bold {P.text}")
        else:
            if self.active_station == "tab-playbooks":
                self.border_title = " STATION 2 · ATTACK PLAYBOOKS "
                self.border_subtitle = " [/ Search] · [Enter: Copy] "
                cmd_line.append("PLAYBOOKS ▸ ", style=f"bold {P.accent}")
                cmd_line.append("Browse attack recipes by service · [/] search · [Enter] copy command", style=f"bold {P.text}")
            elif self.active_station == "tab-creds":
                self.border_title = " STATION 3 · CREDENTIAL VAULT "
                self.border_subtitle = " [Space: Status] · [Enter: Spray] "
                cmd_line.append("CREDENTIALS ▸ ", style=f"bold {P.accent}")
                cmd_line.append("2D lateral movement matrix · [Space] cycle status · [Enter] copy spray cmd", style=f"bold {P.text}")
            elif self.active_station == "tab-loot":
                self.border_title = " STATION 4 · PROOFS & FLAGS "
                self.border_subtitle = " [g: Flags] · [a: Proofs] "
                cmd_line.append("PROOFS & FLAGS ▸ ", style=f"bold {P.accent}")
                cmd_line.append("Captured flags & question proofs · [g] flags · [a] proofs · :stuck dead-ends", style=f"bold {P.text}")
            else:
                self.border_title = " CONTEXT GUIDANCE "
                self.border_subtitle = " [w: Cycle Panels] · [1-4: Stations] "
                cmd_line.append("COCKPIT ▸ ", style=f"bold {P.accent}")
                cmd_line.append("Highlight a service or checklist step to preview & copy commands", style=f"bold {P.text}")

        if self.tip:
            tip_line.append("TIP ▸ ", style=f"bold {P.muted}")
            tip_line.append(ConsoleBar._elide(self.tip, inner - 8), style=f"{P.text_soft}")
        else:
            tip_line.append("STATUS ▸ ", style=f"bold {P.muted}")
            tip_line.append("Ready for command execution or target exploration", style=f"{P.muted}")

        try:
            if getattr(self, "_cmd_static", None) is not None and getattr(self, "_tip_static", None) is not None:
                self._cmd_static.update(cmd_line)
                self._tip_static.update(tip_line)
            else:
                self.query_one("#console-cmd", Static).update(cmd_line)
                self.query_one("#console-tip", Static).update(tip_line)

            if getattr(self, "_hotkeys_lbl", None) is not None:
                self._hotkeys_lbl.update(self._build_hotkey_text())
            else:
                self.query_one("#console-hotkeys", Label).update(self._build_hotkey_text())
        except Exception:
            pass

    @staticmethod
    def _elide(value: str, width: int) -> str:
        if width <= 1:
            return ""
        if len(value) <= width:
            return value
        return value[: max(width - 1, 1)] + "…"


class DataListItem(ListItem):
    """Custom ListItem wrapping a specific data model or placeholder."""

    def __init__(
        self,
        data_obj: Any,
        display_text: Text,
        is_placeholder: bool = False,
        *children: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__(*children, **kwargs)
        self.data_obj = data_obj
        self.display_text = display_text
        self.is_placeholder = is_placeholder

    def compose(self) -> ComposeResult:
        yield Label(self.display_text)

    def update_display(self, new_text: Text) -> None:
        """Update the label text in-place without rebuilding the ListItem or list."""
        self.display_text = new_text
        try:
            self.query_one(Label).update(new_text)
        except Exception:
            pass


_PROTOCOL_BADGE_CACHE: dict[tuple[int, str, str], Text] = {}
_STATUS_ICON_CACHE: dict[tuple[str, str], Text] = {}


def get_protocol_badge(port: int, protocol: str, theme_name: str = "") -> Text:
    """Return pre-styled Rich Text badge for port/protocol, cached across renders."""
    key = (port, protocol.lower(), theme_name)
    cached = _PROTOCOL_BADGE_CACHE.get(key)
    if cached is None:
        port_str = f"[{port}/{protocol}]"
        t = Text(f"{port_str:<11} ", style=S("accent"))
        _PROTOCOL_BADGE_CACHE[key] = t
        return t.copy()
    return cached.copy()


def get_service_status_icon(status_val: str, theme_name: str = "") -> Text:
    """Return pre-styled Rich Text status icon for service status, cached across renders."""
    key = (status_val, theme_name)
    cached = _STATUS_ICON_CACHE.get(key)
    if cached is None:
        if status_val == "CHECKED":
            t = Text("✓ ", style=S("ok"))
        elif status_val == "DEFERRED":
            t = Text("~ ", style=S("warn"))
        elif status_val == "DEAD-END":
            t = Text("✗ ", style=S("danger"))
        else:
            t = Text("→ ", style=S("accent"))
        _STATUS_ICON_CACHE[key] = t
        return t.copy()
    return cached.copy()


def clear_badge_caches() -> None:
    """Clear cached protocol badges and status icons on theme switch."""
    _PROTOCOL_BADGE_CACHE.clear()
    _STATUS_ICON_CACHE.clear()

# -------------------------------------------------------------------------
# Modal Dialogs & Screens (Extracted to modals.py for clean modularity)
# -------------------------------------------------------------------------

from cyb0x_s.tui.modals import (  # noqa: E402, F401
    AddCredentialModal,
    AddFindingModal,
    AddServiceModal,
    AddTargetModal,
    BaseFormModal,
    ConfirmModal,
    FastInputModal,
    HelpModal,
    ReferenceModal,
    SearchModal,
    TemplateSelectionModal,
    ThemePickerModal,
    ThemeSwatch,
)


class PlaybookBrowserWidget(Static):
    """Interactive full-screen playbook and command cheat sheet browser."""

    DEFAULT_CSS = """
    PlaybookBrowserWidget {
        height: 1fr;
        layout: vertical;
        padding: 0 1;
    }
    #playbook-top-bar {
        height: 3;
        layout: horizontal;
        margin-bottom: 1;
    }
    #playbook-search-input {
        width: 1fr;
        border: solid $border;
        background: $surface;
    }
    #playbook-body {
        height: 1fr;
        layout: horizontal;
    }
    #playbook-cat-panel {
        width: 25%;
        height: 1fr;
        border: solid $border;
        background: $surface;
        padding: 0 1;
        margin-right: 1;
    }
    #playbook-cmd-panel {
        width: 75%;
        height: 1fr;
        border: solid $border;
        background: $surface;
        padding: 0 1;
    }
    .panel-hdr {
        text-style: bold;
        color: $accent;
        padding: 0 1;
        height: 1;
    }
    """

    def __init__(self, target_ip: str = "", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.target_ip = target_ip
        self.selected_category = "ALL"
        self.search_query = ""
        self._debounce_timer: Any = None

    def compose(self) -> ComposeResult:
        with Horizontal(id="playbook-top-bar"):
            yield Input(placeholder="Search all commands: smb, winrm, mimikatz, pivot, privesc, sql, hydra...", id="playbook-search-input")
        with Horizontal(id="playbook-body"):
            with Vertical(id="playbook-cat-panel"):
                yield Label("CATEGORIES", classes="panel-hdr")
                yield ListView(id="playbook-cat-list")
            with Vertical(id="playbook-cmd-panel"):
                yield Label("READY-TO-PASTE COMMANDS", id="playbook-cmd-hdr", classes="panel-hdr")
                yield ListView(id="playbook-cmd-list")

    def on_mount(self) -> None:
        self._populate_categories()
        self._populate_commands()

    def update_target_ip(self, target_ip: str) -> None:
        if self.target_ip == target_ip:
            return
        self.target_ip = target_ip
        self._populate_commands()

    def _populate_categories(self) -> None:
        from cyb0x_s.reference import REFERENCE_PLAYBOOK

        cat_list = self.query_one("#playbook-cat-list", ListView)
        cat_list.clear()

        # Count per category
        counts: dict[str, int] = {}
        for item in REFERENCE_PLAYBOOK:
            c = item["category"]
            counts[c] = counts.get(c, 0) + 1

        all_txt = Text(f"★ ALL PLAYBOOKS ({len(REFERENCE_PLAYBOOK)})", style=S("accent"))
        cat_list.append(DataListItem(data_obj="ALL", display_text=all_txt))

        for cat, cnt in sorted(counts.items()):
            txt = Text(f"• {cat} ({cnt})", style=S("text"))
            cat_list.append(DataListItem(data_obj=cat, display_text=txt))

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "playbook-search-input":
            if self._debounce_timer is not None:
                self._debounce_timer.stop()
            self.search_query = event.value
            self._debounce_timer = self.set_timer(0.05, self._populate_commands)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "playbook-search-input":
            if self._debounce_timer is not None:
                self._debounce_timer.stop()
                self._debounce_timer = None
            self.search_query = event.value
            self._populate_commands()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.list_view.id == "playbook-cat-list" and isinstance(event.item, DataListItem):
            self.selected_category = str(event.item.data_obj)
            self._populate_commands()
        elif event.list_view.id == "playbook-cmd-list" and isinstance(event.item, DataListItem):
            if event.item.data_obj and not event.item.is_placeholder:
                cmd = str(event.item.data_obj)
                copy_to_clipboard(cmd)
                self.app.notify(f"Copied command: {cmd}")

    def _populate_commands(self) -> None:
        from cyb0x_s.reference import search_reference

        cmd_list = self.query_one("#playbook-cmd-list", ListView)
        cmd_list.clear()

        matches = search_reference(self.search_query, target_ip=self.target_ip)
        if self.selected_category != "ALL":
            matches = [m for m in matches if m["category"].lower() == self.selected_category.lower()]

        hdr = self.query_one("#playbook-cmd-hdr", Label)
        hdr.update(f"COMMAND REFERENCE: {self.selected_category} ({len(matches)} ready commands)")

        if matches:
            for item in matches:
                txt = Text()
                txt.append(f"[{item['category']}] ", style=S("warn"))
                txt.append(f"{item['title']}\n", style=S("text"))
                txt.append(f"  ❯ {item['command']}\n", style=S("warn"))
                txt.append(f"    ℹ {item['desc']}  [Press Enter to copy]", style="dim italic")
                cmd_list.append(DataListItem(data_obj=item["command"], display_text=txt))
        else:
            txt = Text("  • No matching commands found.", style="dim italic")
            cmd_list.append(DataListItem(data_obj=None, display_text=txt, is_placeholder=True))


class LootAndFlagsWidget(Static):
    """Dedicated status dashboard for Flags, Foothold proofs, and Failure Log."""

    DEFAULT_CSS = """
    LootAndFlagsWidget {
        height: 1fr;
        layout: vertical;
        padding: 0 1;
    }
    #loot-cards-container {
        height: 9;
        layout: horizontal;
        margin-bottom: 1;
    }
    .loot-box {
        width: 1fr;
        height: 9;
        border: solid $border;
        background: $surface;
        padding: 0 1;
        margin-right: 1;
    }
    #loot-lower-container {
        height: 1fr;
        layout: horizontal;
    }
    .loot-lower-box {
        width: 1fr;
        height: 1fr;
        border: solid $border;
        background: $surface;
        padding: 0 1;
        margin-right: 1;
    }
    .loot-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 0;
    }
    .loot-sub {
        height: 1;
        color: $text-muted;
        margin-bottom: 1;
    }
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.target: Optional[Target] = None

    def on_mount(self) -> None:
        """Ensure Loot & Flags data is populated as soon as the station is mounted."""
        if hasattr(self.app, "store"):
            try:
                active = self.app.store.get_active_target()
                failures = self.app.store.list_failure_logs(target_id=active.id if active else None)
                proofs = self.app.store.list_exam_proofs()
                self.update_data(active, failures, proofs=proofs)
            except Exception:
                pass

    def compose(self) -> ComposeResult:
        with Horizontal(id="loot-cards-container"):
            with Vertical(classes="loot-box"):
                yield Label("🏁 CAPTURED FLAGS", classes="loot-title")
                yield Static(id="loot-flags-content")
            with Vertical(classes="loot-box"):
                yield Label("⚡ INITIAL FOOTHOLD & EXPLOIT", classes="loot-title")
                yield Static(id="loot-foothold-content")
            with Vertical(classes="loot-box"):
                yield Label("👑 PRIVILEGE ESCALATION & ROOT PROOF", classes="loot-title")
                yield Static(id="loot-privesc-content")
        with Horizontal(id="loot-lower-container"):
            with Vertical(id="loot-evidence-box", classes="loot-lower-box"):
                yield Label("📝 QUESTION & EVIDENCE PROOFS", classes="loot-title")
                yield Label("Press 'a' or :q <num> <proof> • Enter=Copy • e=Export", classes="loot-sub")
                yield ListView(id="loot-evidence-list")
            with Vertical(id="loot-failure-box", classes="loot-lower-box"):
                yield Label("🧠 RABBIT HOLES & BREAKTHROUGHS", classes="loot-title")
                yield Label("Type :stuck <where> / :clue <breakthrough>", classes="loot-sub")
                yield ListView(id="loot-failure-list")

    def update_data(
        self,
        target: Optional[Target],
        failures: List[Any],
        proofs: Optional[List[Any]] = None,
    ) -> None:
        self.target = target
        P = current_palette()

        # Flags Card
        f_txt = Text()
        if target:
            f_txt.append("User Flag: ", style=S("accent"))
            f_txt.append(f"{target.user_flag or '<NOT CAPTURED YET>'}\n", style=S("ok") if target.user_flag else S("muted", bold=False))
            f_txt.append("Root Flag: ", style=S("warn"))
            f_txt.append(f"{target.root_flag or '<NOT CAPTURED YET>'}\n\n", style=S("ok") if target.root_flag else S("muted", bold=False))
            f_txt.append("[Press 'g' or type :uflag / :rflag to set flags]", style="dim italic")
        else:
            f_txt.append("No active target selected.\nPress 't' to add a target machine or switch with [ / ].", style="dim italic")
        self.query_one("#loot-flags-content", Static).update(f_txt)

        # Foothold Card
        fh_txt = Text()
        if target and (target.initial_access_vuln or target.foothold_cmd):
            fh_txt.append("Vulnerability: ", style=S("accent"))
            fh_txt.append(f"{target.initial_access_vuln or 'N/A'}\n", style=S("text"))
            fh_txt.append("Context: ", style=S("accent"))
            fh_txt.append(f"{target.foothold_context or 'N/A'}\n", style=S("text"))
            fh_txt.append(f"Command:\n❯ {target.foothold_cmd or 'N/A'}", style=S("warn"))
        else:
            fh_txt.append("No foothold recorded yet.\nType :foothold <vuln> or :foot <cmd> to record.", style="dim italic")
        self.query_one("#loot-foothold-content", Static).update(fh_txt)

        # PrivEsc Card
        pe_txt = Text()
        if target and (target.privesc_vector or target.root_proof):
            pe_txt.append("PrivEsc Vector: ", style=S("accent"))
            pe_txt.append(f"{target.privesc_vector or 'N/A'}\n", style=S("text"))
            pe_txt.append(f"Root Proof:\n❯ {target.root_proof or 'whoami && id && ip a'}", style=S("warn"))
        else:
            pe_txt.append("No PrivEsc recorded yet.\nType :privesc <vector> to record root proof.", style="dim italic")
        self.query_one("#loot-privesc-content", Static).update(pe_txt)

        # Question Proofs List
        p_list = self.query_one("#loot-evidence-list", ListView)
        p_list.clear()
        if proofs is None and hasattr(self.app, "store"):
            try:
                proofs = self.app.store.list_exam_proofs()
            except Exception:
                proofs = []
        if proofs:
            def sort_key(p: Any) -> tuple[int, str]:
                q = getattr(p, "question_num", "").lstrip("Qq")
                return (int(q) if q.isdigit() else 9999, getattr(p, "question_num", ""))

            for p in sorted(proofs, key=sort_key):
                txt = Text()
                txt.append(f"[{p.question_num}] ", style=f"bold {P.accent}")
                txt.append(f"[{p.category}] ", style=f"bold {P.warn}")
                txt.append(f"{p.answer_proof}\n", style=f"bold {P.ok}")
                if p.notes:
                    txt.append(f"   ℹ {p.notes}", style="dim italic")
                p_list.append(DataListItem(data_obj=p.answer_proof, display_text=txt))
        else:
            txt = Text("  • No question proofs recorded yet. Press 'a' or :q <num> <proof>", style="dim italic")
            p_list.append(DataListItem(data_obj=None, display_text=txt, is_placeholder=True))

        # Failure Log List
        f_list = self.query_one("#loot-failure-list", ListView)
        f_list.clear()
        if failures:
            for fl in failures:
                txt = Text()
                txt.append("🕳️ [DEAD-END] ", style=S("danger"))
                txt.append(f"{fl.where_stuck}\n", style=S("text"))
                if fl.breakthrough_clue:
                    txt.append(f"   🔑 Breakthrough Clue: {fl.breakthrough_clue}\n", style=S("ok"))
                if fl.rule_for_next_time:
                    txt.append(f"   📌 Permanent Rule: {fl.rule_for_next_time}", style="dim italic")
                f_list.append(DataListItem(data_obj=fl, display_text=txt))
        else:
            txt = Text("  • No rabbit holes or failure logs recorded. Type :stuck <where> / :clue <breakthrough>", style="dim italic")
            f_list.append(DataListItem(data_obj=None, display_text=txt, is_placeholder=True))

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.list_view.id == "loot-evidence-list" and isinstance(event.item, DataListItem):
            if event.item.data_obj and not event.item.is_placeholder:
                copy_to_clipboard(str(event.item.data_obj))
                if hasattr(self.app, "notify"):
                    self.app.notify(f"Copied proof: {event.item.data_obj}")

    def on_key(self, event: Any) -> None:
        if event.key == "a":
            self.action_add_proof()
            event.stop()
        elif event.key == "e":
            self.action_export_proofs()
            event.stop()

    def action_add_proof(self) -> None:
        from cyb0x_s.tui.modals import AddExamProofModal

        def on_proof_submitted(data: Optional[dict]) -> None:
            if data and hasattr(self.app, "store"):
                tgt_id = self.target.id if self.target else None
                self.app.store.add_exam_proof(
                    question_num=data["question_num"],
                    answer_proof=data["answer_proof"],
                    category=data["category"],
                    notes=data["notes"],
                    target_id=tgt_id,
                )
                if hasattr(self.app, "refresh_loot_widget"):
                    self.app.refresh_loot_widget()
                if hasattr(self.app, "notify"):
                    self.app.notify(f"Recorded {data['question_num']} proof!")

        tip = self.target.ip if self.target else ""
        self.app.push_screen(AddExamProofModal(target_ip=tip), callback=on_proof_submitted)

    def action_export_proofs(self) -> None:
        if hasattr(self.app, "store"):
            from pathlib import Path
            md = self.app.store.export_exam_evidence_markdown()
            out_file = Path("exam_evidence.md")
            out_file.write_text(md, encoding="utf-8")
            if hasattr(self.app, "notify"):
                self.app.notify(f"Exported exam evidence to {out_file.resolve()}")


AUTH_SERVICE_NAMES = {
    "ssh", "smb", "microsoft-ds", "netbios-ssn", "winrm", "wsman",
    "rdp", "ms-wbt-server", "mysql", "mssql", "ms-sql-s", "ftp",
    "http", "https", "web", "postgres", "postgresql", "vnc", "telnet"
}
AUTH_SERVICE_PORTS = {21, 22, 80, 443, 445, 1433, 3306, 3389, 5432, 5985, 5986, 8080}


def compile_spray_command(user: str, secret: str, service: str, ip: str, port: int) -> str:
    """Generate ready-to-run credential verification or lateral spray command."""
    s_low = service.strip().lower()
    clean_u = shlex.quote(user.strip())
    clean_p = shlex.quote(secret.strip())
    if s_low in ("smb", "microsoft-ds", "netbios-ssn") or port in (139, 445):
        return f"netexec smb {ip} -u {clean_u} -p {clean_p}"
    elif s_low == "ssh" or port == 22:
        return f"sshpass -p {clean_p} ssh -o StrictHostKeyChecking=no {clean_u}@{ip}"
    elif s_low in ("winrm", "wsman") or port in (5985, 5986):
        return f"evil-winrm -i {ip} -u {clean_u} -p {clean_p}"
    elif s_low in ("rdp", "ms-wbt-server") or port == 3389:
        return f"xfreerdp /u:{clean_u} /p:{clean_p} /v:{ip} /cert:ignore /smart-sizing"
    elif s_low in ("mssql", "ms-sql-s") or port == 1433:
        return f"netexec mssql {ip} -u {clean_u} -p {clean_p}"
    elif s_low in ("mysql",) or port == 3306:
        return f"mysql -h {ip} -u {clean_u} -p{clean_p}"
    elif s_low in ("ftp",) or port == 21:
        return f"hydra -l {clean_u} -p {clean_p} ftp://{ip}"
    elif s_low in ("http", "https", "web") or port in (80, 443, 8080):
        proto = "https" if port == 443 or "https" in s_low else "http"
        return f"curl -s -u {clean_u}:{clean_p} -I {proto}://{ip}:{port}/"
    return f"# Test credential {clean_u}:{clean_p} against {ip}:{port} ({service})"


class CredentialMatrixWidget(Static):
    """Interactive 2D matrix of discovered credentials, lateral movement targets, and verification states."""

    DEFAULT_CSS = """
    CredentialMatrixWidget {
        height: 1fr;
        layout: vertical;
        padding: 0 1;
    }
    #cred-matrix-hdr {
        height: 1;
    }
    #cred-matrix-sub {
        height: 1;
        color: $text-muted;
        padding: 0 1;
        margin-bottom: 1;
    }
    #cred-matrix-table {
        height: 1fr;
        border: solid $border;
        background: $surface;
    }
    #cred-matrix-table:focus {
        border: solid $accent;
    }
    #cred-matrix-empty {
        height: 1fr;
        border: solid $border;
        background: $surface;
        padding: 1 3;
        display: none;
    }
    """

    CELL_CYCLE = ["○ UNTESTED", "✔ VALID", "👑 PWN3D", "✗ INVALID"]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.credentials: List[Credential] = []
        self.auth_services: List[tuple[Target, Service]] = []
        self.revealed_ids: Set[int] = set()
        self.cell_states: Dict[tuple[int, int], str] = {}

    def on_mount(self) -> None:
        """Ensure Credential Matrix data is populated as soon as mounted."""
        if hasattr(self.app, "store"):
            try:
                creds = self.app.store.list_credentials()
                targets = self.app.store.list_targets()
                services = self.app.store.list_services()
                self.update_data(creds, targets, services, getattr(self.app, "revealed_creds", set()))
            except Exception:
                pass

    def compose(self) -> ComposeResult:
        yield Label(
            Text("CREDENTIAL VAULT & LATERAL MOVEMENT MATRIX"),
            id="cred-matrix-hdr",
            classes="panel-header",
        )
        yield Label("", id="cred-matrix-sub", classes="panel-subtitle")
        yield Static(id="cred-matrix-empty")
        table = DataTable(id="cred-matrix-table", cursor_type="cell")
        table.zebra_stripes = True
        yield table

    def _render_empty_guide(self) -> Text:
        P = current_palette()
        t = Text()
        t.append("\n")
        t.append("  🔑 CREDENTIAL SPRAY & LATERAL MOVEMENT MATRIX\n", style=f"bold {P.accent}")
        t.append("  ──────────────────────────────────────────────────────────────────────────────────────────\n", style=f"{P.border}")
        t.append("  This 2D matrix automatically maps discovered credentials against authenticating services\n", style=f"{P.text}")
        t.append("  across all in-scope target machines (SSH, SMB, RDP, WinRM, FTP, databases).\n\n", style=f"{P.text_soft}")
        t.append("  OPERATIONAL WORKFLOW:\n", style=f"bold {P.warn}")
        t.append("  1. Record Credentials:\n", style=f"bold {P.text}")
        t.append("     • Press 'c' to open credential modal, or type in bottom console:\n", style=f"{P.text_soft}")
        t.append("       :c <username:password> [scope]       e.g. :c admin:Summer2024! smb\n", style=f"bold {P.accent}")
        t.append("     • Secrets are masked by default (press [Space] to reveal/mask).\n\n", style=f"{P.muted}")
        t.append("  2. Map Target Services:\n", style=f"bold {P.text}")
        t.append("     • Discover open ports in Station 1 (:s 445 smb, :s 22 ssh, :s 3389 rdp).\n", style=f"{P.text_soft}")
        t.append("     • Every service accepting credentials becomes a matrix column.\n\n", style=f"{P.text_soft}")
        t.append("  3. Test & Track Lateral Movement:\n", style=f"bold {P.text}")
        t.append("     • Move between cells using Arrow keys or j / k / h / l.\n", style=f"{P.text_soft}")
        t.append("     • Press [Space] on any cell to cycle verification state:\n", style=f"{P.text_soft}")
        t.append("       ○ UNTESTED  →  ✔ VALID  →  👑 PWN3D  →  ✗ INVALID\n", style=f"bold {P.ok}")
        t.append("     • Press [Enter] on any cell to compile & copy ready-to-run spray command (netexec, hydra).\n\n", style=f"bold {P.accent}")
        t.append("  [Press 'c' now to record a credential, or press '1' to return to Cockpit]", style="dim italic")
        return t

    def update_data(
        self,
        credentials: List[Credential],
        targets: List[Target],
        services: List[Service],
        revealed_ids: Set[int],
    ) -> None:
        self.credentials = credentials
        self.revealed_ids = revealed_ids
        if hasattr(self.app, "store"):
            try:
                self.cell_states.update(self.app.store.get_cred_validations())
            except Exception:
                pass

        table = self.query_one("#cred-matrix-table", DataTable)
        table.clear(columns=True)

        empty_box = self.query_one("#cred-matrix-empty", Static)

        # Build in-scope authenticating service pairs
        in_scope_targets = {t.id: t for t in targets if t.is_in_scope}
        auth_pairs: List[tuple[Target, Service]] = []
        for s in services:
            t = in_scope_targets.get(s.target_id)
            if t and (s.service.lower() in AUTH_SERVICE_NAMES or s.port in AUTH_SERVICE_PORTS):
                auth_pairs.append((t, s))
        self.auth_services = auth_pairs

        # Summary subtitle
        tested = sum(1 for c in credentials if (c.status or "").lower() in ("valid", "tested"))
        subtitle = self.query_one("#cred-matrix-sub", Label)

        if not credentials:
            subtitle.update("No credentials recorded yet — press 'c' to add one or :c user:pass [scope]")
            empty_box.styles.display = "block"
            table.styles.display = "none"
            empty_box.update(self._render_empty_guide())
            return

        empty_box.styles.display = "none"
        table.styles.display = "block"

        if credentials:
            sub_text = Text()
            if auth_pairs:
                sub_text.append(f"{len(credentials)} credential(s) • {tested} validated • {len(auth_pairs)} spray target(s)   ")
            else:
                sub_text.append(f"{len(credentials)} credential(s) recorded • Add SSH/SMB/RDP in Cockpit to enable 2D spray columns   ")
            sub_text.append("[Space]", style=f"bold {current_palette().accent}")
            sub_text.append("=Cycle Status  ")
            sub_text.append("[Enter]", style=f"bold {current_palette().accent}")
            sub_text.append("=Copy Spray Cmd  ")
            sub_text.append("[c]", style=f"bold {current_palette().accent}")
            sub_text.append("=Add")
            subtitle.update(sub_text)

        # Setup Table Columns
        table.add_column("CREDENTIAL (USER : SECRET)", key="cred")
        if auth_pairs:
            for t, s in auth_pairs:
                col_title = f"{t.ip}:{s.port} ({s.service.upper()})"
                table.add_column(col_title, key=f"svc_{s.id}")
        else:
            table.add_column("SCOPE", key="scope")
            table.add_column("STATUS", key="status")
            table.add_column("SOURCE", key="source")
            table.add_column("LATERAL TARGETS", key="note")

        # Setup Table Rows
        for c in credentials:
            secret = c.secret if c.id in revealed_ids else c.masked_secret
            scope = f"[{c.service_scope.upper()}] " if c.service_scope else ""
            cred_str = f"{scope}{c.username} : {secret}"

            if auth_pairs:
                row_vals: List[Any] = [cred_str]
                for t, s in auth_pairs:
                    state = self.cell_states.get((c.id, s.id))
                    if not state:
                        if (c.service_scope or "").lower() in (s.service.lower(), "global") and (c.status or "").lower() in ("valid", "tested"):
                            state = "✔ VALID"
                        else:
                            state = "○ UNTESTED"
                        self.cell_states[(c.id, s.id)] = state
                    row_vals.append(self._format_state(state))
                table.add_row(*row_vals, key=f"cred_{c.id}")
            else:
                table.add_row(cred_str, c.service_scope or "GLOBAL", c.status.upper(), c.source or "-", "Add SSH/SMB/RDP in Cockpit to spray", key=f"cred_{c.id}")

    def _format_state(self, state: str) -> Text:
        P = current_palette()
        txt = Text()
        if "VALID" in state or "✔" in state:
            txt.append(state, style=f"bold {P.ok}")
        elif "PWN" in state or "👑" in state:
            txt.append(state, style=f"bold {P.accent}")
        elif "INVALID" in state or "✗" in state:
            txt.append(state, style=f"bold {P.danger}")
        else:
            txt.append(state, style=f"{P.muted}")
        return txt

    def on_key(self, event: Any) -> None:
        if event.key == "space":
            self.action_cycle_current_cell()
            event.stop()
        elif event.key == "enter":
            self.action_spray_current_cell()
            event.stop()

    def action_cycle_current_cell(self) -> None:
        """Cycle cell state between UNTESTED -> VALID -> PWN3D -> INVALID."""
        table = self.query_one("#cred-matrix-table", DataTable)
        coord = table.cursor_coordinate
        if not coord or coord.column <= 0 or not self.auth_services:
            return
        row_idx = coord.row
        col_idx = coord.column - 1
        if row_idx < 0 or row_idx >= len(self.credentials) or col_idx < 0 or col_idx >= len(self.auth_services):
            return
        c = self.credentials[row_idx]
        t, s = self.auth_services[col_idx]

        curr = self.cell_states.get((c.id, s.id), "○ UNTESTED")
        try:
            next_idx = (self.CELL_CYCLE.index(curr) + 1) % len(self.CELL_CYCLE)
        except ValueError:
            next_idx = 0
        new_state = self.CELL_CYCLE[next_idx]
        self.cell_states[(c.id, s.id)] = new_state
        table.update_cell_at(coord, self._format_state(new_state))
        if hasattr(self.app, "store") and c.id is not None and s.id is not None:
            try:
                self.app.store.set_cred_validation(c.id, s.id, new_state)
            except Exception:
                pass
        if hasattr(self.app, "notify"):
            self.app.notify(f"{c.username} on {t.ip}:{s.port} -> {new_state}")

    def action_spray_current_cell(self) -> None:
        """Generate and copy spray command for highlighted credential and service."""
        table = self.query_one("#cred-matrix-table", DataTable)
        coord = table.cursor_coordinate
        if not coord or coord.column <= 0 or not self.auth_services:
            return
        row_idx = coord.row
        col_idx = coord.column - 1
        if row_idx < 0 or row_idx >= len(self.credentials) or col_idx < 0 or col_idx >= len(self.auth_services):
            return
        c = self.credentials[row_idx]
        t, s = self.auth_services[col_idx]

        cmd = compile_spray_command(c.username, c.secret, s.service, t.ip, s.port)
        copy_to_clipboard(cmd)
        if hasattr(self.app, "notify"):
            self.app.notify(f"Copied spray command: {cmd}")




