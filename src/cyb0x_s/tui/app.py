"""Main Textual application for CYB0X-S Worksheet.

High-efficiency, keyboard-driven terminal field worksheet for security testing observations.
Strictly passive: stores human-discovered data, never attacks or generates autonomous steps.
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
    FailureLog,
    Finding,
    Lead,
    Note,
    Service,
    Target,
)
from cyb0x_s.templates import (
    apply_template_to_store,
    get_available_templates,
    get_template_guidance_for_title,
)
from cyb0x_s.tui.widgets import (
    DataListItem,
    FastInputModal,
    GuidanceDrawer,
    HelpModal,
    SearchModal,
    TargetInfoPanel,
    TemplateSelectionModal,
    WorksheetHeader,
)


class CyboxSafeApp(App):
    """CYB0X-S Terminal Field Worksheet Application."""

    TITLE = "CYB0X-S Worksheet"
    SUB_TITLE = "Field Notes & Methodology Roadmap"

    BINDINGS = [
        Binding("q", "quit", "Quit", priority=True),
        Binding("y", "copy_selected", "Copy", priority=True),
        Binding("space", "toggle_selected", "Toggle", priority=True),
        Binding("enter", "activate_selected", "Action"),
        Binding("z", "toggle_zoom", "Zoom"),
        Binding("g", "record_flags", "Flags", priority=True),
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
        background: #0d1117;
    }
    #target-bar {
        height: 3;
        background: #161b22;
        border-bottom: solid #30363d;
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
        border: round #30363d;
        background: #161b22;
        margin-bottom: 1;
        padding: 0 1;
    }
    .panel-box:focus-within {
        border: round #58a6ff;
        background: #1c2128;
    }
    #panel-services {
        height: 55%;
    }
    #panel-intel {
        height: 45%;
        border: none;
        background: transparent;
        padding: 0;
        margin-bottom: 0;
    }
    #panel-findings {
        height: 1fr;
        margin-bottom: 1;
    }
    #panel-creds {
        height: 1fr;
    }
    #panel-checklist {
        height: 62%;
    }
    #panel-notes {
        height: 38%;
    }
    .panel-header {
        text-style: bold;
        color: #79c0ff;
        padding: 0 1;
        height: 1;
    }
    .panel-list {
        height: 1fr;
    }
    #cmd-input-bar {
        height: 3;
        border-top: solid #30363d;
        padding: 0 1;
        background: #161b22;
        layout: horizontal;
        align: left middle;
    }
    #cmd-prompt {
        width: 3;
        padding-top: 1;
    }
    #cmd-input {
        width: 1fr;
        border: none;
        background: transparent;
    }
    #cmd-input:focus {
        border: none;
    }
    .maximized {
        width: 100% !important;
        height: 100% !important;
        border: double #58a6ff !important;
        layer: top;
    }
    """

    def __init__(self, store: Optional[NotebookStore] = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.store = store or NotebookStore()
        self.revealed_creds: Set[int] = set()
        self.is_zoomed: bool = False
        self.zoomed_widget: Optional[Vertical] = None

    def compose(self) -> ComposeResult:
        active_ws = self.store.get_active_workspace()
        yield WorksheetHeader(workspace_name=active_ws.name if active_ws else "default")
        yield TargetInfoPanel(id="target-info")
        with Horizontal(id="target-bar"):
            yield Tabs(id="target-tabs")
        with Horizontal(id="main-container"):
            # Left column: Recon & Intel (Services on top, Findings + Creds below)
            with Vertical(id="col-left", classes="column"):
                with Vertical(id="panel-services", classes="panel-box"):
                    yield Label("SERVICES & PORTS", id="hdr-services", classes="panel-header")
                    yield ListView(id="list-services", classes="panel-list")
                with Vertical(id="panel-intel"):
                    with Vertical(id="panel-findings", classes="panel-box"):
                        yield Label("FINDINGS", id="hdr-findings", classes="panel-header")
                        yield ListView(id="list-findings", classes="panel-list")
                    with Vertical(id="panel-creds", classes="panel-box"):
                        yield Label("CREDENTIAL VAULT", id="hdr-creds", classes="panel-header")
                        yield ListView(id="list-creds", classes="panel-list")
            # Right column: Methodology & Notes
            with Vertical(id="col-right", classes="column"):
                with Vertical(id="panel-checklist", classes="panel-box"):
                    yield Label("METHODOLOGY ROADMAP", id="hdr-checklist", classes="panel-header")
                    yield ListView(id="list-checklist", classes="panel-list")
                    yield GuidanceDrawer(id="guidance-box")
                with Vertical(id="panel-notes", classes="panel-box"):
                    yield Label("FIELD NOTES & EVIDENCE", id="hdr-notes", classes="panel-header")
                    yield ListView(id="list-notes", classes="panel-list")
        with Horizontal(id="cmd-input-bar"):
            yield Label("[bold cyan]❯[/bold cyan] ", id="cmd-prompt")
            yield Input(
                placeholder="Quick cmd: :s port/proto svc | :uflag <hash> | :rflag <hash> | :c user:pass | :n note | / search...",
                id="cmd-input",
            )
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
        target_bar = self.query_one("#target-bar", Horizontal)
        tabs.clear()
        targets = self.store.list_targets()
        active = self.store.get_active_target()

        if len(targets) > 1:
            target_bar.styles.display = "block"
            active_tab_id = None
            for t in targets:
                tab_id = f"target-{t.id}"
                label = f"{t.ip} ({t.hostname})" if t.hostname else t.ip
                tabs.add_tab(Tab(label, id=tab_id))
                if active and active.id == t.id:
                    active_tab_id = tab_id
            if active_tab_id:
                tabs.active = active_tab_id
        else:
            target_bar.styles.display = "none"

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
    # Checklist Selection & Live Guidance Drawer
    # -------------------------------------------------------------------------

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        """Update guidance drawer when a checklist item is highlighted."""
        if event.list_view.id == "list-checklist" and event.item:
            item = event.item
            if isinstance(item, DataListItem) and not item.is_placeholder and item.data_obj:
                obj = item.data_obj
                active = self.store.get_active_target()
                target_ip = active.ip if active else ""
                title = obj.title if isinstance(obj, ChecklistItem) else str(obj)
                guidance_box = self.query_one("#guidance-box", GuidanceDrawer)
                guidance_box.update_guidance(title, target_ip=target_ip)

    # -------------------------------------------------------------------------
    # List Population with Clear Formatting
    # -------------------------------------------------------------------------

    def refresh_all(self) -> None:
        """Refresh all data lists from the database."""
        active_target = self.store.get_active_target()
        target_id = active_target.id if active_target else None

        # 1. Services & Ports (Notion 01 format with Potential and Next Action)
        svc_list = self.query_one("#list-services", ListView)
        svc_list.clear()
        services = self.store.list_services(target_id=target_id) if target_id else []
        self.query_one("#hdr-services", Label).update(
            f"SERVICES & PORTS ({len(services)})" if services else "SERVICES & PORTS"
        )
        if services:
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
                txt.append(f"{s.service:<10} ", style="bold cyan")
                if s.access_potential in ("HIGH", "CRITICAL"):
                    txt.append(f"[{s.access_potential}] ", style="bold red")
                elif s.access_potential == "LOW":
                    txt.append("[LOW] ", style="dim")
                if s.version:
                    txt.append(f"{s.version} ", style="bright_white")
                if s.next_action:
                    txt.append(f"→ `{s.next_action}` ", style="bold yellow")
                if s.notes:
                    txt.append(f"({s.notes})", style="dim italic")
                svc_list.append(DataListItem(data_obj=s, display_text=txt))
        else:
            txt = Text("  • No services recorded (Press 's' to add or type ':s 80/tcp http')", style="dim italic")
            svc_list.append(DataListItem(data_obj=None, display_text=txt, is_placeholder=True))

        # 2. Findings
        f_list = self.query_one("#list-findings", ListView)
        f_list.clear()
        findings = self.store.list_findings(target_id=target_id)
        self.query_one("#hdr-findings", Label).update(
            f"FINDINGS ({len(findings)})" if findings else "FINDINGS"
        )
        if findings:
            for f in findings:
                txt = Text()
                txt.append("• ", style="bold yellow")
                txt.append(f.title, style="bold white")
                if f.severity:
                    txt.append(f" [{f.severity}]", style="bold magenta")
                if f.description:
                    txt.append(f" — {f.description}", style="dim")
                f_list.append(DataListItem(data_obj=f, display_text=txt))
        else:
            txt = Text("  • No findings recorded (Press 'f' to add)", style="dim italic")
            f_list.append(DataListItem(data_obj=None, display_text=txt, is_placeholder=True))

        # 3. Credentials
        c_list = self.query_one("#list-creds", ListView)
        c_list.clear()
        creds = self.store.list_credentials(target_id=target_id)
        self.query_one("#hdr-creds", Label).update(
            f"CREDENTIAL VAULT ({len(creds)})" if creds else "CREDENTIAL VAULT"
        )
        if creds:
            for c in creds:
                txt = Text()
                txt.append("🔑 ", style="bold green")
                txt.append(f"{c.username} : ", style="bold cyan")
                secret = c.secret if c.id in self.revealed_creds else c.masked_secret
                txt.append(secret, style="bold white")
                if c.source:
                    txt.append(f" ({c.source})", style="dim")
                c_list.append(DataListItem(data_obj=c, display_text=txt))
        else:
            txt = Text("  • No credentials saved (Press 'c' to add)", style="dim italic")
            c_list.append(DataListItem(data_obj=None, display_text=txt, is_placeholder=True))

        # 4. Checklist & Progress Bar
        ck_list = self.query_one("#list-checklist", ListView)
        ck_list.clear()
        items = self.store.list_checklist_items(target_id=target_id)
        checked_count = sum(1 for i in items if i.status == ChecklistStatus.CHECKED)
        total_items = len(items)
        pct = int((checked_count / total_items * 100)) if total_items > 0 else 0

        bar_len = 10
        filled = int(bar_len * (checked_count / total_items)) if total_items > 0 else 0
        bar_str = "█" * filled + "░" * (bar_len - filled)
        hdr_txt = f"METHODOLOGY ROADMAP  [{pct:2d}%  {bar_str}  {checked_count}/{total_items}]" if total_items else "METHODOLOGY ROADMAP"
        self.query_one("#hdr-checklist", Label).update(hdr_txt)

        if items:
            for item in items:
                txt = Text()
                if item.status == ChecklistStatus.CHECKED:
                    txt.append("[✓] ", style="bold green")
                    txt.append(item.title, style="dim strike")
                elif item.status == ChecklistStatus.DEFERRED:
                    txt.append("[~] ", style="bold yellow")
                    txt.append(item.title, style="bold yellow")
                elif item.status == ChecklistStatus.DEAD_END:
                    txt.append("[✗] ", style="bold red")
                    txt.append(item.title, style="dim red")
                else:
                    txt.append("[ ] ", style="bold cyan")
                    txt.append(item.title, style="bold white")
                ck_list.append(DataListItem(data_obj=item, display_text=txt))
        else:
            txt = Text("  • Press 'm' to load templates (ejpt, web, pivoting, smb, privesc)", style="dim italic")
            ck_list.append(DataListItem(data_obj=None, display_text=txt, is_placeholder=True))

        # 5. Combined Field Notes, Evidence, Leads & Failure Log
        n_list = self.query_one("#list-notes", ListView)
        n_list.clear()
        notes = self.store.list_notes(target_id=target_id)
        evidences = self.store.list_evidence(target_id=target_id)
        leads = self.store.list_leads(target_id=target_id)
        failures = self.store.list_failure_logs(target_id=target_id)
        total_notes_ev = len(notes) + len(evidences) + len(leads) + len(failures)
        self.query_one("#hdr-notes", Label).update(
            f"FIELD NOTES & EVIDENCE ({total_notes_ev})" if total_notes_ev else "FIELD NOTES & EVIDENCE"
        )
        if notes or evidences or leads or failures:
            for n in notes:
                txt = Text()
                txt.append("📝 > ", style="bold magenta")
                txt.append(n.content, style="white")
                n_list.append(DataListItem(data_obj=n, display_text=txt))
            for fl in failures:
                txt = Text()
                txt.append("🕳️ [DEAD-END] ", style="bold red")
                txt.append(fl.where_stuck, style="white")
                if fl.breakthrough_clue:
                    txt.append(f" → 🔑 Clue: {fl.breakthrough_clue}", style="bold green")
                if fl.rule_for_next_time:
                    txt.append(f" (📌 Rule: {fl.rule_for_next_time})", style="dim italic")
                n_list.append(DataListItem(data_obj=fl, display_text=txt))
            for ev in evidences:
                txt = Text()
                txt.append("📷 [EVID] ", style="bold cyan")
                txt.append(ev.path_or_ref, style="bold white")
                if ev.description:
                    txt.append(f" — {ev.description}", style="dim")
                n_list.append(DataListItem(data_obj=ev, display_text=txt))
            for ld in leads:
                txt = Text()
                txt.append("⚡ [LEAD] ", style="bold yellow")
                txt.append(ld.title, style="bold white")
                if ld.notes:
                    txt.append(f" ({ld.notes})", style="dim")
                n_list.append(DataListItem(data_obj=ld, display_text=txt))
        else:
            txt = Text("  • No notes recorded (Press 'n' or type :n <note> below)", style="dim italic")
            n_list.append(DataListItem(data_obj=None, display_text=txt, is_placeholder=True))

    # -------------------------------------------------------------------------
    # Hotkey Actions
    # -------------------------------------------------------------------------

    def action_activate_selected(self) -> None:
        """Handle Enter key on highlighted list item."""
        focused = self.focused
        if isinstance(focused, ListView) and focused.highlighted_child:
            item = focused.highlighted_child
            if isinstance(item, DataListItem) and not item.is_placeholder and item.data_obj:
                obj = item.data_obj
                if isinstance(obj, ChecklistItem):
                    active = self.store.get_active_target()
                    target_ip = active.ip if active else ""
                    guidance = get_template_guidance_for_title(obj.title)
                    if guidance and guidance.get("command"):
                        cmd = guidance["command"]
                        if target_ip:
                            cmd = cmd.replace("<TARGET_IP>", target_ip)
                            cmd = cmd.replace("<TARGET_SUBNET>", f"{target_ip.rsplit('.', 1)[0]}.0/24")
                        copy_to_clipboard(cmd)
                        self.notify(f"Copied command: {cmd}")
                        return

        self.action_copy_selected()

    def action_copy_selected(self) -> None:
        """Copy the value of the currently highlighted list item."""
        focused = self.focused
        if isinstance(focused, ListView) and focused.highlighted_child:
            item = focused.highlighted_child
            if isinstance(item, DataListItem) and not item.is_placeholder and item.data_obj:
                obj = item.data_obj
                if isinstance(obj, Service) and obj.next_action:
                    copy_to_clipboard(obj.next_action)
                    self.notify(f"Copied Next Action: {obj.next_action}")
                    return
                active = self.store.get_active_target()
                target_ip = active.ip if active else None
                val = extract_copy_value(item.data_obj, target_ip=target_ip)
                if val:
                    copy_to_clipboard(val)
                    self.notify(f"Copied: {val}")
                    return
        self.notify("Select a valid item to copy (y)")

    def action_toggle_selected(self) -> None:
        """Toggle checklist status or credential reveal."""
        focused = self.focused
        if isinstance(focused, ListView) and focused.highlighted_child:
            item = focused.highlighted_child
            if isinstance(item, DataListItem) and not item.is_placeholder and item.data_obj:
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

    def action_toggle_zoom(self) -> None:
        """Toggle maximize/fullscreen view on the active panel."""
        focused = self.focused
        if self.is_zoomed and self.zoomed_widget:
            self.zoomed_widget.remove_class("maximized")
            self.query_one("#col-left").styles.display = "block"
            self.query_one("#col-right").styles.display = "block"
            self.is_zoomed = False
            self.zoomed_widget = None
            self.notify("Restored standard view")
            return

        curr = focused
        target_box = None
        while curr and curr != self:
            if hasattr(curr, "has_class") and curr.has_class("panel-box"):
                target_box = curr
                break
            curr = getattr(curr, "parent", None)

        if target_box:
            self.zoomed_widget = target_box
            self.is_zoomed = True
            target_box.add_class("maximized")
            self.notify("Maximized panel (Press 'z' again to restore)")

    def action_record_flags(self) -> None:
        """Record user and root flags for active target."""
        active = self.store.get_active_target()
        if not active:
            self.notify("Create or select a target first (Press 't')", severity="warning")
            return

        def on_result(data: Optional[dict]) -> None:
            if data:
                uflag = data.get("user", "").strip()
                rflag = data.get("root", "").strip()
                self.store.update_target_details(active.id, user_flag=uflag, root_flag=rflag)
                self.refresh_targets()
                self.refresh_all()
                self.notify(f"Flags updated for {active.ip}")

        self.push_screen(
            FastInputModal(
                title=f"Record Flags for {active.ip}",
                fields=[
                    ("user", "User Flag (user.txt)", active.user_flag),
                    ("root", "Root Flag (root.txt)", active.root_flag),
                ],
            ),
            callback=on_result,
        )

    def action_delete_selected(self) -> None:
        """Delete highlighted item."""
        focused = self.focused
        if isinstance(focused, ListView) and focused.highlighted_child:
            item = focused.highlighted_child
            if isinstance(item, DataListItem) and not item.is_placeholder and item.data_obj:
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
                elif isinstance(obj, Lead):
                    self.store.delete_lead(obj.id)
                elif isinstance(obj, FailureLog):
                    self.store.delete_failure_log(obj.id)
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
                        access_potential=data.get("potential", "MED") or "MED",
                        next_action=data.get("next", ""),
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
                    ("potential", "Initial Access Potential (HIGH, MED, LOW)", "MED"),
                    ("next", "Next Action / Command (e.g. gobuster)", ""),
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

        def on_template_selected(template_name: Optional[str]) -> None:
            if template_name:
                try:
                    items = apply_template_to_store(self.store, template_name, target_id=target_id)
                    self.refresh_all()
                    t_name = template_name.upper()
                    self.notify(f"Applied {t_name} checklist ({len(items)} items)")
                except ValueError as e:
                    self.notify(str(e), severity="error")

        self.push_screen(TemplateSelectionModal(), callback=on_template_selected)

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

        if val.startswith(":uflag ") or val.startswith(":flag user "):
            uflag = val.split(maxsplit=1)[1].replace("user ", "").strip()
            if active:
                self.store.update_target_details(active.id, user_flag=uflag)
                self.refresh_targets()
                self.notify(f"User flag saved: {uflag}")
            else:
                self.notify("No active target set", severity="error")
        elif val.startswith(":rflag ") or val.startswith(":flag root "):
            rflag = val.split(maxsplit=1)[1].replace("root ", "").strip()
            if active:
                self.store.update_target_details(active.id, root_flag=rflag)
                self.refresh_targets()
                self.notify(f"Root flag saved: {rflag}")
            else:
                self.notify("No active target set", severity="error")
        elif val.startswith(":foothold "):
            fh = val[10:].strip()
            if active:
                self.store.update_target_details(active.id, initial_access_vuln=fh)
                self.refresh_targets()
                self.notify(f"Foothold saved: {fh}")
        elif val.startswith(":privesc "):
            pe = val[9:].strip()
            if active:
                self.store.update_target_details(active.id, privesc_vector=pe)
                self.notify(f"PrivEsc saved: {pe}")
        elif val.startswith(":stuck ") or val.startswith(":dead "):
            stuck_txt = val.split(maxsplit=1)[1].strip()
            self.store.add_failure_log(target_id=target_id, where_stuck=stuck_txt)
            self.notify(f"Dead-end logged: {stuck_txt}")
        elif val.startswith(":clue "):
            clue_txt = val[6:].strip()
            self.store.add_failure_log(target_id=target_id, breakthrough_clue=clue_txt)
            self.notify(f"Breakthrough clue logged: {clue_txt}")
        elif val.startswith(":n "):
            note_text = val[3:].strip()
            self.store.add_note(content=note_text, target_id=target_id)
            self.notify(f"Note added: {note_text}")
        elif val.startswith(":f "):
            finding_text = val[3:].strip()
            self.store.add_finding(title=finding_text, target_id=target_id)
            self.notify(f"Finding added: {finding_text}")
        elif val.startswith(":c "):
            cred_str = val[3:].strip()
            if ":" in cred_str:
                u, p = cred_str.split(":", 1)
            else:
                u, p = cred_str, ""
            self.store.add_credential(username=u, secret=p, target_id=target_id)
            self.notify(f"Cred added: {u}")
        elif val.startswith(":t "):
            ip = val[3:].strip()
            self.store.add_target(ip=ip)
            self.refresh_targets()
            self.notify(f"Target added: {ip}")
        elif val.startswith(":s "):
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
        elif val.startswith(":ev "):
            ev_path = val[4:].strip()
            self.store.add_evidence(path_or_ref=ev_path, target_id=target_id)
            self.notify(f"Evidence logged: {ev_path}")
        elif val.startswith("/"):
            self.action_open_search()
            return
        elif val == ":q":
            self.exit()
            return
        else:
            self.store.add_note(content=val, target_id=target_id)
            self.notify(f"Note added: {val}")

        self.refresh_all()
