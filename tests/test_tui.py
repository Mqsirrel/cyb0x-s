"""Interactive TUI automated testing using Textual test pilot."""

import pytest
from textual.widgets import Input, ListView, TabbedContent, TabPane

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


# -----------------------------------------------------------------------------
# Performance: roster diff-refresh keeps scroll & appends in O(change)
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tui_roster_append_fast_path_preserves_list_item() -> None:
    store = NotebookStore(":memory:")
    target = store.add_target("10.10.10.20", hostname="box")
    store.add_service(target_id=target.id, port=22, service="SSH")
    app = CyboxSafeApp(store=store)

    async with app.run_test(size=(140, 40)) as pilot:
        await pilot.pause()

        lv = app.query_one("#list-services", ListView)
        before = list(lv.children)
        assert len(before) == 1

        # Append-only change: existing widget objects should be kept.
        store.add_service(target_id=target.id, port=80, service="HTTP")
        app.refresh_all()
        await pilot.pause()

        after = list(lv.children)
        assert len(after) == 2
        assert after[0] is before[0], "append fast path must not rebuild existing rows"
        assert not after[0].is_placeholder

        # Deletion path still stays correct (full rebuild).
        store.delete_service(after[1].data_obj.id)
        app.refresh_all()
        await pilot.pause()
        assert len(app.query_one("#list-services", ListView).children) == 1


# -----------------------------------------------------------------------------
# Exam Mode: visible badge for proctored exams
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tui_exam_mode_badge_and_persistence() -> None:
    store = NotebookStore(":memory:")
    store.set_setting("welcome_seen", "1")
    app = CyboxSafeApp(store=store)

    async with app.run_test(size=(140, 40)) as pilot:
        await pilot.pause()
        header = app.query_one(WorksheetHeader)

        assert header.exam_mode is False
        app.action_toggle_exam_mode()
        await pilot.pause()
        assert app.exam_mode is True
        assert header.exam_mode is True
        assert store.get_setting("exam_mode") == "1"
        header_render = header.render().plain
        assert "EXAM MODE" in header_render

        # Restores across "restarts" (new app, same store).
        app2 = CyboxSafeApp(store=store)
        async with app2.run_test(size=(140, 40)) as pilot2:
            await pilot2.pause()
            assert app2.exam_mode is True
            assert "EXAM MODE" in app2.query_one(WorksheetHeader).render().plain
            app2.set_exam_mode(False)
            await pilot2.pause()
            assert store.get_setting("exam_mode") == "0"
            assert "EXAM MODE" not in app2.query_one(WorksheetHeader).render().plain


# -----------------------------------------------------------------------------
# Performance round 2: 60fps fades, notes fast path, pulse paint-skip
# -----------------------------------------------------------------------------

def test_fade_ramp_is_60fps_out_cubic() -> None:
    app_cls = CyboxSafeApp
    steps = app_cls._FADE_STEPS
    assert len(steps) == 8, "one step per animation frame (~60fps)"
    assert steps[-1] == 1.0
    assert steps == tuple(sorted(steps))
    assert all(0.0 <= v <= 1.0 for v in steps)
    assert app_cls._FADE_STEP_MS <= 17, "at most one step per frame"


@pytest.mark.asyncio
async def test_fade_runs_and_generation_guard_supersedes() -> None:
    store = NotebookStore(":memory:")
    store.set_setting("welcome_seen", "1")
    app = CyboxSafeApp(store=store)

    async with app.run_test(size=(140, 40)) as pilot:
        await pilot.pause()
        import asyncio as _asyncio

        app._fade_in_station("tab-worksheet")
        pane_content = app.query_one("#tab-worksheet", TabPane).children[0]
        # Poll with a generous deadline: under parallel test load the 16 ms
        # frame timers fire late, but they always fire.
        loop = _asyncio.get_running_loop()
        deadline = loop.time() + 5.0
        while pane_content.styles.opacity != 1.0 and loop.time() < deadline:
            await _asyncio.sleep(0.02)
        assert pane_content.styles.opacity == 1.0, "fade must land fully opaque"

        # The generation guard: a frame scheduled by an older fade must be a
        # no-op once a newer fade started (rapid station flipping never lets
        # an old fade fight the new one).
        g_now = app._fade_gen
        app._fade_frame(g_now - 1, pane_content, 0.5)
        assert pane_content.styles.opacity != 0.5, "stale-generation frame must be cancelled"
        app._fade_frame(g_now, pane_content, 0.5)
        assert pane_content.styles.opacity == 0.5, "current-generation frame must apply"


@pytest.mark.asyncio
async def test_notes_panel_append_fast_path_preserves_rows() -> None:
    store = NotebookStore(":memory:")
    target = store.add_target("10.10.10.30", hostname="web")
    store.add_note(target_id=target.id, content="first note")
    app = CyboxSafeApp(store=store)

    async with app.run_test(size=(140, 40)) as pilot:
        await pilot.pause()

        lv = app.query_one("#list-notes", ListView)
        before = list(lv.children)
        assert len(before) == 1 and not before[0].is_placeholder

        # Appending a second note extends the notes segment -> fast path
        # keeps the existing row widget alive.
        store.add_note(target_id=target.id, content="second note")
        app.refresh_all()
        await pilot.pause()

        after = list(lv.children)
        assert len(after) == 2
        assert after[0] is before[0], "notes fast path must not rebuild existing rows"
        texts = [c.display_text.plain for c in after]
        assert "[NOTE]" in texts[0] and "[NOTE]" in texts[1]

        # A finding sorts BEFORE notes (prepend) -> correct full rebuild.
        store.add_finding(target_id=target.id, title="anon SMB", severity="HIGH")
        app.refresh_all()
        await pilot.pause()
        lv2 = app.query_one("#list-notes", ListView)
        assert len(lv2.children) == 3
        assert "[VULN]" in lv2.children[0].display_text.plain
        assert "[NOTE]" in lv2.children[1].display_text.plain
        assert "first note" in lv2.children[1].display_text.plain

        # Deletions still fall back to a correct full rebuild.
        store.delete_note(before[0].data_obj.id)
        app.refresh_all()
        await pilot.pause()
        lv3 = app.query_one("#list-notes", ListView)
        assert len(lv3.children) == 2
        assert "[VULN]" in lv3.children[0].display_text.plain


@pytest.mark.asyncio
async def test_pulse_widget_skips_noop_repaints() -> None:
    store = NotebookStore(":memory:")
    store.set_setting("welcome_seen", "1")
    target = store.add_target("10.10.10.40")
    app = CyboxSafeApp(store=store)

    async with app.run_test(size=(140, 40)) as pilot:
        await pilot.press("0")  # station 0 renders Pulse once
        await pilot.pause()
        pw = app.query_one("#pulse-view", PulseWidget)
        assert getattr(pw, "_last_paint_key", None) is not None, "first paint recorded"

        calls = {"n": 0}
        original = pw._render_dashboard

        def counting(store_arg):
            calls["n"] += 1
            return original(store_arg)

        pw._render_dashboard = counting

        pw.refresh_pulse()  # warm-up: settle layout size after the patch
        calls["n"] = 0
        pw.refresh_pulse()  # nothing changed -> skip
        pw.refresh_pulse()
        assert calls["n"] == 0, "identical fingerprint+palette+size must skip repaint"

        store.add_note(target_id=target.id, content="new data changes the fingerprint")
        pw.refresh_pulse()
        assert calls["n"] == 1, "changed data must repaint"
