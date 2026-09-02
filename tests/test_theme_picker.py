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
        await pilot.pause()

        # Cycle through stations once to confirm the status strip stays alive
        for key in ("2", "3", "4", "1"):
            await pilot.press(key)
            await pilot.pause()
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


def test_resolve_palette_name_and_aliases() -> None:
    from cyb0x_s.tui.theme import get_default_theme, resolve_palette_name

    assert resolve_palette_name("1") == "slate"
    assert resolve_palette_name("2") == "midnight"
    assert resolve_palette_name("3") == "ember"
    assert resolve_palette_name("4") == "moss"
    assert resolve_palette_name("5") == "neon"
    assert resolve_palette_name("6") == "mono"
    assert resolve_palette_name("7") == "warm"
    assert resolve_palette_name("8") == "cyber"

    # Prefix and short abbreviations
    assert resolve_palette_name("w") == "warm"
    assert resolve_palette_name("wa") == "warm"
    assert resolve_palette_name("sl") == "slate"
    assert resolve_palette_name("mid") == "midnight"
    assert resolve_palette_name("em") == "ember"
    assert resolve_palette_name("mo") == "moss"
    assert resolve_palette_name("ne") == "neon"
    assert resolve_palette_name("mon") == "mono"
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
        # Press T to open picker, then press '7' for warm
        await pilot.press("T")
        await pilot.pause()
        assert isinstance(app.screen, ThemePickerModal)

        await pilot.press("7")
        await pilot.pause()
        assert app.theme_name == "warm"
        assert len(app.screen_stack) == 1

        # Press T again, then press '1' for slate
        await pilot.press("T")
        await pilot.pause()
        await pilot.press("1")
        await pilot.pause()
        assert app.theme_name == "slate"
        assert len(app.screen_stack) == 1


@pytest.mark.asyncio
async def test_command_bar_prefix_theme_switch(seeded_store: NotebookStore) -> None:
    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test(size=(160, 44)) as pilot:
        cmd_input = app.query_one("#cmd-input")
        cmd_input.focus()

        # Switch to warm using prefix ':theme w'
        cmd_input.value = ":theme w"
        await pilot.press("enter")
        await pilot.pause()
        assert app.theme_name == "warm"

        # Switch to midnight using ':theme mid'
        cmd_input.value = ":theme mid"
        await pilot.press("enter")
        await pilot.pause()
        assert app.theme_name == "midnight"

        # Switch using digit ':theme 3' (ember)
        cmd_input.value = ":theme 3"
        await pilot.press("enter")
        await pilot.pause()
        assert app.theme_name == "ember"


@pytest.mark.asyncio
async def test_set_default_theme_in_picker(seeded_store: NotebookStore, monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """Test pressing 'd' in the theme picker sets the persistent default."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from cyb0x_s.tui.theme import get_default_theme

    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test(size=(160, 44)) as pilot:
        await pilot.press("T")
        await pilot.pause()
        assert isinstance(app.screen, ThemePickerModal)

        # Move to midnight (index 1) and press 'd'
        await pilot.press("down")
        await pilot.pause()
        assert app.theme_name == "midnight"

        await pilot.press("d")
        await pilot.pause()
        assert len(app.screen_stack) == 1
        assert app.theme_name == "midnight"
        assert get_default_theme(seeded_store) == "midnight"


@pytest.mark.asyncio
async def test_command_bar_set_default_theme(seeded_store: NotebookStore, monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """Test setting default theme via command bar ':theme default warm'."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from cyb0x_s.tui.theme import get_default_theme

    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test(size=(160, 44)) as pilot:
        cmd_input = app.query_one("#cmd-input")
        cmd_input.focus()

        cmd_input.value = ":theme default warm"
        await pilot.press("enter")
        await pilot.pause()

        assert app.theme_name == "warm"
        assert get_default_theme(seeded_store) == "warm"


@pytest.mark.asyncio
async def test_transparency_toggle_and_persistence(seeded_store: NotebookStore, monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """Test toggling glass/transparency via app method and key g in picker."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from cyb0x_s.tui.theme import get_default_transparency

    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test(size=(160, 44)) as pilot:
        assert not app.is_transparent
        assert not app.screen.has_class("transparent")

        # Toggle on
        app.toggle_transparency(persist=True)
        assert app.is_transparent
        assert app.screen.has_class("transparent")
        assert get_default_transparency(seeded_store) is True

        # Open theme picker and press 'g' to toggle off
        await pilot.press("T")
        await pilot.pause()
        assert isinstance(app.screen, ThemePickerModal)

        await pilot.press("g")
        await pilot.pause()
        assert not app.is_transparent
        assert not app.screen.has_class("transparent")
        assert get_default_transparency(seeded_store) is False


@pytest.mark.asyncio
async def test_transparency_command_bar(seeded_store: NotebookStore, monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """Test :trans on and :trans off via bottom command bar."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from cyb0x_s.tui.theme import get_default_transparency

    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test(size=(160, 44)) as pilot:
        cmd_input = app.query_one("#cmd-input")
        cmd_input.focus()

        cmd_input.value = ":trans on"
        await pilot.press("enter")
        await pilot.pause()
        assert app.is_transparent
        assert get_default_transparency(seeded_store) is True

        cmd_input.focus()
        cmd_input.value = ":trans off"
        await pilot.press("enter")
        await pilot.pause()
        assert not app.is_transparent
        assert get_default_transparency(seeded_store) is False


