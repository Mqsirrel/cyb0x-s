"""Main Textual application for CYB0X-S Worksheet.

High-efficiency, keyboard-driven terminal field worksheet and offensive cheatsheet station.
Strictly passive: stores human-discovered data, provides instant offline command references.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import (
    Footer,
    Input,
    Label,
    ListView,
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
from cyb0x_s.settings import (
    derive_guidance_enabled,
    describe_derive_guidance,
    set_derive_guidance,
)
from cyb0x_s.templates import (
    apply_template_to_store,
    get_guidance_for_service,
    get_template_guidance_for_title,
)
from cyb0x_s.tui.theme import (
    APP_CSS,
    PALETTES,
    S,
    get_default_theme,
    resolve_palette_name,
    save_default_theme,
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
    clear_badge_caches,
    get_protocol_badge,
    get_service_status_icon,
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
        Binding("colon", "focus_command_bar", "Command", show=False),
        Binding("left_square_bracket", "prev_target", "Prev Target", show=False),
        Binding("right_square_bracket", "next_target", "Next Target", show=False),
        Binding("b", "toggle_sidebar", "Sidebar", show=False),
        Binding("comma", "prev_recipe", "Prev Recipe", show=False),
        Binding("full_stop", "next_recipe", "Next Recipe", show=False),
        Binding("w", "cycle_panel", "Cycle Panel", show=False),
        Binding("h", "focus_left", "Left Column", show=False),
        Binding("l", "focus_right", "Right Column", show=False),
    ]

    CSS = APP_CSS

    # Everything in CYB0X-S is passive and human-driven, so the generic
    # Textual command palette adds nothing but a confusing ^p entry.
    ENABLE_COMMAND_PALETTE = False

    def __init__(
        self,
        store: Optional[NotebookStore] = None,
        theme: Optional[str] = None,
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
        self._cached_active_target: Optional[Target] = None

    def get_current_target(self) -> Optional[Target]:
        """Return the active target from memory cache, querying SQLite only if unpopulated."""
        if self._cached_active_target is None:
            self._cached_active_target = self.store.get_active_target()
        return self._cached_active_target

    def invalidate_target_cache(self, new_target: Optional[Target] = None) -> None:
        """Invalidate or update active target memory cache when target changes."""
        self._cached_active_target = new_target

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
                                yield Label("ATTACK SURFACE", classes="panel-title")
                                yield Label("", id="cnt-surface", classes="panel-count")
                            yield TargetTreeWidget(id="target-tree")
                        with Vertical(id="panel-creds", classes="panel-box"):
                            with Horizontal(classes="panel-header-row"):
                                yield Label("CREDENTIALS", classes="panel-title")
                                yield Label("", id="cnt-creds", classes="panel-count")
                            yield ListView(id="list-creds", classes="panel-list")
                    with Vertical(id="workbench"):
                        with Vertical(id="panel-services", classes="panel-box"):
                            with Horizontal(classes="panel-header-row"):
                                yield Label("SERVICES & PORTS", classes="panel-title")
                                yield Label("", id="cnt-services", classes="panel-count")
                            yield ListView(id="list-services", classes="panel-list")
                        with Horizontal(id="lower-band"):
                            with Vertical(id="panel-checklist", classes="panel-box"):
                                with Horizontal(classes="panel-header-row"):
                                    yield Label("METHODOLOGY", classes="panel-title")
                                    yield Label("", id="cnt-checklist", classes="panel-count")
                                yield ListView(id="list-checklist", classes="panel-list")
                            with Vertical(id="panel-notes", classes="panel-box"):
                                with Horizontal(classes="panel-header-row"):
                                    yield Label("NOTES & FINDINGS", classes="panel-title")
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
        self.refresh_targets()
        self.refresh_all()
        self._apply_responsive_layout()

    def on_resize(self, event: Any) -> None:
        """Switch to a stacked, single-column workbench on narrow terminals."""
        self._apply_responsive_layout()

    def _apply_responsive_layout(self) -> None:
        try:
            is_compact_w = self.size.width < 105
            is_compact_h = self.size.height < 28
            self.screen.set_class(is_compact_w, "compact")
            self.screen.set_class(is_compact_w, "compact-width")
            self.screen.set_class(is_compact_h, "compact-height")
        except Exception:
            pass

    def action_focus_command_bar(self) -> None:
        """Global ':' hotkey to jump immediately into command input."""
        try:
            inp = self.query_one("#cmd-input", Input)
            inp.value = ":"
            inp.cursor_position = 1
            inp.focus()
            try:
                console = self.query_one("#guidance-box", ConsoleBar)
                console.update_input_hint(":")
            except Exception:
                pass
        except Exception:
            pass

    def action_focus_workbench(self) -> None:
        """Restore focus to workbench list after exiting command bar."""
        try:
            self.query_one("#list-services", ListView).focus()
        except Exception:
            pass

    def action_prev_target(self) -> None:
        """Switch to previous target in list via '[' hotkey."""
        self._cycle_target(-1)

    def action_next_target(self) -> None:
        """Switch to next target in list via ']' hotkey."""
        self._cycle_target(1)

    def _cycle_target(self, delta: int) -> None:
        targets = self.store.list_targets()
        if not targets:
            return
        active = self.store.get_active_target()
        active_id = active.id if active else targets[0].id
        ids = [t.id for t in targets]
        try:
            curr_idx = ids.index(active_id)
        except ValueError:
            curr_idx = 0
        next_idx = (curr_idx + delta) % len(ids)
        new_target = targets[next_idx]
        self.store.set_active_target(new_target.id)
        self.invalidate_target_cache(new_target)
        self.refresh_targets()
        self.refresh_all()
        self.notify(f"Active target: {new_target.ip}")

    def action_toggle_sidebar(self) -> None:
        """Toggle sidebar visibility to maximize workbench on small displays ('b' hotkey)."""
        try:
            sidebar = self.query_one("#sidebar")
            sidebar.toggle_class("hidden")
            is_hidden = sidebar.has_class("hidden")
            self.notify("Sidebar hidden (full width workbench)" if is_hidden else "Sidebar visible")
        except Exception:
            pass

    def action_next_recipe(self) -> None:
        """Cycle to next recipe for currently selected service ('.' hotkey)."""
        try:
            console = self.query_one("#guidance-box", ConsoleBar)
            cmd = console.cycle_recipe(1)
            if cmd:
                self.notify(f"Selected: {cmd[:40]}")
        except Exception:
            pass

    def action_prev_recipe(self) -> None:
        """Cycle to previous recipe for currently selected service (',' hotkey)."""
        try:
            console = self.query_one("#guidance-box", ConsoleBar)
            cmd = console.cycle_recipe(-1)
            if cmd:
                self.notify(f"Selected: {cmd[:40]}")
        except Exception:
            pass

    def action_cycle_panel(self) -> None:
        """Cycle focus sequentially through the five Cockpit panels ('w' hotkey)."""
        panel_ids = ["#target-tree", "#list-creds", "#list-services", "#list-checklist", "#list-notes"]
        curr_idx = -1
        for i, pid in enumerate(panel_ids):
            try:
                w = self.query_one(pid)
                if w.has_focus:
                    curr_idx = i
                    break
            except Exception:
                pass
        next_idx = (curr_idx + 1) % len(panel_ids)
        try:
            self.query_one(panel_ids[next_idx]).focus()
        except Exception:
            pass

    def action_focus_left(self) -> None:
        """Jump focus to Sidebar (Attack Surface tree) via 'h' hotkey."""
        try:
            self.query_one("#target-tree").focus()
        except Exception:
            pass

    def action_focus_right(self) -> None:
        """Jump focus to Workbench (Services list) via 'l' hotkey."""
        try:
            self.query_one("#list-services", ListView).focus()
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
            self.refresh_cred_matrix()
        elif tab_id == "tab-loot":
            self.refresh_loot_widget()

    def refresh_cred_matrix(self) -> None:
        """Update Station 3 Credential Vault & Matrix on demand."""
        try:
            creds = self.store.list_credentials()
            targets = self.store.list_targets()
            services = self.store.list_services()
            self.query_one("#cred-matrix-widget", CredentialMatrixWidget).update_data(
                creds, targets, services, self.revealed_creds
            )
        except Exception:
            pass

    def refresh_loot_widget(self, target: Optional[Target] = None, failures: Optional[List[Any]] = None) -> None:
        """Update Station 4 Loot & Flags widget on demand."""
        try:
            active = target or self.store.get_active_target()
            if failures is None:
                failures = self.store.list_failure_logs(target_id=active.id if active else None)
            proofs = self.store.list_exam_proofs()
            self.query_one("#loot-flags-widget", LootAndFlagsWidget).update_data(active, failures, proofs=proofs)
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
        """Push a service's static reference commands/recipes into the console bar."""
        from cyb0x_s.templates import get_recipes_for_service

        try:
            guidance_box = self.query_one("#guidance-box", ConsoleBar)
        except Exception:
            return
        recipes = (
            get_recipes_for_service(svc.service, svc.port)
            if derive_guidance_enabled()
            else []
        )
        if recipes:
            guidance_box.show_recipes(recipes, index=0, target_ip=target_ip)
        elif svc.next_action:
            guidance_box.show_command(
                svc.next_action,
                f"Custom next action recorded for port {svc.port}/{svc.protocol}.",
                target_ip=target_ip,
                heading="NEXT",
            )
        else:
            guidance_box.reset()

    def _cross_filter_for_service(self, svc: Service) -> None:
        """Context-aware cross-filtering: align checklist and credentials with highlighted service."""
        if getattr(self, "_is_cross_filtering", False):
            return

        self._is_cross_filtering = True
        try:
            with self.batch_update():
                s_name = svc.service.lower()
                port_str = str(svc.port)

                # 1. Align checklist: find first step matching service name or port
                try:
                    ck_list = getattr(self, "_list_checklist", None) or self.query_one("#list-checklist", ListView)
                    for idx, child in enumerate(ck_list.children):
                        if isinstance(child, DataListItem) and not child.is_placeholder and child.data_obj:
                            obj = child.data_obj
                            title = getattr(obj, "title", "").lower()
                            cat = getattr(obj, "category", "").lower()
                            if s_name in title or s_name in cat or port_str in title:
                                if ck_list.index != idx:
                                    ck_list.index = idx
                                break
                except Exception:
                    pass

                # 2. Align credentials: find first credential matching service scope
                try:
                    c_list = getattr(self, "_list_creds", None) or self.query_one("#list-creds", ListView)
                    for idx, child in enumerate(c_list.children):
                        if isinstance(child, DataListItem) and not child.is_placeholder and child.data_obj:
                            obj = child.data_obj
                            scope = getattr(obj, "service_scope", "").lower()
                            if scope in (s_name, "global"):
                                if c_list.index != idx:
                                    c_list.index = idx
                                break
                except Exception:
                    pass
        finally:
            self._is_cross_filtering = False

    def on_tree_node_highlighted(self, event: Tree.NodeHighlighted) -> None:
        """Dynamically preview service guidance or pivot routing when moving through the target tree."""
        if event.node and event.node.data:
            d = event.node.data
            node_type = d.get("type")
            if node_type == "service":
                svc = d.get("service")
                target = d.get("target")
                if svc and target:
                    self._guidance_for_service(svc, target.ip)
            elif node_type == "target" and d.get("is_pivot"):
                target = d.get("target")
                proute = d.get("pivot_route") or "192.168.1.0/24 via socks5:1080"
                try:
                    gb = self.query_one("#guidance-box", ConsoleBar)
                    gb.show_command(
                        f"chisel client {target.ip}:8000 R:socks  # or: ssh -D 1080 user@{target.ip} ({proute})",
                        target_ip=target.ip,
                    )
                except Exception:
                    pass
            elif node_type == "subnet":
                snet = d.get("subnet")
                try:
                    gb = self.query_one("#guidance-box", ConsoleBar)
                    gb.show_command(
                        f"sudo nmap -sn {snet}  # or: sudo arp-scan -I eth1 {snet}"
                    )
                except Exception:
                    pass

    def _refresh_header(
        self,
        active: Optional[Target],
        targets: List[Target],
        *,
        counts: Optional[Dict[str, int]] = None,
        items: Optional[List[ChecklistItem]] = None,
        failure_count: Optional[int] = None,
    ) -> None:
        """Keep the header, the surface count and the status strip in sync."""
        try:
            workspace = self.store.get_active_workspace()
        except Exception:
            workspace = None

        target_id = active.id if active else None

        # Fetch fast target counts in one SQL query if not passed by caller
        if counts is None:
            counts = self.store.get_target_counts(target_id=target_id)

        try:
            self.query_one(WorksheetHeader).update_status(
                workspace_name=workspace.name if workspace else "default",
                counts={"targets": len(targets)},
                active_ip=active.ip if active else "",
            )
        except Exception:
            pass

        self._set_count("cnt-surface", f"{len(targets)} host" + ("s" if len(targets) != 1 else ""))

        # Checklist progress and next step
        next_step = ""
        progress = (0, 0, 0)
        blockers = counts.get("dead_ends", 0) + (
            failure_count if failure_count is not None else counts.get("failures", 0)
        )

        try:
            if items is None:
                items = self.store.list_checklist_items(target_id=target_id)
            total = len(items)
            done = sum(1 for i in items if i.status == ChecklistStatus.CHECKED)
            pct = int(done / total * 100) if total else 0
            pending = [i.title for i in items if i.status == ChecklistStatus.TODO]
            next_step = pending[0] if pending else ""
            progress = (done, total, pct)
            blockers = sum(1 for i in items if i.status == ChecklistStatus.DEAD_END) + (
                failure_count if failure_count is not None else counts.get("failures", 0)
            )
        except Exception:
            pass

        try:
            self.query_one("#target-info", MachineStatusStrip).update_status(
                target=active,
                counts={
                    "ports": counts.get("ports", 0),
                    "creds": counts.get("creds", 0),
                    "vulns": counts.get("vulns", 0),
                    "notes": counts.get("notes", 0),
                },
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
                self.invalidate_target_cache(active)
                self.query_one("#target-info", MachineStatusStrip).update_status(target=active)
                self.refresh_all()

    def on_tabs_tab_activated(self, event: Tabs.TabActivated) -> None:
        """Switch active target when tab changes."""
        if event.tab and event.tab.id and event.tab.id.startswith("target-"):
            try:
                t_id = int(event.tab.id.split("-")[1])
                self.store.set_active_target(t_id)
                active = self.store.get_target(t_id)
                self.invalidate_target_cache(active)
                self.query_one("#target-info", MachineStatusStrip).update_status(target=active)
                self.refresh_all()
            except (ValueError, IndexError):
                pass

    # -------------------------------------------------------------------------
    # Checklist Selection & Live Guidance Drawer
    # -------------------------------------------------------------------------

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        """Update guidance drawer when a checklist item or service is highlighted."""
        if getattr(self, "_is_cross_filtering", False):
            return

        if not event.item or not isinstance(event.item, DataListItem) or event.item.is_placeholder:
            return

        obj = event.item.data_obj
        if not obj:
            return

        active = self.get_current_target()
        target_ip = active.ip if active else ""

        if event.list_view.id == "list-checklist":
            try:
                guidance_box = self.query_one("#guidance-box", ConsoleBar)
                title = obj.title if isinstance(obj, ChecklistItem) else str(obj)
                guidance_box.update_guidance(title, target_ip=target_ip)
            except Exception:
                pass
        elif event.list_view.id == "list-services" and isinstance(obj, Service):
            self._guidance_for_service(obj, target_ip)
            # Debounce secondary list alignment during rapid scrolling (40ms settle window)
            if hasattr(self, "_cross_filter_timer") and self._cross_filter_timer is not None:
                self._cross_filter_timer.stop()
            self._cross_filter_timer = self.set_timer(0.04, lambda: self._cross_filter_for_service(obj))

    # -------------------------------------------------------------------------
    # List Population with Clear Formatting
    # -------------------------------------------------------------------------

    def _set_count(self, label_id: str, text: str) -> None:
        try:
            self.query_one(f"#{label_id}", Label).update(text)
        except Exception:
            pass

    def _format_service_row(self, s: Service) -> Text:
        txt = Text()
        txt.append(get_service_status_icon(s.status.value, self.theme_name))
        txt.append(get_protocol_badge(s.port, s.protocol, self.theme_name))
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
        return txt

    def _format_credential_row(self, c: Credential) -> Text:
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
        return txt

    def _format_checklist_row(self, item: ChecklistItem) -> Text:
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
        return txt

    def _update_checklist_progress(self) -> None:
        """Update checklist header counters and status strip progress bar without rebuilding lists."""
        active = self.get_current_target()
        target_id = active.id if active else None
        items = self.store.list_checklist_items(target_id=target_id)
        checked_count = sum(1 for i in items if i.status == ChecklistStatus.CHECKED)
        total_items = len(items)
        pct = int((checked_count / total_items * 100)) if total_items > 0 else 0

        bar_len = 10
        filled = int(bar_len * (checked_count / total_items)) if total_items > 0 else 0
        bar_str = "█" * filled + "░" * (bar_len - filled)
        hdr_txt = f"{bar_str} {pct:>3d}% {checked_count}/{total_items}" if total_items else "—"
        self._set_count("cnt-checklist", hdr_txt)

        try:
            self.query_one("#target-info", MachineStatusStrip).update_status(
                target=active,
                checklist_total=total_items,
                checklist_done=checked_count,
            )
        except Exception:
            pass

    def refresh_all(self) -> None:
        """Refresh all data lists from the database."""
        with self.batch_update():
            active_target = self.get_current_target()
            target_id = active_target.id if active_target else None
            targets = self.store.list_targets()

            # Check which tab is currently active to avoid rendering hidden tabs
            try:
                active_tab = self.query_one("#tabs", TabbedContent).active
            except Exception:
                active_tab = "tab-worksheet"

            # 1. Services & Ports (Notion 01 format with Potential and Next Action)
            svc_list = self.query_one("#list-services", ListView)
            saved_svc_idx = svc_list.index
            svc_list.clear()
            services = self.store.list_services(target_id=target_id) if target_id else []
            self._set_count("cnt-services", f"{len(services)} ports" if services else "—")
            if services:
                for s in services:
                    svc_list.append(DataListItem(data_obj=s, display_text=self._format_service_row(s)))
            else:
                txt = Text("  • No services recorded (Press 's' to add or type ':s 80/tcp http')", style="dim italic")
                svc_list.append(DataListItem(data_obj=None, display_text=txt, is_placeholder=True))
            if saved_svc_idx is not None and len(svc_list.children) > 0:
                svc_list.index = min(saved_svc_idx, len(svc_list.children) - 1)

            # 2. Credentials (Compact Preview in Tab 1 + Full List in Tab 3)
            c_list = self.query_one("#list-creds", ListView)
            saved_c_idx = c_list.index
            c_list.clear()
            creds = self.store.list_credentials(target_id=target_id)
            self._set_count("cnt-creds", f"{len(creds)} saved" if creds else "—")
            if creds:
                for c in creds:
                    c_list.append(DataListItem(data_obj=c, display_text=self._format_credential_row(c)))
            else:
                txt = Text("  • No credentials saved (Press 'c' to add)", style="dim italic")
                c_list.append(DataListItem(data_obj=None, display_text=txt, is_placeholder=True))
            if saved_c_idx is not None and len(c_list.children) > 0:
                c_list.index = min(saved_c_idx, len(c_list.children) - 1)

            # Tab 3 Credential Matrix: only update if user is looking at Tab 3
            if active_tab == "tab-creds":
                self.refresh_cred_matrix()

            # 3. Checklist & Progress Bar
            ck_list = self.query_one("#list-checklist", ListView)
            saved_ck_idx = ck_list.index
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
                    ck_list.append(DataListItem(data_obj=item, display_text=self._format_checklist_row(item)))
            else:
                txt = Text("  • Press 'm' to load templates (ejpt, web, pivoting, smb, privesc)", style="dim italic")
                ck_list.append(DataListItem(data_obj=None, display_text=txt, is_placeholder=True))
            if saved_ck_idx is not None and len(ck_list.children) > 0:
                ck_list.index = min(saved_ck_idx, len(ck_list.children) - 1)

            # 4. Combined Field Notes, Evidence & Findings
            n_list = self.query_one("#list-notes", ListView)
            saved_n_idx = n_list.index
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
            if saved_n_idx is not None and len(n_list.children) > 0:
                n_list.index = min(saved_n_idx, len(n_list.children) - 1)

            # 5. Fast Header and Status Strip update (reusing already-queried lists!)
            failures = self.store.list_failure_logs(target_id=target_id)
            dead_ends = sum(1 for i in items if i.status == ChecklistStatus.DEAD_END)
            counts = {
                "ports": len(services),
                "creds": len(creds),
                "vulns": len(findings),
                "notes": len(notes),
                "dead_ends": dead_ends,
                "failures": len(failures),
            }
            self._refresh_header(
                active_target,
                targets,
                counts=counts,
                items=items,
                failure_count=len(failures),
            )

            # 6. Tab 4: Loot & Flags Widget update (only if active)
            if active_tab == "tab-loot":
                self.refresh_loot_widget(active_target, failures)

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
                copied: Optional[str] = None
                if isinstance(obj, Service) and obj.next_action:
                    copied = obj.next_action
                else:
                    active = self.store.get_active_target()
                    target_ip = active.ip if active else None
                    copied = extract_copy_value(item.data_obj, target_ip=target_ip)
                if copied:
                    copy_to_clipboard(copied)
                    try:
                        console = self.query_one("#guidance-box", ConsoleBar)
                        console.show_copied_feedback(copied)
                    except Exception:
                        pass
                    self.notify(f"Copied: {copied}")
                    return
        self.notify("Select a valid item to copy (y)")

    def action_toggle_selected(self) -> None:
        """Toggle checklist status or credential reveal with in-place differential row updates."""
        focused = self.focused
        if isinstance(focused, ListView) and focused.highlighted_child:
            item = focused.highlighted_child
            if isinstance(item, DataListItem) and not item.is_placeholder and item.data_obj:
                obj = item.data_obj
                if isinstance(obj, ChecklistItem):
                    updated = self.store.cycle_checklist_status(obj.id)
                    if updated:
                        item.data_obj = updated
                        item.update_display(self._format_checklist_row(updated))
                    else:
                        item.update_display(self._format_checklist_row(obj))
                    self._update_checklist_progress()
                    return
                elif isinstance(obj, Service):
                    updated = self.store.cycle_service_status(obj.id)
                    if updated:
                        item.data_obj = updated
                        item.update_display(self._format_service_row(updated))
                    else:
                        item.update_display(self._format_service_row(obj))
                    self.refresh_targets()
                    return
                elif isinstance(obj, Credential):
                    if obj.id in self.revealed_creds:
                        self.revealed_creds.remove(obj.id)
                    else:
                        self.revealed_creds.add(obj.id)
                    item.update_display(self._format_credential_row(obj))
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
        clear_badge_caches()
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

                if data.get("subnet") or data.get("is_pivot"):
                    self.store.update_target_details(
                        target.id,
                        subnet=data.get("subnet", ""),
                        is_pivot=bool(data.get("is_pivot", False)),
                    )

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

        def on_template_selected(result: Any) -> None:
            if not result:
                return
            if isinstance(result, tuple):
                template_name, replace = result
            else:
                template_name, replace = result, True

            try:
                items = apply_template_to_store(
                    self.store, template_name, target_id=target_id, replace=replace
                )
                # Reset checklist cursor to top when switching methodology
                try:
                    ck_list = self.query_one("#list-checklist", ListView)
                    ck_list.index = 0
                except Exception:
                    pass
                self.refresh_all()
                t_name = template_name.upper()
                action_word = "Switched to" if replace else "Appended"
                self.notify(f"{action_word} {t_name} methodology ({len(items)} items)")
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

        from cyb0x_s.tui.commands import execute_command

        execute_command(self, val)

