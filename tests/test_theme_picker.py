"""Tests for the theme picker, palette contrast, and the derive-guidance gate."""

from __future__ import annotations

import pytest
from textual.widgets import ListView

from cyb0x_s.db.store import NotebookStore
from cyb0x_s.settings import derive_guidance_enabled, set_derive_guidance
from cyb0x_s.tui.app import CyboxSafeApp
from cyb0x_s.tui.theme import PALETTES
from cyb0x_s.tui.widgets import (
    ConsoleBar,
    MachineStatusStrip,
    ThemePickerModal,
    ThemeSwatch,
)


@pytest.fixture
def seeded_store() -> NotebookStore:
    store = NotebookStore(":memory:")
    target = store.add_target("10.10.10.20", hostname="target.local", os_name="Linux")
    store.add_service(target_id=target.id, port=22, service="SSH", version="OpenSSH 8.2p1")
    store.add_service(target_id=target.id, port=445, service="SMB", version="Samba 4.3")
    return store


@pytest.mark.asyncio
async def test_T_opens_picker_with_all_palettes(seeded_store: NotebookStore) -> None:
    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test(size=(160, 44)) as pilot:
        await pilot.press("T")
        await pilot.pause()
        assert isinstance(app.screen, ThemePickerModal)
        assert len(app.screen.query(ThemeSwatch)) == len(PALETTES)
        # Enter keeps the current palette and closes.
        await pilot.press("enter")
        await pilot.pause()
        assert len(app.screen_stack) == 1


@pytest.mark.asyncio
async def test_picker_move_down_previews_and_esc_restores(seeded_store: NotebookStore) -> None:
    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test(size=(160, 44)) as pilot:
        await pilot.press("T")
        await pilot.pause()
        original = app.theme_name

        await pilot.press("down")
        await pilot.pause()
        assert app.theme_name != original, "moving the cursor should preview a new palette"

        await pilot.press("escape")
        await pilot.pause()
        assert app.theme_name == original, "Esc should restore the previous palette"
        assert len(app.screen_stack) == 1


@pytest.mark.asyncio
async def test_picker_reopen_move_enter_keeps_preview(seeded_store: NotebookStore) -> None:
    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test(size=(160, 44)) as pilot:
        await pilot.press("T")
        await pilot.pause()
        await pilot.press("down")
        await pilot.pause()
        previewed = app.theme_name

        await pilot.press("enter")
        await pilot.pause()
        assert app.theme_name == previewed, "Enter should keep the previewed palette"
        assert len(app.screen_stack) == 1


@pytest.mark.asyncio
async def test_every_palette_renders_and_is_accessible(seeded_store: NotebookStore) -> None:
    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test(size=(160, 44)) as pilot:
        for name in PALETTES:
            palette = PALETTES[name]
            # Contrast is AAA for body text, AA for muted text on its own bg.
            assert palette.contrast_ratio() >= 7.0, name
            assert palette.contrast_ratio(palette.muted, palette.bg) >= 4.5, name
            assert len(palette.swatch()) == 7, name

            app.apply_theme(name, quiet=True)
            await pilot.pause()
            assert app.theme_name == name

            # Cycle through the stations and confirm the status strip stays alive.
            for key in ("2", "3", "4", "1"):
                await pilot.press(key)
                await pilot.pause()
                strip = app.query_one(MachineStatusStrip)
                assert strip.render().plain.strip(), f"{name} tab {key} rendered empty"


@pytest.mark.asyncio
async def test_guidance_gate_console(seeded_store: NotebookStore) -> None:
    """With guidance off (default) the console proposes no tool for a service."""
    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test(size=(160, 44)) as pilot:
        assert derive_guidance_enabled() is False
        svc_list = app.query_one("#list-services", ListView)
        svc_list.focus()
        await pilot.press("down")
        await pilot.pause()
        console = app.query_one("#guidance-box", ConsoleBar)
        cmd_off = console.query_one("#console-cmd").render().plain
        assert "feroxbuster" not in cmd_off
        assert "smbmap" not in cmd_off

        # Opting in restores the suggestion for the highlighted service.
        set_derive_guidance(True)
        smb_service = seeded_store.list_services()[1]  # port 445 SMB (ports sorted)
        app._guidance_for_service(smb_service, "10.10.10.20")
        await pilot.pause()
        cmd_on = console.query_one("#console-cmd").render().plain
        assert "smbmap" in cmd_on
        set_derive_guidance(None)
