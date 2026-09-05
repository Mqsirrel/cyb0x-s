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




@pytest.mark.asyncio
async def test_T_opens_picker_with_all_palettes(seeded_store: NotebookStore) -> None:
    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test(size=(160, 44)) as pilot:
        await pilot.press("T")
        assert isinstance(app.screen, ThemePickerModal)
        assert len(app.screen.query(ThemeSwatch)) == len(PALETTES)
        # Enter keeps the current palette and closes.
        await pilot.press("enter")
        assert len(app.screen_stack) == 1


@pytest.mark.asyncio
async def test_picker_move_down_previews_and_esc_restores(seeded_store: NotebookStore) -> None:
    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test(size=(160, 44)) as pilot:
        await pilot.press("T")
        original = app.theme_name

        await pilot.press("down")
        assert app.theme_name != original, "moving the cursor should preview a new palette"

        await pilot.press("escape")
        assert app.theme_name == original, "Esc should restore the previous palette"
        assert len(app.screen_stack) == 1


@pytest.mark.asyncio
async def test_picker_reopen_move_enter_keeps_preview(seeded_store: NotebookStore) -> None:
    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test(size=(160, 44)) as pilot:
        await pilot.press("T")
        await pilot.press("down")
        previewed = app.theme_name

        await pilot.press("enter")
        assert app.theme_name == previewed, "Enter should keep the previewed palette"
        assert len(app.screen_stack) == 1


def test_palette_contrast_and_accessibility() -> None:
    """Pure mathematical contrast and accessibility checks (instant, no TUI overhead)."""
    for name, palette in PALETTES.items():
        assert palette.contrast_ratio() >= 7.0, name
        assert palette.contrast_ratio(palette.muted, palette.bg) >= 4.5, name
        assert len(palette.swatch()) == 7, name


@pytest.mark.asyncio
async def test_every_palette_renders_and_is_accessible(seeded_store: NotebookStore) -> None:
    """Verify live theme switching across all palettes in the TUI."""
    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test(size=(160, 44)) as pilot:
        for name in PALETTES:
            app.apply_theme(name, quiet=True)
            assert app.theme_name == name
        await pilot.pause(0)

        # Cycle through stations once to confirm the status strip stays alive
        for key in ("2", "3", "4", "1"):
            await pilot.press(key)
            strip = app.query_one(MachineStatusStrip)
            assert strip.render().plain.strip(), f"tab {key} rendered empty"


@pytest.mark.asyncio
async def test_guidance_gate_console(seeded_store: NotebookStore) -> None:
    """With guidance off (default) the console proposes no tool for a service."""
    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test(size=(160, 44)) as pilot:
        assert derive_guidance_enabled() is False
        svc_list = app.query_one("#list-services", ListView)
        svc_list.focus()
        await pilot.press("down")
        console = app.query_one("#guidance-box", ConsoleBar)
        cmd_off = console.query_one("#console-cmd").render().plain
        assert "feroxbuster" not in cmd_off
        assert "smbmap" not in cmd_off

        # Opting in restores the suggestion for the highlighted service.
        set_derive_guidance(True)
        smb_service = seeded_store.list_services()[1]  # port 445 SMB (ports sorted)
        app._guidance_for_service(smb_service, "10.10.10.20")
        await pilot.pause(0)
        cmd_on = console.query_one("#console-cmd").render().plain
        assert "smbmap" in cmd_on
        set_derive_guidance(None)


def test_resolve_palette_name_and_aliases() -> None:
    from cyb0x_s.tui.theme import get_default_theme, resolve_palette_name

    assert resolve_palette_name("1") == "slate"
    assert resolve_palette_name("2") == "midnight"
    assert resolve_palette_name("3") == "ember"
    assert resolve_palette_name("4") == "cyber"
    assert resolve_palette_name("5") == "sugary"
    assert resolve_palette_name("6") == "candy"
    assert resolve_palette_name("7") == "caramel"

    # Prefix and short abbreviations
    assert resolve_palette_name("su") == "sugary"
    assert resolve_palette_name("sug") == "sugary"
    assert resolve_palette_name("sugar") == "sugary"
    assert resolve_palette_name("ca") == "candy"
    assert resolve_palette_name("can") == "candy"
    assert resolve_palette_name("car") == "caramel"
    assert resolve_palette_name("sl") == "slate"
    assert resolve_palette_name("mid") == "midnight"
    assert resolve_palette_name("em") == "ember"
    assert resolve_palette_name("cy") == "cyber"
    assert resolve_palette_name("c") == "cyber"
    assert resolve_palette_name("tokyo") == "cyber"

    # Fallbacks and default
    assert resolve_palette_name("invalid_theme_xyz") is None
    assert resolve_palette_name("") is None
    assert get_default_theme() == "slate"


@pytest.mark.asyncio
async def test_picker_digit_hotkey_instantly_selects(seeded_store: NotebookStore) -> None:
    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test(size=(160, 44)) as pilot:
        # Press T to open picker, then press '5' for sugary
        await pilot.press("T")
        assert isinstance(app.screen, ThemePickerModal)

        await pilot.press("5")
        assert app.theme_name == "sugary"
        assert len(app.screen_stack) == 1

        # Press T again, then press '1' for slate
        await pilot.press("T")
        await pilot.press("1")
        assert app.theme_name == "slate"
        assert len(app.screen_stack) == 1


@pytest.mark.asyncio
async def test_command_bar_prefix_theme_switch(seeded_store: NotebookStore) -> None:
    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test(size=(160, 44)) as pilot:
        cmd_input = app.query_one("#cmd-input")
        cmd_input.focus()

        # Switch to sugary using prefix ':theme su'
        cmd_input.value = ":theme su"
        await pilot.press("enter")
        assert app.theme_name == "sugary"

        # Switch to midnight using ':theme mid'
        cmd_input.value = ":theme mid"
        await pilot.press("enter")
        assert app.theme_name == "midnight"

        # Switch using digit ':theme 3' (ember)
        cmd_input.value = ":theme 3"
        await pilot.press("enter")
        assert app.theme_name == "ember"


@pytest.mark.asyncio
async def test_set_default_theme_in_picker(seeded_store: NotebookStore, monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """Test pressing 'd' in the theme picker sets the persistent default."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from cyb0x_s.tui.theme import get_default_theme

    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test(size=(160, 44)) as pilot:
        await pilot.press("T")
        assert isinstance(app.screen, ThemePickerModal)

        # Move to midnight (index 1) and press 'd'
        await pilot.press("down")
        assert app.theme_name == "midnight"

        await pilot.press("d")
        assert len(app.screen_stack) == 1
        assert app.theme_name == "midnight"
        assert get_default_theme(seeded_store) == "midnight"


@pytest.mark.asyncio
async def test_command_bar_set_default_theme(seeded_store: NotebookStore, monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """Test setting default theme via command bar ':theme default sugary'."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from cyb0x_s.tui.theme import get_default_theme

    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test(size=(160, 44)) as pilot:
        cmd_input = app.query_one("#cmd-input")
        cmd_input.focus()

        cmd_input.value = ":theme default sugary"
        await pilot.press("enter")

        assert app.theme_name == "sugary"
        assert get_default_theme(seeded_store) == "sugary"


@pytest.mark.asyncio
async def test_sugary_themes_apply_and_render(seeded_store: NotebookStore) -> None:
    """Test applying sugary, candy, and caramel themes."""
    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test(size=(160, 44)) as pilot:
        for theme_name in ("sugary", "candy", "caramel"):
            app.apply_theme(theme_name)
            await pilot.pause(0)
            assert app.theme_name == theme_name
            strip = app.query_one(MachineStatusStrip)
            assert strip.render().plain.strip()


