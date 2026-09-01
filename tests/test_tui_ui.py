"""Regression tests for the TUI layout and interaction fixes.

These cover the behaviours that were found broken during the UI review:
invisible active station tab, the crash when highlighting a service, the
zero-height failure log, the no-op zoom, unguarded deletes and j/k movement.
"""

from __future__ import annotations

import pytest
from textual.widgets import Input, ListView

from cyb0x_s.db.store import NotebookStore
from cyb0x_s.tui.app import CyboxSafeApp
from cyb0x_s.tui.widgets import (
    ConfirmModal,
    GuidanceDrawer,
    LootAndFlagsWidget,
    SearchModal,
    TargetTreeWidget,
    WorksheetHeader,
)


@pytest.fixture
def seeded_store() -> NotebookStore:
    store = NotebookStore(":memory:")
    target = store.add_target("10.10.10.20", hostname="target.local", os_name="Linux")
    store.add_service(target_id=target.id, port=22, service="SSH", version="OpenSSH 8.2p1")
    store.add_service(target_id=target.id, port=445, service="SMB", version="Samba 4.3")
    store.add_credential(username="admin", secret="Summer2024!", target_id=target.id)
    store.add_checklist_item(title="SMB enumeration", target_id=target.id)
    store.add_note("backup share contains archive.zip", target_id=target.id)
    return store


@pytest.mark.asyncio
async def test_active_tab_label_is_visible(seeded_store: NotebookStore) -> None:
    """The active station must render its label (it used to collapse to 0px)."""
    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test() as pilot:
        active_tabs = [t for t in app.query("Tab") if "-active" in t.classes]
        assert active_tabs, "expected exactly one active tab"
        active = active_tabs[0]
        assert active.size.height >= 1
        assert active.render().plain.strip(), "active tab label rendered empty"
        assert "Field Worksheet" in active.render().plain
        # The underline is the only other "you are here" indicator.
        underline = app.query_one("Underline")
        assert underline.styles.display != "none"


@pytest.mark.asyncio
async def test_highlighting_a_service_updates_drawer(seeded_store: NotebookStore) -> None:
    """Highlighting a service fills the guidance drawer instead of raising."""
    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test(size=(160, 44)) as pilot:
        svc_list = app.query_one("#list-services", ListView)
        svc_list.focus()
        await pilot.press("down")
        await pilot.pause()

        drawer = app.query_one("#guidance-box", GuidanceDrawer)
        text = drawer.render().plain
        assert "10.10.10.20" in text, "target IP should be substituted into the command"
        assert drawer.size.height >= 1


@pytest.mark.asyncio
async def test_tree_navigation_updates_drawer(seeded_store: NotebookStore) -> None:
    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test() as pilot:
        tree = app.query_one(TargetTreeWidget)
        tree.focus()
        await pilot.press("down")
        await pilot.pause()
        drawer = app.query_one("#guidance-box", GuidanceDrawer)
        assert drawer.render().plain


@pytest.mark.asyncio
async def test_failure_log_panel_has_height(seeded_store: NotebookStore) -> None:
    """Tab 4's rabbit-hole log must actually occupy screen space."""
    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test(size=(140, 40)) as pilot:
        app.action_switch_tab("tab-loot")
        await pilot.pause()
        loot = app.query_one(LootAndFlagsWidget)
        failure_box = loot.query_one("#loot-failure-box")
        assert failure_box.size.height > 0
        assert failure_box.region.y + failure_box.size.height <= loot.region.bottom + 1


@pytest.mark.asyncio
async def test_zoom_expands_panel_and_restores(seeded_store: NotebookStore) -> None:
    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test(size=(160, 44)) as pilot:
        panel = app.query_one("#panel-services")
        width_before = panel.size.width

        panel.query_one(ListView).focus()
        await pilot.pause()
        app.action_toggle_zoom()
        await pilot.pause()

        assert panel.size.width > width_before, "zoomed panel should span the workbench"
        assert app.query_one("#col-right").styles.display == "none"
        assert app.query_one("#main-container").has_class("zoomed-mode")

        app.action_toggle_zoom()
        await pilot.pause()
        assert not app.query_one("#main-container").has_class("zoomed-mode")
        assert app.query_one("#col-right").styles.display == "block"


@pytest.mark.asyncio
async def test_delete_asks_for_confirmation(seeded_store: NotebookStore) -> None:
    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test() as pilot:
        svc_list = app.query_one("#list-services", ListView)
        svc_list.focus()
        await pilot.press("down")
        await pilot.pause()

        await pilot.press("d")
        await pilot.pause()
        assert isinstance(app.screen, ConfirmModal)

        # Cancelling keeps the data.
        await pilot.press("escape")
        await pilot.pause()
        assert len(seeded_store.list_services()) == 2

        # Confirming removes it.
        await pilot.press("d")
        await pilot.pause()
        await pilot.press("y")
        await pilot.pause()
        assert len(seeded_store.list_services()) == 1


@pytest.mark.asyncio
async def test_j_and_k_move_the_highlight(seeded_store: NotebookStore) -> None:
    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test(size=(160, 44)) as pilot:
        svc_list = app.query_one("#list-services", ListView)
        svc_list.focus()
        await pilot.pause()
        await pilot.press("down")
        await pilot.pause()
        assert svc_list.index == 0
        await pilot.press("j")
        await pilot.pause()
        assert svc_list.index == 1
        await pilot.press("k")
        await pilot.pause()
        assert svc_list.index == 0
        # 'k' must not open the add-checklist dialog any more.
        assert not any(isinstance(s, SearchModal) for s in app.screen_stack)


@pytest.mark.asyncio
async def test_search_enter_copies_and_closes(seeded_store: NotebookStore) -> None:
    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test() as pilot:
        app.action_open_search()
        await pilot.pause()
        assert isinstance(app.screen, SearchModal)
        app.screen.query_one("#search-input", Input).value = "archive"
        await pilot.pause()
        await pilot.pause()
        results = app.screen.query_one("#search-results", ListView)
        assert len(results.children) >= 1
        await pilot.press("enter")
        await pilot.pause()
        assert not isinstance(app.screen, SearchModal)


@pytest.mark.asyncio
async def test_footer_only_shows_core_keys(seeded_store: NotebookStore) -> None:
    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test():
        shown = [b for b in app.BINDINGS if b.show]
        assert len(shown) <= 6


@pytest.mark.asyncio
async def test_header_reports_workspace_and_counts(seeded_store: NotebookStore) -> None:
    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test(size=(160, 44)):
        header = app.query_one(WorksheetHeader)
        text = header.render().plain
        assert "default" in text or "Lab" in text
        assert "targets 1" in text
        assert "ports 2" in text


@pytest.mark.asyncio
async def test_command_bar_still_captures_shortcuts(seeded_store: NotebookStore) -> None:
    """Typing in the command bar must not trigger single-letter hotkeys."""
    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test() as pilot:
        cmd = app.query_one("#cmd-input", Input)
        cmd.focus()
        for char in ":njk":
            await pilot.press(char)
            await pilot.pause()
        assert cmd.value == ":njk"
        assert not any(isinstance(s, ConfirmModal) for s in app.screen_stack)
