"""Textual widgets and modal dialogs for CYB0X-S Worksheet."""

from __future__ import annotations

from typing import Any, Callable, List, Optional, Set
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, ListItem, ListView, Select, Static, Tree

from cyb0x_s.clipboard import copy_to_clipboard, extract_copy_value
from cyb0x_s.models import (
    ChecklistItem,
    ChecklistStatus,
    Credential,
    Evidence,
    Finding,
    Lead,
    Note,
    Service,
    Target,
)
from cyb0x_s.search import SearchMatch, search_notebook
from cyb0x_s.settings import derive_guidance_enabled
from cyb0x_s.templates import get_template_guidance_for_title
from cyb0x_s.tui.theme import (
    PALETTES,
    S,
    current_palette,
    get_default_theme,
    mix,
    ramp,
    save_default_theme,
)


def substitute_command_placeholders(command: str, target_ip: str = "") -> str:
    """Fill the static command templates with the active target context.

    Purely mechanical string substitution on human-curated reference text:
    no command is ever generated, inferred or suggested.
    """
    if not command or not target_ip:
        return command
    subnet = f"{target_ip.rsplit('.', 1)[0]}.0/24" if "." in target_ip else ""
    return command.replace("<TARGET_IP>", target_ip).replace("<TARGET_SUBNET>", subnet)


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
        super().__init__("Targets & Attack Surface", **kwargs)
        self.show_root = False

    def populate(
        self,
        targets: List[Target],
        services: List[Service],
        selected_target_id: Optional[int] = None,
    ) -> None:
        self.clear()
        root = self.root

        svc_map: dict[int, list[Service]] = {}
        for s in services:
            svc_map.setdefault(s.target_id, []).append(s)

        P = current_palette()
        for target in targets:
            target_svcs = svc_map.get(target.id or 0, [])
            icon = "✔" if target.root_flag else ("★" if target.initial_access_vuln or target.user_flag else "○")
            safe_ip = target.ip
            # Sidebar is narrow: keep hostnames short so IPs never scroll away.
            host = target.hostname or ""
            if len(host) > 12:
                host = host[:11] + "…"
            safe_host = f" ({host})" if host else ""
            label = f"{icon} [bold]{safe_ip}[/bold]{safe_host} [{P.muted}]({len(target_svcs)})[/]"
            if not target.is_in_scope:
                label = f"[{P.muted} strike]{label} ⃠[/]"

            target_node = root.add(label, data={"type": "target", "id": target.id, "target": target})

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

            target_node.expand()


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

    def __init__(self, workspace_name: str = "default", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.workspace_name = workspace_name
        self.counts: dict[str, int] = {}
        self.active_ip: str = ""

    def update_status(
        self,
        workspace_name: str = "",
        counts: Optional[dict[str, int]] = None,
        active_ip: str = "",
    ) -> None:
        """Refresh the header meta information (workspace, counters, target)."""
        if workspace_name:
            self.workspace_name = workspace_name
        if counts is not None:
            self.counts = counts
        self.active_ip = active_ip
        self.refresh()

    def render(self) -> Text:
        P = current_palette()
        t = Text()
        t.append("CYB0X-S ", style=f"bold {P.accent}")
        t.append("WORKSHEET", style=f"bold {P.text_soft}")
        t.append("  ›  ", style=f"{P.muted}")
        t.append(f"[ {self.workspace_name} ]", style=f"bold {P.accent}")

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
                break
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

    def update_status(
        self,
        target: Optional[Target] = None,
        counts: Optional[dict[str, int]] = None,
        next_step: Optional[str] = None,
        progress: Optional[tuple[int, int, int]] = None,
        blockers: Optional[int] = None,
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
        width = max(self.size.width - 4, 20)

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
            row1.append(f" [{scope_badge}] ", style=f"bold {P.ok if scope_ok else P.danger}")

            for label, value in (("🏁", self.target.user_flag), ("👑", self.target.root_flag)):
                row1.append(f" {label} ", style="")
                if value:
                    row1.append(self._elide(value, 12), style=f"bold {P.ok}")
                else:
                    row1.append("—", style=f"{P.muted}")

            if self.target.initial_access_vuln:
                row1.append("  ⚡ ", style="")
                row1.append(self._elide(self.target.initial_access_vuln, 18), style=f"bold {P.warn}")
        else:
            row1.append("◇ ", style=f"bold {P.warn}")
            row1.append("no target selected  ·  press 't' to add one", style=f"{P.muted}")

        # right-hand counters
        if self.counts:
            counts_text = "   ".join(f"{v} {k}" for k, v in self.counts.items())
            pad = width - len(row1.plain) - len(counts_text)
            if pad > 2:
                row1.append(" " * pad)
                row1.append(counts_text, style=f"bold {P.muted}")

        t.append_text(row1 if len(row1.plain) <= width else Text(self._elide(row1.plain, width)))
        t.append("\n")

        if self.size.height < 2:
            # Short terminal: keep only the identity row.
            return t

        # ---- row 2: next step + progress + blockers ---------------------
        row2 = Text()
        done, total, pct = self.progress
        if self.next_step:
            row2.append("NEXT ▸ ", style=f"bold {P.warn}")
            row2.append(f"{self.next_step} ", style=f"bold {P.text}")
        elif total:
            row2.append("NEXT ▸ ", style=f"bold {P.warn}")
            row2.append("methodology complete ", style=f"bold {P.ok}")
        else:
            row2.append("NEXT ▸ ", style=f"bold {P.warn}")
            row2.append("press 'm' to load a methodology template ", style=f"{P.muted}")

        if total:
            row2.append_text(self._progress_bar(pct, 12, P))
            row2.append(f" {pct:>3d}% ({done}/{total})", style=f"{P.text_soft}")

        tail = f"🕳 {self.blockers} dead end" + ("s" if self.blockers != 1 else "") if self.blockers else "no blockers"
        pad = width - len(row2.plain) - len(tail)
        if pad > 2:
            row2.append(" " * pad)
            row2.append(tail, style=f"bold {P.danger}" if self.blockers else f"{P.muted}")

        t.append_text(self._elide(row2.plain, width) if len(row2.plain) > width else row2)
        return t


class ConsoleBar(Container):
    """Full-width bottom console: the highlighted command, its tip, and input.

    Replaces the old 4-row guidance drawer: the command now gets the full
    terminal width, so nothing worth copying is ever clipped.
    """

    DEFAULT_CSS = """
    ConsoleBar {
        height: 5;
        border: round $border;
        background: $surface;
        padding: 0 1;
        margin: 0 1;
    }
    ConsoleBar:focus-within {
        border: round $accent;
    }
    #console-cmd {
        height: 1;
        color: $foreground;
    }
    #console-tip {
        height: 1;
        color: $text-muted;
    }
    #console-input-row {
        height: 1;
        layout: horizontal;
    }
    #console-prompt {
        width: 2;
        color: $accent;
        text-style: bold;
    }
    #cmd-input {
        width: 1fr;
        height: 1;
        border: none;
        background: transparent;
        color: $foreground;
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
        ":q": ":q",
    }

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.command: str = ""
        self.tip: str = ""
        self.heading: str = "CMD"

    def on_mount(self) -> None:
        # Paint the idle hint straight away so the console is never blank.
        self.call_after_refresh(self._paint)

    def compose(self) -> ComposeResult:
        yield Static(id="console-cmd")
        yield Static(id="console-tip")
        with Horizontal(id="console-input-row"):
            yield Label("❯", id="console-prompt")
            yield Input(
                placeholder="Type : for command menu (:t target, :s svc, :c cred, :theme, :1-4) or type any note...",
                id="cmd-input",
            )

    def update_input_hint(self, val: str) -> None:
        """Dynamically display live syntax guidance as the operator types."""
        v = val.strip()
        if not v:
            self._paint()
            return

        P = current_palette()
        inner = max(self.size.width - 4, 16)
        cmd_line = Text()
        tip_line = Text()

        cmd_line.append("❯ ", style=f"bold {P.accent}")

        if v == ":":
            cmd_line.append("[COMMAND MENU] ", style=f"bold {P.warn}")
            cmd_line.append(":t target  :s svc  :c cred  :m tmpl  :n note  :f finding  :theme  :1-:4  :ref  ? help", style=f"bold {P.text}")
            tip_line.append("Press Tab to autocomplete or type a command name", style=f"{P.muted}")
        elif v.startswith(":m") or v.startswith(":template") or v.startswith(":methodology"):
            cmd_line.append("[METHODOLOGY CHECKLIST] ", style=f"bold {P.warn}")
            cmd_line.append(":m <name> [append]", style=f"bold {P.text}")
            tip_line.append("e.g. :m web, :m smb, :m pivoting, :m ejpt (press 'm' for modal picker)", style=f"{P.muted}")
        elif v.startswith(":t") or v.startswith("target ") or v.startswith("add target"):
            cmd_line.append("[ADD TARGET] ", style=f"bold {P.warn}")
            cmd_line.append(":t <ip> [hostname] [os]", style=f"bold {P.text}")
            tip_line.append("e.g. :t 10.10.11.10 dc01.corp.local Linux", style=f"{P.muted}")
        elif v.startswith(":s") or v.startswith("service ") or v.startswith("add service"):
            cmd_line.append("[ADD SERVICE] ", style=f"bold {P.warn}")
            cmd_line.append(":s <port/proto> <service_name>", style=f"bold {P.text}")
            tip_line.append("e.g. :s 80/tcp http   or   :s 445 smb   or   :s 22/tcp ssh", style=f"{P.muted}")
        elif v.startswith(":c") or v.startswith("cred ") or v.startswith("add cred"):
            cmd_line.append("[ADD CREDENTIAL] ", style=f"bold {P.warn}")
            cmd_line.append(":c <username:password> [scope]", style=f"bold {P.text}")
            tip_line.append("e.g. :c admin:Secret123! SMB   or   :c root:toor SSH", style=f"{P.muted}")
        elif v.startswith(":n") or v.startswith("note ") or v.startswith("add note"):
            cmd_line.append("[FIELD NOTE] ", style=f"bold {P.warn}")
            cmd_line.append(":n <your note observation>", style=f"bold {P.text}")
            tip_line.append("Saves instant note under NOTES & FINDINGS (press Enter to save)", style=f"{P.muted}")
        elif v.startswith(":f") or v.startswith("finding ") or v.startswith("add finding"):
            cmd_line.append("[FINDING / VULN] ", style=f"bold {P.warn}")
            cmd_line.append(":f <vulnerability title>", style=f"bold {P.text}")
            tip_line.append("e.g. :f Anonymous SMB Share Access (press Enter to save)", style=f"{P.muted}")
        elif v.startswith(":th") or v.startswith("theme"):
            cmd_line.append("[THEME / PALETTE] ", style=f"bold {P.warn}")
            cmd_line.append(":theme <1-7 or slate|midnight|ember|moss|neon|mono|warm>", style=f"bold {P.text}")
            tip_line.append("e.g. :theme warm, :theme 3 (ember), or :theme alone to cycle", style=f"{P.muted}")
        elif v.startswith(":u") or v.startswith(":flag user"):
            cmd_line.append("[USER FLAG] ", style=f"bold {P.warn}")
            cmd_line.append(":uflag <hash_string>", style=f"bold {P.text}")
            tip_line.append("Records captured user.txt flag hash for active target", style=f"{P.muted}")
        elif v.startswith(":r") or v.startswith(":flag root"):
            cmd_line.append("[ROOT FLAG] ", style=f"bold {P.warn}")
            cmd_line.append(":rflag <hash_string>", style=f"bold {P.text}")
            tip_line.append("Records captured root.txt / proof.txt flag hash", style=f"{P.muted}")
        elif v.startswith(":ref") or v.startswith(":cheat"):
            cmd_line.append("[CHEAT SHEET] ", style=f"bold {P.warn}")
            cmd_line.append(":ref <search term>", style=f"bold {P.text}")
            tip_line.append("e.g. :ref winrm, :ref smb, :ref pivoting (opens reference modal)", style=f"{P.muted}")
        elif v.startswith(":foot"):
            cmd_line.append("[FOOTHOLD] ", style=f"bold {P.warn}")
            cmd_line.append(":foothold <initial access vulnerability>", style=f"bold {P.text}")
            tip_line.append("e.g. :foothold Apache Struts S2-045 RCE", style=f"{P.muted}")
        elif v.startswith(":priv"):
            cmd_line.append("[PRIVESC] ", style=f"bold {P.warn}")
            cmd_line.append(":privesc <privilege escalation vector>", style=f"bold {P.text}")
            tip_line.append("e.g. :privesc Sudo NOPASSWD /usr/bin/find GTFOBins", style=f"{P.muted}")
        elif v.startswith(":stuck") or v.startswith(":dead"):
            cmd_line.append("[RABBIT HOLE] ", style=f"bold {P.warn}")
            cmd_line.append(":stuck <where you spent time>", style=f"bold {P.text}")
            tip_line.append("e.g. :stuck Brute-forcing SSH for 45m with wrong user", style=f"{P.muted}")
        elif v.startswith(":clue"):
            cmd_line.append("[BREAKTHROUGH] ", style=f"bold {P.warn}")
            cmd_line.append(":clue <breakthrough observation>", style=f"bold {P.text}")
            tip_line.append("e.g. :clue Found cleartext password in db_backup.sql", style=f"{P.muted}")
        elif v in (":1", ":2", ":3", ":4"):
            cmd_line.append("[SWITCH STATION] ", style=f"bold {P.warn}")
            names = {":1": "Cockpit (Workbench)", ":2": "Playbooks & Checklists", ":3": "Credential Vault", ":4": "Loot & Flags"}
            cmd_line.append(f"Switching to {names.get(v, '')}", style=f"bold {P.text}")
            tip_line.append("Press Enter to switch screen", style=f"{P.muted}")
        elif v in ("?", "help", ":help", ":?"):
            cmd_line.append("[HELP & SHORTCUTS] ", style=f"bold {P.warn}")
            cmd_line.append("Press Enter to open full help reference guide", style=f"bold {P.text}")
            tip_line.append("Shows all keyboard shortcuts and interactive guide", style=f"{P.muted}")
        elif v.startswith(":q"):
            cmd_line.append("[QUIT] ", style=f"bold {P.warn}")
            cmd_line.append("Press Enter to exit CYB0X-S", style=f"bold {P.text}")
            tip_line.append("Exits the application", style=f"{P.muted}")
        else:
            cmd_line.append("[RAW NOTE] ", style=f"bold {P.warn}")
            cmd_line.append(ConsoleBar._elide(v, inner - 14), style=f"bold {P.text}")
            tip_line.append("📝 Free-form note — press Enter to save to Notes & Findings", style=f"{P.muted}")

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

    def reset(self) -> None:
        self.command = ""
        self.tip = ""
        self.heading = "CMD"
        self._paint()

    # -- painting ---------------------------------------------------------
    def _paint(self) -> None:
        P = current_palette()
        inner = max(self.size.width - 4, 16)
        cmd_line = Text()
        tip_line = Text()

        if self.command:
            cmd_line.append("❯ ", style=f"bold {P.accent}")
            room = inner - 2 - len(f"[{self.heading}] ") - 2
            cmd_line.append(f"[{self.heading}] ", style=f"bold {P.warn}")
            cmd_line.append(ConsoleBar._elide(self.command, room), style=f"bold {P.text}")
            hint = "[Enter]=copy"
            pad = inner - len(cmd_line.plain) - len(hint)
            if pad > 1:
                cmd_line.append(" " * pad)
                cmd_line.append(hint, style=f"bold {P.accent}")
        else:
            cmd_line.append("❯ ", style=f"bold {P.accent}")
            cmd_line.append(
                ConsoleBar._elide(
                    "highlight a service or checklist step to see its command", inner - 2
                ),
                style=f"{P.muted}",
            )

        if self.tip:
            tip_line.append(ConsoleBar._elide(self.tip, inner), style=f"{P.muted}")

        try:
            self.query_one("#console-cmd", Static).update(cmd_line)
            self.query_one("#console-tip", Static).update(tip_line)
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


class ConfirmModal(ModalScreen[bool]):
    """Small yes/no guard for destructive actions (delete, quit, ...)."""

    DEFAULT_CSS = """
    ConfirmModal {
        align: center middle;
    }
    #confirm-box {
        width: 60;
        height: auto;
        border: round $error;
        background: $surface;
        padding: 1 2;
        color: $foreground;
    }
    #confirm-message {
        height: auto;
        margin-bottom: 1;
    }
    """

    def __init__(self, title: str, message: str, confirm_label: str = "Delete") -> None:
        super().__init__()
        self.modal_title = title
        self.message = message
        self.confirm_label = confirm_label

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-box"):
            yield Label(f"▸ {self.modal_title}", classes="modal-header")
            yield Label(self.message, id="confirm-message")
            with Horizontal(classes="modal-buttons"):
                yield Button(
                    f"{self.confirm_label} (y)", variant="error", classes="danger-btn", id="btn-confirm"
                )
                yield Button("Cancel (Esc)", id="btn-cancel")

    def on_mount(self) -> None:
        self.query_one("#btn-cancel", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "btn-confirm")

    def on_key(self, event: Any) -> None:
        if event.key in ("escape", "n", "N"):
            self.dismiss(False)
        elif event.key in ("y", "Y", "enter"):
            self.dismiss(True)


class ThemeSwatch(Static):
    """One row in the theme picker: colour strip, name, vibe, contrast, and default badge."""

    DEFAULT_CSS = """
    ThemeSwatch {
        height: 3;
        padding: 0 1;
    }
    ThemeSwatch.selected {
        background: $surface-lighten-1;
    }
    """

    def __init__(
        self,
        palette_name: str,
        palette_label: str,
        index: int = 1,
        default_name: str = "slate",
    ) -> None:
        super().__init__(id=f"theme-{palette_name}")
        self.palette_name = palette_name
        self.palette_label = palette_label
        self.index = index
        self.default_name = default_name

    def render(self) -> Text:
        palette = PALETTES[self.palette_name]
        is_active = current_palette().name == palette.name
        is_default = self.palette_name == self.default_name

        out = Text()
        out.append(f"[{self.index}] ", style=f"bold {palette.accent}")
        if is_active:
            out.append("● ", style=f"bold {palette.accent}")
        else:
            out.append("○ ", style=palette.muted)

        # colour strip — the palette's own hues
        for _label, colour in palette.swatch():
            out.append("██", style=f"on {colour}")

        desc = palette.label.split("·", 1)[-1].strip()
        out.append("  ")
        out.append(f"{palette.name:<9}", style=f"bold {palette.text}")
        out.append(f"{desc:<18}", style=palette.text_soft)

        ratio = palette.contrast_ratio()
        grade = "AAA" if ratio >= 7 else ("AA" if ratio >= 4.5 else "low")
        out.append(f" {ratio:4.1f}:1 {grade:<3}", style=palette.ok if ratio >= 7 else palette.warn)

        if is_default:
            out.append(" ★ DEFAULT", style=f"bold {palette.warn}")
        elif is_active:
            out.append(" ● active", style=f"bold {palette.accent}")
        return out


class ThemePickerModal(ModalScreen[Optional[str]]):
    """Interactive palette picker with live preview and default persistence."""

    DEFAULT_CSS = """
    ThemePickerModal {
        align: center middle;
        background: rgba(6, 9, 12, 0.72);
    }

    #theme-picker-box {
        width: 88;
        height: auto;
        max-height: 90%;
        border: round $accent;
        background: $surface;
        padding: 1 2;
    }

    #theme-picker-title {
        width: 100%;
        padding: 0 0 1 0;
        color: $accent;
        text-style: bold;
    }

    #theme-picker-list {
        height: auto;
        max-height: 24;
        background: transparent;
        border: none;
    }

    #theme-picker-list > ListItem {
        padding: 0;
        background: transparent;
    }

    #theme-picker-list > ListItem.-selected {
        background: $surface-lighten-1;
    }

    #theme-picker-list > ListItem:hover {
        background: $surface-lighten-1;
    }

    #theme-picker-buttons {
        height: 3;
        margin-top: 1;
        layout: horizontal;
        align: right middle;
    }

    #theme-picker-buttons Button {
        margin-left: 1;
    }

    #theme-picker-hint {
        width: 100%;
        padding: 1 0 0 0;
        color: $text-soft;
    }
    """

    def __init__(self, current: str, store: Any = None) -> None:
        super().__init__()
        self.original = current
        self.store = store
        self.default_theme = get_default_theme(store)

    def compose(self) -> ComposeResult:
        with Vertical(id="theme-picker-box"):
            yield Label(
                "◈  COLOR THEMES — ↑↓/j/k Preview  •  Enter Apply  •  d Set Default",
                id="theme-picker-title",
            )
            yield ListView(
                *[
                    ListItem(
                        ThemeSwatch(
                            name,
                            palette.label,
                            index=i + 1,
                            default_name=self.default_theme,
                        )
                    )
                    for i, (name, palette) in enumerate(PALETTES.items())
                ],
                id="theme-picker-list",
            )
            with Horizontal(id="theme-picker-buttons"):
                yield Button("Set as Default (d)", variant="warning", id="btn-set-default")
                yield Button("Glass Canvas (g)", id="btn-toggle-glass")
                yield Button("Apply (Enter)", variant="primary", classes="primary-btn", id="btn-apply")
                yield Button("Cancel (Esc)", id="btn-cancel")
            yield Label(
                "↑↓/j/k: live preview   1-8: pick   g: glass/transparency   d: save default   Enter: apply   Esc: cancel",
                id="theme-picker-hint",
            )

    def on_mount(self) -> None:
        names = list(PALETTES)
        index = names.index(self.original) if self.original in names else 0
        list_view = self.query_one("#theme-picker-list", ListView)
        list_view.index = index
        list_view.focus()

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        """Live preview: apply the palette the cursor is sitting on."""
        for row in self.query(ThemeSwatch):
            row.set_class(row.palette_name == current_palette().name, "selected")
        if event.item is None:
            return
        rows = event.item.query(ThemeSwatch)
        if not rows:
            return
        name = rows[0].palette_name
        if name != current_palette().name:
            self.app.apply_theme(name, quiet=True)  # type: ignore[attr-defined]

    def _selected_theme_name(self) -> str:
        list_view = self.query_one("#theme-picker-list", ListView)
        item = list_view.highlighted_child
        if item is not None:
            rows = item.query(ThemeSwatch)
            if rows:
                return rows[0].palette_name
        return current_palette().name

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-set-default":
            chosen = self._selected_theme_name()
            if hasattr(self.app, "set_default_theme"):
                self.app.set_default_theme(chosen)
            else:
                save_default_theme(chosen, self.store)
                self.app.apply_theme(chosen)  # type: ignore[attr-defined]
            self.dismiss(chosen)
        elif event.button.id == "btn-toggle-glass":
            if hasattr(self.app, "toggle_transparency"):
                is_trans = self.app.toggle_transparency(persist=True)
                mode = "ON (Glass)" if is_trans else "OFF (Solid)"
                self.app.notify(f"Canvas Transparency: {mode}", timeout=3)
        elif event.button.id == "btn-apply":
            chosen = self._selected_theme_name()
            self.app.apply_theme(chosen)  # type: ignore[attr-defined]
            self.dismiss(chosen)
        elif event.button.id == "btn-cancel":
            self.app.apply_theme(self.original)  # type: ignore[attr-defined]
            self.dismiss(self.original)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Click or Enter on list item selects and keeps it."""
        if event.item is not None:
            rows = event.item.query(ThemeSwatch)
            if rows:
                chosen = rows[0].palette_name
                self.app.apply_theme(chosen)  # type: ignore[attr-defined]
                self.dismiss(chosen)

    def on_key(self, event: Any) -> None:
        names = list(PALETTES)
        if event.key in "12345678":
            event.stop()
            idx = int(event.key) - 1
            if 0 <= idx < len(names):
                chosen = names[idx]
                self.app.apply_theme(chosen)  # type: ignore[attr-defined]
                self.dismiss(chosen)
            return
        if event.key in ("g", "G"):
            event.stop()
            if hasattr(self.app, "toggle_transparency"):
                is_trans = self.app.toggle_transparency(persist=True)
                mode = "ON (Glass)" if is_trans else "OFF (Solid)"
                self.app.notify(f"Canvas Transparency: {mode}", timeout=3)
            return
        if event.key in ("d", "D", "s"):
            event.stop()
            chosen = self._selected_theme_name()
            if hasattr(self.app, "set_default_theme"):
                self.app.set_default_theme(chosen)
            else:
                save_default_theme(chosen, self.store)
                self.app.apply_theme(chosen)  # type: ignore[attr-defined]
            self.dismiss(chosen)
            return
        if event.key == "escape":
            event.stop()
            self.app.apply_theme(self.original)  # type: ignore[attr-defined]
            self.dismiss(self.original)
        elif event.key == "enter":
            event.stop()
            chosen = self._selected_theme_name()
            self.app.apply_theme(chosen)  # type: ignore[attr-defined]
            self.dismiss(chosen)


class SearchModal(ModalScreen):
    """Interactive global search modal (Ctrl+F or /)."""

    DEFAULT_CSS = """
    SearchModal {
        align: center middle;
    }
    #search-box {
        width: 80%;
        height: 80%;
        border: round $accent;
        background: $surface;
        padding: 1 2;
    }
    #search-input {
        margin-bottom: 1;
    }
    #search-results {
        height: 1fr;
        border: solid $surface-lighten-1;
        background: $background;
    }
    #search-status {
        height: 1;
        margin-top: 1;
        color: $text-muted;
    }
    """

    def __init__(self, store: Any, on_select: Optional[Callable[[SearchMatch], None]] = None) -> None:
        super().__init__()
        self.store = store
        self.on_select = on_select
        self.matches: List[SearchMatch] = []

    def compose(self) -> ComposeResult:
        with Vertical(id="search-box"):
            yield Label(
                f"[bold {current_palette().accent}]SEARCH WORKSHEET[/]"
                f" [{current_palette().muted}](↑↓ / j·k move, Enter copy & close, y copy, Esc close)[/]"
            )
            yield Input(placeholder="Type keywords to search across notes, services, creds, findings...", id="search-input")
            yield ListView(id="search-results")
            yield Label("0 results", id="search-status")

    def on_mount(self) -> None:
        self.query_one("#search-input", Input).focus()

    def _selected_match(self) -> Optional[SearchMatch]:
        results_view = self.query_one("#search-results", ListView)
        child = results_view.highlighted_child
        if isinstance(child, DataListItem) and not child.is_placeholder and child.data_obj:
            return child.data_obj  # type: ignore[return-value]
        return None

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Enter / click on a result copies it and closes the dialog."""
        match = self._selected_match()
        if match is not None:
            self._copy(match)
            self.dismiss(match)

    def _copy(self, match: SearchMatch) -> None:
        val = match.title or match.snippet
        copy_to_clipboard(val)
        self.notify(f"Copied: {val}")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Enter while typing copies the top hit — the fastest capture path."""
        event.stop()
        match = self._selected_match() or (self.matches[0] if self.matches else None)
        if match is not None:
            self._copy(match)
            self.dismiss(match)
        else:
            self.query_one("#search-results", ListView).focus()

    def on_key(self, event: Any) -> None:
        if event.key == "escape":
            self.dismiss(None)
            return
        if isinstance(self.focused, Input):
            return
        if event.key in ("j", "down"):
            self.query_one("#search-results", ListView).action_cursor_down()
            event.stop()
        elif event.key in ("k", "up"):
            self.query_one("#search-results", ListView).action_cursor_up()
            event.stop()
        elif event.key == "y":
            match = self._selected_match()
            if match is not None:
                self._copy(match)

    def on_input_changed(self, event: Input.Changed) -> None:
        query = event.value.strip()
        results_view = self.query_one("#search-results", ListView)
        status_label = self.query_one("#search-status", Label)
        results_view.clear()

        if not query:
            status_label.update("0 results")
            self.matches = []
            return

        self.matches = search_notebook(self.store, query)
        status_label.update(f"{len(self.matches)} results found")

        for m in self.matches:
            txt = Text()
            txt.append(f"[{m.entity_type.upper()}] ", style=S("accent"))
            if m.target_ip:
                txt.append(f"{m.target_ip} ", style=S("warn"))
            txt.append(f"{m.title} — ", style=S("text"))
            txt.append(m.snippet, style=S("muted", bold=False))
            results_view.append(DataListItem(data_obj=m, display_text=txt))


class AddTargetModal(ModalScreen[Optional[dict]]):
    """Fast modal for creating a target host with OS dropdown and preset ports."""

    DEFAULT_CSS = """
    AddTargetModal {
        align: center middle;
    }
    #add-target-container {
        width: 74;
        height: auto;
        max-height: 92%;
        border: round $accent;
        background: $surface;
        padding: 1 2;
        color: $foreground;
    }
    AddTargetModal .modal-row {
        height: auto;
        layout: horizontal;
        margin-bottom: 0;
    }
    AddTargetModal .modal-col {
        width: 1fr;
        height: auto;
        margin-right: 1;
    }
    AddTargetModal .modal-col:last-child {
        margin-right: 0;
    }
    AddTargetModal Input {
        height: 3;
        border: round $border;
        background: $background;
        color: $foreground;
        padding: 0 1;
    }
    AddTargetModal Input:focus {
        border: round $accent;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="add-target-container", classes="synapse-modal-dialog"):
            yield Label("▸ ADD TARGET HOST", classes="modal-header")

            with Horizontal(classes="modal-row"):
                with Vertical(classes="modal-col"):
                    yield Label("Target IP / Hostname *:", classes="field-label")
                    yield Input(placeholder="e.g. 10.10.11.10", id="target-ip")
                with Vertical(classes="modal-col"):
                    yield Label("FQDN / NetBIOS (optional):", classes="field-label")
                    yield Input(placeholder="e.g. dc01.corp.local", id="target-host")

            with Horizontal(classes="modal-row"):
                with Vertical(classes="modal-col"):
                    yield Label("Operating System:", classes="field-label")
                    yield Select(
                        [
                            ("Linux (Debian / Kali / Ubuntu)", "Linux"),
                            ("Windows Server / Active Directory", "Windows Server"),
                            ("Windows Workstation", "Windows"),
                            ("FreeBSD / Unix", "FreeBSD"),
                            ("Embedded / Network Device", "Embedded"),
                            ("Unknown / Other", "Unknown"),
                        ],
                        value="Linux",
                        id="target-os",
                    )
                with Vertical(classes="modal-col"):
                    yield Label("Initial Ports Preset:", classes="field-label")
                    yield Select(
                        [
                            ("None / Custom", ""),
                            ("Web Standard (80, 443)", "80,443"),
                            ("Web & SSH (22, 80, 443, 8080)", "22,80,443,8080"),
                            ("Active Directory (53, 88, 135, 389, 445)", "53,88,135,389,445"),
                            ("Top Common (21,22,25,80,443,445,3389)", "21,22,25,80,443,445,3389"),
                        ],
                        value="",
                        id="target-ports-preset",
                    )

            with Horizontal(classes="modal-row"):
                with Vertical(classes="modal-col"):
                    yield Label("Custom Ports (optional):", classes="field-label")
                    yield Input(placeholder="e.g. 22, 80, 445", id="target-ports-custom")
                with Vertical(classes="modal-col"):
                    yield Label("Target Notes (optional):", classes="field-label")
                    yield Input(placeholder="e.g. In-scope lab machine", id="target-notes")

            with Horizontal(classes="modal-buttons"):
                yield Button("Save Target (Enter)", variant="primary", classes="primary-btn", id="btn-save")
                yield Button("Cancel (Esc)", id="btn-cancel")

    def on_mount(self) -> None:
        self.query_one("#target-ip", Input).focus()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "target-ports-preset" and event.value:
            curr = self.query_one("#target-ports-custom", Input)
            if not curr.value:
                curr.value = str(event.value)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-save":
            self.submit_data()
        else:
            self.dismiss(None)

    def on_key(self, event: Any) -> None:
        if event.key == "escape":
            self.dismiss(None)
        elif event.key == "enter" and not isinstance(self.focused, Select):
            self.submit_data()

    def submit_data(self) -> None:
        ip_val = self.query_one("#target-ip", Input).value.strip()
        if not ip_val:
            return
        host_val = self.query_one("#target-host", Input).value.strip()
        os_val = str(self.query_one("#target-os", Select).value or "Linux")
        ports_preset = str(self.query_one("#target-ports-preset", Select).value or "")
        ports_custom = self.query_one("#target-ports-custom", Input).value.strip()
        notes_val = self.query_one("#target-notes", Input).value.strip()

        ports_raw = ports_custom or ports_preset
        ports = []
        if ports_raw:
            for p in ports_raw.split(","):
                p = p.strip()
                if p.isdigit() and 1 <= int(p) <= 65535:
                    ports.append(int(p))

        self.dismiss({
            "ip": ip_val,
            "hostname": host_val,
            "os": os_val,
            "ports": ports,
            "notes": notes_val,
        })


class AddServiceModal(ModalScreen[Optional[dict]]):
    """Fast service creation dialog with auto-filling presets and access potential."""

    DEFAULT_CSS = """
    AddServiceModal {
        align: center middle;
    }
    #add-service-container {
        width: 72;
        height: auto;
        max-height: 92%;
        border: round $accent;
        background: $surface;
        padding: 1 2;
        color: $foreground;
    }
    AddServiceModal Input {
        height: 3;
        border: round $border;
        background: $background;
        color: $foreground;
        padding: 0 1;
    }
    AddServiceModal Input:focus {
        border: round $accent;
    }
    """

    SERVICE_PRESETS = [
        ("Custom / Manual Entry", "custom"),
        ("21 / FTP (Anonymous / vsftpd)", "21/tcp/ftp/HIGH/ftp <TARGET_IP>"),
        ("22 / SSH (OpenSSH / Brute-force)", "22/tcp/ssh/MED/hydra -l user -P rockyou.txt ssh://<TARGET_IP>"),
        ("23 / Telnet (Unencrypted CLI)", "23/tcp/telnet/HIGH/telnet <TARGET_IP>"),
        ("25 / SMTP (User Enum / VRFY)", "25/tcp/smtp/MED/smtp-user-enum -M VRFY -U users.txt -t <TARGET_IP>"),
        ("53 / DNS (Zone Transfer / axfr)", "53/tcp/domain/MED/dig axfr @<TARGET_IP> <DOMAIN>"),
        ("80 / HTTP (Web / Directory Busting)", "80/tcp/http/HIGH/feroxbuster -u http://<TARGET_IP>/ -w /usr/share/wordlists/dirb/common.txt"),
        ("88 / Kerberos (Active Directory)", "88/tcp/kerberos/HIGH/GetNPUsers.py <DOMAIN>/ -no-pass -usersfile users.txt"),
        ("110 / POP3 (Mail Server)", "110/tcp/pop3/MED/nc -vn <TARGET_IP> 110"),
        ("139 / NetBIOS (Session)", "139/tcp/netbios-ssn/MED/nbtscan <TARGET_IP>"),
        ("389 / LDAP (Active Directory)", "389/tcp/ldap/HIGH/ldapsearch -x -H ldap://<TARGET_IP> -b 'DC=corp,DC=local'"),
        ("443 / HTTPS (SSL Web Server)", "443/tcp/https/HIGH/feroxbuster -u https://<TARGET_IP>/ -k"),
        ("445 / SMB (Samba / Shares / Null Session)", "445/tcp/microsoft-ds/HIGH/netexec smb <TARGET_IP> -u '' -p '' --shares"),
        ("1433 / MSSQL (SQL Server)", "1433/tcp/ms-sql-s/HIGH/mssqlclient.py <DOMAIN>/user:pass@<TARGET_IP> -windows-auth"),
        ("3306 / MySQL (Database)", "3306/tcp/mysql/MED/mysql -h <TARGET_IP> -u root -p"),
        ("3389 / RDP (Remote Desktop)", "3389/tcp/ms-wbt-server/MED/xfreerdp /u:user /p:pass /v:<TARGET_IP> /smart-sizing"),
        ("5985 / WinRM (PowerShell Remoting)", "5985/tcp/wsman/HIGH/evil-winrm -i <TARGET_IP> -u user -p 'pass'"),
        ("8080 / HTTP-Proxy / Tomcat Manager", "8080/tcp/http-proxy/HIGH/curl -s http://<TARGET_IP>:8080/manager/html"),
    ]

    def __init__(self, target_ip: str = "", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.target_ip = target_ip

    def compose(self) -> ComposeResult:
        with Vertical(id="add-service-container", classes="synapse-modal-dialog"):
            yield Label(f"▸ ADD SERVICE — {self.target_ip or 'Active Target'}", classes="modal-header")

            yield Label("Quick Service Preset (Auto-fills below fields):", classes="field-label")
            yield Select(
                self.SERVICE_PRESETS,
                value="custom",
                id="svc-preset",
            )

            with Horizontal():
                with Vertical(classes="column"):
                    yield Label("Port Number *:", classes="field-label")
                    yield Input(value="80", id="svc-port")
                with Vertical(classes="column"):
                    yield Label("Protocol:", classes="field-label")
                    yield Select([("tcp", "tcp"), ("udp", "udp")], value="tcp", id="svc-proto")

            yield Label("Service Name *:", classes="field-label")
            yield Input(value="HTTP", id="svc-name")

            yield Label("Version / Banner (optional):", classes="field-label")
            yield Input(placeholder="e.g. Apache 2.4.52, Samba 4.3, OpenSSH 8.9", id="svc-ver")

            yield Label("Initial Access Potential:", classes="field-label")
            yield Select(
                [
                    ("— not rated —", ""),
                    ("HIGH (Direct RCE / Credentials / Easy Win)", "HIGH"),
                    ("MED (Enumeration / Brute-force)", "MED"),
                    ("LOW (Informational / Hardened)", "LOW"),
                ],
                value="",
                id="svc-potential",
            )

            yield Label("Next Action / Command Recipe:", classes="field-label")
            yield Input(placeholder="e.g. feroxbuster, smbmap, hydra...", id="svc-next")

            with Horizontal(classes="modal-buttons"):
                yield Button("Save Service (Enter)", variant="primary", classes="primary-btn", id="btn-save")
                yield Button("Cancel (Esc)", id="btn-cancel")

    def on_mount(self) -> None:
        self.query_one("#svc-preset", Select).focus()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "svc-preset" and event.value and event.value != "custom":
            val = str(event.value)
            parts = val.split("/")
            if len(parts) >= 5:
                port, proto, name, pot, nxt = parts[0], parts[1], parts[2], parts[3], "/".join(parts[4:])
                self.query_one("#svc-port", Input).value = port
                self.query_one("#svc-proto", Select).value = proto
                self.query_one("#svc-name", Input).value = name.upper()
                if not derive_guidance_enabled():
                    # Exam-safe: don't auto-fill a rating or a next command.
                    return
                self.query_one("#svc-potential", Select).value = pot
                if self.target_ip:
                    nxt = nxt.replace("<TARGET_IP>", self.target_ip)
                self.query_one("#svc-next", Input).value = nxt

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-save":
            self.submit_data()
        else:
            self.dismiss(None)

    def on_key(self, event: Any) -> None:
        if event.key == "escape":
            self.dismiss(None)
        elif event.key == "enter" and not isinstance(self.focused, Select):
            self.submit_data()

    def submit_data(self) -> None:
        port_raw = self.query_one("#svc-port", Input).value.strip()
        if not port_raw.isdigit():
            return
        port = int(port_raw)
        proto = str(self.query_one("#svc-proto", Select).value or "tcp")
        name = self.query_one("#svc-name", Input).value.strip() or "unknown"
        ver = self.query_one("#svc-ver", Input).value.strip()
        pot = str(self.query_one("#svc-potential", Select).value or "")
        nxt = self.query_one("#svc-next", Input).value.strip()

        self.dismiss({
            "port": port,
            "protocol": proto,
            "service": name,
            "version": ver,
            "potential": pot,
            "next": nxt,
        })


class AddCredentialModal(ModalScreen[Optional[dict]]):
    """Fast credential recording dialog with service scope and credential type pickers."""

    DEFAULT_CSS = """
    AddCredentialModal {
        align: center middle;
    }
    #add-cred-container {
        width: 68;
        height: auto;
        max-height: 90%;
        border: round $accent;
        background: $surface;
        padding: 1 2;
        color: $foreground;
    }
    AddCredentialModal Input {
        height: 3;
        border: round $border;
        background: $background;
        color: $foreground;
        padding: 0 1;
    }
    AddCredentialModal Input:focus {
        border: round $accent;
    }
    """

    SCOPE_PRESETS = [
        ("GLOBAL / All Services", "GLOBAL"),
        ("SMB (Windows / Samba Shares)", "SMB"),
        ("SSH (Linux Shell)", "SSH"),
        ("HTTP / Web Application", "HTTP"),
        ("WinRM (PowerShell Remoting)", "WinRM"),
        ("MSSQL (Database)", "MSSQL"),
        ("MySQL (Database)", "MySQL"),
        ("RDP (Remote Desktop)", "RDP"),
        ("FTP (File Transfer)", "FTP"),
    ]

    TYPE_PRESETS = [
        ("Cleartext Password", "password"),
        ("NTLM Hash (LM:NTLM or NTLM)", "ntlm_hash"),
        ("Kerberos Ticket (TGT / TGS ccache)", "kerberos"),
        ("SSH Private Key", "ssh_key"),
        ("API Token / Session Cookie", "token"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="add-cred-container", classes="synapse-modal-dialog"):
            yield Label("▸ RECORD CREDENTIAL", classes="modal-header")

            yield Label("Username *:", classes="field-label")
            yield Input(placeholder="e.g. administrator, root, tomcat", id="cred-user")

            yield Label("Secret / Password / Hash *:", classes="field-label")
            yield Input(placeholder="e.g. Password123!, aad3b435b51404eeaad3b435b51404ee:...", id="cred-secret")

            yield Label("Service Scope / Protocol:", classes="field-label")
            yield Select(self.SCOPE_PRESETS, value="SMB", id="cred-scope")

            yield Label("Credential Type:", classes="field-label")
            yield Select(self.TYPE_PRESETS, value="password", id="cred-type")

            yield Label("Source / Origin (optional):", classes="field-label")
            yield Input(placeholder="e.g. SAM dump, /etc/shadow, backup.zip, tomcat-users.xml", id="cred-source")

            with Horizontal(classes="modal-buttons"):
                yield Button("Save Credential (Enter)", variant="primary", classes="primary-btn", id="btn-save")
                yield Button("Cancel (Esc)", id="btn-cancel")

    def on_mount(self) -> None:
        self.query_one("#cred-user", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-save":
            self.submit_data()
        else:
            self.dismiss(None)

    def on_key(self, event: Any) -> None:
        if event.key == "escape":
            self.dismiss(None)
        elif event.key == "enter" and not isinstance(self.focused, Select):
            self.submit_data()

    def submit_data(self) -> None:
        u = self.query_one("#cred-user", Input).value.strip()
        p = self.query_one("#cred-secret", Input).value.strip()
        if not u:
            return
        scope = str(self.query_one("#cred-scope", Select).value or "GLOBAL")
        source = self.query_one("#cred-source", Input).value.strip()

        self.dismiss({
            "username": u,
            "secret": p,
            "scope": scope,
            "source": source,
        })


class AddFindingModal(ModalScreen[Optional[dict]]):
    """Fast finding dialog with category presets and severity dropdown."""

    DEFAULT_CSS = """
    AddFindingModal {
        align: center middle;
    }
    #add-finding-container {
        width: 68;
        height: auto;
        max-height: 90%;
        border: round $accent;
        background: $surface;
        padding: 1 2;
        color: $foreground;
    }
    AddFindingModal Input {
        height: 3;
        border: round $border;
        background: $background;
        color: $foreground;
        padding: 0 1;
    }
    AddFindingModal Input:focus {
        border: round $accent;
    }
    """

    FINDING_PRESETS = [
        ("Custom Finding", "", "MEDIUM"),
        ("Default Administrative Credentials", "Default credentials identified allowing privileged access.", "CRITICAL"),
        ("Anonymous / Guest SMB Share Access", "Unauthenticated guest access permits reading sensitive shares.", "HIGH"),
        ("Unauthenticated Remote Code Execution (RCE)", "Vulnerability allows direct arbitrary code execution.", "CRITICAL"),
        ("SQL Injection (Auth Bypass / Exfiltration)", "SQL injection allows database dump or login bypass.", "HIGH"),
        ("Weak / Predictable Password", "Service vulnerable to dictionary brute-force.", "HIGH"),
        ("Unquoted Service Path Privilege Escalation", "Windows service path contains unquoted space allowing binary planting.", "HIGH"),
        ("SUID Binary Exploitation PrivEsc", "Linux SUID binary with GTFOBins exploitation path.", "HIGH"),
        ("Sudo NOPASSWD Misconfiguration PrivEsc", "User can run command as root without password.", "HIGH"),
        ("Kerberoasting (SPN Hash Exfiltration)", "Service principal accounts requestable for offline cracking.", "HIGH"),
        ("AS-REP Roasting (No Pre-Authentication)", "User account DONT_REQ_PREAUTH allows offline TGT crack.", "HIGH"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="add-finding-container", classes="synapse-modal-dialog"):
            yield Label("▸ RECORD VULNERABILITY / FINDING", classes="modal-header")

            yield Label("Category Preset (Auto-fills title and severity):", classes="field-label")
            yield Select(
                [(p[0], f"{p[0]}|{p[1]}|{p[2]}") for p in self.FINDING_PRESETS],
                value=f"{self.FINDING_PRESETS[0][0]}||MEDIUM",
                id="finding-preset",
            )

            yield Label("Finding Title *:", classes="field-label")
            yield Input(placeholder="e.g. Apache Tomcat Default Credentials", id="finding-title")

            yield Label("Severity Level:", classes="field-label")
            yield Select(
                [
                    ("CRITICAL (Direct Foothold / Domain Admin)", "CRITICAL"),
                    ("HIGH (Privilege Escalation / Sensitive Data)", "HIGH"),
                    ("MEDIUM (Misconfiguration / Brute-force)", "MEDIUM"),
                    ("LOW (Information Leak)", "LOW"),
                    ("INFO (Recon Observation)", "INFO"),
                ],
                value="HIGH",
                id="finding-sev",
            )

            yield Label("Exploitation Details / Description (optional):", classes="field-label")
            yield Input(placeholder="e.g. tomcat:s3cret_p4ss allows uploading WAR reverse shell", id="finding-desc")

            with Horizontal(classes="modal-buttons"):
                yield Button("Save Finding (Enter)", variant="primary", classes="primary-btn", id="btn-save")
                yield Button("Cancel (Esc)", id="btn-cancel")

    def on_mount(self) -> None:
        self.query_one("#finding-preset", Select).focus()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "finding-preset" and event.value:
            val = str(event.value)
            parts = val.split("|", 2)
            if len(parts) == 3:
                title, desc, sev = parts[0], parts[1], parts[2]
                if title != "Custom Finding":
                    self.query_one("#finding-title", Input).value = title
                    self.query_one("#finding-desc", Input).value = desc
                    self.query_one("#finding-sev", Select).value = sev

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-save":
            self.submit_data()
        else:
            self.dismiss(None)

    def on_key(self, event: Any) -> None:
        if event.key == "escape":
            self.dismiss(None)
        elif event.key == "enter" and not isinstance(self.focused, Select):
            self.submit_data()

    def submit_data(self) -> None:
        title = self.query_one("#finding-title", Input).value.strip()
        if not title:
            return
        sev = str(self.query_one("#finding-sev", Select).value or "MEDIUM")
        desc = self.query_one("#finding-desc", Input).value.strip()

        self.dismiss({
            "title": title,
            "severity": sev,
            "desc": desc,
        })


class FastInputModal(ModalScreen[Optional[dict]]):
    """Generic quick-entry modal for simple key-value inputs."""

    DEFAULT_CSS = """
    FastInputModal {
        align: center middle;
    }
    #input-container {
        width: 65%;
        height: auto;
        border: round $primary;
        background: $surface;
        padding: 1 2;
        color: $foreground;
    }
    #modal-title {
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
    }
    .input-field {
        margin-bottom: 1;
        background: $background;
        border: round $surface-lighten-1;
        color: $foreground;
    }
    .input-field:focus {
        border: round $primary;
    }
    #button-bar {
        height: 3;
        margin-top: 1;
        layout: horizontal;
        align: right middle;
    }
    """

    def __init__(self, title: str, fields: List[tuple[str, str, str]]) -> None:
        super().__init__()
        self.modal_title = title
        self.fields = fields

    def compose(self) -> ComposeResult:
        with Vertical(id="input-container"):
            yield Label(f"▸ {self.modal_title}", id="modal-title")
            for key, label_text, default_val in self.fields:
                yield Label(label_text, classes="field-label")
                yield Input(value=default_val, id=f"field-{key}", classes="input-field")
            with Horizontal(id="button-bar"):
                yield Button("Save (Enter)", variant="primary", classes="primary-btn", id="btn-save")
                yield Button("Cancel (Esc)", id="btn-cancel")

    def on_mount(self) -> None:
        first_input = self.query(Input).first()
        if first_input:
            first_input.focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-save":
            data = {}
            for key, _, _ in self.fields:
                inp = self.query_one(f"#field-{key}", Input)
                data[key] = inp.value.strip()
            self.dismiss(data)
        else:
            self.dismiss(None)

    def on_key(self, event: Any) -> None:
        if event.key == "escape":
            self.dismiss(None)
        elif event.key == "enter":
            data = {}
            for key, _, _ in self.fields:
                inp = self.query_one(f"#field-{key}", Input)
                data[key] = inp.value.strip()
            self.dismiss(data)


class HelpModal(ModalScreen):
    """Modal displaying keyboard shortcuts and workflow reference."""

    DEFAULT_CSS = """
    HelpModal {
        align: center middle;
    }
    #help-box {
        width: 75%;
        height: 80%;
        border: round $primary;
        background: $surface;
        padding: 1 2;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="help-box"):
            P = current_palette()
            yield Label(f"[bold {P.accent}]CYB0X-S WORKSHEET — KEYBOARD REFERENCE[/bold {P.accent}]\n")
            with VerticalScroll():
                text = f"""
[bold]Key Design Principle:[/bold]
The human decides and performs the security-testing actions. CYB0X-S records and organizes them.
Pure passive recording • Local-first SQLite store • Zero background scanning or AI.

[bold]Stations:[/bold]
  [{P.accent}]1[/]  Cockpit       attack surface, services, methodology, notes — one screen
  [{P.accent}]2[/]  Playbooks     offline command reference (Enter copies)
  [{P.accent}]3[/]  Credentials   full vault, reveal / copy, spray targets
  [{P.accent}]4[/]  Loot & Flags  user/root flags, foothold, rabbit holes

[bold]Cockpit layout:[/bold]
  The status strip under the header answers the four exam questions at a glance:
  which box, what is captured, what to do next, what is blocking me.
  The bottom console always shows the command for the highlighted row and
  doubles as the fast-capture bar. Press [{P.accent}]?[/] any time — or [{P.accent}]T[/] to change theme.

[bold]Navigation:[/bold]
  [{P.accent}]Tab / Shift+Tab[/]  : Move focus between panels
  [{P.accent}]j / k  (or ↑ / ↓)[/] : Move down / up inside the focused list or tree
  [{P.accent}]z[/]                : Zoom the focused panel, press again to restore
  [{P.accent}]Esc[/]              : Close any dialog

[bold]Working with the highlighted item:[/bold]
  [{P.accent}]Enter[/]            : Copy the ready-to-paste command / next action
  [{P.accent}]y[/]                : Copy the value (IP, IP:port, secret, note text)
  [{P.accent}]Space[/]            : Cycle checklist status (TODO → CHECKED → DEFERRED → DEAD-END)
                     or reveal / re-mask a credential
  [{P.accent}]d[/]                : Delete it (asks for confirmation)

[bold]Capture & Modals:[/bold]
  [{P.accent}]t[/]  add target modal         [{P.accent}]s[/]  add service modal    [{P.accent}]f[/]  add finding modal
  [{P.accent}]c[/]  add credential modal     [{P.accent}]n[/]  add note modal       [{P.accent}]K[/]  (shift+k) checklist item
  [{P.accent}]m[/]  methodology templates    [{P.accent}]g[/]  record flags         [{P.accent}]r[/]  cheat sheet
  [{P.accent}]T[/]  (shift+t) theme picker   [{P.accent}]o[/]  toggle scope         [{P.accent}]/[/] or [{P.accent}]Ctrl+F[/] search
  [{P.accent}]?[/]  this help modal          [{P.accent}]q[/]  quit app

[bold]Fast capture commands (bottom bar):[/bold]
  :t 10.10.10.20          add a target
  :s 445/tcp smb          add a service
  :c admin:password123    add a credential
  :n found backup.zip     add a note
  :f smb null session     add a finding
  :uflag / :rflag <hash>  record user / root flag
  :foothold / :privesc    record foothold & privilege escalation vector
  :stuck <why> / :clue    log a rabbit hole or the breakthrough clue
  :ref <term>             offline cheat sheet       :1 :2 :3 :4  stations

[bold]Shell equivalents:[/bold]
  cyb0x-s target 10.10.10.20
  cyb0x-s service 10.10.10.20 445/tcp SMB --version "Samba 4.3"
  cyb0x-s finding "SMB anonymous access enabled" --severity HIGH
  cyb0x-s cred admin:password --source backup.zip
  cyb0x-s export --format md -o notes.md

Press [bold]Esc[/bold] or [bold]q[/bold] to return to the worksheet.
"""
                yield Static(text)
            yield Button("Close", id="btn-close", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(None)

    def on_key(self, event: Any) -> None:
        if event.key in ("escape", "q", "enter"):
            self.dismiss(None)


class TemplateSelectionModal(ModalScreen[Any]):
    """Interactive selector for eJPTv2 & standard penetration testing methodology templates."""

    DEFAULT_CSS = """
    TemplateSelectionModal {
        align: center middle;
    }
    #template-box {
        width: 80%;
        height: 80%;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }
    #template-list {
        height: 1fr;
        border: solid $secondary 40%;
        margin-top: 1;
        margin-bottom: 1;
    }
    #btn-bar {
        height: 3;
        layout: horizontal;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="template-box"):
            P = current_palette()
            yield Label(
                f"[bold {P.accent}]METHODOLOGY CHECKLIST TEMPLATES[/bold {P.accent}]"
                f" [{P.muted}](Standard Assessment Workflows)[/]"
            )
            yield Label(
                f"[{P.muted}]Select a template:[/] [bold {P.accent}]Enter[/] [{P.muted}]to switch/replace checklist  • [/] "
                f"[bold {P.accent}]a[/] [{P.muted}]to append items  • [/] [bold {P.accent}]Esc[/] [{P.muted}]to cancel[/]"
            )
            yield ListView(id="template-list")
            with Horizontal(id="btn-bar"):
                yield Button("Switch Methodology (Enter)", variant="primary", id="btn-switch")
                yield Button("Append Items (a)", variant="default", id="btn-append")
                yield Button("Cancel (Esc)", variant="default", id="btn-cancel")

    def on_mount(self) -> None:
        from cyb0x_s.templates import STATIC_TEMPLATES

        t_list = self.query_one("#template-list", ListView)
        for key, tmpl in STATIC_TEMPLATES.items():
            txt = Text()
            txt.append(f"{key.upper():<16} ", style=S("accent"))
            txt.append(f"({len(tmpl['items'])} items)  ", style=S("warn"))
            txt.append(f"{tmpl['description']}", style=S("muted", bold=False))
            t_list.append(DataListItem(data_obj=key, display_text=txt))
        t_list.focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-switch":
            self._select_current(replace=True)
        elif event.button.id == "btn-append":
            self._select_current(replace=False)
        else:
            self.dismiss(None)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if isinstance(event.item, DataListItem):
            self.dismiss((event.item.data_obj, True))

    def _select_current(self, replace: bool = True) -> None:
        t_list = self.query_one("#template-list", ListView)
        if t_list.highlighted_child and isinstance(t_list.highlighted_child, DataListItem):
            self.dismiss((t_list.highlighted_child.data_obj, replace))
        else:
            self.dismiss(None)

    def on_key(self, event: Any) -> None:
        if event.key == "escape":
            self.dismiss(None)
        elif event.key == "enter":
            self._select_current(replace=True)
        elif event.key in ("a", "A"):
            self._select_current(replace=False)


class ReferenceModal(ModalScreen[Optional[str]]):
    """Searchable command reference and penetration testing playbook modal."""

    DEFAULT_CSS = """
    ReferenceModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.75);
    }
    #ref-box {
        width: 85%;
        height: 85%;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    #ref-filter-input {
        margin-top: 1;
        margin-bottom: 1;
        border: solid $border;
        background: $background;
    }
    #ref-list {
        height: 1fr;
        border: solid $border;
        margin-bottom: 1;
    }
    #ref-btn-bar {
        height: 3;
        layout: horizontal;
    }
    """

    def __init__(self, target_ip: str = "", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.target_ip = target_ip

    def compose(self) -> ComposeResult:
        with Vertical(id="ref-box"):
            P = current_palette()
            yield Label(
                f"[bold {P.accent}]📖 eJPTv2 CHEAT SHEET & COMMAND REFERENCE[/bold {P.accent}]"
                f" [{P.muted}](Offline Playbook)[/]"
            )
            yield Label(
                f"[{P.muted}]Target IP: [bold {P.text}]{self.target_ip or 'None'}[/bold {P.text}]"
                f" • Type to filter, Enter to copy command, Esc to exit[/]"
            )
            yield Input(placeholder="Search commands: smb, winrm, mimikatz, pivot, privesc, sql, hydra...", id="ref-filter-input")
            yield ListView(id="ref-list")
            with Horizontal(id="ref-btn-bar"):
                yield Button("Copy Selected Command (Enter)", variant="primary", id="btn-copy-ref")
                yield Button("Close (Esc)", variant="default", id="btn-close-ref")

    def on_mount(self) -> None:
        self._populate_list("")
        inp = self.query_one("#ref-filter-input", Input)
        inp.focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        self._populate_list(event.value)

    def _populate_list(self, query: str) -> None:
        from cyb0x_s.reference import search_reference

        ref_list = self.query_one("#ref-list", ListView)
        ref_list.clear()
        matches = search_reference(query, target_ip=self.target_ip)
        if matches:
            for item in matches:
                txt = Text()
                txt.append(f"[{item['category']}] ", style=S("warn"))
                txt.append(f"{item['title']}\n", style=S("text"))
                txt.append(f"  ❯ {item['command']}\n", style=S("warn"))
                txt.append(f"    ℹ {item['desc']}", style="dim italic")
                ref_list.append(DataListItem(data_obj=item["command"], display_text=txt))
        else:
            txt = Text("  • No matching commands found. Try 'smb', 'web', 'sql', 'privesc'...", style="dim italic")
            ref_list.append(DataListItem(data_obj=None, display_text=txt, is_placeholder=True))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-copy-ref":
            self._select_current()
        else:
            self.dismiss(None)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if isinstance(event.item, DataListItem) and not event.item.is_placeholder and event.item.data_obj:
            self.dismiss(str(event.item.data_obj))

    def _select_current(self) -> None:
        ref_list = self.query_one("#ref-list", ListView)
        if ref_list.highlighted_child and isinstance(ref_list.highlighted_child, DataListItem) and not ref_list.highlighted_child.is_placeholder:
            self.dismiss(str(ref_list.highlighted_child.data_obj))
        else:
            self.dismiss(None)

    def on_key(self, event: Any) -> None:
        if event.key == "escape":
            self.dismiss(None)


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
        border: round $border;
        background: $surface;
        padding: 0 1;
        margin-right: 1;
    }
    #playbook-cmd-panel {
        width: 75%;
        height: 1fr;
        border: round $border;
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
        /* Explicit height: with `auto` the cards stretched over the whole
           tab and pushed the failure log off-screen. */
        height: 9;
        layout: horizontal;
        margin-bottom: 1;
    }
    .loot-box {
        width: 1fr;
        height: 9;
        border: round $border;
        background: $surface;
        padding: 0 1;
        margin-right: 1;
    }
    #loot-failure-box {
        height: 1fr;
        border: round $border;
        background: $surface;
        padding: 0 1;
    }
    .loot-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.target: Optional[Target] = None

    def compose(self) -> ComposeResult:
        with Horizontal(id="loot-cards-container"):
            with Vertical(classes="loot-box"):
                yield Label("🏁 CAPTURED EXAM FLAGS", classes="loot-title")
                yield Static(id="loot-flags-content")
            with Vertical(classes="loot-box"):
                yield Label("⚡ INITIAL FOOTHOLD & EXPLOIT", classes="loot-title")
                yield Static(id="loot-foothold-content")
            with Vertical(classes="loot-box"):
                yield Label("👑 PRIVILEGE ESCALATION & ROOT PROOF", classes="loot-title")
                yield Static(id="loot-privesc-content")
        with Vertical(id="loot-failure-box"):
            yield Label("🧠 RABBIT HOLE & BREAKTHROUGH ANALYSIS (FAILURE LOG)", classes="loot-title")
            yield ListView(id="loot-failure-list")

    def update_data(self, target: Optional[Target], failures: List[Any]) -> None:
        self.target = target

        # Flags Card
        f_txt = Text()
        if target:
            f_txt.append("User Flag: ", style=S("accent"))
            f_txt.append(f"{target.user_flag or '<NOT CAPTURED YET>'}\n", style=S("ok") if target.user_flag else S("muted", bold=False))
            f_txt.append("Root Flag: ", style=S("warn"))
            f_txt.append(f"{target.root_flag or '<NOT CAPTURED YET>'}\n\n", style=S("ok") if target.root_flag else S("muted", bold=False))
            f_txt.append("[Press 'g' or type :uflag / :rflag to set flags]", style="dim italic")
        else:
            f_txt.append("No active target selected.", style="dim italic")
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
            fh_txt.append("No foothold recorded yet.\nType :foothold <vuln> to record.", style="dim italic")
        self.query_one("#loot-foothold-content", Static).update(fh_txt)

        # PrivEsc Card
        pe_txt = Text()
        if target and (target.privesc_vector or target.root_proof):
            pe_txt.append("PrivEsc Vector: ", style=S("accent"))
            pe_txt.append(f"{target.privesc_vector or 'N/A'}\n", style=S("text"))
            pe_txt.append(f"Root Proof:\n❯ {target.root_proof or 'whoami && id && ip a'}", style=S("warn"))
        else:
            pe_txt.append("No PrivEsc recorded yet.\nType :privesc <vector> to record.", style="dim italic")
        self.query_one("#loot-privesc-content", Static).update(pe_txt)

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


class CredentialMatrixWidget(Static):
    """Full-screen matrix of discovered credentials, lateral movement targets, and spray gaps."""

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
    #cred-matrix-list {
        height: 1fr;
        border: round $border;
        background: $surface;
    }
    """

    def compose(self) -> ComposeResult:
        yield Label(
            Text("CREDENTIAL VAULT & LATERAL MOVEMENT MATRIX"),
            id="cred-matrix-hdr",
            classes="panel-header",
        )
        yield Label("", id="cred-matrix-sub", classes="panel-subtitle")
        yield ListView(id="cred-matrix-list")

    def update_data(
        self,
        credentials: List[Credential],
        targets: List[Target],
        services: List[Service],
        revealed_ids: Set[int],
    ) -> None:
        c_list = self.query_one("#cred-matrix-list", ListView)
        c_list.clear()

        # Build in-scope targets mapping per service
        in_scope_targets = [t for t in targets if t.is_in_scope]
        svc_target_map: dict[str, list[str]] = {}
        for s in services:
            t = next((tgt for tgt in in_scope_targets if tgt.id == s.target_id), None)
            if t:
                svc_target_map.setdefault(s.service.lower(), []).append(t.ip)

        # Summary line: how much of the vault has actually been tried.
        tested = sum(1 for c in credentials if (c.status or "").lower() in ("valid", "tested"))
        subtitle = self.query_one("#cred-matrix-sub", Label)
        if credentials:
            subtitle.update(
                f"{len(credentials)} credential(s) • {tested} validated • "
                f"{len(credentials) - tested} untested   [Space]=Reveal  [y]=Copy  [c]=Add"
            )
        else:
            subtitle.update("No credentials recorded yet — press 'c' to add one.")

        if credentials:
            for c in credentials:
                txt = Text()
                txt.append("🔑 ", style=S("ok"))
                scope = (c.service_scope or "GLOBAL").upper()
                scope = scope if len(scope) <= 8 else scope[:7] + "…"
                txt.append(f"[{scope:<8}] ", style=S("warn"))
                user = c.username if len(c.username) <= 16 else c.username[:15] + "…"
                txt.append(f"{user:<16} : ", style=S("accent"))
                secret = c.secret if c.id in revealed_ids else c.masked_secret
                txt.append(f"{secret:<20} ", style=S("text"))

                # Tested vs Unsprayed
                scope_key = (c.service_scope or "").lower()
                applicable_hosts = svc_target_map.get(scope_key, [t.ip for t in in_scope_targets])
                if c.source:
                    txt.append(f" Source: {c.source} │ ", style=S("muted", bold=False))
                txt.append(f"Status: {c.status.upper()} │ ", style=S("warn"))
                if len(applicable_hosts) > 1:
                    txt.append(f"⚠ Spray Target(s): {', '.join(applicable_hosts[:3])}", style=S("warn"))

                c_list.append(DataListItem(data_obj=c, display_text=txt))
        else:
            for line in (
                "  • Nothing in the vault yet.",
                "  • Press 'c' to record a credential, or type :c user:pass below.",
                "  • Secrets stay masked until you reveal them with Space.",
            ):
                txt = Text(line, style="dim italic")
                c_list.append(DataListItem(data_obj=None, display_text=txt, is_placeholder=True))




