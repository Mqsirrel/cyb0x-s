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
            t.append("TARGET: ", style="bold magenta")
            t.append(self.target.ip, style="bold white")
            if self.target.hostname:
                t.append(f" ({self.target.hostname})", style="cyan")
            if self.target.os and self.target.os != "Unknown":
                t.append(f" [{self.target.os}]", style="dim")
            if self.target.notes:
                t.append(f"  •  {self.target.notes}", style="dim italic")
        else:
            t.append("○ ", style="dim yellow")
            t.append("TARGET: ", style="bold yellow")
            t.append("No active target selected", style="yellow")
            t.append("  (Press 't' to add a target or type ':t <ip>' in command bar)", style="dim")
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
        font-weight: bold;
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
