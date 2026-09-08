"""Tests for the theme picker, palette contrast, and the derive-guidance gate."""

from __future__ import annotations

import pytest
from textual.widgets import ListView

from glacis.db.store import NotebookStore
from glacis.settings import derive_guidance_enabled, set_derive_guidance
from glacis.tui.app import GlacisApp
from glacis.tui.theme import PALETTES
from glacis.tui.widgets import (
    ConsoleBar,
    MachineStatusStrip,
    ThemePickerModal,
    ThemeSwatch,
)


def test_palette_contrast_and_accessibility() -> None:
    """Pure mathematical contrast and accessibility checks (instant, no TUI overhead)."""
    for name, palette in PALETTES.items():
        assert palette.contrast_ratio() >= 7.0, name
        assert palette.contrast_ratio(palette.muted, palette.bg) >= 4.5, name
        assert len(palette.swatch()) == 7, name


def test_resolve_palette_name_and_aliases() -> None:
    from glacis.tui.theme import get_default_theme, resolve_palette_name

    assert resolve_palette_name("1") == "slate"
    assert resolve_palette_name("2") == "midnight"
    assert resolve_palette_name("3") == "ember"
    assert resolve_palette_name("4") == "cyber"
    assert resolve_palette_name("5") == "sugary"
    assert resolve_palette_name("6") == "candy"
    assert resolve_palette_name("7") == "caramel"
    assert resolve_palette_name("8") == "catppuccin"

    # Prefix and short abbreviations
    assert resolve_palette_name("su") == "sugary"
    assert resolve_palette_name("sug") == "sugary"
    assert resolve_palette_name("sugar") == "sugary"
    assert resolve_palette_name("ca") == "candy"
    assert resolve_palette_name("can") == "candy"
    assert resolve_palette_name("car") == "caramel"
    assert resolve_palette_name("cat") == "catppuccin"
    assert resolve_palette_name("catp") == "catppuccin"
    assert resolve_palette_name("mocha") == "catppuccin"
    assert resolve_palette_name("catppuccin") == "catppuccin"
    assert resolve_palette_name("sl") == "slate"
    assert resolve_palette_name("glacier") == "slate"
    assert resolve_palette_name("frost") == "slate"
    assert resolve_palette_name("ice") == "slate"
    assert resolve_palette_name("glacis") == "slate"
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
async def test_theme_picker_modal_full_workflow(
    seeded_store: NotebookStore, monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """Consolidated end-to-end verification of theme picker modal behaviors.

    Tests opening with 'T', swatch enumeration, arrow preview, Esc restoration,
    Enter confirmation, digit instant selection, and 'd' default persistence
    in a single headless run to minimize harness setup overhead.
    """
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from glacis.tui.theme import get_default_theme

    app = GlacisApp(store=seeded_store)
    async with app.run_test(size=(160, 44)) as pilot:
        # 1. 'T' opens picker with all palette swatches
        await pilot.press("T")
        assert isinstance(app.screen, ThemePickerModal)
        assert len(app.screen.query(ThemeSwatch)) == len(PALETTES)

        # 2. Moving down previews; Escape cancels and restores original
        original = app.theme_name
        await pilot.press("down")
        assert app.theme_name != original, "moving cursor should preview a new palette"
        await pilot.press("escape")
        assert app.theme_name == original, "Esc should restore the previous palette"
        assert len(app.screen_stack) == 1

        # 3. Reopen, move down, Enter confirms and keeps preview
        await pilot.press("T")
        await pilot.press("down")
        previewed = app.theme_name
        await pilot.press("enter")
        assert app.theme_name == previewed, "Enter should keep the previewed palette"
        assert len(app.screen_stack) == 1

        # 4. Digit hotkeys select instantly and dismiss modal
        await pilot.press("T")
        await pilot.press("5")  # sugary
        assert app.theme_name == "sugary"
        assert len(app.screen_stack) == 1

        await pilot.press("T")
        await pilot.press("8")  # catppuccin
        assert app.theme_name == "catppuccin"
        assert len(app.screen_stack) == 1

        await pilot.press("T")
        await pilot.press("1")  # slate
        assert app.theme_name == "slate"
        assert len(app.screen_stack) == 1

        # 5. Pressing 'd' sets persistent default
        await pilot.press("T")
        await pilot.press("down")  # midnight
        assert app.theme_name == "midnight"
        await pilot.press("d")
        assert len(app.screen_stack) == 1
        assert app.theme_name == "midnight"
        assert get_default_theme(seeded_store) == "midnight"


@pytest.mark.asyncio
async def test_command_bar_theme_switching(
    seeded_store: NotebookStore, monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """Test switching themes and setting persistent default via command bar."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from glacis.tui.theme import get_default_theme

    app = GlacisApp(store=seeded_store)
    async with app.run_test(size=(160, 44)) as pilot:
        cmd_input = app.query_one("#cmd-input")
        cmd_input.focus()

        # Prefix ':theme su' -> sugary
        cmd_input.value = ":theme su"
        await pilot.press("enter")
        assert app.theme_name == "sugary"

        # Prefix ':theme mid' -> midnight
        cmd_input.value = ":theme mid"
        await pilot.press("enter")
        assert app.theme_name == "midnight"

        # Digit ':theme 3' -> ember
        cmd_input.value = ":theme 3"
        await pilot.press("enter")
        assert app.theme_name == "ember"

        # Digit ':theme 8' -> catppuccin
        cmd_input.value = ":theme 8"
        await pilot.press("enter")
        assert app.theme_name == "catppuccin"

        # ':theme' alone cycles to next palette (catppuccin -> slate)
        cmd_input.value = ":theme"
        await pilot.press("enter")
        assert app.theme_name == "slate"

        # Persistent default ':theme default sugary'
        cmd_input.value = ":theme default sugary"
        await pilot.press("enter")
        assert app.theme_name == "sugary"
        assert get_default_theme(seeded_store) == "sugary"

        # Invalid theme name does not change theme
        cmd_input.value = ":theme nope"
        await pilot.press("enter")
        assert app.theme_name == "sugary"


@pytest.mark.asyncio
async def test_every_palette_renders_and_is_accessible(seeded_store: NotebookStore) -> None:
    """Verify live theme switching across all palettes in the TUI."""
    app = GlacisApp(store=seeded_store)
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
    app = GlacisApp(store=seeded_store)
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


@pytest.mark.asyncio
async def test_action_cycle_theme_all_palettes(seeded_store: NotebookStore) -> None:
    """Verify action_cycle_theme cycles through all 8 registered palettes in order and wraps around."""
    app = GlacisApp(store=seeded_store)
    async with app.run_test(size=(160, 44)):
        names = list(PALETTES.keys())
        # Start at default (slate)
        assert app.theme_name == names[0]
        # Cycle through all other palettes
        for expected in names[1:] + [names[0]]:
            app.action_cycle_theme()
            assert app.theme_name == expected



