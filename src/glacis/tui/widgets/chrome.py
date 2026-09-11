"""Application chrome: header, exam-speed status strip and the command console."""

from __future__ import annotations

import time
from datetime import timedelta
from typing import Any, Dict, List, Optional

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import Input, Label, Static

from glacis.templates import get_template_guidance_for_title
from glacis.tui.anim import guarded_interval, guarded_timer
from glacis.tui.theme import current_palette, mix, ramp
from glacis.tui.widgets.lists import substitute_command_placeholders


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
        t.append("GLACIS ", style=f"bold {P.accent}")
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
    """At-a-glance machine state — the exam-speed panel (answerable in one glance)."""

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
        self.target: Optional[Any] = None
        self.counts: dict[str, int] = {}
        self.next_step: str = ""
        self.progress: tuple[int, int, int] = (0, 0, 0)
        self.blockers: int = 0
        self.session_start = time.monotonic()
        self.exam_start: Optional[float] = None

    def on_mount(self) -> None:
        """Restore a persisted exam start; tick the clock only outside tests."""
        try:
            store = getattr(self.app, "store", None)
            if store is not None and hasattr(store, "get_setting"):
                raw = store.get_setting("exam_started_at")
                if raw:
                    self.exam_start = float(raw)
        except Exception:
            self.exam_start = None
        guarded_interval(self, 1, self.refresh)

    def update_status(
        self,
        target: Optional[Any] = None,
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
        filled = int(round(width * pct / 100))
        shades = ramp(P.ok, filled, dim_towards=P.surface, floor=0.35) if filled else []
        empty = mix(P.border, P.surface, 0.55)
        bar = Text()
        for i in range(filled):
            bar.append("█", style=f"bold {shades[i]}")
        if filled < width:
            bar.append("░" * (width - filled), style=empty)
        return bar

    def render(self) -> Text:
        P = current_palette()
        t = Text()
        width = max(self.size.width - 4, 20) if self.size.width > 0 else 120

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

            lh, lp = "", "4444"
            if hasattr(self.app, "store"):
                try:
                    lh = getattr(self.app.store, "get_lhost", lambda: "")()
                    lp = getattr(self.app.store, "get_lport", lambda: "4444")()
                except Exception:
                    pass
            if lh:
                row1.append(f"[LHOST: {lh}:{lp}] ", style=f"bold {P.accent}")

            row1.append("[USER: ✔] " if self.target.user_flag else "[USER: ◯] ",
                        style=f"bold {P.ok}" if self.target.user_flag else f"bold {P.muted}")
            row1.append("[ROOT: ✔] " if self.target.root_flag else "[ROOT: ◯] ",
                        style=f"bold {P.ok}" if self.target.root_flag else f"bold {P.muted}")

            if self.target.initial_access_vuln:
                row1.append(f"[{self._elide(self.target.initial_access_vuln, 16)}] ", style=f"bold {P.warn}")
        else:
            row1.append("◇ TARGET ▸ ", style=f"bold {P.warn}")
            row1.append("no target selected  ·  press 't' to add one", style=f"{P.muted}")

        placed = False
        counts_text = ""
        if self.counts:
            counts_text = "   ".join(f"{v} {k}" for k, v in self.counts.items())
            pad = width - len(row1.plain) - len(counts_text)
            if pad >= 4:
                row1.append(" " * pad)
                row1.append(counts_text, style=f"bold {P.muted}")
                placed = True

        if self.size.height < 2:
            return Text(self._elide(row1.plain, width)) if len(row1.plain) > width else row1

        if len(row1.plain) > width:
            t.append(self._elide(row1.plain, width))
        else:
            t.append_text(row1)
        t.append("\n")

        done, total, pct = self.progress
        tail2 = Text()
        if total:
            tail2.append_text(self._progress_bar(pct, 10, P))
            tail2.append(f" {pct:>3d}% ({done}/{total})  ", style=f"{P.text_soft}")
        if not placed and counts_text:
            tail2.append(counts_text + "   ", style=f"bold {P.muted}")
        blocker_text = (
            f"🕳 {self.blockers} dead end" + ("s" if self.blockers != 1 else "")
            if self.blockers else "no blockers"
        )
        tail2.append(blocker_text, style=f"bold {P.danger}" if self.blockers else f"{P.muted}")

        left2 = Text()
        avail_left = max(width - len(tail2.plain) - 4, 16)
        if self.next_step:
            left2.append("TODO ▸ ", style=f"bold {P.warn}")
            left2.append(self._elide(self.next_step, max(avail_left - 7, 8)), style=f"bold {P.text}")
        elif total:
            left2.append("CHECKLIST ▸ ", style=f"bold {P.ok}")
            left2.append(self._elide("methodology complete", max(avail_left - 12, 8)), style=f"bold {P.ok}")
        else:
            left2.append("CHECKLIST ▸ ", style=f"bold {P.muted}")
            left2.append(
                self._elide("press 'm' to load a methodology template", max(avail_left - 12, 8)),
                style=f"{P.muted}",
            )

        pad2 = width - len(left2.plain) - len(tail2.plain)
        row2 = Text()
        row2.append_text(left2)
        row2.append(" " * pad2 if pad2 > 0 else " ")
        row2.append_text(tail2)
        t.append(self._elide(row2.plain, width) if len(row2.plain) > width else row2)
        return t


class ConsoleBar(Container):
    """Full-width bottom console: highlighted command, tip and capture input."""

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
    ConsoleBar.copied-flash {
        border: solid $success;
    }
    #console-cmd { height: 1; padding: 0 1; color: $foreground; }
    #console-tip { height: 1; padding: 0 1; color: $text-muted; }
    #console-input-row {
        height: 1;
        padding: 0 1;
        background: $surface-darken-1;
        layout: horizontal;
    }
    #console-prompt { width: auto; color: $accent; text-style: bold; }
    #cmd-input {
        width: 1fr; height: 1; border: none; background: transparent;
        color: $foreground; padding: 0;
    }
    #cmd-input:focus { border: none; }
    #console-hotkeys { width: auto; color: $text-muted; text-align: right; }
    """

    AUTOCOMPLETE_PREFIXES: Dict[str, str] = {
        ":t": ":t ", ":target": ":t ",
        ":s": ":s ", ":service": ":s ",
        ":snap": ":snap ", ":snapshot": ":snap ",
        ":c": ":c ", ":cred": ":c ",
        ":n": ":n ", ":note": ":n ",
        ":f": ":f ", ":finding": ":f ",
        ":th": ":theme ", ":theme": ":theme ",
        ":ref": ":ref ",
        ":u": ":uflag ", ":uflag": ":uflag ",
        ":r": ":rflag ", ":rflag": ":rflag ",
        ":foot": ":foothold ", ":foothold": ":foothold ",
        ":priv": ":privesc ", ":privesc": ":privesc ",
        ":st": ":stuck ", ":stuck": ":stuck ",
        ":cl": ":clue ", ":clue": ":clue ",
        ":ev": ":ev ",
        ":m": ":m ", ":meth": ":m ",
        ":pivot": ":pivot ",
        ":proof": ":q ",
        ":subnet": ":subnet ",
        ":export": ":export exam",
        ":w": ":w ", ":wordlist": ":w ",
        ":q": ":q",
        ":0": ":0", ":5": ":5", ":net": ":5 ", ":network": ":5 ",
        ":pulse": ":0",
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
        t.append(" [0-5]", style=f"bold {P.warn}")
        t.append(" stations ", style=f"{P.muted}")
        t.append(" [?]", style=f"bold {P.warn}")
        t.append(" help ", style=f"{P.muted}")
        t.append(" [q]", style=f"bold {P.warn}")
        t.append(" quit", style=f"{P.muted}")
        return t

    def set_active_station(self, station_id: str) -> None:
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
        self.call_after_refresh(self._paint)

    def compose(self) -> ComposeResult:
        yield Static(id="console-cmd")
        yield Static(id="console-tip")
        with Horizontal(id="console-input-row"):
            yield Label(" [ : ] ❯ ", id="console-prompt")
            yield Input(
                placeholder="Capture: :t :s :c :n :f :m :snap   ·   stations 0-5   ·   Tab completes",
                id="cmd-input",
            )
            yield Label(self._build_hotkey_text(), id="console-hotkeys")

    # -- live syntax hints ------------------------------------------------
    def update_input_hint(self, val: str) -> None:
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
            cmd_line.append(":t target  :s svc  :c cred  :m tmpl  :snap backup  :0 pulse  :5 network  :theme  ? help",
                            style=f"bold {P.text}")
            tip_line.append("TIP ▸ ", style=f"bold {P.muted}")
            tip_line.append("Press Tab to autocomplete or type a command name", style=f"{P.muted}")
        elif v.startswith(":w") or v.startswith("wordlist "):
            cmd_line.append("[WORDLIST ALIAS] ", style=f"bold {P.warn}")
            cmd_line.append(":w <rockyou|common|medium|raft-d|users>", style=f"bold {P.text}")
            tip_line.append("TIP ▸ ", style=f"bold {P.muted}")
            tip_line.append("Copies a standard SecLists/Kali wordlist path to clipboard", style=f"{P.muted}")
        elif v.startswith(":snap"):
            cmd_line.append("[SNAPSHOT SAFETY NET] ", style=f"bold {P.warn}")
            cmd_line.append(":snap [note]", style=f"bold {P.text}")
            tip_line.append("TIP ▸ ", style=f"bold {P.muted}")
            tip_line.append("Backs up the notebook DB (rotates to the newest 5)", style=f"{P.muted}")
        elif v.startswith(":m") or v.startswith(":template") or v.startswith(":methodology"):
            cmd_line.append("[METHODOLOGY CHECKLIST] ", style=f"bold {P.warn}")
            cmd_line.append(":m <name> [append]", style=f"bold {P.text}")
            tip_line.append("TIP ▸ ", style=f"bold {P.muted}")
            tip_line.append("e.g. :m web, :m smb, :m pivoting, :m ejpt (press 'm' for modal picker)", style=f"{P.muted}")
        elif v.startswith(":t") or v.startswith("target "):
            cmd_line.append("[ADD TARGET] ", style=f"bold {P.warn}")
            cmd_line.append(":t <ip> [hostname] [os]", style=f"bold {P.text}")
            tip_line.append("TIP ▸ ", style=f"bold {P.muted}")
            tip_line.append("e.g. :t 10.10.11.10 dc01.corp.local Linux", style=f"{P.muted}")
        elif v.startswith(":s") or v.startswith("service "):
            cmd_line.append("[ADD SERVICE] ", style=f"bold {P.warn}")
            cmd_line.append(":s <port/proto> <service_name>", style=f"bold {P.text}")
            tip_line.append("TIP ▸ ", style=f"bold {P.muted}")
            tip_line.append("e.g. :s 80/tcp http   :s 445 smb   :s 22/tcp ssh", style=f"{P.muted}")
        elif v.startswith(":c") or v.startswith("cred "):
            cmd_line.append("[ADD CREDENTIAL] ", style=f"bold {P.warn}")
            cmd_line.append(":c <username:password> [scope]", style=f"bold {P.text}")
            tip_line.append("TIP ▸ ", style=f"bold {P.muted}")
            tip_line.append("e.g. :c admin:Secret123! SMB", style=f"{P.muted}")
        elif v.startswith(":n") or v.startswith("note "):
            cmd_line.append("[FIELD NOTE] ", style=f"bold {P.warn}")
            cmd_line.append(":n <observation>", style=f"bold {P.text}")
            tip_line.append("TIP ▸ ", style=f"bold {P.muted}")
            tip_line.append("Saves an instant note (Enter to save)", style=f"{P.muted}")
        elif v.startswith(":f") or v.startswith("finding "):
            cmd_line.append("[FINDING / VULN] ", style=f"bold {P.warn}")
            cmd_line.append(":f <vulnerability title>", style=f"bold {P.text}")
            tip_line.append("TIP ▸ ", style=f"bold {P.muted}")
            tip_line.append("e.g. :f Anonymous SMB Share Access", style=f"{P.muted}")
        elif v.startswith(":th") or v.startswith("theme"):
            cmd_line.append("[THEME / PALETTE] ", style=f"bold {P.warn}")
            cmd_line.append(":theme <1-8 or slate|midnight|ember|cyber|sugary|candy|caramel|catppuccin>", style=f"bold {P.text}")
            tip_line.append("TIP ▸ ", style=f"bold {P.muted}")
            tip_line.append("e.g. :theme cyber, :theme 3 (ember); T opens the visual picker", style=f"{P.muted}")
        elif v.startswith(":u") or v.startswith(":flag user"):
            cmd_line.append("[USER FLAG] ", style=f"bold {P.warn}")
            cmd_line.append(":uflag <hash>", style=f"bold {P.text}")
            tip_line.append("TIP ▸ ", style=f"bold {P.muted}")
            tip_line.append("Records captured user.txt for the active target", style=f"{P.muted}")
        elif v.startswith(":r") or v.startswith(":flag root"):
            cmd_line.append("[ROOT FLAG] ", style=f"bold {P.warn}")
            cmd_line.append(":rflag <hash>", style=f"bold {P.text}")
            tip_line.append("TIP ▸ ", style=f"bold {P.muted}")
            tip_line.append("Records captured root.txt / proof.txt", style=f"{P.muted}")
        elif v.startswith(":ref"):
            cmd_line.append("[REFERENCE] ", style=f"bold {P.warn}")
            cmd_line.append(":ref <search term>", style=f"bold {P.text}")
            tip_line.append("TIP ▸ ", style=f"bold {P.muted}")
            tip_line.append("e.g. :ref winrm, :ref smb, :ref pivoting", style=f"{P.muted}")
        elif v.startswith(":foot"):
            cmd_line.append("[FOOTHOLD] ", style=f"bold {P.warn}")
            cmd_line.append(":foothold <initial access vulnerability>", style=f"bold {P.text}")
            tip_line.append("TIP ▸ ", style=f"bold {P.muted}")
            tip_line.append("e.g. :foothold Apache Struts S2-045 RCE", style=f"{P.muted}")
        elif v.startswith(":priv"):
            cmd_line.append("[PRIVESC] ", style=f"bold {P.warn}")
            cmd_line.append(":privesc <privesc vector>", style=f"bold {P.text}")
            tip_line.append("TIP ▸ ", style=f"bold {P.muted}")
            tip_line.append("e.g. :privesc Sudo NOPASSWD /usr/bin/find (GTFOBins)", style=f"{P.muted}")
        elif v.startswith(":stuck") or v.startswith(":dead"):
            cmd_line.append("[RABBIT HOLE] ", style=f"bold {P.warn}")
            cmd_line.append(":stuck <where you spent time>", style=f"bold {P.text}")
            tip_line.append("TIP ▸ ", style=f"bold {P.muted}")
            tip_line.append("e.g. :stuck brute-forcing SSH for 45m with the wrong user", style=f"{P.muted}")
        elif v.startswith(":clue"):
            cmd_line.append("[BREAKTHROUGH] ", style=f"bold {P.warn}")
            cmd_line.append(":clue <breakthrough observation>", style=f"bold {P.text}")
            tip_line.append("TIP ▸ ", style=f"bold {P.muted}")
            tip_line.append("e.g. :clue cleartext password found in db_backup.sql", style=f"{P.muted}")
        elif v in (":0", ":1", ":2", ":3", ":4", ":5"):
            names = {":0": "Pulse triage", ":1": "Cockpit", ":2": "Playbooks", ":3": "Credentials",
                     ":4": "Loot & Flags", ":5": "Network topology"}
            cmd_line.append("[SWITCH STATION] ", style=f"bold {P.warn}")
            cmd_line.append(f"Switching to {names.get(v, '')}", style=f"bold {P.text}")
            tip_line.append("TIP ▸ ", style=f"bold {P.muted}")
            tip_line.append("Press Enter to switch screen", style=f"{P.muted}")
        elif v in ("?", "help", ":help", ":?"):
            cmd_line.append("[HELP & SHORTCUTS] ", style=f"bold {P.warn}")
            cmd_line.append("Press Enter to open the full shortcut reference", style=f"bold {P.text}")
            tip_line.append("TIP ▸ ", style=f"bold {P.muted}")
            tip_line.append("Shows all keyboard shortcuts and the interaction guide", style=f"{P.muted}")
        elif v.startswith(":q"):
            cmd_line.append("[QUIT] ", style=f"bold {P.warn}")
            cmd_line.append("Press Enter to exit GLACIS", style=f"bold {P.text}")
            tip_line.append("TIP ▸ ", style=f"bold {P.muted}")
            tip_line.append("Notebook is saved continuously — snapshots via :snap", style=f"{P.muted}")
        else:
            cmd_line.append("[RAW NOTE] ", style=f"bold {P.warn}")
            cmd_line.append(ConsoleBar._elide(v, inner - 14), style=f"bold {P.text}")
            tip_line.append("TIP ▸ ", style=f"bold {P.muted}")
            tip_line.append("Free-form note — Enter saves it to Notes & Findings", style=f"{P.muted}")

        try:
            self.query_one("#console-cmd", Static).update(cmd_line)
            self.query_one("#console-tip", Static).update(tip_line)
        except Exception:
            pass

    def on_key(self, event: Any) -> None:
        if event.key == "tab":
            inp = self.query_one("#cmd-input", Input)
            v = inp.value.strip()
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

    def show_copied_feedback(self, cmd: str) -> None:
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
            def _revert() -> None:
                self.set_class(False, "copied-flash")
                self._paint()
            guarded_timer(self, 1.8, _revert)
        except Exception:
            pass

    def _get_lhost_lport(self) -> tuple[str, str]:
        if hasattr(self.app, "store"):
            try:
                return (
                    getattr(self.app.store, "get_lhost", lambda: "")(),
                    getattr(self.app.store, "get_lport", lambda: "4444")(),
                )
            except Exception:
                pass
        return "", "4444"

    def show_command(self, command: str, tip: str, target_ip: str = "", heading: str = "CMD") -> None:
        lh, lp = self._get_lhost_lport()
        self.command = substitute_command_placeholders(command or "", target_ip, lhost=lh, lport=lp)
        self.tip = tip or ""
        self.heading = heading
        self._paint()

    def show_step(self, title: str, target_ip: str = "") -> None:
        self.heading = "CMD"
        self.command = ""
        self.tip = ""
        guidance = get_template_guidance_for_title(title)
        if guidance:
            lh, lp = self._get_lhost_lport()
            self.command = substitute_command_placeholders(
                guidance.get("command", ""), target_ip, lhost=lh, lport=lp
            )
            self.tip = guidance.get("tip", "")
        elif title:
            self.heading = "STEP"
            self.tip = title
        self._paint()

    def update_guidance(self, item_title: str, target_ip: str = "") -> None:
        self.show_step(item_title, target_ip)

    def show_recipes(
        self, recipes: List[Dict[str, str]], index: int = 0, target_ip: str = ""
    ) -> None:
        if not recipes:
            self.reset()
            return
        self.recipes = recipes
        self.recipe_index = max(0, min(index, len(recipes) - 1))
        self.recipe_target_ip = target_ip
        r = self.recipes[self.recipe_index]
        count = len(recipes)
        heading = f"RECIPE {self.recipe_index + 1}/{count}" if count > 1 else "RECIPE"
        self.show_command(r.get("command", ""), r.get("tip", ""), target_ip=target_ip, heading=heading)

    def cycle_recipe(self, delta: int) -> Optional[str]:
        if not getattr(self, "recipes", None):
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
            idle = {
                "tab-pulse": (
                    " STATION 0 · PULSE TRIAGE ", " [Enter: Open station] ",
                    "PULSE ▸ ", "Deterministic host phases and explainable next-focus signals · Enter jumps to a station",
                ),
                "tab-playbooks": (
                    " STATION 2 · ATTACK PLAYBOOKS ", " [/ Search] · [Enter: Copy] ",
                    "PLAYBOOKS ▸ ", "Browse offline recipes by service · [/] search · [Enter] copy command",
                ),
                "tab-creds": (
                    " STATION 3 · CREDENTIAL VAULT ", " [Space: Status] · [Enter: Spray] ",
                    "CREDENTIALS ▸ ", "2D lateral movement matrix · [Space] cycle status · [Enter] copy spray cmd",
                ),
                "tab-network": (
                    " STATION 5 · NETWORK TOPOLOGY ", " [Enter: Copy route] ",
                    "NETWORK ▸ ", "Documented subnets, pivots and SOCKS hop chains · Enter copies tunnel syntax",
                ),
                "tab-loot": (
                    " STATION 4 · PROOFS & FLAGS ", " [g: Flags] · [a: Proofs] ",
                    "PROOFS & FLAGS ▸ ", "Flags, proofs, evidence files and rabbit-hole log · :snap before risky steps",
                ),
            }
            if self.active_station in idle:
                title, sub, tag, body = idle[self.active_station]
                self.border_title = title
                self.border_subtitle = sub
                cmd_line.append(tag, style=f"bold {P.accent}")
                cmd_line.append(body, style=f"bold {P.text}")
            else:
                self.border_title = " CONTEXT GUIDANCE "
                self.border_subtitle = " [w: Cycle Panels] · [0-5: Stations] "
                cmd_line.append("COCKPIT ▸ ", style=f"bold {P.accent}")
                cmd_line.append("Highlight a service or step to preview & copy commands · 0 opens the Pulse board",
                                style=f"bold {P.text}")

        if self.tip:
            tip_line.append("TIP ▸ ", style=f"bold {P.muted}")
            tip_line.append(ConsoleBar._elide(self.tip, inner - 8), style=f"{P.text_soft}")
        else:
            tip_line.append("STATUS ▸ ", style=f"bold {P.muted}")
            tip_line.append("Ready — everything you run happens in your own terminal", style=f"{P.muted}")

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
