"""Textual widgets and modal dialogs for CYB0X-S Worksheet."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Input, Label, ListItem, ListView, Static, Tree

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




