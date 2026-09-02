"""Interactive TUI automated testing using Textual test pilot."""

import pytest
from textual.widgets import Input

from cyb0x_s.db.store import NotebookStore
from cyb0x_s.models import ChecklistStatus
from cyb0x_s.tui.app import CyboxSafeApp
from cyb0x_s.tui.widgets import SearchModal


@pytest.mark.asyncio
async def test_tui_lifecycle_and_navigation() -> None:
    store = NotebookStore(":memory:")
    # Seed data
    target = store.add_target("10.10.10.20", hostname="target.local", os_name="Linux")
    store.add_service(target_id=target.id, port=445, service="SMB", version="Samba 4.3")
    store.add_finding(title="SMB Anonymous Share", target_id=target.id)
    store.add_credential(username="admin", secret="Summer2024!", target_id=target.id)
    store.add_checklist_item(title="SMB null session", target_id=target.id, status=ChecklistStatus.TODO)
    store.add_note("Note 1", target_id=target.id)

    app = CyboxSafeApp(store=store)

    async with app.run_test() as pilot:
        # Check initial UI state
        assert app.is_running
        target_info = app.query_one("#target-info")
        assert "10.10.10.20" in target_info.render().plain

        # Test command bar submission: :n Quick Note Added
        cmd_input = app.query_one("#cmd-input", Input)
        cmd_input.focus()
        cmd_input.value = ":n Quick Note Added"
        await cmd_input.action_submit()
        await pilot.pause()

        # Verify note added to DB
        notes = store.list_notes(target_id=target.id)
        assert any(n.content == "Quick Note Added" for n in notes)

        # Test opening search modal
        app.action_open_search()
        await pilot.pause()
        assert any(isinstance(screen, SearchModal) for screen in app.screen_stack)

        # Exit search modal with Escape
        await pilot.press("escape")
        await pilot.pause()

        # Focus non-input widget so number hotkeys trigger
        app.query_one("#list-services").focus()
        await pilot.pause()

        # Test tab switching with hotkeys: 2 -> Playbooks
        await pilot.press("2")
        await pilot.pause()
        tabbed = app.query_one("#tabs")
        assert tabbed.active == "tab-playbooks"

        # Test tab switching: 3 -> Creds
        await pilot.press("3")
        await pilot.pause()
        assert tabbed.active == "tab-creds"

        # Test tab switching: 4 -> Loot / Flags
        await pilot.press("4")
        await pilot.pause()
        assert tabbed.active == "tab-loot"

        # Test tab switching back: 1 -> Worksheet
        await pilot.press("1")
        await pilot.pause()
        assert tabbed.active == "tab-worksheet"

        # Test tree population
        tree = app.query_one("#target-tree")
        assert tree is not None
        assert len(tree.root.children) == 1

        # Test scope toggle action
        app.action_toggle_scope()
        await pilot.pause()
        updated_target = store.get_target(target.id)
        assert updated_target is not None
        assert updated_target.is_in_scope is False

        # Quit app
        app.exit()

    store.close()


