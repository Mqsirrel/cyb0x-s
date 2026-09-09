"""Interactive TUI automated testing using Textual test pilot."""

import pytest
from textual.widgets import Input, ListView, TabbedContent

from glacis.db.store import NotebookStore
from glacis.models import ChecklistStatus
from glacis.tui.app import CyboxSafeApp
from glacis.tui.widgets import PulseWidget, SearchModal, WelcomeModal, WorksheetHeader


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

        # Focus non-input widget so number hotkeys trigger
        app.query_one("#list-services").focus()

        # Test tab switching with hotkeys: 2 -> Playbooks
        await pilot.press("2")
        tabbed = app.query_one("#tabs")
        assert tabbed.active == "tab-playbooks"

        # Test tab switching: 3 -> Creds
        await pilot.press("3")
        assert tabbed.active == "tab-creds"

        # Test tab switching: 4 -> Loot / Flags
        await pilot.press("4")
        assert tabbed.active == "tab-loot"

        # Test tab switching back: 1 -> Worksheet
        await pilot.press("1")
        assert tabbed.active == "tab-worksheet"

        # Test tree population
        tree = app.query_one("#target-tree")
        assert tree is not None
        assert len(tree.root.children) == 1

        # Test scope toggle action
        app.action_toggle_scope()
        await pilot.pause(0)
        updated_target = store.get_target(target.id)
        assert updated_target is not None
        assert updated_target.is_in_scope is False

        # Quit app
        app.exit()

    store.close()




# -----------------------------------------------------------------------------
# Station 0 — Pulse dashboard (v0.2.0)
# -----------------------------------------------------------------------------

def _pulse_text(app) -> str:
    """Render the PulseWidget's Rich renderable to plain text."""
    import io

    from rich.console import Console

    pulse_widget = app.query_one("#pulse-view", PulseWidget)
    buf = io.StringIO()
    console = Console(file=buf, width=200, legacy_windows=False, force_terminal=False)
    console.print(pulse_widget._render_dashboard(app.store))
    return buf.getvalue()

@pytest.mark.asyncio
async def test_tui_pulse_station_renders_dashboard() -> None:
    store = NotebookStore(":memory:")
    target = store.add_target("10.10.10.20", hostname="target.local", os_name="Linux")
    store.add_service(target_id=target.id, port=445, service="SMB", version="Samba 4.3")
    store.add_finding(title="SMB Anonymous Share", target_id=target.id, severity="HIGH")
    store.add_credential(username="admin", secret="Summer2024!", target_id=target.id)
    store.add_note("check backup share", target_id=target.id)

    app = CyboxSafeApp(store=store)

    async with app.run_test(size=(140, 44)) as pilot:
        await pilot.press("0")
        await pilot.pause()

        tabbed = app.query_one("#tabs", TabbedContent)
        assert tabbed.active == "tab-pulse"

        rendered = _pulse_text(app)
        assert "PULSE" in rendered
        assert "TARGET SCORECARDS" in rendered
        assert "NEXT ACTIONS" in rendered
        assert "TIMELINE" in rendered
        assert "10.10.10.20" in rendered

        # Header breadcrumb reflects the new station
        header = app.query_one(WorksheetHeader)
        assert header.active_station == "Pulse"

        # Return to cockpit still works
        await pilot.press("1")
        await pilot.pause()
        assert tabbed.active == "tab-worksheet"


@pytest.mark.asyncio
async def test_tui_pulse_station_empty_workspace() -> None:
    store = NotebookStore(":memory:")
    app = CyboxSafeApp(store=store)

    async with app.run_test(size=(140, 44)) as pilot:
        await pilot.press("0")
        await pilot.pause()
        rendered = _pulse_text(app)
        assert "PULSE" in rendered  # empty workspace must not crash the station


# -----------------------------------------------------------------------------
# First-run onboarding (welcome card) & self-explanatory empty states
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tui_welcome_shows_once_and_dismisses() -> None:
    store = NotebookStore(":memory:")
    app = CyboxSafeApp(store=store)

    async with app.run_test(size=(120, 34)) as pilot:
        await pilot.pause()
        assert any(isinstance(s, WelcomeModal) for s in app.screen_stack), \
            "welcome card should auto-open for a brand-new empty workspace"

        await pilot.press("escape")
        await pilot.pause()
        assert not any(isinstance(s, WelcomeModal) for s in app.screen_stack)
        assert store.get_setting("welcome_seen") == "1"

        # A second pass must NOT greet again (setting persisted).
        app._maybe_show_welcome()
        await pilot.pause()
        assert not any(isinstance(s, WelcomeModal) for s in app.screen_stack)


@pytest.mark.asyncio
async def test_tui_welcome_not_shown_when_targets_exist() -> None:
    store = NotebookStore(":memory:")
    store.add_target("10.10.10.20")
    app = CyboxSafeApp(store=store)

    async with app.run_test(size=(120, 34)) as pilot:
        await pilot.pause()
        assert not any(isinstance(s, WelcomeModal) for s in app.screen_stack)


@pytest.mark.asyncio
async def test_tui_welcome_reopen_command() -> None:
    store = NotebookStore(":memory:")
    store.set_setting("welcome_seen", "1")
    app = CyboxSafeApp(store=store)

    async with app.run_test(size=(120, 34)) as pilot:
        await pilot.pause()
        from glacis.tui.commands import execute_command

        execute_command(app, ":welcome")
        await pilot.pause()
        assert any(isinstance(s, WelcomeModal) for s in app.screen_stack)
        await pilot.press("q")  # any key dismisses
        await pilot.pause()
        assert not any(isinstance(s, WelcomeModal) for s in app.screen_stack)


@pytest.mark.asyncio
async def test_tui_empty_states_are_self_explanatory() -> None:
    store = NotebookStore(":memory:")
    store.set_setting("welcome_seen", "1")
    app = CyboxSafeApp(store=store)

    async with app.run_test(size=(120, 34)) as pilot:
        await pilot.pause()
        from glacis.tui.widgets import TargetTreeWidget

        tree = app.query_one("#target-tree", TargetTreeWidget)
        assert "press t" in str(tree.root.label)

        # Every empty cockpit panel advertises its fill key.
        for list_id, key_hint in (("#list-services", "press s"), ("#list-creds", "press c"),
                                  ("#list-checklist", "press m"), ("#list-notes", "n note")):
            lst = app.query_one(list_id, ListView)
            texts = []
            for child in lst.children:
                hint = getattr(child, "display_text", None)
                texts.append(hint.plain if hint is not None else str(child))
            rendered = " ".join(texts)
            assert key_hint in rendered, f"{list_id} hint should mention '{key_hint}', got: {rendered}"
