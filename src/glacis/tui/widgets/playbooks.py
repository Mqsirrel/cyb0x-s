"""Station 2: offline playbook/command-reference browser."""

from __future__ import annotations

from typing import Any

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Input, ListView, Static

from glacis.tui import widgets as _pkg
from glacis.tui.anim import run_debounced
from glacis.tui.theme import current_palette
from glacis.tui.widgets.lists import DataListItem


class PlaybookBrowserWidget(Static):
    """Interactive full-screen playbook and command command reference browser."""

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
        height: 3;
        border: solid $border;
        border-title-color: $text-soft;
        border-title-style: bold;
        border-subtitle-color: $text-muted;
        border-subtitle-align: right;
        background: $surface;
        padding: 0 1;
    }
    #playbook-search-input:focus {
        border: double $accent;
        border-title-color: $accent;
        border-subtitle-color: $accent;
    }
    #playbook-body {
        height: 1fr;
        layout: horizontal;
    }
    #playbook-cat-panel {
        width: 26%;
        height: 1fr;
        border: solid $border;
        border-title-color: $text-soft;
        border-title-style: bold;
        border-subtitle-color: $text-muted;
        border-subtitle-align: right;
        background: $surface;
        padding: 0;
        margin-right: 1;
    }
    #playbook-cat-panel:focus-within {
        border: double $accent;
        border-title-color: $accent;
        border-subtitle-color: $accent;
    }
    #playbook-cmd-panel {
        width: 74%;
        height: 1fr;
        border: solid $border;
        border-title-color: $text-soft;
        border-title-style: bold;
        border-subtitle-color: $accent;
        border-subtitle-align: right;
        background: $surface;
        padding: 0;
    }
    #playbook-cmd-panel:focus-within {
        border: double $accent;
        border-title-color: $accent;
        border-subtitle-color: $accent;
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
            yield Input(placeholder="Search commands, tools, exploits (e.g. smb, winrm, mimikatz, privesc, pivot)...", id="playbook-search-input")
        with Horizontal(id="playbook-body"):
            with Vertical(id="playbook-cat-panel"):
                yield ListView(id="playbook-cat-list")
            with Vertical(id="playbook-cmd-panel"):
                yield ListView(id="playbook-cmd-list")

    def on_mount(self) -> None:
        try:
            self.query_one("#playbook-search-input", Input).border_title = " QUICK SEARCH "
            self.query_one("#playbook-cat-panel", Vertical).border_title = " PLAYBOOK CATEGORIES "
            self.query_one("#playbook-cat-panel", Vertical).border_subtitle = " [Tab ⇄] "
            self.query_one("#playbook-cmd-panel", Vertical).border_subtitle = " [Enter: Copy] "
        except Exception:
            pass
        self._populate_categories()
        self._populate_commands()

    def update_target_ip(self, target_ip: str) -> None:
        if self.target_ip == target_ip:
            return
        self.target_ip = target_ip
        self._populate_commands()

    def _populate_categories(self) -> None:
        from glacis.reference import REFERENCE_PLAYBOOK

        cat_list = self.query_one("#playbook-cat-list", ListView)
        cat_list.clear()

        P = current_palette()
        counts: dict[str, int] = {}
        for item in REFERENCE_PLAYBOOK:
            c = item["category"]
            counts[c] = counts.get(c, 0) + 1

        all_txt = Text()
        all_txt.append(" [★ ALL] ", style=f"bold {P.bg} on {P.accent}")
        all_txt.append(f"  All Playbooks [{len(REFERENCE_PLAYBOOK)}]", style=f"bold {P.text}")
        cat_list.append(DataListItem(data_obj="ALL", display_text=all_txt))

        for cat, cnt in sorted(counts.items()):
            txt = Text()
            txt.append(" ● ", style=f"bold {P.accent}")
            txt.append(f"{cat:<16}", style=f"bold {P.text}")
            txt.append(f" [{cnt}]", style=f"{P.muted}")
            cat_list.append(DataListItem(data_obj=cat, display_text=txt))

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "playbook-search-input":
            self.search_query = event.value
            run_debounced(self, "_debounce_timer", 0.05, self._populate_commands)

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
                _pkg.copy_to_clipboard(cmd)
                self.app.notify(f"Copied command: {cmd}")

    def _populate_commands(self) -> None:
        import re

        from glacis.reference import search_reference

        cmd_list = self.query_one("#playbook-cmd-list", ListView)
        cmd_list.clear()

        lhost = ""
        lport = "4444"
        if hasattr(self.app, "store"):
            try:
                lhost = getattr(self.app.store, "get_lhost", lambda: "")()
                lport = getattr(self.app.store, "get_lport", lambda: "4444")()
            except Exception:
                pass

        matches = search_reference(self.search_query, target_ip=self.target_ip, lhost=lhost, lport=lport)
        if self.selected_category != "ALL":
            matches = [m for m in matches if m["category"].lower() == self.selected_category.lower()]

        try:
            cmd_panel = self.query_one("#playbook-cmd-panel", Vertical)
            count_str = f" ({len(matches)} ready commands)" if matches else ""
            cat_label = self.selected_category.upper()
            cmd_panel.border_title = f" COMMAND REFERENCE · {cat_label}{count_str} "
            cmd_panel.border_subtitle = " [Enter: Copy to Clipboard] "
        except Exception:
            pass

        P = current_palette()
        if matches:
            for item in matches:
                txt = Text()
                cat = item.get("category", "CMD").upper()
                txt.append(f"[{cat}] ", style=f"bold {P.bg} on {P.accent}")
                txt.append(f" {item['title']}\n", style=f"bold {P.text}")

                txt.append("  ❯ ", style=f"bold {P.ok}")
                cmd_str = item["command"]
                tokens = re.split(r"(<[^>]+>)", cmd_str)
                for t in tokens:
                    if t.startswith("<") and t.endswith(">"):
                        txt.append(t, style=f"bold {P.warn} on {P.raised}")
                    else:
                        txt.append(t, style=f"bold {P.text_soft}")
                txt.append("\n")
                desc = item.get("desc", "")
                if desc:
                    txt.append(f"    • {desc}\n", style=f"{P.muted}")
                else:
                    txt.append("\n")
                cmd_list.append(DataListItem(data_obj=item["command"], display_text=txt))
        else:
            txt = Text("\n  • No matching commands found for current filter.\n  • Press Backspace to clear search.", style="dim italic")
            cmd_list.append(DataListItem(data_obj=None, display_text=txt, is_placeholder=True))


