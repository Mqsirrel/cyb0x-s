"""GLACIS theming: palettes, design tokens and the application stylesheet.

Eight palettes ship with the app:

* ``slate``      — cool glacial graphite chrome with cyan/frost mint data and amber warnings.
                   Default: tuned for long sessions, pristine contrast and at-a-glance state.
* ``midnight``   — indigo / periwinkle, calm and low-flare for long labs.
* ``ember``      — amber CRT, warm monochrome-adjacent reading glow.
* ``cyber``      — tokyo / electric, high-energy cyan and neon accents.
* ``sugary``     — vanilla cream / espresso ink, warm light mode.
* ``candy``      — cotton lilac / glaze, soft pastel background with violet highlights.
* ``caramel``    — toffee / maple sugar, warm parchment with honey and roasted tones.
* ``catppuccin`` — mocha / sapphire, soothing pastel dark theme.

The stylesheet below deliberately contains **no literal colours**: every rule
references a Textual design token (``$surface``, ``$accent``, ``$text-muted`` …)
that is generated from the active :class:`Palette`. Switching palette therefore
only has to swap the registered theme and Textual re-parses the CSS.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from textual.theme import Theme


@dataclass(frozen=True)
class Palette:
    """A complete colour set for the worksheet."""

    name: str
    label: str
    bg: str
    surface: str
    raised: str
    border: str
    border_strong: str
    text: str
    text_soft: str
    muted: str
    accent: str  # focus, ports, data
    ok: str  # captured / checked / success
    warn: str  # deferred / next action / attention
    danger: str  # findings / dead ends / critical
    dark: bool = True

    def _luminance(self, colour: str) -> float:
        """Relative luminance of a ``#RRGGBB`` colour, per WCAG."""
        colour = colour.lstrip("#")
        channels = [int(colour[i : i + 2], 16) / 255 for i in (0, 2, 4)]

        def _linear(c: float) -> float:
            return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

        r, g, b = (_linear(c) for c in channels)
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    def contrast_ratio(self, foreground: str = "", background: str = "") -> float:
        """WCAG contrast ratio between two palette colours (defaults text-on-bg)."""
        fg = self._luminance(foreground or self.text)
        bg = self._luminance(background or self.bg)
        lighter, darker = max(fg, bg), min(fg, bg)
        return (lighter + 0.05) / (darker + 0.05)

    def swatch(self) -> List[tuple[str, str]]:
        """Ordered (label, colour) pairs for the theme picker's colour strip."""
        return [
            ("bg", self.bg),
            ("surface", self.surface),
            ("text", self.text),
            ("accent", self.accent),
            ("ok", self.ok),
            ("warn", self.warn),
            ("danger", self.danger),
        ]

    def textual_theme(self) -> Theme:
        """Build the Textual theme (and thus all ``$`` tokens) for this palette."""
        return Theme(
            name=f"glacis-{self.name}",
            primary=self.accent,
            secondary=self.text_soft,
            accent=self.accent,
            foreground=self.text,
            background=self.bg,
            surface=self.surface,
            panel=self.surface,
            success=self.ok,
            warning=self.warn,
            error=self.danger,
            dark=self.dark,
            variables={
                "text-soft": self.text_soft,
                "border": self.border,
                "border-strong": self.border_strong,
                "border-blurred": self.border,
                "block-cursor-background": self.accent,
                "block-cursor-foreground": self.bg,
                "block-cursor-text-style": "bold",
                "footer-background": self.bg,
                "footer-foreground": self.muted,
                "footer-key-foreground": self.accent,
                "footer-description-foreground": self.text_soft,
                "input-selection-background": self.raised,
                "input-selection-foreground": self.text,
                "scrollbar": self.border_strong,
                "scrollbar-background": self.bg,
                "scrollbar-hover": self.border_strong,
                "scrollbar-active": self.accent,
                "link-color": self.accent,
            },
        )


SLATE = Palette(
    name="slate",
    label="Slate · glacial cyan / frost mint",
    bg="#0E1418",
    surface="#151C22",
    raised="#1D262E",
    border="#49545B",
    border_strong="#5F6D77",
    text="#DDE6EE",
    text_soft="#B6C7D6",
    muted="#98A8B5",
    accent="#4FD6E8",
    ok="#6FE3B0",
    warn="#F5B455",
    danger="#FF816A",
)

MIDNIGHT = Palette(
    name="midnight",
    label="Midnight · indigo / periwinkle",
    bg="#0B1020",
    surface="#131A2E",
    raised="#1C2542",
    border="#48526A",
    border_strong="#5D6A8B",
    text="#DCE3F5",
    text_soft="#AFBAD7",
    muted="#9BA5C0",
    accent="#6DA8FF",
    ok="#7EE7BE",
    warn="#F2C078",
    danger="#FF7C94",
)

EMBER = Palette(
    name="ember",
    label="Ember · amber CRT",
    bg="#120E09",
    surface="#1D1710",
    raised="#272019",
    border="#574F45",
    border_strong="#736757",
    text="#F4E7D2",
    text_soft="#D6C5A8",
    muted="#B2A08D",
    accent="#FFB000",
    ok="#C3D95C",
    warn="#FF8C42",
    danger="#FF7C6A",
)

CYBER = Palette(
    name="cyber",
    label="Cyber · tokyo / electric",
    bg="#0B0F19",
    surface="#121827",
    raised="#1B2337",
    border="#475166",
    border_strong="#38BDF8",
    text="#EEF2F8",
    text_soft="#B0C0DA",
    muted="#97A4B9",
    accent="#00E5FF",
    ok="#00F5A0",
    warn="#FFB800",
    danger="#FF7894",
)

SUGARY = Palette(
    name="sugary",
    label="Sugary · vanilla cream / espresso ink",
    bg="#DFD8CB",
    surface="#EBE5DA",
    raised="#E1DACE",
    border="#A39A8D",
    border_strong="#7E6F5E",
    text="#1C1713",
    text_soft="#3B332B",
    muted="#4A4138",
    accent="#134669",
    ok="#184C29",
    warn="#643805",
    danger="#7F1E1E",
    dark=False,
)

CANDY = Palette(
    name="candy",
    label="Candy · cotton lilac / glaze",
    bg="#FBF7FA",
    surface="#F3E9F1",
    raised="#EADBE7",
    border="#AC9BA9",
    border_strong="#917D8E",
    text="#2B1E29",
    text_soft="#584154",
    muted="#5B4858",
    accent="#6E14C0",
    ok="#08593E",
    warn="#6C4604",
    danger="#9E0923",
    dark=False,
)

CARAMEL = Palette(
    name="caramel",
    label="Caramel · toffee parchment / teal instrument accent",
    bg="#FDF8F3",
    surface="#F5EDE4",
    raised="#EBE0D4",
    border="#ACA094",
    border_strong="#928271",
    text="#302318",
    text_soft="#5E4734",
    muted="#5E4C3A",
    accent="#0A515C",
    ok="#1F5A2C",
    warn="#784203",
    danger="#972323",
    dark=False,
)

CATPPUCCIN = Palette(
    name="catppuccin",
    label="Catppuccin · mocha / sapphire",
    bg="#11111B",
    surface="#181825",
    raised="#1E1E2E",
    border="#4F505F",
    border_strong="#89B4FA",
    text="#CDD6F4",
    text_soft="#BAC2DE",
    muted="#A0A3B5",
    accent="#89B4FA",
    ok="#A6E3A1",
    warn="#FAB387",
    danger="#F38BA8",
    dark=True,
)

PALETTES: Dict[str, Palette] = {
    p.name: p for p in (SLATE, MIDNIGHT, EMBER, CYBER, SUGARY, CANDY, CARAMEL, CATPPUCCIN)
}
DEFAULT_PALETTE = SLATE.name

#: The palette every widget reads at render time. Swapped by :func:`set_palette`.
PALETTE: Palette = PALETTES[DEFAULT_PALETTE]


# ---------------------------------------------------------------------------
# Glyph taxonomy
# ---------------------------------------------------------------------------
#
# Rules for anything that appears in chrome (panel titles, station tabs,
# status pills, rows):
#
#   1. One glyph === one meaning.  ``★`` is always "root / pwned / complete";
#      it is never also the "Loot" station badge or a "credentials" counter.
#   2. No emoji.  Emoji are missing from DejaVu Sans Mono (the default font on
#      most Linux terminals), they are double-width in every terminal that does
#      render them, and their shape changes between emulators. All three
#      effects tear the border grid that every panel here is built from.
#   3. Every glyph below is verified to exist in DejaVu Sans Mono and to
#      advance exactly one cell.  ``tests/test_theme_picker.py`` re-checks it.
#
#: Glyphs that are safe to use in chrome (verified, single-cell, non-emoji).
SAFE_CHROME_GLYPHS = frozenset(
    "★☆◆◇◈●○◐◑▸▷►▲▼△▽✔✖✗✓⌂◎▣▤▥▦■□▪▫⇄↳⊘❯›·•─│┌┐└┘├┤┬┴┼█░▒▀▄▌▐☰§¶✦✚⚡~"
)

#: The one glyph per concept. Import this instead of embedding literals.
GLYPHS: Dict[str, str] = {
    # stations
    "pulse": "◎",
    "cockpit": "⌂",
    "playbooks": "▸",
    "credentials": "◆",
    "loot": "★",
    "network": "◈",
    # cockpit panels
    "surface": "▣",
    "services": "▥",
    "checklist": "☰",
    "notes": "▤",
    # entities
    "target": "▣",
    "host_untouched": "◇",
    "host_recon": "◐",
    "host_foothold": "▸",
    "host_user": "◆",
    "host_root": "★",
    "host_complete": "✔",
    "pivot": "⇄",
    # states
    "done": "✔",
    "open": "●",
    "untested": "○",
    "deferred": "~",
    "dead_end": "✖",
    "invalid": "✗",
    "pwned": "★",
    "warn": "▲",
    "hint": "•",
    "info": "·",
    "next": "▸",
    "run": "❯",
    "dead_end_count": "✖",
    "progress_full": "█",
    "progress_empty": "░",
}


#: WCAG 2.1 "enhanced" (AAA) contrast threshold for body text.
AAA_CONTRAST = 7.0
#: Non-text contrast (WCAG 2.1 SC 1.4.11) - the floor we hold panel borders to
#: so the layout grid stays readable without turning into glare.
STRUCTURE_CONTRAST = 2.0

#: Semantic tokens that carry meaning and are therefore contrast-critical.
SEMANTIC_TOKENS = ("text", "text_soft", "muted", "accent", "ok", "warn", "danger")


def set_palette(name: str) -> Palette:
    """Activate ``name`` and return the palette now in use."""
    global PALETTE
    PALETTE = PALETTES.get(name, PALETTES[DEFAULT_PALETTE])
    return PALETTE


def contrast_audit(
    *, text_target: float = AAA_CONTRAST, structure_target: float = STRUCTURE_CONTRAST
) -> Dict[str, List[tuple[str, str, str, float]]]:
    """Return every palette/token pair that misses its contrast target.

    Each entry is ``(token, foreground, background, ratio)``. An empty mapping
    means the whole palette set is AAA-clean. Rows are checked against *both*
    ``bg`` and ``surface`` because panels paint on ``surface`` while the gaps
    between them paint on ``bg``.
    """
    failures: Dict[str, List[tuple[str, str, str, float]]] = {}
    for name, pal in PALETTES.items():
        rows: List[tuple[str, str, str, float]] = []
        for token in SEMANTIC_TOKENS:
            fg = getattr(pal, token)
            for bg_name in ("bg", "surface"):
                bg = getattr(pal, bg_name)
                ratio = pal.contrast_ratio(fg, bg)
                if ratio < text_target:
                    rows.append((token, fg, bg, round(ratio, 2)))
        border_ratio = pal.contrast_ratio(pal.border, pal.surface)
        if border_ratio < structure_target:
            rows.append(("border", pal.border, pal.surface, round(border_ratio, 2)))
        if rows:
            failures[name] = rows
    return failures


def current_palette() -> Palette:
    return PALETTE


def resolve_palette_name(query: Optional[str]) -> Optional[str]:
    """Resolve a user-supplied theme string, digit (1-8), or prefix into a canonical palette name.

    Examples:
        '1' -> 'slate'
        '4' -> 'cyber'
        '5' -> 'sugary'
        '8' -> 'catppuccin'
        'su' or 'sugary' -> 'sugary'
        'ca' or 'candy' -> 'candy'
        'cat' or 'catppuccin' -> 'catppuccin'
        'sl' or 'slate' -> 'slate'
        'glacier' or 'frost' -> 'slate'
        'mid' or 'midnight' -> 'midnight'
        'em' or 'ember' -> 'ember'
        'cy' or 'cyber' -> 'cyber'
    """
    if not query:
        return None
    q = str(query).strip().lower()
    if not q:
        return None

    names = list(PALETTES)
    # Check 1-based digit index
    if q.isdigit():
        idx = int(q) - 1
        if 0 <= idx < len(names):
            return names[idx]

    # Check exact match
    if q in PALETTES:
        return q

    # Disambiguate common short abbreviations
    alias_map = {
        "sl": "slate",
        "s": "slate",
        "glacier": "slate",
        "glacis": "slate",
        "frost": "slate",
        "ice": "slate",
        "mid": "midnight",
        "mi": "midnight",
        "em": "ember",
        "e": "ember",
        "cy": "cyber",
        "c": "cyber",
        "tokyo": "cyber",
        "cat": "catppuccin",
        "catp": "catppuccin",
        "mocha": "catppuccin",
        "catppuccin": "catppuccin",
        "su": "sugary",
        "sug": "sugary",
        "sugar": "sugary",
        "ca": "candy",
        "can": "candy",
        "car": "caramel",
        "cara": "caramel",
    }
    if q in alias_map and alias_map[q] in PALETTES:
        return alias_map[q]

    # Prefix match
    matches = [name for name in names if name.startswith(q)]
    if len(matches) >= 1:
        return matches[0]

    return None


def get_theme_config_path() -> Path:
    """Return path to persistent theme configuration file."""
    config_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    legacy_file = config_home / "cyb0x-s" / "theme"
    theme_dir = config_home / "glacis"
    theme_dir.mkdir(parents=True, exist_ok=True)
    theme_file = theme_dir / "theme"
    if not theme_file.exists() and legacy_file.exists():
        return legacy_file
    return theme_file


def get_saved_default_theme() -> Optional[str]:
    """Read default theme stored in ~/.config/glacis/theme (or ~/.config/cyb0x-s/theme)."""
    try:
        cfg = get_theme_config_path()
        if cfg.is_file():
            saved = cfg.read_text(encoding="utf-8").strip()
            return resolve_palette_name(saved)
    except Exception:
        pass
    return None


def save_default_theme(name: str, store: Any = None) -> bool:
    """Save the default theme to user config and database."""
    resolved = resolve_palette_name(name)
    if not resolved:
        return False
    # 1. Save to ~/.config/glacis/theme
    try:
        cfg = get_theme_config_path()
        cfg.write_text(resolved, encoding="utf-8")
    except Exception:
        pass
    # 2. Save to store settings if available
    if store is not None and hasattr(store, "set_setting"):
        try:
            store.set_setting("default_theme", resolved)
        except Exception:
            pass
    return True


def get_default_theme(store: Any = None) -> str:
    """Read the configured default theme from environment, config file, or settings, fallback to slate."""
    # 1. Explicit environment override
    env_theme = (
        os.environ.get("GLACIS_THEME")
        or os.environ.get("GLACIS_PALETTE")
        or os.environ.get("CYB0X_THEME")
        or os.environ.get("CYB0X_PALETTE", "")
    )
    resolved_env = resolve_palette_name(env_theme)
    if resolved_env:
        return resolved_env

    # 2. User config file (~/.config/glacis/theme or ~/.config/cyb0x-s/theme)
    saved_cfg = get_saved_default_theme()
    if saved_cfg:
        return saved_cfg

    # 3. Database setting
    if store is not None and hasattr(store, "get_setting"):
        try:
            db_theme = store.get_setting("default_theme")
            resolved_db = resolve_palette_name(db_theme)
            if resolved_db:
                return resolved_db
        except Exception:
            pass

    return DEFAULT_PALETTE


def S(token: str, bold: bool = True) -> str:  # noqa: N802 - short by design
    """Rich style string for a palette token, e.g. ``S("ok")`` → ``bold #6FE3B0``.

    Rows are composed in Python (not CSS), so they read the live palette here.
    """
    colour = getattr(PALETTE, token, PALETTE.text)
    return f"bold {colour}" if bold else colour


def mix(colour_a: str, colour_b: str, t: float) -> str:
    """Linear interpolation between two ``#RRGGBB`` colours, clamped to ``[0,1]``."""
    t = max(0.0, min(1.0, t))

    def _ch(v: str) -> tuple[int, int, int]:
        v = v.lstrip("#")
        return (int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16))

    a, b = _ch(colour_a), _ch(colour_b)
    channels = (
        max(0, min(255, round(a[i] + (b[i] - a[i]) * t))) for i in range(3)
    )
    return "#" + "".join(f"{c:02X}" for c in channels)


def ramp(colour: str, steps: int, *, dim_towards: str = "#000000", floor: float = 0.0) -> List[str]:
    """A ``steps``-length gradient from ``dim_towards`` up to ``colour``.

    ``floor`` shifts the starting point away from pure ``dim_towards`` so the
    first step stays legible on dark backgrounds.
    """
    if steps <= 0:
        return []
    if steps == 1:
        return [colour]
    return [mix(dim_towards, colour, floor + (1.0 - floor) * (i / (steps - 1))) for i in range(steps)]


# ---------------------------------------------------------------------------
# Stylesheet
# ---------------------------------------------------------------------------

APP_CSS = """
Screen {
    background: $background;
    color: $foreground;
    layout: vertical;
}

/* --- chrome ------------------------------------------------------------- */
#app-header {
    height: 1;
    background: $background;
    color: $text-muted;
    padding: 0 2;
}

TabbedContent {
    height: 1fr;
    background: $background;
}

#target-info {
    height: 3;
    background: $surface;
    border-bottom: solid $border;
    padding: 0 2;
}

Tabs {
    height: 2;
    background: $background;
    border-bottom: solid $border;
}

Tab {
    padding: 0 2;
    color: $text-muted;
    background: transparent;
}

Tab:hover {
    color: $foreground;
    background: $surface;
}

/* Station identity is a hard, inverted pill: colour alone is not an
   affordance, and a stressed reader must find "where am I" in one glance. */
Tab.-active {
    color: $background;
    background: $accent;
    text-style: bold;
}

Underline > .underline--bar {
    background: $border;
    color: $accent;
}

/* --- cockpit (station 1) ------------------------------------------------ */
#cockpit {
    height: 1fr;
    layout: horizontal;
    background: $background;
}

#sidebar {
    width: 38;
    min-width: 28;
    max-width: 44;
    height: 100%;
    padding: 0 1;
}

#sidebar.hidden {
    display: none;
}

#workbench {
    width: 1fr;
    height: 100%;
    padding: 0 1;
    layout: vertical;
}

.panel-box {
    border: solid $border;
    border-title-color: $text-soft;
    border-title-style: bold;
    border-subtitle-color: $text-muted;
    border-subtitle-align: right;
    background: $surface;
    margin-bottom: 1;
    padding: 0;
}

.panel-box:focus-within {
    border: double $accent;
    border-title-color: $accent;
    border-subtitle-color: $accent;
    background: $surface;
}

/* Panel legends: a one- or two-line key pinned to the floor of a board so the
   glyphs/counters are readable without a manual, and so a short list does not
   trail off into dead space. */
.panel-legend {
    height: 3;
    padding: 0 1;
    color: $text-muted;
    border-top: solid $border;
}

.loot-sub {
    height: 2;
    padding: 0 1;
    color: $text-muted;
    border-top: solid $border;
}

.panel-header-row {
    display: none;
}

.panel-title {
    width: 1fr;
    color: $accent;
    text-style: bold;
    padding: 0;
}

.panel-count {
    width: auto;
    color: $text-muted;
    padding: 0;
}

.panel-list {
    height: 1fr;
    background: transparent;
}

#panel-surface {
    height: 3fr;
    min-height: 7;
}

#panel-creds {
    height: 2fr;
    min-height: 5;
    margin-bottom: 0;
}

#panel-services {
    height: 3fr;
    min-height: 8;
}

#lower-band {
    height: 2fr;
    min-height: 6;
    layout: horizontal;
}

#panel-checklist {
    width: 32%;
    height: 100%;
    margin-bottom: 0;
}

#panel-notes {
    width: 68%;
    height: 100%;
    margin-bottom: 0;
    margin-left: 1;
}

/* --- console ------------------------------------------------------------ */
#guidance-box {
    height: 5;
    border: solid $border;
    border-top: solid $accent;
    border-title-color: $text-soft;
    border-title-style: bold;
    border-subtitle-color: $accent;
    border-subtitle-align: right;
    background: $surface;
    padding: 0;
    margin: 0 1;
}

#guidance-box:focus-within {
    border: solid $accent;
}

#guidance-box.copied-flash {
    border: solid $success;
}

#console-cmd {
    height: 1;
    padding: 0 1;
    color: $foreground;
}

#console-tip {
    height: 1;
    padding: 0 1;
    color: $text-muted;
}

#console-input-row {
    height: 1;
    padding: 0 1;
    background: $surface-darken-1;
    layout: horizontal;
}

#console-prompt {
    width: auto;
    color: $accent;
    text-style: bold;
}

#cmd-input {
    height: 1;
    width: 1fr;
    border: none;
    background: transparent;
    color: $foreground;
    padding: 0;
}

#cmd-input:focus {
    border: none;
}

#console-hotkeys {
    width: auto;
    color: $text-muted;
    text-align: right;
}

Input {
    height: 3;
    width: 1fr;
    border: round $border;
    background: $background;
    color: $foreground;
}

Input:focus {
    border: round $accent;
    background: $background;
}

/* --- lists -------------------------------------------------------------- */
ListView {
    scrollbar-size-vertical: 1;
    scrollbar-gutter: stable;
    scrollbar-background: $surface;
    scrollbar-color: $border-strong;
    scrollbar-color-hover: $border-strong;
    scrollbar-color-active: $accent;
}

/* Rows are composed in Python, so a long value must be *elided* by the
   renderer instead of being guillotined mid-word by the widget edge.
   Only single-line lists get this treatment: advisory / recipe / proof rows
   are deliberately multi-line and must keep wrapping. */
#list-services ListItem,
#list-creds ListItem,
#list-checklist ListItem,
#list-notes ListItem,
#list-targets ListItem,
.single-line {
    width: 100%;
}

#list-services Label,
#list-creds Label,
#list-checklist Label,
#list-notes Label,
#list-targets Label,
.single-line {
    width: 100%;
    text-overflow: ellipsis;
    text-wrap: nowrap;
}

Tree {
    scrollbar-size-vertical: 1;
    scrollbar-gutter: stable;
}

DataTable {
    scrollbar-size-vertical: 1;
    scrollbar-size-horizontal: 1;
    scrollbar-gutter: stable;
}

ListView > ListItem {
    padding: 0 1;
    color: $foreground;
}

ListView:focus > ListItem.-highlight,
ListView > ListItem.-highlight,
ListView > ListItem.-selected {
    background: $accent 18%;
    color: $foreground;
    text-style: bold;
}

Tree:focus > .tree--cursor,
Tree > .tree--cursor {
    background: $accent 18%;
    color: $foreground;
    text-style: bold;
}

Footer {
    display: none;
}

/* --- stations 2-4 ------------------------------------------------------- */
.station-pad {
    height: 1fr;
    padding: 0 1;
}

/* Station 2: Playbooks */
#playbook-top-bar {
    height: 3;
    layout: horizontal;
    margin-bottom: 1;
}

#playbook-search-input {
    width: 1fr;
    height: 3;
    border: solid $border;
    border-title-color: $text-soft;
    border-title-style: bold;
    border-subtitle-color: $text-muted;
    border-subtitle-align: right;
    background: $surface;
    padding: 0 1;
}

#playbook-search-input:focus {
    border: double $accent;
    border-title-color: $accent;
    border-subtitle-color: $accent;
}

#playbook-body {
    height: 1fr;
    layout: horizontal;
}

#playbook-cat-panel {
    width: 26%;
    height: 1fr;
    border: solid $border;
    border-title-color: $text-soft;
    border-title-style: bold;
    border-subtitle-color: $text-muted;
    border-subtitle-align: right;
    background: $surface;
    padding: 0;
    margin-right: 1;
}

#playbook-cat-panel:focus-within {
    border: double $accent;
    border-title-color: $accent;
    border-subtitle-color: $accent;
}

#playbook-cmd-panel {
    width: 74%;
    height: 1fr;
    border: solid $border;
    border-title-color: $text-soft;
    border-title-style: bold;
    border-subtitle-color: $accent;
    border-subtitle-align: right;
    background: $surface;
    padding: 0;
}

#playbook-cmd-panel:focus-within {
    border: double $accent;
    border-title-color: $accent;
    border-subtitle-color: $accent;
}

/* Station 3: Credentials Matrix */
#cred-matrix-top-bar {
    height: 1;
    layout: horizontal;
    margin-bottom: 1;
    padding: 0 1;
}

#cred-matrix-hdr {
    width: 1fr;
    height: 1;
}

#cred-matrix-sub {
    width: auto;
    height: 1;
    color: $text-muted;
    text-align: right;
}

#cred-matrix-list, #cred-matrix-table {
    height: 1fr;
    border: solid $border;
    border-title-color: $text-soft;
    border-title-style: bold;
    border-subtitle-color: $accent;
    border-subtitle-align: right;
    background: $surface;
}

#cred-matrix-table:focus {
    border: double $accent;
    border-title-color: $accent;
    border-subtitle-color: $accent;
}

#cred-matrix-empty {
    height: 1fr;
    border: solid $border;
    border-title-color: $text-soft;
    border-title-style: bold;
    background: $surface;
    padding: 1 3;
}

/* The matrix owns its frame; the table inside must not draw a second one. */
#cred-matrix-table {
    border: none;
    background: transparent;
}

/* Station 4: Loot & Flags */
#loot-cards-container {
    height: 9;
    layout: horizontal;
    margin-bottom: 1;
}

.loot-box {
    width: 1fr;
    height: 9;
    border: solid $border;
    border-title-color: $text-soft;
    border-title-style: bold;
    border-subtitle-color: $text-muted;
    border-subtitle-align: right;
    background: $surface;
    padding: 0 1;
    margin-right: 1;
}

.loot-box:last-child {
    margin-right: 0;
}

.loot-box:focus-within {
    border: double $accent;
    border-title-color: $accent;
    border-subtitle-color: $accent;
}

#loot-lower-container {
    height: 1fr;
    layout: horizontal;
}

.loot-lower-box {
    width: 1fr;
    height: 1fr;
    border: solid $border;
    border-title-color: $text-soft;
    border-title-style: bold;
    border-subtitle-color: $text-muted;
    border-subtitle-align: right;
    background: $surface;
    padding: 0;
    margin-right: 1;
}

.loot-lower-box:last-child {
    margin-right: 0;
}

.loot-lower-box:focus-within {
    border: double $accent;
    border-title-color: $accent;
    border-subtitle-color: $accent;
}

.loot-title {
    display: none;
}

/* --- modals ------------------------------------------------------------- */
ModalScreen {
    align: center middle;
    /* Palette-derived scrim: light palettes dim to their own paper tone
       instead of a hard-coded near-black that fights the theme. */
    background: $background 82%;
}

.glacis-modal-dialog, .synapse-modal-dialog {
    /* Odd width so a two-column form grid splits into two *equal* columns
       (inner = width - border - padding; the gutter takes one more cell).
       At even widths Textual rounds the halves 32/33 and the input boxes
       never line up. */
    width: 73;
    height: auto;
    max-height: 92%;
    overflow-y: auto;
    border: round $accent;
    background: $surface;
    padding: 1 2;
    color: $foreground;
}

.modal-header {
    text-style: bold;
    color: $accent;
    height: 2;
    border-bottom: solid $border;
    margin-bottom: 1;
}

.field-label {
    color: $text-soft;
    text-style: bold;
    margin-top: 1;
}

/* Required-field marker is meaningless without a legend, so the legend is
   part of the form chrome rather than something the reader must infer. */
.field-legend {
    color: $text-muted;
    height: 1;
    margin-top: 1;
}

/* Two-up forms use a real grid: `1fr` + margin rounding produced 32/33
   column pairs whose input boxes never lined up. */
.form-grid {
    layout: grid;
    grid-size: 2;
    grid-columns: 1fr 1fr;
    grid-gutter: 1 1;
    height: auto;
}

.form-cell {
    height: auto;
    width: 100%;
}

.modal-input {
    height: 3;
    width: 100%;
    border: round $border;
    background: $background;
    color: $foreground;
}

.modal-input:focus {
    border: round $accent;
}

Select {
    height: 3;
    background: $background;
    color: $foreground;
    border: round $border;
}

Select:focus {
    border: round $accent;
}

SelectCurrent {
    background: $background;
    color: $foreground;
    border: none;
}

SelectOverlay {
    background: $surface-lighten-1;
    border: round $accent;
    color: $foreground;
}

.modal-buttons {
    height: 3;
    margin-top: 1;
    layout: horizontal;
    align: right middle;
}

Button {
    background: $surface-lighten-1;
    color: $foreground;
    border: none;
    margin-left: 1;
    height: 3;
    min-width: 12;
}

Button:hover {
    background: $accent;
    color: $background;
    text-style: bold;
}

Button.primary-btn {
    background: $accent;
    color: $background;
    text-style: bold;
}

Button.primary-btn:hover {
    background: $accent-lighten-1;
    color: $background;
}

Button.danger-btn {
    background: $error;
    color: $background;
    text-style: bold;
}

Button.danger-btn:hover {
    background: $error-lighten-1;
    color: $background;
}

#confirm-box {
    width: 60;
    height: auto;
    border: round $error;
    background: $surface;
    padding: 1 2;
    color: $foreground;
}

#search-box {
    width: 86;
    height: 24;
    max-height: 90%;
    border: round $accent;
    background: $surface;
    padding: 1 2;
}

#search-results {
    height: 1fr;
    border: round $border;
    background: $surface;
}

#search-status {
    height: 1;
    margin-top: 1;
    color: $text-muted;
}

#help-box, #template-box, #ref-box {
    width: 80%;
    height: 85%;
    border: round $accent;
    background: $surface;
    padding: 1 2;
}

#template-list, #ref-list {
    height: 1fr;
    border: round $border;
    background: $background;
    margin-top: 1;
    margin-bottom: 1;
}

#ref-filter-input {
    height: 3;
    border: round $border;
    background: $background;
    margin-top: 1;
    margin-bottom: 1;
}

/* --- zoom + responsive -------------------------------------------------- */
#cockpit.zoomed-mode > #sidebar {
    display: none;
}

#cockpit.zoomed-mode > #workbench {
    width: 100%;
}

.maximized {
    height: 100% !important;
    border: double $accent !important;
}

Screen.compact #sidebar,
Screen.compact-width #sidebar {
    width: 22;
    min-width: 18;
}

Screen.compact #workbench,
Screen.compact-width #workbench {
    width: 1fr;
}

Screen.compact #lower-band,
Screen.compact-width #lower-band {
    layout: vertical;
}

Screen.compact #panel-checklist,
Screen.compact-width #panel-checklist,
Screen.compact #panel-notes,
Screen.compact-width #panel-notes {
    width: 100%;
    height: 1fr;
    margin-left: 0;
}

Screen.compact #console-tip,
Screen.compact-height #console-tip {
    display: none;
}

Screen.compact #guidance-box,
Screen.compact-height #guidance-box {
    height: 4;
}

Screen.compact #target-info,
Screen.compact-height #target-info {
    height: 2;
}
"""
