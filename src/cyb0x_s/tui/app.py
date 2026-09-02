"""Main Textual application for CYB0X-S Worksheet.

High-efficiency, keyboard-driven terminal field worksheet and offensive cheatsheet station.
Strictly passive: stores human-discovered data, provides instant offline command references.
"""

from __future__ import annotations

from typing import Any, List, Optional, Set
from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Button,
    Footer,
    Input,
    Label,
    ListItem,
    ListView,
    Static,
    Tab,
    TabbedContent,
    TabPane,
    Tabs,
    Tree,
)

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
    get_guidance_for_service,
    get_template_guidance_for_title,
)
from cyb0x_s.settings import (
    describe_derive_guidance,
    derive_guidance_enabled,
    set_derive_guidance,
)
from cyb0x_s.tui.theme import (
    APP_CSS,
    DEFAULT_PALETTE,
    PALETTES,
    S,
    current_palette,
    get_default_theme,
    get_default_transparency,
    resolve_palette_name,
    save_default_theme,
    save_default_transparency,
    set_palette,
)
from cyb0x_s.tui.widgets import (
    AddCredentialModal,
    AddFindingModal,
    AddServiceModal,
    AddTargetModal,
    ConfirmModal,
    ConsoleBar,
    CredentialMatrixWidget,
    DataListItem,
    FastInputModal,
    HelpModal,
    LootAndFlagsWidget,
    MachineStatusStrip,
    PlaybookBrowserWidget,
    ReferenceModal,
    SearchModal,
    TargetTreeWidget,
    TemplateSelectionModal,
    ThemePickerModal,
    WorksheetHeader,
    substitute_command_placeholders,
)


class CyboxSafeApp(App):
    """CYB0X-S Terminal Field Worksheet & Playbook Station."""

    TITLE = "CYB0X-S Worksheet"
    SUB_TITLE = "Field Notes • Methodology Roadmap • Playbook Reference"

    # The footer is a quick reminder, not documentation: only the handful of
    # keys a new operator needs are shown. Everything lives in `?`.
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("question_mark", "show_help", "Help"),
        Binding("slash", "open_search", "Search"),
        Binding("y", "copy_selected", "Copy"),
        Binding("space", "toggle_selected", "Toggle"),
        Binding("enter", "activate_selected", "Action", show=False),
        Binding("z", "toggle_zoom", "Zoom", show=False),
        Binding("g", "record_flags", "Flags", show=False),
        Binding("r", "show_reference", "CheatSheet", show=False),
        Binding("o", "toggle_scope", "Scope", show=False),
        Binding("1", "switch_tab('tab-worksheet')", "Worksheet", show=False),
        Binding("2", "switch_tab('tab-playbooks')", "Playbooks", show=False),
        Binding("3", "switch_tab('tab-creds')", "Creds", show=False),
        Binding("4", "switch_tab('tab-loot')", "Loot", show=False),
        # vim-style list movement; safe next to fast-capture because Textual
        # hands printable keys to a focused Input before app bindings.
        Binding("j", "nav_down", "Down", show=False),
        Binding("k", "nav_up", "Up", show=False),
        Binding("ctrl+f", "open_search", "Search", show=False),
        Binding("t", "add_target", "Target", show=False),
        Binding("s", "add_service", "Service", show=False),
        Binding("f", "add_finding", "Finding", show=False),
        Binding("c", "add_credential", "Cred", show=False),
        Binding("n", "add_note", "Note", show=False),
        Binding("K", "add_checklist", "Checklist", show=False),
        Binding("m", "apply_template", "Template", show=False),
        Binding("d", "delete_selected", "Delete", show=False),
        Binding("T", "open_theme_picker", "Theme", show=False),
        Binding("G", "toggle_guidance", "Suggestions", show=False),
    ]

    CSS = APP_CSS

    # Everything in CYB0X-S is passive and human-driven, so the generic
    # Textual command palette adds nothing but a confusing ^p entry.
    ENABLE_COMMAND_PALETTE = False

    def __init__(
        self,
        store: Optional[NotebookStore] = None,
        theme: Optional[str] = None,
        transparent: Optional[bool] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        # Register every palette up front so switching is a one-liner later.
        for palette in PALETTES.values():
            self.register_theme(palette.textual_theme())
        self.store = store or NotebookStore()
        resolved = resolve_palette_name(theme) or get_default_theme(self.store)
        self.theme_name: str = resolved
        set_palette(self.theme_name)
        self.theme = PALETTES[self.theme_name].textual_theme().name
        self.revealed_creds: Set[int] = set()
        self.is_zoomed: bool = False
        self.zoomed_widget: Optional[Vertical] = None
        self.hidden_by_zoom: List[Any] = []
        if transparent is not None:
            self.is_transparent: bool = bool(transparent)
        else:
            self.is_transparent = get_default_transparency(self.store)

    def compose(self) -> ComposeResult:
        active_ws = self.store.get_active_workspace()
        yield WorksheetHeader(workspace_name=active_ws.name if active_ws else "default")
        yield MachineStatusStrip(id="target-info")

        with TabbedContent(initial="tab-worksheet", id="tabs"):
            # Station 1 — cockpit: everything needed for the next five minutes.
            with TabPane("1 ⌂ Cockpit", id="tab-worksheet"):
                with Horizontal(id="cockpit"):
                    with Vertical(id="sidebar"):
                        with Vertical(id="panel-surface", classes="panel-box"):
                            with Horizontal(classes="panel-header-row"):
                                yield Label("◈ ATTACK SURFACE", classes="panel-title")
                                yield Label("", id="cnt-surface", classes="panel-count")
                            yield TargetTreeWidget(id="target-tree")
                        with Vertical(id="panel-creds", classes="panel-box"):
                            with Horizontal(classes="panel-header-row"):
                                yield Label("🔑 CREDENTIALS", classes="panel-title")
                                yield Label("", id="cnt-creds", classes="panel-count")
                            yield ListView(id="list-creds", classes="panel-list")
                    with Vertical(id="workbench"):
                        with Vertical(id="panel-services", classes="panel-box"):
                            with Horizontal(classes="panel-header-row"):
                                yield Label("⚡ SERVICES & PORTS", classes="panel-title")
                                yield Label("", id="cnt-services", classes="panel-count")
                            yield ListView(id="list-services", classes="panel-list")
                        with Horizontal(id="lower-band"):
                            with Vertical(id="panel-checklist", classes="panel-box"):
                                with Horizontal(classes="panel-header-row"):
                                    yield Label("📋 METHODOLOGY", classes="panel-title")
                                    yield Label("", id="cnt-checklist", classes="panel-count")
                                yield ListView(id="list-checklist", classes="panel-list")
                            with Vertical(id="panel-notes", classes="panel-box"):
                                with Horizontal(classes="panel-header-row"):
                                    yield Label("📝 NOTES & FINDINGS", classes="panel-title")
                                    yield Label("", id="cnt-notes", classes="panel-count")
                                yield ListView(id="list-notes", classes="panel-list")

            # Station 2: Cheatsheet & Ready-to-Paste Playbooks
            with TabPane("2 ▸ Playbooks", id="tab-playbooks"):
                yield PlaybookBrowserWidget(id="playbook-browser")

            # Station 3: Dedicated Full-Screen Credential Vault Matrix
            with TabPane("3 ▸ Credentials", id="tab-creds"):
                yield CredentialMatrixWidget(id="cred-matrix-widget")

            # Station 4: Flags, Foothold & Failure Log
            with TabPane("4 ▸ Loot & Flags", id="tab-loot"):
                yield LootAndFlagsWidget(id="loot-flags-widget")

        yield ConsoleBar(id="guidance-box")
        yield Footer()

    def on_mount(self) -> None:
        if self.is_transparent:
            self.screen.add_class("transparent")
        self.refresh_targets()
        self.refresh_all()
        self._apply_responsive_layout()

    def on_resize(self, event: Any) -> None:
        """Switch to a stacked, single-column workbench on narrow terminals."""
        self._apply_responsive_layout()

    def _apply_responsive_layout(self) -> None:
        try:
            self.screen.set_class(self.size.width < 110, "compact")
        except Exception:
            pass

    # -------------------------------------------------------------------------
    # Tab Switching
    # -------------------------------------------------------------------------

    def action_switch_tab(self, tab_id: str) -> None:
        """Switch active TabbedContent pane."""
        tabbed = self.query_one("#tabs", TabbedContent)
        tabbed.active = tab_id
        active = self.store.get_active_target()
        target_ip = active.ip if active else ""

        if tab_id == "tab-playbooks":
            try:
                self.query_one("#playbook-browser", PlaybookBrowserWidget).update_target_ip(target_ip)
            except Exception:
                pass
        elif tab_id == "tab-creds":
            try:
                creds = self.store.list_credentials()
                targets = self.store.list_targets()
                services = self.store.list_services()
                self.query_one("#cred-matrix-widget", CredentialMatrixWidget).update_data(
                    creds, targets, services, self.revealed_creds
                )
            except Exception:
                pass

    # -------------------------------------------------------------------------
    # Target Management & Sidebar Tree
    # -------------------------------------------------------------------------

    def refresh_targets(self) -> None:
        """Update target tree, target tabs, and active target panel."""
        targets = self.store.list_targets()
        services = self.store.list_services()
        active = self.store.get_active_target()

        # Update Tree Sidebar
        try:
            tree = self.query_one("#target-tree", TargetTreeWidget)
            tree.populate(targets, services, selected_target_id=active.id if active else None)
        except Exception:
            pass

        try:
            self.query_one("#target-info", MachineStatusStrip).update_status(target=active)
        except Exception:
            pass

        # Update Playbook Target IP
        target_ip = active.ip if active else ""
        try:
            self.query_one("#playbook-browser", PlaybookBrowserWidget).update_target_ip(target_ip)
        except Exception:
            pass

        self._refresh_header(active, targets)

    def _guidance_for_service(self, svc: Service, target_ip: str) -> None:
        """Push a service's static reference command into the guidance drawer."""
        svc_guidance = (
            get_guidance_for_service(svc.service, svc.port)
            if derive_guidance_enabled()
            else None
        )
        try:
            guidance_box = self.query_one("#guidance-box", ConsoleBar)
        except Exception:
            return
        if svc_guidance:
            guidance_box.show_command(
                svc_guidance.get("command", ""),
                svc_guidance.get("tip", ""),
                target_ip=target_ip,
                heading="PORT",
            )
        elif svc.next_action:
            guidance_box.show_command(
                svc.next_action,
                f"Custom next action recorded for port {svc.port}/{svc.protocol}.",
                target_ip=target_ip,
                heading="NEXT",
            )
        else:
            guidance_box.reset()

    def on_tree_node_highlighted(self, event: Tree.NodeHighlighted) -> None:
        """Dynamically preview service guidance when moving through the target tree."""
        if event.node and event.node.data:
            d = event.node.data
            if d.get("type") == "service":
                svc = d.get("service")
                target = d.get("target")
                if svc and target:
                    self._guidance_for_service(svc, target.ip)

    def _refresh_header(self, active: Optional[Target], targets: List[Target]) -> None:
        """Keep the header, the surface count and the status strip in sync."""
        try:
            workspace = self.store.get_active_workspace()
        except Exception:
            workspace = None

        try:
            ports = len(self.store.list_services())
            creds = len(self.store.list_credentials())
            findings = len(self.store.list_findings())
            notes = len(self.store.list_notes())
        except Exception:
            return

        try:
            self.query_one(WorksheetHeader).update_status(
                workspace_name=workspace.name if workspace else "default",
                counts={"targets": len(targets)},
                active_ip=active.ip if active else "",
            )
        except Exception:
            pass

        self._set_count("cnt-surface", f"{len(targets)} host" + ("s" if len(targets) != 1 else ""))

        # "What do I do next?" — the first TODO step, plus how far along we are.
        next_step = ""
        progress = (0, 0, 0)
        blockers = 0
        try:
            items = self.store.list_checklist_items(target_id=active.id if active else None)
            total = len(items)
            done = sum(1 for i in items if i.status == ChecklistStatus.CHECKED)
            pct = int(done / total * 100) if total else 0
            pending = [i.title for i in items if i.status == ChecklistStatus.TODO]
            next_step = pending[0] if pending else ""
            progress = (done, total, pct)
            blockers = sum(1 for i in items if i.status == ChecklistStatus.DEAD_END)
            blockers += len(self.store.list_failure_logs(target_id=active.id if active else None))
        except Exception:
            pass

        try:
            self.query_one("#target-info", MachineStatusStrip).update_status(
                target=active,
                counts={"ports": ports, "creds": creds, "vulns": findings, "notes": notes},
                next_step=next_step,
                progress=progress,
                blockers=blockers,
            )
        except Exception:
            pass

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Switch active target when selected in Tree."""
        if event.node and event.node.data:
            d = event.node.data
            target_id = d.get("target_id") or d.get("id")
            if target_id:
                self.store.set_active_target(int(target_id))
                active = self.store.get_target(int(target_id))
                self.query_one("#target-info", MachineStatusStrip).update_status(target=active)
                self.refresh_all()

    def on_tabs_tab_activated(self, event: Tabs.TabActivated) -> None:
        """Switch active target when tab changes."""
        if event.tab and event.tab.id and event.tab.id.startswith("target-"):
            try:
                t_id = int(event.tab.id.split("-")[1])
                self.store.set_active_target(t_id)
                active = self.store.get_target(t_id)
                self.query_one("#target-info", MachineStatusStrip).update_status(target=active)
                self.refresh_all()
            except (ValueError, IndexError):
                pass

    # -------------------------------------------------------------------------
    # Checklist Selection & Live Guidance Drawer
    # -------------------------------------------------------------------------

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        """Update guidance drawer when a checklist item or service is highlighted."""
        if not event.item or not isinstance(event.item, DataListItem) or event.item.is_placeholder:
            return

        obj = event.item.data_obj
        if not obj:
            return

        active = self.store.get_active_target()
        target_ip = active.ip if active else ""
        try:
            guidance_box = self.query_one("#guidance-box", ConsoleBar)
        except Exception:
            return

        if event.list_view.id == "list-checklist":
            title = obj.title if isinstance(obj, ChecklistItem) else str(obj)
            guidance_box.update_guidance(title, target_ip=target_ip)
        elif event.list_view.id == "list-services" and isinstance(obj, Service):
            self._guidance_for_service(obj, target_ip)

    # -------------------------------------------------------------------------
    # List Population with Clear Formatting
    # -------------------------------------------------------------------------

    def _set_count(self, label_id: str, text: str) -> None:
        try:
            self.query_one(f"#{label_id}", Label).update(text)
        except Exception:
            pass

    def refresh_all(self) -> None:
        """Refresh all data lists from the database."""
        active_target = self.store.get_active_target()
        target_id = active_target.id if active_target else None

        # 1. Services & Ports (Notion 01 format with Potential and Next Action)
        svc_list = self.query_one("#list-services", ListView)
        svc_list.clear()
        services = self.store.list_services(target_id=target_id) if target_id else []
        self._set_count("cnt-services", f"{len(services)} ports" if services else "—")
        if services:
            for s in services:
                txt = Text()
                if s.status.value == "CHECKED":
                    txt.append("✓ ", style=S("ok"))
                elif s.status.value == "DEFERRED":
                    txt.append("~ ", style=S("warn"))
                elif s.status.value == "DEAD-END":
                    txt.append("✗ ", style=S("danger"))
                else:
                    txt.append("→ ", style=S("accent"))

                port_str = f"[{s.port}/{s.protocol}]"
                txt.append(f"{port_str:<11} ", style=S("accent"))
                txt.append(f"{s.service:<12} ", style=S("text"))
                if s.access_potential in ("HIGH", "CRITICAL"):
                    txt.append(f"[{s.access_potential}] ", style=S("danger"))
                elif s.access_potential == "LOW":
                    txt.append("[LOW] ", style=S("muted", bold=False))
                if s.version:
                    txt.append(f"{s.version} ", style=S("muted", bold=False))
                if s.next_action:
                    txt.append(f"→ `{s.next_action}` ", style=S("warn"))
                if s.notes:
                    txt.append(f"({s.notes})", style="dim italic")
                svc_list.append(DataListItem(data_obj=s, display_text=txt))
        else:
            txt = Text("  • No services recorded (Press 's' to add or type ':s 80/tcp http')", style="dim italic")
            svc_list.append(DataListItem(data_obj=None, display_text=txt, is_placeholder=True))

        # 2. Credentials (Compact Preview in Tab 1 + Full List in Tab 3)
        c_list = self.query_one("#list-creds", ListView)
        c_list.clear()
        creds = self.store.list_credentials(target_id=target_id)
        self._set_count("cnt-creds", f"{len(creds)} saved" if creds else "—")
        if creds:
            for c in creds:
                txt = Text()
                txt.append("🔑 ", style=S("ok"))
                txt.append(f"{c.username} ", style=S("text"))
                txt.append("› ", style=S("muted", bold=False))
                secret = c.secret if c.id in self.revealed_creds else c.masked_secret
                txt.append(f"{secret} ", style=S("accent"))
                if c.service_scope:
                    txt.append(f"[{c.service_scope}] ", style=S("warn"))
                if c.source:
                    txt.append(f"({c.source})", style=S("muted", bold=False))
                c_list.append(DataListItem(data_obj=c, display_text=txt))
        else:
            txt = Text("  • No credentials saved (Press 'c' to add)", style="dim italic")
            c_list.append(DataListItem(data_obj=None, display_text=txt, is_placeholder=True))

        # Tab 3 Credential Matrix Update
        try:
            all_creds = self.store.list_credentials()
            all_targets = self.store.list_targets()
            all_services = self.store.list_services()
            self.query_one("#cred-matrix-widget", CredentialMatrixWidget).update_data(
                all_creds, all_targets, all_services, self.revealed_creds
            )
        except Exception:
            pass

        # 3. Checklist & Progress Bar
        ck_list = self.query_one("#list-checklist", ListView)
        ck_list.clear()
        items = self.store.list_checklist_items(target_id=target_id)
        checked_count = sum(1 for i in items if i.status == ChecklistStatus.CHECKED)
        total_items = len(items)
        pct = int((checked_count / total_items * 100)) if total_items > 0 else 0

        bar_len = 10
        filled = int(bar_len * (checked_count / total_items)) if total_items > 0 else 0
        bar_str = "█" * filled + "░" * (bar_len - filled)
        hdr_txt = f"{bar_str} {pct:>3d}% {checked_count}/{total_items}" if total_items else "—"
        self._set_count("cnt-checklist", hdr_txt)

        if items:
            for item in items:
                txt = Text()
                if item.status == ChecklistStatus.CHECKED:
                    txt.append("[✓ DONE] ", style=S("ok"))
                    txt.append(item.title, style="dim strike")
                elif item.status == ChecklistStatus.DEFERRED:
                    txt.append("[⏸ DEFER] ", style=S("warn"))
                    txt.append(item.title, style=S("warn"))
                elif item.status == ChecklistStatus.DEAD_END:
                    txt.append("[✖ DROP] ", style=S("danger"))
                    txt.append(item.title, style=S("muted", bold=False))
                else:
                    txt.append("[⏳ TODO] ", style=S("accent"))
                    txt.append(item.title, style=S("text"))
                ck_list.append(DataListItem(data_obj=item, display_text=txt))
        else:
            txt = Text("  • Press 'm' to load templates (ejpt, web, pivoting, smb, privesc)", style="dim italic")
            ck_list.append(DataListItem(data_obj=None, display_text=txt, is_placeholder=True))

        # 4. Combined Field Notes, Evidence & Findings
        n_list = self.query_one("#list-notes", ListView)
        n_list.clear()
        notes = self.store.list_notes(target_id=target_id)
        findings = self.store.list_findings(target_id=target_id)
        evidences = self.store.list_evidence(target_id=target_id)
        leads = self.store.list_leads(target_id=target_id)
        total_notes_ev = len(notes) + len(findings) + len(evidences) + len(leads)
        self._set_count("cnt-notes", f"{total_notes_ev} entries" if total_notes_ev else "—")
        if notes or findings or evidences or leads:
            for f in findings:
                txt = Text()
                txt.append("⚠️ [VULN] ", style=S("danger"))
                txt.append(f"{f.title} ", style=S("text"))
                if f.severity:
                    txt.append(f"[{f.severity}] ", style=S("warn"))
                if f.description:
                    txt.append(f"— {f.description}", style=S("muted", bold=False))
                n_list.append(DataListItem(data_obj=f, display_text=txt))
            for n in notes:
                txt = Text()
                txt.append("📝 [NOTE] ", style=S("warn"))
                txt.append(n.content, style=S("text"))
                n_list.append(DataListItem(data_obj=n, display_text=txt))
            for ev in evidences:
                txt = Text()
                txt.append("📷 [EVID] ", style=S("accent"))
                txt.append(f"{ev.path_or_ref} ", style=S("text"))
                if ev.description:
                    txt.append(f"— {ev.description}", style=S("muted", bold=False))
                n_list.append(DataListItem(data_obj=ev, display_text=txt))
            for ld in leads:
                txt = Text()
                txt.append("⚡ [LEAD] ", style=S("warn"))
                txt.append(f"{ld.title} ", style=S("text"))
                if ld.notes:
                    txt.append(f"({ld.notes})", style=S("muted", bold=False))
                n_list.append(DataListItem(data_obj=ld, display_text=txt))
        else:
            txt = Text("  • No notes recorded (Press 'n' or type :n <note> below)", style="dim italic")
            n_list.append(DataListItem(data_obj=None, display_text=txt, is_placeholder=True))

        # 5. Tab 4: Loot & Flags Widget update
        failures = self.store.list_failure_logs(target_id=target_id)
        self._refresh_header(active_target, self.store.list_targets())
        try:
            loot_widget = self.query_one("#loot-flags-widget", LootAndFlagsWidget)
            loot_widget.update_data(active_target, failures)
        except Exception:
            pass

    # -------------------------------------------------------------------------
    # Hotkey Actions
    # -------------------------------------------------------------------------

    def action_toggle_scope(self) -> None:
        """Toggle in-scope vs out-of-scope for active target."""
        active = self.store.get_active_target()
        if active:
            new_scope = not active.is_in_scope
            self.store.update_target_details(active.id, is_in_scope=new_scope)
            active.is_in_scope = new_scope
            self.query_one("#target-info", MachineStatusStrip).update_status(target=active)
            self.refresh_targets()
            tag = "[bold #8FA876]IN-SCOPE[/]" if new_scope else "[bold #E5846B]OUT-OF-SCOPE[/bold #E5846B]"
            self.notify(f"Target {active.ip} marked {tag}")

    def action_activate_selected(self) -> None:
        """Handle Enter key on highlighted list item."""
        focused = self.focused
        if isinstance(focused, ListView) and focused.highlighted_child:
            item = focused.highlighted_child
            if isinstance(item, DataListItem) and not item.is_placeholder and item.data_obj:
                obj = item.data_obj
                active = self.store.get_active_target()
                target_ip = active.ip if active else ""

                if isinstance(obj, ChecklistItem):
                    guidance = get_template_guidance_for_title(obj.title)
                    if guidance and guidance.get("command"):
                        cmd = substitute_command_placeholders(guidance["command"], target_ip)
                        copy_to_clipboard(cmd)
                        self.notify(f"Copied command: {cmd}")
                        return
                elif isinstance(obj, Service):
                    if obj.next_action:
                        copy_to_clipboard(obj.next_action)
                        self.notify(f"Copied Next Action: {obj.next_action}")
                        return
                    # Only auto-suggest a command for a recorded service when the
                    # operator has opted in; otherwise CYB0X-S stays passive.
                    if derive_guidance_enabled():
                        svc_guidance = get_guidance_for_service(obj.service, obj.port)
                        if svc_guidance and svc_guidance.get("command"):
                            cmd = substitute_command_placeholders(svc_guidance["command"], target_ip)
                            copy_to_clipboard(cmd)
                            self.notify(f"Copied Service Command: {cmd}")
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
        """Give the focused panel the whole cockpit (z toggles)."""
        if self.is_zoomed and self.zoomed_widget:
            self.zoomed_widget.remove_class("maximized")
            for widget in self.hidden_by_zoom:
                widget.styles.display = "block"
            self.hidden_by_zoom = []
            try:
                self.query_one("#cockpit").remove_class("zoomed-mode")
            except Exception:
                pass
            self.is_zoomed = False
            self.zoomed_widget = None
            self.notify("Restored cockpit view")
            return

        curr = self.focused
        target_box = None
        while curr is not None and curr is not self:
            if hasattr(curr, "has_class") and curr.has_class("panel-box"):
                target_box = curr
                break
            curr = getattr(curr, "parent", None)

        if target_box is None:
            self.notify("Focus a panel first (Tab), then press 'z' to zoom it")
            return

        # Hide every region that does not contain the target panel.
        hidden: List[Any] = []
        try:
            sidebar = self.query_one("#sidebar")
            workbench = self.query_one("#workbench")
            lower_band = self.query_one("#lower-band")
            services = self.query_one("#panel-services")
            in_sidebar = target_box in sidebar.walk_children()
            for region in (sidebar, workbench, lower_band, services):
                if region is target_box or target_box in region.walk_children():
                    continue
                if in_sidebar and region is not sidebar:
                    region.styles.display = "none"
                    hidden.append(region)
                elif not in_sidebar and region in (sidebar, lower_band, services):
                    region.styles.display = "none"
                    hidden.append(region)
            if not in_sidebar:
                self.query_one("#cockpit").add_class("zoomed-mode")
        except Exception:
            pass

        self.hidden_by_zoom = hidden
        self.zoomed_widget = target_box
        self.is_zoomed = True
        target_box.add_class("maximized")
        self.notify("Zoomed panel — press 'z' again to restore")

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

    def action_cycle_theme(self) -> None:
        """Switch to the next available palette."""
        names = list(PALETTES)
        current = names.index(self.theme_name) if self.theme_name in names else 0
        self.apply_theme(names[(current + 1) % len(names)])

    def apply_theme(self, name: str, quiet: bool = False) -> None:
        """Activate a palette by name, index (1-7), or alias/prefix, live."""
        resolved = resolve_palette_name(name)
        if not resolved or resolved not in PALETTES:
            self.notify(
                f"Unknown theme '{name}'. Available: {', '.join(PALETTES)} (or 1-7)",
                severity="warning",
            )
            return
        self.theme_name = resolved
        palette = set_palette(resolved)
        self.theme = palette.textual_theme().name
        self.refresh_targets()
        self.refresh_all()
        if not quiet:
            self.notify(f"Theme: {palette.label}")

    def set_default_theme(self, name: str) -> None:
        """Persist the chosen palette as the permanent default and activate it."""
        resolved = resolve_palette_name(name)
        if not resolved or resolved not in PALETTES:
            self.notify(f"Unknown theme '{name}'", severity="warning")
            return
        save_default_theme(resolved, self.store)
        self.apply_theme(resolved, quiet=True)
        self.notify(f"★ Theme '{resolved}' saved as default!", severity="information")

    def action_open_theme_picker(self) -> None:
        """Open the palette picker (live preview, Esc restores the old one)."""
        self.push_screen(ThemePickerModal(self.theme_name, store=self.store))

    def toggle_transparency(self, enable: Optional[bool] = None, persist: bool = False) -> bool:
        """Toggle or set glass/transparent canvas mode."""
        if enable is None:
            self.is_transparent = not self.is_transparent
        else:
            self.is_transparent = bool(enable)
        self.screen.set_class(self.is_transparent, "transparent")
        if persist:
            save_default_transparency(self.is_transparent, self.store)
        return self.is_transparent

    def action_toggle_guidance(self) -> None:
        """Switch derived suggestions (access potential / next command) on or off.

        Off is the default and the exam-safe posture: CYB0X-S then only records
        what you tell it and looks up references when you ask.
        """
        set_derive_guidance(not derive_guidance_enabled())
        state = describe_derive_guidance()
        self.notify(
            f"Derived suggestions: {state}"
            + ("" if state == "on" else " — notebook records only what you enter")
        )
        self.refresh_targets()
        self.refresh_all()

    def action_show_reference(self) -> None:
        """Open searchable cheat sheet and command reference modal."""
        active = self.store.get_active_target()
        target_ip = active.ip if active else ""

        def on_selected(cmd: Optional[str]) -> None:
            if cmd:
                copy_to_clipboard(cmd)
                self.notify(f"Copied command: {cmd}")

        self.push_screen(ReferenceModal(target_ip=target_ip), callback=on_selected)

    @staticmethod
    def _describe(obj: Any) -> str:
        """Human readable one-liner used by the delete confirmation."""
        if isinstance(obj, Service):
            return f"service {obj.port}/{obj.protocol} ({obj.service})"
        if isinstance(obj, Credential):
            return f"credential for '{obj.username}'"
        if isinstance(obj, (Finding, ChecklistItem, Lead)):
            return f"'{obj.title}'"
        if isinstance(obj, Note):
            return f"note '{obj.content[:40]}'"
        if isinstance(obj, Evidence):
            return f"evidence '{obj.path_or_ref}'"
        if isinstance(obj, FailureLog):
            return f"failure log '{obj.where_stuck[:40]}'"
        return "this item"

    def action_delete_selected(self) -> None:
        """Delete highlighted item — after an explicit confirmation."""
        focused = self.focused
        if not (isinstance(focused, ListView) and focused.highlighted_child):
            return
        item = focused.highlighted_child
        if not (isinstance(item, DataListItem) and not item.is_placeholder and item.data_obj):
            self.notify("Select an item to delete (d)")
            return

        obj = item.data_obj

        def on_confirm(confirmed: Optional[bool]) -> None:
            if not confirmed:
                self.notify("Delete cancelled")
                return
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
            self.notify(f"Deleted {self._describe(obj)}")
            self.refresh_targets()
            self.refresh_all()

        self.push_screen(
            ConfirmModal(
                title="CONFIRM DELETE",
                message=f"Delete {self._describe(obj)}?\nThis cannot be undone.",
                confirm_label="Delete",
            ),
            callback=on_confirm,
        )

    # -------------------------------------------------------------------------
    # List navigation (vim style)
    # -------------------------------------------------------------------------

    def _move_focused_list(self, delta: int) -> None:
        focused = self.focused
        if focused is None:
            return
        action = "action_cursor_down" if delta > 0 else "action_cursor_up"
        mover = getattr(focused, action, None)
        if callable(mover):
            mover()
        elif hasattr(focused, "scroll_relative"):
            focused.scroll_relative(y=delta)

    def action_nav_down(self) -> None:
        """Move down inside the focused list or tree."""
        self._move_focused_list(1)

    def action_nav_up(self) -> None:
        """Move up inside the focused list or tree."""
        self._move_focused_list(-1)

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
                target = self.store.add_target(
                    ip=data["ip"],
                    hostname=data.get("hostname", ""),
                    os_name=data.get("os", "Unknown") or "Unknown",
                    notes=data.get("notes", ""),
                )
                ports = data.get("ports", [])
                for p in ports:
                    svc_name = "http" if p in (80, 443, 8080) else ("ssh" if p == 22 else ("smb" if p == 445 else "unknown"))
                    self.store.add_service(target_id=target.id, port=p, protocol="tcp", service=svc_name)

                self.refresh_targets()
                self.refresh_all()
                self.notify(f"Target {data['ip']} added ({len(ports)} ports)")

        self.push_screen(AddTargetModal(), callback=on_result)

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
                        access_potential=data.get("potential", "") or "",
                        next_action=data.get("next", ""),
                    )
                    self.refresh_targets()
                    self.refresh_all()
                    self.notify(f"Service {port} added")
                except ValueError:
                    self.notify("Port must be an integer", severity="error")

        self.push_screen(AddServiceModal(target_ip=active.ip), callback=on_result)

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
                )
                self.refresh_all()
                self.notify("Finding recorded")

        self.push_screen(AddFindingModal(), callback=on_result)

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

        self.push_screen(AddCredentialModal(), callback=on_result)

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

    def on_input_changed(self, event: Input.Changed) -> None:
        """Update live command syntax preview as the operator types."""
        if event.input.id == "cmd-input":
            try:
                console = self.query_one("#guidance-box", ConsoleBar)
                console.update_input_hint(event.value)
            except Exception:
                pass

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle quick command bar submission."""
        val = event.value.strip()
        inp = self.query_one("#cmd-input", Input)
        inp.value = ""
        try:
            console = self.query_one("#guidance-box", ConsoleBar)
            console.reset()
        except Exception:
            pass

        if not val:
            return

        # Direct Help triggers
        if val in ("?", "help", ":help", ":?"):
            self.action_help()
            return

        # Natural language keyword conversions (without leading colon)
        if val.startswith("add target ") or val.startswith("target "):
            raw = val.replace("add target ", "", 1).replace("target ", "", 1).strip()
            val = f":t {raw}"
        elif val.startswith("add service ") or val.startswith("service "):
            raw = val.replace("add service ", "", 1).replace("service ", "", 1).strip()
            val = f":s {raw}"
        elif val.startswith("add cred ") or val.startswith("cred "):
            raw = val.replace("add cred ", "", 1).replace("cred ", "", 1).strip()
            val = f":c {raw}"
        elif val.startswith("add note ") or val.startswith("note "):
            raw = val.replace("add note ", "", 1).replace("note ", "", 1).strip()
            val = f":n {raw}"
        elif val.startswith("add finding ") or val.startswith("finding "):
            raw = val.replace("add finding ", "", 1).replace("finding ", "", 1).strip()
            val = f":f {raw}"
        elif val.startswith("theme ") or val.startswith("palette "):
            raw = val.replace("theme ", "", 1).replace("palette ", "", 1).strip()
            val = f":theme {raw}"
        elif val == "theme" or val == "palette":
            val = ":theme"
        elif val in ("quit", "exit"):
            self.action_quit_app()
            return

        # Handle tab switching via command: :1, :2, :3, :4
        if val == ":1":
            self.action_switch_tab("tab-worksheet")
            return
        elif val == ":2":
            self.action_switch_tab("tab-playbooks")
            return
        elif val == ":3":
            self.action_switch_tab("tab-creds")
            return
        elif val == ":4":
            self.action_switch_tab("tab-loot")
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
        elif val.startswith(":ref ") or val.startswith(":cheat "):
            active_ip = active.ip if active else ""
            def on_cmd_selected(cmd: Optional[str]) -> None:
                if cmd:
                    copy_to_clipboard(cmd)
                    self.notify(f"Copied command: {cmd}")
            self.push_screen(ReferenceModal(target_ip=active_ip), callback=on_cmd_selected)
            return
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
        elif val.startswith(":theme"):
            parts = val.split(maxsplit=2)
            if len(parts) == 1:
                self.action_cycle_theme()
            elif len(parts) == 3 and parts[1].lower() in ("default", "set-default", "def", "save"):
                self.set_default_theme(parts[2].strip().lower())
            else:
                arg = val[6:].strip()
                if arg.lower().startswith("default ") or arg.lower().startswith("set-default "):
                    def_target = arg.split(maxsplit=1)[1].strip()
                    self.set_default_theme(def_target)
                else:
                    self.apply_theme(arg.lower())
            return
        elif val.startswith((":trans", ":glass")):
            parts = val.split()
            if len(parts) > 1 and parts[1].lower() in ("on", "1", "yes", "true"):
                self.toggle_transparency(True, persist=True)
                self.notify("Glass transparency enabled (saved as default)")
            elif len(parts) > 1 and parts[1].lower() in ("off", "0", "no", "false"):
                self.toggle_transparency(False, persist=True)
                self.notify("Solid background enabled (saved as default)")
            else:
                state = self.toggle_transparency(persist=True)
                msg = "Glass transparency enabled" if state else "Solid background enabled"
                self.notify(f"{msg} (saved as default)")
            return
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
