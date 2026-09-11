"""Regression tests for the visual-design audit.

These lock in the findings of the terminal-UI review so a future change cannot
silently reintroduce them:

* every palette meets WCAG AAA (7:1) for text tokens and keeps panel borders
  above the non-text contrast floor;
* chrome glyphs stay inside the verified, single-cell, emoji-free set;
* keycap-looking border titles survive repainting (a leading ``[/`` used to
  raise ``MarkupError`` and silently freeze the console bar);
* composed rows elide instead of being guillotined mid-word.
"""

from __future__ import annotations

import pytest

from glacis.tui.theme import (
    AAA_CONTRAST,
    GLYPHS,
    PALETTES,
    SAFE_CHROME_GLYPHS,
    STRUCTURE_CONTRAST,
    contrast_audit,
)
from glacis.tui.widgets.lists import elide, elide_middle, keycap_line, status_badge


# ---------------------------------------------------------------------------
# Colour
# ---------------------------------------------------------------------------


def test_every_palette_meets_wcag_aaa_for_text() -> None:
    failures = contrast_audit()
    assert failures == {}, f"palettes below {AAA_CONTRAST}:1 -> {failures}"


@pytest.mark.parametrize("name", sorted(PALETTES))
def test_panel_borders_are_discernible(name: str) -> None:
    pal = PALETTES[name]
    assert pal.contrast_ratio(pal.border, pal.surface) >= STRUCTURE_CONTRAST


@pytest.mark.parametrize("name", sorted(PALETTES))
def test_semantic_tokens_stay_above_aaa_on_both_backgrounds(name: str) -> None:
    pal = PALETTES[name]
    for token in ("text", "text_soft", "muted", "accent", "ok", "warn", "danger"):
        fg = getattr(pal, token)
        for bg_name in ("bg", "surface"):
            ratio = pal.contrast_ratio(fg, getattr(pal, bg_name))
            assert ratio >= AAA_CONTRAST, f"{name}.{token} on {bg_name} = {ratio:.2f}"


@pytest.mark.parametrize("name", sorted(PALETTES))
def test_accent_and_background_are_mutually_legible(name: str) -> None:
    """The active-tab pill paints $background text on $accent."""
    pal = PALETTES[name]
    assert pal.contrast_ratio(pal.accent, pal.bg) >= AAA_CONTRAST


# ---------------------------------------------------------------------------
# Iconography
# ---------------------------------------------------------------------------


def test_chrome_glyphs_are_verified_single_cell_glyphs() -> None:
    offenders = {
        name: glyph for name, glyph in GLYPHS.items() if glyph not in SAFE_CHROME_GLYPHS
    }
    assert offenders == {}, f"unverified glyphs in taxonomy: {offenders}"


def test_glyph_taxonomy_is_unambiguous_within_each_domain() -> None:
    """Two glyphs meaning different things *in the same place* is the bug.

    Cross-domain reuse is deliberate and meaningful (★ is both the Loot
    station and "root / pwned" because the Loot station is where root is
    banked), but inside one vocabulary every concept needs its own mark.
    """
    domains = {
        "stations": ["pulse", "cockpit", "playbooks", "credentials", "loot", "network"],
        "host phases": [
            "host_untouched",
            "host_recon",
            "host_foothold",
            "host_user",
            "host_root",
            "host_complete",
        ],
        "states": [
            "done",
            "open",
            "untested",
            "deferred",
            "dead_end",
            "invalid",
            "pwned",
            "warn",
            "hint",
            "info",
            "next",
            "run",
            "pivot",
        ],
    }
    for domain, keys in domains.items():
        seen: dict[str, list[str]] = {}
        for key in keys:
            seen.setdefault(GLYPHS[key], []).append(key)
        shared = {g: names for g, names in seen.items() if len(names) > 1}
        assert shared == {}, f"{domain}: glyphs reused for different meanings: {shared}"


# ---------------------------------------------------------------------------
# Border titles / keycaps
# ---------------------------------------------------------------------------


def test_keycap_border_titles_do_not_raise_markup_errors() -> None:
    """Regression: ``" [/ Search] · [Enter: Copy] "`` killed the whole repaint.

    Textual parses a plain ``str`` border title as console markup, so the
    leading ``[/`` was read as a closing tag. The exception happened inside a
    repaint the caller had wrapped in ``try/except``, so Station 2 silently
    kept the *previous* station's console copy.
    """
    from textual.app import ComposeResult
    from textual.widgets import Static

    from glacis.tui.widgets.chrome import set_border_text

    class _Pane(Static):
        pass

    pane = _Pane("x")
    for title in (
        " STATION 2 · ATTACK PLAYBOOKS ",
        " [/ Search] · [Enter: Copy] ",
        " [w: Cycle Panels] · [0-5: Stations] ",
    ):
        set_border_text(pane, title=title, subtitle=title)
        # Textual re-encodes the Text as an escaped markup string; the point is
        # that nothing raised and every character survived the round-trip.
        assert str(pane.border_title).replace("\\", "") == title
        assert str(pane.border_subtitle).replace("\\", "") == title


@pytest.mark.asyncio
async def test_console_bar_follows_the_active_station(seeded_store) -> None:
    """The end-to-end regression: Station 2 used to show Station 1's copy."""
    from glacis.tui.app import GlacisApp

    app = GlacisApp(store=seeded_store)
    async with app.run_test(size=(160, 44)) as pilot:
        expected = {
            "0": "PULSE",
            "1": "COCKPIT",
            "2": "PLAYBOOKS",
            "3": "CREDENTIALS",
            "4": "PROOFS & FLAGS",
            "5": "NETWORK",
        }
        for key, station in expected.items():
            await pilot.press(key)
            await pilot.pause()
            screen = "\n".join(
                "".join(seg.text for seg in strip._segments)
                for strip in app.screen._compositor.render_strips()
            )
            assert f"{station} \u25b8" in screen, f"console bar did not follow station {key}"


def test_keycap_line_renders_brackets_verbatim() -> None:
    text = keycap_line(("a", "add proof"), ("Enter", "copy"))
    # A markup string would drop "[a]" and "[Enter]" entirely.
    assert text.plain == "[a] add proof · [Enter] copy"


# ---------------------------------------------------------------------------
# Row composition
# ---------------------------------------------------------------------------


def test_elide_marks_the_clip() -> None:
    assert elide("evidence/proof_screenshot_01.png", 20).endswith("…")
    assert elide("short", 20) == "short"
    clipped = elide("evidence/proof_screenshot_01.png", 20)
    assert clipped == "evidence/proof_scre…"
    assert len(clipped) == 20


def test_elide_middle_keeps_the_discriminating_tail() -> None:
    clipped = elide_middle("evidence/proof_screenshot_01.png", 24)
    assert clipped == "evidence/pro…shot_01.png"
    assert len(clipped) == 24
    assert elide_middle("eJPT{root_flag_f04b8d195ae32}", 20) == "eJPT{root_…d195ae32}"


def test_status_badges_share_one_width() -> None:
    widths = {status_badge(state).plain for state in ("TODO", "CHECKED", "DEFERRED", "DEAD-END")}
    assert len({len(w) for w in widths}) == 1, "ragged pills break the column raster"
