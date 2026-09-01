"""Main Textual application for CYB0X-S (Safe Field Notebook).

Keyboard-driven, high-speed, human-controlled terminal interface.
"""

from __future__ import annotations

from typing import Any, List, Optional, Set
from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.widgets import Footer, Input, Label, ListItem, ListView, Static, Tab, Tabs

from cyb0x_s.clipboard import copy_to_clipboard, extract_copy_value
from cyb0x_s.db.store import NotebookStore
from cyb0x_s.models import (
    ChecklistItem,
    ChecklistStatus,
    Credential,
    Evidence,
    Finding,
    Note,
    Service,
    Target,
)
from cyb0x_s.templates import apply_template_to_store, get_available_templates
from cyb0x_s.tui.widgets import (
    DataListItem,
    FastInputModal,
    HelpModal,
    SafeHeader,
    SearchModal,
    TargetInfoPanel,
)


class CyboxSafeApp(App):
    """CYB0X-S Terminal Field Notebook Application."""

    TITLE = "CYB0X-S — SAFE FIELD NOTEBOOK"
    SUB_TITLE = "Human-controlled • Passive recording"

    BINDINGS = [
        Binding("q", "quit", "Quit", priority=True),
        Binding("y", "copy_selected", "Copy", priority=True),
        Binding("space", "toggle_selected", "Toggle", priority=True),
        Binding("slash", "open_search", "Search"),
        Binding("ctrl+f", "open_search", "Search"),
        Binding("t", "add_target", "Target"),
        Binding("s", "add_service", "Service"),
        Binding("f", "add_finding", "Finding"),
        Binding("c", "add_credential", "Cred"),
        Binding("n", "add_note", "Note"),
        Binding("k", "add_checklist", "Checklist"),
        Binding("m", "apply_template", "Template"),
        Binding("d", "delete_selected", "Delete"),
        Binding("question_mark", "show_help", "Help"),
    ]

    CSS = """
    Screen {
        layout: vertical;
        background: $background;
    }
    #target-bar {
        height: 3;
        background: $surface;
        border-bottom: solid $secondary;
    }
    #main-container {
        height: 1fr;
        layout: horizontal;
    }
    .column {
        width: 1fr;
        height: 1fr;
        padding: 0 1;
    }
    .panel-box {
        border: round $primary;
        height: 1fr;
        margin-bottom: 1;
        padding: 0 1;
        background: $surface-darken-1;
    }
    .panel-header {
        text-style: bold;
        color: $accent;
        padding: 0 1;
        background: $surface;
    }
    .panel-list {
        height: 1fr;
    }
    #cmd-input-bar {
        height: 3;
        border-top: solid $secondary;
        padding: 0 1;
        background: $surface;
    }
    #cmd-input {
        width: 1fr;
    }
    """

    def __init__(self, store: Optional[NotebookStore] = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.store = store or NotebookStore()
        self.revealed_creds: Set[int] = set()

    def compose(self) -> ComposeResult:
        yield SafeHeader()
        yield TargetInfoPanel(id="target-info")
        with Horizontal(id="target-bar"):
            yield Tabs(id="target-tabs")
        with Horizontal(id="main-container"):
            with Vertical(classes="column"):
                with Vertical(classes="panel-box"):
                    yield Label("SERVICES", classes="panel-header")
                    yield ListView(id="list-services", classes="panel-list")
                with Vertical(classes="panel-box"):
                    yield Label("FINDINGS", classes="panel-header")
                    yield ListView(id="list-findings", classes="panel-list")
                with Vertical(classes="panel-box"):
                    yield Label("CREDENTIALS (Space to reveal)", classes="panel-header")
                    yield ListView(id="list-creds", classes="panel-list")
            with Vertical(classes="column"):
                with Vertical(classes="panel-box"):
                    yield Label("CHECKLIST (Space to cycle)", classes="panel-header")
                    yield ListView(id="list-checklist", classes="panel-list")
                with Vertical(classes="panel-box"):
                    yield Label("NOTES", classes="panel-header")
                    yield ListView(id="list-notes", classes="panel-list")
                with Vertical(classes="panel-box"):
                    yield Label("EVIDENCE", classes="panel-header")
                    yield ListView(id="list-evidence", classes="panel-list")
        with Horizontal(id="cmd-input-bar"):
            yield Label("[dim]:n Note | :f Finding | :s Port/Proto Service | :c User:Pass[/dim]  ", id="cmd-label")
            yield Input(placeholder="Quick command or :n <note> (press Enter)", id="cmd-input")
        yield Footer()

    def on_mount(self) -> None:
        self.refresh_targets()
        self.refresh_all()

    # -------------------------------------------------------------------------
    # Target Management & Tabs
    # -------------------------------------------------------------------------

    def refresh_targets(self) -> None:
        """Update target tabs and active target panel."""
        tabs = self.query_one("#target-tabs", Tabs)
        tabs.clear()
        targets = self.store.list_targets()
        active = self.store.get_active_target()

        if targets:
            active_tab_id = None
            for t in targets:
                tab_id = f"target-{t.id}"
                label = f"{t.ip} ({t.hostname})" if t.hostname else t.ip
                tabs.add_tab(Tab(label, id=tab_id))
                if active and active.id == t.id:
                    active_tab_id = tab_id
            if active_tab_id:
                tabs.active = active_tab_id

        target_panel = self.query_one("#target-info", TargetInfoPanel)
        target_panel.update_target(active)

    def on_tabs_tab_activated(self, event: Tabs.TabActivated) -> None:
        """Switch active target when tab changes."""
        if event.tab and event.tab.id and event.tab.id.startswith("target-"):
            try:
                t_id = int(event.tab.id.split("-")[1])
                self.store.set_active_target(t_id)
                active = self.store.get_target(t_id)
                self.query_one("#target-info", TargetInfoPanel).update_target(active)
                self.refresh_all()
            except (ValueError, IndexError):
                pass

    # -------------------------------------------------------------------------
    # List Population
    # -------------------------------------------------------------------------

    def refresh_all(self) -> None:
        """Refresh all data lists from the database."""
        active_target = self.store.get_active_target()
        target_id = active_target.id if active_target else None
        target_ip = active_target.ip if active_target else None

        # 1. Services
        svc_list = self.query_one("#list-services", ListView)
        svc_list.clear()
        if target_id is not None:
            services = self.store.list_services(target_id=target_id)
            for s in services:
                txt = Text()
                if s.status.value == "CHECKED":
                    txt.append("✓ ", style="bold green")
                elif s.status.value == "DEFERRED":
                    txt.append("~ ", style="bold yellow")
                elif s.status.value == "DEAD-END":
                    txt.append("✗ ", style="bold red")
                else:
                    txt.append("→ ", style="bold cyan")
                txt.append(f"{s.port}/{s.protocol:<4} ", style="bold white")
                txt.append(f"{s.service:<10} ", style="cyan")
                if s.version:
                    txt.append(f"{s.version} ", style="dim")
                if s.notes:
                    txt.append(f"({s.notes})", style="italic dim")
                svc_list.append(DataListItem(data_obj=s, display_text=txt))

        # 2. Findings
        f_list = self.query_one("#list-findings", ListView)
        f_list.clear()
        findings = self.store.list_findings(target_id=target_id)
        for f in findings:
            txt = Text()
            txt.append("• ", style="bold yellow")
            txt.append(f.title, style="bold white")
            if f.severity:
                txt.append(f" [{f.severity}]", style="bold magenta")
            if f.description:
                txt.append(f" — {f.description}", style="dim")
            f_list.append(DataListItem(data_obj=f, display_text=txt))

        # 3. Credentials
        c_list = self.query_one("#list-creds", ListView)
        c_list.clear()
        creds = self.store.list_credentials(target_id=target_id)
        for c in creds:
            txt = Text()
            txt.append("• ", style="bold green")
            txt.append(f"{c.username} : ", style="bold cyan")
            secret = c.secret if c.id in self.revealed_creds else c.masked_secret
            txt.append(secret, style="bold white")
            if c.source:
                txt.append(f" ({c.source})", style="dim")
            c_list.append(DataListItem(data_obj=c, display_text=txt))

        # 4. Checklist
        ck_list = self.query_one("#list-checklist", ListView)
        ck_list.clear()
        items = self.store.list_checklist_items(target_id=target_id)
        for item in items:
            txt = Text()
            if item.status == ChecklistStatus.CHECKED:
                txt.append("[✓] ", style="bold green")
            elif item.status == ChecklistStatus.DEFERRED:
                txt.append("[~] ", style="bold yellow")
            elif item.status == ChecklistStatus.DEAD_END:
                txt.append("[✗] ", style="bold red")
            else:
                txt.append("[ ] ", style="bold white")
            txt.append(item.title, style="white")
            if item.category and item.category != "ENUMERATION":
                txt.append(f" ({item.category})", style="dim")
            ck_list.append(DataListItem(data_obj=item, display_text=txt))

        # 5. Notes
        n_list = self.query_one("#list-notes", ListView)
        n_list.clear()
        notes = self.store.list_notes(target_id=target_id)
        for n in notes:
            txt = Text()
            txt.append("> ", style="bold magenta")
            txt.append(n.content, style="white")
            n_list.append(DataListItem(data_obj=n, display_text=txt))

        # 6. Evidence
        ev_list = self.query_one("#list-evidence", ListView)
        ev_list.clear()
        evidences = self.store.list_evidence(target_id=target_id)
        for ev in evidences:
            txt = Text()
            txt.append(f"[{ev.evidence_type}] ", style="bold cyan")
            txt.append(ev.path_or_ref, style="bold white")
            if ev.description:
                txt.append(f" — {ev.description}", style="dim")
            ev_list.append(DataListItem(data_obj=ev, display_text=txt))

    # -------------------------------------------------------------------------
    # Hotkey Actions
    # -------------------------------------------------------------------------

    def action_copy_selected(self) -> None:
        """Copy the value of the currently highlighted list item."""
        focused = self.focused
        if isinstance(focused, ListView) and focused.highlighted_child:
            item = focused.highlighted_child
            if isinstance(item, DataListItem):
                active = self.store.get_active_target()
                target_ip = active.ip if active else None
                val = extract_copy_value(item.data_obj, target_ip=target_ip)
                if val:
                    copy_to_clipboard(val)
                    self.notify(f"Copied: {val}")
                    return
        self.notify("Select an item to copy (y)")

    def action_toggle_selected(self) -> None:
        """Toggle checklist status or credential reveal."""
        focused = self.focused
        if isinstance(focused, ListView) and focused.highlighted_child:
            item = focused.highlighted_child
            if isinstance(item, DataListItem):
                obj = item.data_obj
                if isinstance(obj, ChecklistItem):
                    self.store.cycle_checklist_status(obj.id)
                    self.refresh_all()
                    return
                elif isinstance(obj, Credential):
                    if obj.id in self.revealed_creds:
                        self.revealed_creds.remove(obj.id)
                    else:
                        self.revealed_creds.add(obj.id)
                    self.refresh_all()
                    return

    def action_delete_selected(self) -> None:
        """Delete highlighted item."""
        focused = self.focused
        if isinstance(focused, ListView) and focused.highlighted_child:
            item = focused.highlighted_child
            if isinstance(item, DataListItem):
                obj = item.data_obj
                if isinstance(obj, Service):
                    self.store.delete_service(obj.id)
                elif isinstance(obj, Finding):
                    self.store.delete_finding(obj.id)
                elif isinstance(obj, Credential):
                    self.store.delete_credential(obj.id)
                elif isinstance(obj, ChecklistItem):
                    self.store.delete_checklist_item(obj.id)
                elif isinstance(obj, Note):
                    self.store.delete_note(obj.id)
                elif isinstance(obj, Evidence):
                    self.store.delete_evidence(obj.id)
                self.notify("Item deleted")
                self.refresh_all()

    def action_open_search(self) -> None:
        """Open global search dialog."""
        self.push_screen(SearchModal(store=self.store))

    def action_show_help(self) -> None:
        """Open help sheet."""
        self.push_screen(HelpModal())

    # -------------------------------------------------------------------------
    # Add Item Modals
    # -------------------------------------------------------------------------

    def action_add_target(self) -> None:
        def on_result(data: Optional[dict]) -> None:
            if data and data.get("ip"):
                self.store.add_target(
                    ip=data["ip"],
                    hostname=data.get("hostname", ""),
                    os_name=data.get("os", "Unknown") or "Unknown",
                    notes=data.get("notes", ""),
                )
                self.refresh_targets()
                self.refresh_all()
                self.notify(f"Target {data['ip']} added")

        self.push_screen(
            FastInputModal(
                title="Add Target",
                fields=[
                    ("ip", "Target IP / Hostname *", ""),
                    ("hostname", "FQDN / NetBIOS name", ""),
                    ("os", "Operating System", "Linux"),
                    ("notes", "Target Notes", ""),
                ],
            ),
            callback=on_result,
        )

    def action_add_service(self) -> None:
        active = self.store.get_active_target()
        if not active:
            self.notify("Create a target first (Press 't')", severity="warning")
            return

        def on_result(data: Optional[dict]) -> None:
            if data and data.get("port"):
                try:
                    port = int(data["port"])
                    self.store.add_service(
                        target_id=active.id,
                        port=port,
                        protocol=data.get("protocol", "tcp") or "tcp",
                        service=data.get("service", "unknown") or "unknown",
                        version=data.get("version", ""),
                        notes=data.get("notes", ""),
                    )
                    self.refresh_all()
                    self.notify(f"Service {port} added")
                except ValueError:
                    self.notify("Port must be an integer", severity="error")

        self.push_screen(
            FastInputModal(
                title=f"Add Service for {active.ip}",
                fields=[
                    ("port", "Port Number *", "80"),
                    ("protocol", "Protocol (tcp/udp)", "tcp"),
                    ("service", "Service Name (e.g. HTTP, SSH)", "HTTP"),
                    ("version", "Version / Banner", ""),
                    ("notes", "Observations", ""),
                ],
            ),
            callback=on_result,
        )

    def action_add_finding(self) -> None:
        active = self.store.get_active_target()
        target_id = active.id if active else None

        def on_result(data: Optional[dict]) -> None:
            if data and data.get("title"):
                self.store.add_finding(
                    title=data["title"],
                    target_id=target_id,
                    description=data.get("desc", ""),
                    severity=data.get("severity") or None,
                    notes=data.get("notes", ""),
                )
                self.refresh_all()
                self.notify("Finding recorded")

        self.push_screen(
            FastInputModal(
                title="Record Finding",
                fields=[
                    ("title", "Finding Title *", ""),
                    ("desc", "Description", ""),
                    ("severity", "Severity (INFO, LOW, MEDIUM, HIGH, CRITICAL)", ""),
                    ("notes", "Notes", ""),
                ],
            ),
            callback=on_result,
        )

    def action_add_credential(self) -> None:
        active = self.store.get_active_target()
        target_id = active.id if active else None

        def on_result(data: Optional[dict]) -> None:
            if data and data.get("username"):
                self.store.add_credential(
                    username=data["username"],
                    secret=data.get("secret", ""),
                    source=data.get("source", ""),
                    target_id=target_id,
                    service_scope=data.get("scope", ""),
                )
                self.refresh_all()
                self.notify("Credential saved")

        self.push_screen(
            FastInputModal(
                title="Record Credential",
                fields=[
                    ("username", "Username *", ""),
                    ("secret", "Password / Hash / Secret *", ""),
                    ("source", "Source (e.g. shadow, backup.zip)", ""),
                    ("scope", "Service Scope (e.g. SSH, SMB)", ""),
                ],
            ),
            callback=on_result,
        )

    def action_add_note(self) -> None:
        active = self.store.get_active_target()
        target_id = active.id if active else None

        def on_result(data: Optional[dict]) -> None:
            if data and data.get("content"):
                self.store.add_note(content=data["content"], target_id=target_id)
                self.refresh_all()
                self.notify("Note recorded")

        self.push_screen(
            FastInputModal(
                title="Record Field Note",
                fields=[
                    ("content", "Note Content *", ""),
                ],
            ),
            callback=on_result,
        )

    def action_add_checklist(self) -> None:
        active = self.store.get_active_target()
        target_id = active.id if active else None

        def on_result(data: Optional[dict]) -> None:
            if data and data.get("title"):
                self.store.add_checklist_item(
                    title=data["title"],
                    category=data.get("category", "ENUMERATION") or "ENUMERATION",
                    target_id=target_id,
                )
                self.refresh_all()
                self.notify("Checklist item added")

        self.push_screen(
            FastInputModal(
                title="Add Checklist Item",
                fields=[
                    ("title", "Checklist Item *", ""),
                    ("category", "Category", "ENUMERATION"),
                ],
            ),
            callback=on_result,
        )

    def action_apply_template(self) -> None:
        active = self.store.get_active_target()
        target_id = active.id if active else None
        avail = ", ".join(get_available_templates())

        def on_result(data: Optional[dict]) -> None:
            if data and data.get("template"):
                tmpl_name = data["template"].strip().lower()
                try:
                    items = apply_template_to_store(self.store, tmpl_name, target_id=target_id)
                    self.refresh_all()
                    self.notify(f"Applied template '{tmpl_name}' ({len(items)} items)")
                except ValueError as e:
                    self.notify(str(e), severity="error")

        self.push_screen(
            FastInputModal(
                title=f"Apply Static Methodology Template ({avail})",
                fields=[
                    ("template", f"Template Name ({avail})", "linux"),
                ],
            ),
            callback=on_result,
        )

    # -------------------------------------------------------------------------
    # Quick Command Line Input Handling
    # -------------------------------------------------------------------------

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle quick command bar submission."""
        val = event.value.strip()
        inp = self.query_one("#cmd-input", Input)
        inp.value = ""

        if not val:
            return

        active = self.store.get_active_target()
        target_id = active.id if active else None

        if val.startswith(":n "):
            # Quick note
            note_text = val[3:].strip()
            self.store.add_note(content=note_text, target_id=target_id)
            self.notify(f"Note added: {note_text}")
        elif val.startswith(":f "):
            # Quick finding
            finding_text = val[3:].strip()
            self.store.add_finding(title=finding_text, target_id=target_id)
            self.notify(f"Finding added: {finding_text}")
        elif val.startswith(":c "):
            # Quick cred
            cred_str = val[3:].strip()
            if ":" in cred_str:
                u, p = cred_str.split(":", 1)
            else:
                u, p = cred_str, ""
            self.store.add_credential(username=u, secret=p, target_id=target_id)
            self.notify(f"Cred added: {u}")
        elif val.startswith(":t "):
            # Quick target
            ip = val[3:].strip()
            self.store.add_target(ip=ip)
            self.refresh_targets()
            self.notify(f"Target added: {ip}")
        elif val.startswith(":s "):
            # Quick service :s 445/tcp SMB
            parts = val[3:].strip().split()
            if parts and active:
                port_proto = parts[0]
                svc_name = parts[1] if len(parts) > 1 else "unknown"
                proto = "tcp"
                if "/" in port_proto:
                    port_str, proto = port_proto.split("/", 1)
                else:
                    port_str = port_proto
                try:
                    self.store.add_service(
                        target_id=active.id,
                        port=int(port_str),
                        protocol=proto,
                        service=svc_name,
                    )
                    self.notify(f"Service added: {port_str}/{proto} {svc_name}")
                except ValueError:
                    self.notify("Invalid port", severity="error")
        elif val.startswith("/"):
            # Trigger search
            self.action_open_search()
            return
        elif val == ":q":
            self.exit()
            return
        else:
            # Treat bare text as a field note
            self.store.add_note(content=val, target_id=target_id)
            self.notify(f"Note added: {val}")

        self.refresh_all()
