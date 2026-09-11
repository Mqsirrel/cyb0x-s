"""Regression tests for the v0.2.0 features ported onto the GLACIS mainline.

Covers: Pulse station (0), onboarding welcome card, Exam Mode badge,
reduced-motion station fades, diff-append/in-place roster sync, and the
pulse/snapshot/exam-safety CLI surface.
"""

import pytest
from textual.widgets import ListView, TabbedContent, TabPane

from glacis.db.store import NotebookStore
from glacis.models import ChecklistStatus, ServiceStatus
from glacis.tui.app import CyboxSafeApp
from glacis.tui.widgets import PulseWidget, WorksheetHeader

# -----------------------------------------------------------------------------
# Pulse station
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pulse_station_renders_and_refreshes() -> None:
    store = NotebookStore(":memory:")
    target = store.add_target("10.10.10.20", hostname="dc01")
    store.add_service(target_id=target.id, port=445, service="SMB")

    app = CyboxSafeApp(store=store)
    async with app.run_test(size=(140, 40)) as pilot:
        await pilot.press("0")
        await pilot.pause()
        tabbed = app.query_one("#tabs", TabbedContent)
        assert tabbed.active == "tab-pulse"
        pw = app.query_one("#pulse-view", PulseWidget)
        from rich.console import Console

        buf = Console()
        with buf.capture() as cap:
            buf.print(pw._render_dashboard(app.store))
        rendered = cap.get()
        assert "PULSE" in rendered
        assert "10.10.10.20" in rendered  # scorecard row


@pytest.mark.asyncio
async def test_pulse_paint_skip_skips_identical_state() -> None:
    store = NotebookStore(":memory:")
    store.set_setting("welcome_seen", "1")
    target = store.add_target("10.10.10.30")
    app = CyboxSafeApp(store=store)
    async with app.run_test(size=(140, 40)) as pilot:
        await pilot.press("0")
        await pilot.pause()
        pw = app.query_one("#pulse-view", PulseWidget)
        assert getattr(pw, "_last_paint_key", None) is not None

        calls = {"n": 0}
        original = pw._render_dashboard

        def counting(store_arg):
            calls["n"] += 1
            return original(store_arg)

        pw._render_dashboard = counting
        pw.refresh_pulse()  # warm-up after patch (settles size key)
        calls["n"] = 0
        pw.refresh_pulse()
        pw.refresh_pulse()
        assert calls["n"] == 0, "unchanged fingerprint+palette+size must skip repaint"

        store.add_note(target_id=target.id, content="changes the fingerprint")
        pw.refresh_pulse()
        assert calls["n"] == 1, "changed data must repaint"


# -----------------------------------------------------------------------------
# Welcome card (first-run onboarding)
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_welcome_card_auto_shows_once_then_never_again() -> None:
    store = NotebookStore(":memory:")  # brand-new workspace
    app = CyboxSafeApp(store=store)
    async with app.run_test(size=(120, 34)) as pilot:
        await pilot.pause()
        await pilot.pause()
        from glacis.tui.widgets import WelcomeModal

        assert isinstance(app.screen, WelcomeModal), "first run must open the welcome card"
        await pilot.press("escape")
        await pilot.pause()
        assert store.get_setting("welcome_seen") == "1"

    # Second launch: suppressed.
    app2 = CyboxSafeApp(store=store)
    async with app2.run_test(size=(120, 34)) as pilot2:
        await pilot2.pause()
        from glacis.tui.widgets import WelcomeModal

        assert not isinstance(app2.screen, WelcomeModal)


@pytest.mark.asyncio
async def test_welcome_reopens_via_command() -> None:
    from glacis.tui.commands import execute_command
    from glacis.tui.widgets import WelcomeModal

    store = NotebookStore(":memory:")
    store.set_setting("welcome_seen", "1")
    app = CyboxSafeApp(store=store)
    async with app.run_test(size=(120, 34)) as pilot:
        await pilot.pause()
        execute_command(app, ":welcome")
        await pilot.pause()
        assert isinstance(app.screen, WelcomeModal)


# -----------------------------------------------------------------------------
# Exam Mode (visible badge for AI-proctored exams)
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_exam_mode_badge_and_persistence() -> None:
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
        assert store.get_setting("exam_mode") == "1"
        assert "EXAM MODE" in header.render().plain

        app2 = CyboxSafeApp(store=store)
        async with app2.run_test(size=(140, 40)) as pilot2:
            await pilot2.pause()
            assert app2.exam_mode is True, "exam mode must persist across sessions"
            assert "EXAM MODE" in app2.query_one(WorksheetHeader).render().plain
            app2.set_exam_mode(False)
            await pilot2.pause()
            assert store.get_setting("exam_mode") == "0"
            assert "EXAM MODE" not in app2.query_one(WorksheetHeader).render().plain


# -----------------------------------------------------------------------------
# Station fade: 60fps ramp, generation guard, reduced-motion
# -----------------------------------------------------------------------------

def test_fade_ramp_is_60fps_out_cubic() -> None:
    steps = CyboxSafeApp._FADE_STEPS
    assert len(steps) == 8, "one step per animation frame (~60fps)"
    assert steps[-1] == 1.0
    assert steps == tuple(sorted(steps))
    assert all(0.0 <= v <= 1.0 for v in steps)
    assert CyboxSafeApp._FADE_STEP_MS <= 17


@pytest.mark.asyncio
async def test_fade_generation_guard_cancels_stale_frames() -> None:

    store = NotebookStore(":memory:")
    store.set_setting("welcome_seen", "1")
    app = CyboxSafeApp(store=store)
    async with app.run_test(size=(140, 40)) as pilot:
        await pilot.pause()
        pane_content = app.query_one("#tab-worksheet", TabPane).children[0]

        # Tests run with GLACIS_ANIMATE=0 (conftest): fades are disabled and
        # opacity must jump straight to 1.0 — no timers, no races.
        app._fade_in_station("tab-worksheet")
        assert pane_content.styles.opacity == 1.0

        # The generation guard itself: a frame from an older fade is a no-op.
        g_now = app._fade_gen
        app._fade_frame(g_now - 1, pane_content, 0.5)
        assert pane_content.styles.opacity != 0.5, "stale-generation frame must be cancelled"
        app._fade_frame(g_now, pane_content, 0.5)
        assert pane_content.styles.opacity == 0.5, "current-generation frame must apply"


@pytest.mark.asyncio
async def test_reduced_motion_pref_overrides(monkeypatch) -> None:
    store = NotebookStore(":memory:")
    store.set_setting("welcome_seen", "1")
    app = CyboxSafeApp(store=store)
    async with app.run_test(size=(140, 40)) as pilot:
        await pilot.pause()
        # env explicitly on -> enabled even though conftest default is off
        monkeypatch.setenv("GLACIS_ANIMATE", "1")
        monkeypatch.delenv("SSH_CONNECTION", raising=False)
        assert app._station_fade_enabled() is True

        # persisted '0' wins over env-absence
        monkeypatch.delenv("GLACIS_ANIMATE")
        store.set_setting("animations", "0")
        assert app._station_fade_enabled() is False

        # explicit '1' re-enables even under SSH
        store.set_setting("animations", "1")
        monkeypatch.setenv("SSH_CONNECTION", "1.2.3.4 5.6.7.8 22")
        assert app._station_fade_enabled() is True

        # auto: SSH session with no explicit pref -> off
        store.set_setting("animations", "-")
        store.conn.commit()
        app.store.set_setting("animations", "")  # clear
        # remove the key entirely
        store.conn.execute("DELETE FROM settings WHERE key = 'animations'")
        store.conn.commit()
        assert app._station_fade_enabled() is False, "SSH auto-detect defaults to reduced motion"


# -----------------------------------------------------------------------------
# Roster sync: append fast path + in-place toggle (same-length updates)
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_roster_append_fast_path_preserves_widgets() -> None:
    store = NotebookStore(":memory:")
    target = store.add_target("10.10.10.40")
    store.add_service(target_id=target.id, port=22, service="SSH")
    app = CyboxSafeApp(store=store)
    async with app.run_test(size=(140, 40)) as pilot:
        await pilot.pause()
        lv = app.query_one("#list-services", ListView)
        before = list(lv.children)
        assert len(before) == 1

        store.add_service(target_id=target.id, port=80, service="HTTP")
        app.refresh_all()
        await pilot.pause()

        after = list(lv.children)
        assert len(after) == 2
        assert after[0] is before[0], "append must not rebuild existing rows"


@pytest.mark.asyncio
async def test_roster_in_place_status_toggle_avoids_rebuild() -> None:
    store = NotebookStore(":memory:")
    target = store.add_target("10.10.10.50")
    svc = store.add_service(target_id=target.id, port=22, service="SSH")
    app = CyboxSafeApp(store=store)
    async with app.run_test(size=(140, 40)) as pilot:
        await pilot.pause()
        lv = app.query_one("#list-services", ListView)
        original = lv.children[0]
        before_text = original.display_text.plain

        # Same-length in-place update: TODO->CHECKED style status flips must
        # update the row in place (widget identity kept, text refreshed).
        store.update_service_status(svc.id, ServiceStatus.DEAD_END)
        app.refresh_all()
        await pilot.pause()

        assert lv.children[0] is original, "same-length toggle must update in place"
        assert lv.children[0].display_text.plain != before_text, "row text must refresh"


@pytest.mark.asyncio
async def test_checklist_toggle_updates_in_place() -> None:
    store = NotebookStore(":memory:")
    target = store.add_target("10.10.10.60")
    item = store.add_checklist_item(title="enum SMB", target_id=target.id)
    app = CyboxSafeApp(store=store)
    async with app.run_test(size=(140, 40)) as pilot:
        await pilot.pause()
        lv = app.query_one("#list-checklist", ListView)
        original = lv.children[0]

        store.update_checklist_status(item.id, ChecklistStatus.CHECKED)
        app.refresh_all()
        await pilot.pause()

        assert lv.children[0] is original
        panel = app.query_one("#panel-checklist")
        subtitle = str(panel.border_subtitle or "")
        assert "1/1" in subtitle or "100" in subtitle, f"progress not updated: {subtitle!r}"


@pytest.mark.asyncio
async def test_roster_delete_falls_back_to_rebuild() -> None:
    store = NotebookStore(":memory:")
    target = store.add_target("10.10.10.70")
    s1 = store.add_service(target_id=target.id, port=22, service="SSH")
    store.add_service(target_id=target.id, port=80, service="HTTP")
    app = CyboxSafeApp(store=store)
    async with app.run_test(size=(140, 40)) as pilot:
        await pilot.pause()
        lv = app.query_one("#list-services", ListView)
        assert len(lv.children) == 2

        store.delete_service(s1.id)
        app.refresh_all()
        await pilot.pause()

        lv2 = app.query_one("#list-services", ListView)
        assert len(lv2.children) == 1
        assert "80" in lv2.children[0].display_text.plain


@pytest.mark.asyncio
async def test_notes_panel_merges_and_appends() -> None:
    store = NotebookStore(":memory:")
    target = store.add_target("10.10.10.80")
    store.add_note(target_id=target.id, content="first note")
    app = CyboxSafeApp(store=store)
    async with app.run_test(size=(140, 40)) as pilot:
        await pilot.pause()
        lv = app.query_one("#list-notes", ListView)
        before = list(lv.children)
        assert len(before) == 1

        store.add_note(target_id=target.id, content="second note")
        app.refresh_all()
        await pilot.pause()
        after = list(lv.children)
        assert len(after) == 2
        assert after[0] is before[0], "note append must keep existing row"

        store.add_finding(target_id=target.id, title="anon SMB", severity="HIGH")
        app.refresh_all()
        await pilot.pause()
        lv2 = app.query_one("#list-notes", ListView)
        assert len(lv2.children) == 3
        assert "[VULN]" in lv2.children[0].display_text.plain, "findings sort first"
        assert "first note" in lv2.children[1].display_text.plain


# -----------------------------------------------------------------------------
# CLI: pulse, snapshots, exam-safety audit
# -----------------------------------------------------------------------------

def test_cli_exam_check_passes(cli_runner, temp_db_path) -> None:
    from glacis.cli import cli

    res = cli_runner.invoke(cli, ["--db", str(temp_db_path), "exam-check"])
    assert res.exit_code == 0
    assert "EXAM-SAFETY AUDIT" in res.output
    assert "FAIL" not in res.output, "glacis sources must have zero network imports"
    assert "zero network imports" in res.output


def test_cli_stats_and_timeline(seeded_store, cli_runner, temp_db_path, monkeypatch) -> None:
    from glacis.cli import cli

    res = cli_runner.invoke(cli, ["--db", str(temp_db_path), "stats"])
    assert res.exit_code == 0
    res = cli_runner.invoke(cli, ["--db", str(temp_db_path), "timeline", "-n", "5"])
    assert res.exit_code == 0


def test_cli_backup_and_backups(cli_runner, temp_db_path, tmp_path, monkeypatch) -> None:
    from glacis.cli import cli

    monkeypatch.chdir(tmp_path)  # snapshots land in the CWD workspace — keep the repo clean
    res = cli_runner.invoke(cli, ["--db", str(temp_db_path), "backup", "--label", "test"])
    assert res.exit_code == 0
    res = cli_runner.invoke(cli, ["--db", str(temp_db_path), "backups"])
    assert res.exit_code == 0
    assert "test" in res.output or "snapshot" in res.output.lower()
