"""Textual widgets and modal dialogs for CYB0X-S Worksheet."""

from __future__ import annotations

from typing import Any, Callable, List, Optional
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, ListItem, ListView, Static

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


class WorksheetHeader(Static):
    """Clean, high-density terminal header without loud safe-mode labels."""

    DEFAULT_CSS = """
    WorksheetHeader {
        height: 2;
        background: $surface-darken-2;
        color: $text;
        border-bottom: solid $primary 30%;
        padding: 0 2;
    }
    """

    def __init__(self, workspace_name: str = "default", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.workspace_name = workspace_name

    def render(self) -> Text:
        t = Text()
        t.append("CYB0X-S ", style="bold cyan")
        t.append("WORKSHEET", style="bold white")
        t.append("  │  ", style="dim")
        t.append("Field Notes & Methodology", style="dim italic")
        return t


class TargetInfoPanel(Static):
    """Displays compact, clean status for the currently active target."""

    DEFAULT_CSS = """
    TargetInfoPanel {
        height: 2;
        border-bottom: solid $secondary 25%;
        padding: 0 2;
        background: $surface-darken-1;
    }
    """

    target: Optional[Target] = None

    def update_target(self, target: Optional[Target]) -> None:
        self.target = target
        self.refresh()

    def render(self) -> Text:
        t = Text()
        if self.target:
            t.append("● ", style="bold green")
            scope_style = "bold green" if self.target.is_in_scope else "bold red"
            scope_txt = "[IN-SCOPE] " if self.target.is_in_scope else "[OUT-OF-SCOPE] "
            t.append(scope_txt, style=scope_style)
            t.append("TARGET: ", style="bold magenta")
            t.append(self.target.ip, style="bold white")
            if self.target.hostname:
                t.append(f" ({self.target.hostname})", style="cyan")
            if self.target.os and self.target.os != "Unknown":
                t.append(f" [{self.target.os}]", style="dim")

            # Flags indicators
            t.append("  │  ", style="dim")
            if self.target.user_flag:
                t.append("🏁 User: ", style="bold green")
                t.append(self.target.user_flag[:15] + ("..." if len(self.target.user_flag) > 15 else "") + " ", style="white")
            else:
                t.append("🏁 User: [ ] ", style="dim")

            if self.target.root_flag:
                t.append("👑 Root: ", style="bold yellow")
                t.append(self.target.root_flag[:15] + ("..." if len(self.target.root_flag) > 15 else "") + " ", style="bold white")
            else:
                t.append("👑 Root: [ ] ", style="dim")

            if self.target.initial_access_vuln:
                t.append(f" │ ⚡ {self.target.initial_access_vuln}", style="bold cyan")
        else:
            t.append("○ ", style="dim yellow")
            t.append("TARGET: ", style="bold yellow")
            t.append("No active target selected", style="yellow")
            t.append("  (Press 't' to add target or type ':t <ip>' in command bar)", style="dim")
        return t


class GuidanceDrawer(Static):
    """Dynamic command & methodology tips inspector for active checklist item."""

    DEFAULT_CSS = """
    GuidanceDrawer {
        height: 4;
        border: solid #30363d;
        background: #0d1117;
        padding: 0 1;
        margin-top: 1;
    }
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.item_title: str = ""
        self.target_ip: str = ""

    def update_guidance(self, item_title: str, target_ip: str = "") -> None:
        self.item_title = item_title
        self.target_ip = target_ip
        self.refresh()

    def render(self) -> Text:
        t = Text()
        if not self.item_title:
            t.append("💡 STEP GUIDANCE: ", style="bold cyan")
            t.append("Highlight any checklist item to inspect recommended commands & tips.\n", style="dim italic")
            t.append("Shortcuts: [Space] Cycle status  •  [Enter] Copy command  •  [y] Copy title", style="dim")
            return t

        from cyb0x_s.templates import get_template_guidance_for_title
        guidance = get_template_guidance_for_title(self.item_title)
        if guidance:
            cmd = guidance.get("command", "")
            tip = guidance.get("tip", "")
            if self.target_ip:
                cmd = cmd.replace("<TARGET_IP>", self.target_ip)
                cmd = cmd.replace("<TARGET_SUBNET>", f"{self.target_ip.rsplit('.', 1)[0]}.0/24")

            t.append("💡 CMD: ", style="bold green")
            t.append(f"{cmd}\n", style="bold white")
            t.append("ℹ️  TIP: ", style="bold yellow")
            t.append(f"{tip} ", style="dim")
            t.append("[Enter=Copy Cmd | Space=Cycle]", style="bold cyan")
        else:
            t.append("💡 STEP: ", style="bold cyan")
            t.append(f"{self.item_title}\n", style="white")
            t.append("Shortcuts: [Space] Cycle status  •  [y] Copy item  •  [d] Delete item", style="dim")
        return t


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


class SearchModal(ModalScreen):
    """Interactive global search modal (Ctrl+F or /)."""

    DEFAULT_CSS = """
    SearchModal {
        align: center middle;
    }
    #search-box {
        width: 80%;
        height: 80%;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }
    #search-input {
        margin-bottom: 1;
    }
    #search-results {
        height: 1fr;
        border: solid $secondary 40%;
    }
    #search-status {
        height: 1;
        margin-top: 1;
    }
    """

    def __init__(self, store: Any, on_select: Optional[Callable[[SearchMatch], None]] = None) -> None:
        super().__init__()
        self.store = store
        self.on_select = on_select
        self.matches: List[SearchMatch] = []

    def compose(self) -> ComposeResult:
        with Vertical(id="search-box"):
            yield Label("[bold cyan]SEARCH WORKSHEET[/bold cyan] [dim](Esc to close, y to copy item)[/dim]")
            yield Input(placeholder="Type keywords to search across notes, services, creds, findings...", id="search-input")
            yield ListView(id="search-results")
            yield Label("0 results", id="search-status")

    def on_mount(self) -> None:
        self.query_one("#search-input", Input).focus()

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
            txt.append(f"[{m.entity_type.upper()}] ", style="bold cyan")
            if m.target_ip:
                txt.append(f"{m.target_ip} ", style="magenta")
            txt.append(f"{m.title} — ", style="bold white")
            txt.append(m.snippet, style="dim")
            results_view.append(DataListItem(data_obj=m, display_text=txt))

    def on_key(self, event: Any) -> None:
        if event.key == "escape":
            self.dismiss(None)
        elif event.key == "y":
            results_view = self.query_one("#search-results", ListView)
            if results_view.highlighted_child and isinstance(results_view.highlighted_child, DataListItem):
                match = results_view.highlighted_child.data_obj
                if not results_view.highlighted_child.is_placeholder and match:
                    val = match.snippet or match.title
                    copy_to_clipboard(val)
                    self.notify(f"Copied: {val}")


class FastInputModal(ModalScreen[Optional[dict]]):
    """Generic quick-entry modal."""

    DEFAULT_CSS = """
    FastInputModal {
        align: center middle;
    }
    #input-container {
        width: 65%;
        height: auto;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }
    #modal-title {
        text-style: bold;
        margin-bottom: 1;
    }
    .input-field {
        margin-bottom: 1;
    }
    #button-bar {
        height: 3;
        margin-top: 1;
    }
    """

    def __init__(self, title: str, fields: List[tuple[str, str, str]]) -> None:
        super().__init__()
        self.modal_title = title
        self.fields = fields

    def compose(self) -> ComposeResult:
        with Vertical(id="input-container"):
            yield Label(f"[bold cyan]{self.modal_title}[/bold cyan]", id="modal-title")
            for key, label_text, default_val in self.fields:
                yield Label(label_text)
                yield Input(value=default_val, id=f"field-{key}", classes="input-field")
            with Horizontal(id="button-bar"):
                yield Button("Save (Enter)", variant="primary", id="btn-save")
                yield Button("Cancel (Esc)", variant="default", id="btn-cancel")

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
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="help-box"):
            yield Label("[bold cyan]CYB0X-S WORKSHEET — KEYBOARD REFERENCE[/bold cyan]\n")
            with VerticalScroll():
                text = """
[bold]Key Design Principle:[/bold]
The human decides and performs the security-testing actions. CYB0X-S records and organizes them.
Pure passive recording • Local-first SQLite store • Zero background scanning or AI.

[bold]Keyboard Navigation:[/bold]
  [cyan]Tab / Shift+Tab[/cyan]  : Move focus between worksheet panels
  [cyan]j / k or ↑ / ↓[/cyan]   : Navigate items in active panel
  [cyan]y[/cyan]                : Copy highlighted value (IP, port, secret, note text)
  [cyan]Space[/cyan]            : Cycle checklist status (TODO → CHECKED → DEFERRED → DEAD-END)
                     or toggle credential password mask
  [cyan]/ or Ctrl+F[/cyan]      : Global search across all recorded data
  [cyan]t[/cyan]                : Add or switch target machine
  [cyan]s[/cyan]                : Add service to current target
  [cyan]f[/cyan]                : Record security finding
  [cyan]c[/cyan]                : Record credential
  [cyan]n[/cyan]                : Add field note
  [cyan]k[/cyan]                : Add checklist item
  [cyan]m[/cyan]                : Apply static methodology checklist template
  [cyan]d[/cyan]                : Delete highlighted item
  [cyan]?[/cyan]                : Open this help dialog
  [cyan]q[/cyan]                : Quit worksheet

[bold]Fast Capture Commands (Bottom Bar / Shell):[/bold]
  cyb0x-s target 10.10.10.20
  cyb0x-s service 10.10.10.20 445/tcp SMB --version "Samba 4.3"
  cyb0x-s finding "SMB anonymous access enabled" --severity HIGH
  cyb0x-s cred admin:password --source backup.zip
  cyb0x-s checklist template smb
  cyb0x-s checklist check "null session"
  cyb0x-s note "backup share contains archive.zip"
  cyb0x-s export --format md -o notes.md

Press [bold]Esc[/bold] or [bold]q[/bold] to return to worksheet.
"""
                yield Static(text)
            yield Button("Close", id="btn-close", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(None)

    def on_key(self, event: Any) -> None:
        if event.key in ("escape", "q", "enter"):
            self.dismiss(None)


class TemplateSelectionModal(ModalScreen[Optional[str]]):
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
            yield Label("[bold cyan]METHODOLOGY CHECKLIST TEMPLATES[/bold cyan] [dim](eJPTv2 & Reddit Curated)[/dim]")
            yield Label("[dim]Select a template using ↑ / ↓ and press Enter (or click Apply)[/dim]")
            yield ListView(id="template-list")
            with Horizontal(id="btn-bar"):
                yield Button("Apply Template (Enter)", variant="primary", id="btn-apply")
                yield Button("Cancel (Esc)", variant="default", id="btn-cancel")

    def on_mount(self) -> None:
        from cyb0x_s.templates import STATIC_TEMPLATES

        t_list = self.query_one("#template-list", ListView)
        for key, tmpl in STATIC_TEMPLATES.items():
            txt = Text()
            txt.append(f"{key.upper():<16} ", style="bold cyan")
            txt.append(f"({len(tmpl['items'])} items)  ", style="bold yellow")
            txt.append(f"{tmpl['description']}", style="dim")
            t_list.append(DataListItem(data_obj=key, display_text=txt))
        t_list.focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-apply":
            self._select_current()
        else:
            self.dismiss(None)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if isinstance(event.item, DataListItem):
            self.dismiss(event.item.data_obj)

    def _select_current(self) -> None:
        t_list = self.query_one("#template-list", ListView)
        if t_list.highlighted_child and isinstance(t_list.highlighted_child, DataListItem):
            self.dismiss(t_list.highlighted_child.data_obj)
        else:
            self.dismiss(None)

    def on_key(self, event: Any) -> None:
        if event.key == "escape":
            self.dismiss(None)
        elif event.key == "enter":
            self._select_current()


class ReferenceModal(ModalScreen[Optional[str]]):
    """Searchable command reference and playbook modal (dev-angelist / eJPTv2 curated)."""

    DEFAULT_CSS = """
    ReferenceModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.75);
    }
    #ref-box {
        width: 85%;
        height: 85%;
        border: thick #58a6ff;
        background: #161b22;
        padding: 1 2;
    }
    #ref-filter-input {
        margin-top: 1;
        margin-bottom: 1;
        border: solid #30363d;
        background: #0d1117;
    }
    #ref-list {
        height: 1fr;
        border: solid #30363d;
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
            yield Label("[bold cyan]📖 eJPTv2 CHEAT SHEET & COMMAND REFERENCE[/bold cyan] [dim](Offline Playbook)[/dim]")
            yield Label(f"[dim]Target IP: [bold]{self.target_ip or 'None'}[/bold] • Type to filter, Enter to copy command, Esc to exit[/dim]")
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
                txt.append(f"[{item['category']}] ", style="bold magenta")
                txt.append(f"{item['title']}\n", style="bold white")
                txt.append(f"  ❯ {item['command']}\n", style="bold yellow")
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
        border: solid #30363d;
        background: #161b22;
    }
    #playbook-body {
        height: 1fr;
        layout: horizontal;
    }
    #playbook-cat-panel {
        width: 25%;
        height: 1fr;
        border: round #30363d;
        background: #161b22;
        padding: 0 1;
        margin-right: 1;
    }
    #playbook-cmd-panel {
        width: 75%;
        height: 1fr;
        border: round #30363d;
        background: #161b22;
        padding: 0 1;
    }
    .panel-hdr {
        text-style: bold;
        color: #79c0ff;
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

        all_txt = Text(f"★ ALL PLAYBOOKS ({len(REFERENCE_PLAYBOOK)})", style="bold cyan")
        cat_list.append(DataListItem(data_obj="ALL", display_text=all_txt))

        for cat, cnt in sorted(counts.items()):
            txt = Text(f"• {cat} ({cnt})", style="bold white")
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
                txt.append(f"[{item['category']}] ", style="bold magenta")
                txt.append(f"{item['title']}\n", style="bold white")
                txt.append(f"  ❯ {item['command']}\n", style="bold yellow")
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
        height: auto;
        layout: horizontal;
        margin-bottom: 1;
    }
    .loot-box {
        width: 1fr;
        border: round #30363d;
        background: #161b22;
        padding: 1;
        margin-right: 1;
    }
    #loot-failure-box {
        height: 1fr;
        border: round #30363d;
        background: #161b22;
        padding: 0 1;
    }
    .loot-title {
        text-style: bold;
        color: #79c0ff;
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
            f_txt.append("User Flag: ", style="bold cyan")
            f_txt.append(f"{target.user_flag or '<NOT CAPTURED YET>'}\n", style="bold green" if target.user_flag else "dim")
            f_txt.append("Root Flag: ", style="bold yellow")
            f_txt.append(f"{target.root_flag or '<NOT CAPTURED YET>'}\n\n", style="bold green" if target.root_flag else "dim")
            f_txt.append("[Press 'g' or type :uflag / :rflag to set flags]", style="dim italic")
        else:
            f_txt.append("No active target selected.", style="dim italic")
        self.query_one("#loot-flags-content", Static).update(f_txt)

        # Foothold Card
        fh_txt = Text()
        if target and (target.initial_access_vuln or target.foothold_cmd):
            fh_txt.append("Vulnerability: ", style="bold cyan")
            fh_txt.append(f"{target.initial_access_vuln or 'N/A'}\n", style="white")
            fh_txt.append("Context: ", style="bold cyan")
            fh_txt.append(f"{target.foothold_context or 'N/A'}\n", style="white")
            fh_txt.append(f"Command:\n❯ {target.foothold_cmd or 'N/A'}", style="bold yellow")
        else:
            fh_txt.append("No foothold recorded yet.\nType :foothold <vuln> to record.", style="dim italic")
        self.query_one("#loot-foothold-content", Static).update(fh_txt)

        # PrivEsc Card
        pe_txt = Text()
        if target and (target.privesc_vector or target.root_proof):
            pe_txt.append("PrivEsc Vector: ", style="bold cyan")
            pe_txt.append(f"{target.privesc_vector or 'N/A'}\n", style="white")
            pe_txt.append(f"Root Proof:\n❯ {target.root_proof or 'whoami && id && ip a'}", style="bold yellow")
        else:
            pe_txt.append("No PrivEsc recorded yet.\nType :privesc <vector> to record.", style="dim italic")
        self.query_one("#loot-privesc-content", Static).update(pe_txt)

        # Failure Log List
        f_list = self.query_one("#loot-failure-list", ListView)
        f_list.clear()
        if failures:
            for fl in failures:
                txt = Text()
                txt.append("🕳️ [DEAD-END] ", style="bold red")
                txt.append(f"{fl.where_stuck}\n", style="white")
                if fl.breakthrough_clue:
                    txt.append(f"   🔑 Breakthrough Clue: {fl.breakthrough_clue}\n", style="bold green")
                if fl.rule_for_next_time:
                    txt.append(f"   📌 Permanent Rule: {fl.rule_for_next_time}", style="dim italic")
                f_list.append(DataListItem(data_obj=fl, display_text=txt))
        else:
            txt = Text("  • No rabbit holes or failure logs recorded. Type :stuck <where> / :clue <breakthrough>", style="dim italic")
            f_list.append(DataListItem(data_obj=None, display_text=txt, is_placeholder=True))



