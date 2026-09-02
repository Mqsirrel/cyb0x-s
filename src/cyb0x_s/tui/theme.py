"""CYB0X-S theming: palettes, design tokens and the application stylesheet.

Seven palettes ship with the app:

* ``slate``    — cool graphite chrome with cyan/mint data and amber warnings.
                 Default: tuned for long sessions and at-a-glance state.
* ``midnight`` — indigo / periwinkle, calm and low-flare for long labs.
* ``ember``    — amber CRT, warm monochrome-adjacent reading glow.
* ``moss``     — forest / lime, low-eye-strain green.
* ``neon``     — magenta / electric, high-energy accent.
* ``mono``     — luminance only, colour-blind safe (no hue at all).
* ``warm``     — the original charcoal / terracotta / kraft identity.

The stylesheet below deliberately contains **no literal colours**: every rule
references a Textual design token (``$surface``, ``$accent``, ``$text-muted`` …)
that is generated from the active :class:`Palette`. Switching palette therefore
only has to swap the registered theme and Textual re-parses the CSS.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List, Optional

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
            name=f"cyb0x-{self.name}",
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
    label="Slate · cyan / mint",
    bg="#0E1418",
    surface="#151C22",
    raised="#1D262E",
    border="#2A363F",
    border_strong="#3A4B58",
    text="#DDE6EE",
    text_soft="#B6C7D6",
    muted="#8698A8",
    accent="#4FD6E8",
    ok="#6FE3B0",
    warn="#F5B455",
    danger="#FF8069",
)

MIDNIGHT = Palette(
    name="midnight",
    label="Midnight · indigo / periwinkle",
    bg="#0B1020",
    surface="#131A2E",
    raised="#1C2542",
    border="#27324F",
    border_strong="#3B4A72",
    text="#DCE3F5",
    text_soft="#AFBAD7",
    muted="#7E8AAE",
    accent="#6DA8FF",
    ok="#7EE7BE",
    warn="#F2C078",
    danger="#FF7A93",
)

EMBER = Palette(
    name="ember",
    label="Ember · amber CRT",
    bg="#120E09",
    surface="#1D1710",
    raised="#272019",
    border="#3A3126",
    border_strong="#574835",
    text="#F4E7D2",
    text_soft="#D6C5A8",
    muted="#A6907A",
    accent="#FFB000",
    ok="#C3D95C",
    warn="#FF8C42",
    danger="#FF6B57",
)

MOSS = Palette(
    name="moss",
    label="Moss · forest / lime",
    bg="#0C1410",
    surface="#131E18",
    raised="#1B2B22",
    border="#27392D",
    border_strong="#3A5544",
    text="#DCEBE0",
    text_soft="#B4CDBE",
    muted="#7F9A8B",
    accent="#68D6A0",
    ok="#A3E635",
    warn="#E8C46A",
    danger="#FF8A75",
)

NEON = Palette(
    name="neon",
    label="Neon · magenta / electric",
    bg="#0A0812",
    surface="#151026",
    raised="#201938",
    border="#312754",
    border_strong="#4A3C7D",
    text="#EEE8FF",
    text_soft="#C5B9EA",
    muted="#8E81BC",
    accent="#FF5EDB",
    ok="#4ADE80",
    warn="#FDE047",
    danger="#FB7185",
)

MONO = Palette(
    name="mono",
    label="Mono · luminance only",
    bg="#0D0E10",
    surface="#17181B",
    raised="#212226",
    border="#2F3136",
    border_strong="#4C4F56",
    text="#F5F6F7",
    text_soft="#C7CAD0",
    muted="#8C9097",
    accent="#E9ECEF",
    ok="#B6BBC1",
    warn="#DCE0E4",
    danger="#FFFFFF",
)

WARM = Palette(
    name="warm",
    label="Warm · terracotta (legacy)",
    bg="#211E1B",
    surface="#2A2622",
    raised="#332E29",
    border="#3A342E",
    border_strong="#4A423A",
    text="#EDE6DA",
    text_soft="#CFC5B8",
    muted="#A8A099",
    accent="#D97757",
    ok="#8FA876",
    warn="#D4A27F",
    danger="#E5846B",
)

PALETTES: Dict[str, Palette] = {
    p.name: p for p in (SLATE, MIDNIGHT, EMBER, MOSS, NEON, MONO, WARM)
}
DEFAULT_PALETTE = SLATE.name

#: The palette every widget reads at render time. Swapped by :func:`set_palette`.
PALETTE: Palette = PALETTES[DEFAULT_PALETTE]


def set_palette(name: str) -> Palette:
    """Activate ``name`` and return the palette now in use."""
    global PALETTE
    PALETTE = PALETTES.get(name, PALETTES[DEFAULT_PALETTE])
    return PALETTE


def current_palette() -> Palette:
    return PALETTE


def resolve_palette_name(query: Optional[str]) -> Optional[str]:
    """Resolve a user-supplied theme string, digit (1-7), or prefix into a canonical palette name.

    Examples:
        '1' -> 'slate'
        '7' -> 'warm'
        'w' or 'warm' -> 'warm'
        'sl' or 'slate' -> 'slate'
        'mid' or 'midnight' -> 'midnight'
        'em' or 'ember' -> 'ember'
        'mo' or 'moss' -> 'moss'
        'ne' or 'neon' -> 'neon'
        'mon' or 'mono' -> 'mono'
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
        "w": "warm",
        "wa": "warm",
        "sl": "slate",
        "s": "slate",
        "mid": "midnight",
        "mi": "midnight",
        "em": "ember",
        "e": "ember",
        "mo": "moss",
        "mos": "moss",
        "ne": "neon",
        "n": "neon",
        "mon": "mono",
    }
    if q in alias_map and alias_map[q] in PALETTES:
        return alias_map[q]

    # Prefix match
    matches = [name for name in names if name.startswith(q)]
    if len(matches) >= 1:
        return matches[0]

    return None


def get_default_theme() -> str:
    """Read the configured default theme from environment or settings, fallback to slate."""
    env_theme = os.environ.get("CYB0X_THEME") or os.environ.get("CYB0X_PALETTE", "")
    resolved = resolve_palette_name(env_theme)
    return resolved or DEFAULT_PALETTE


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

#status-strip {
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

Tab.-active {
    color: $accent;
    text-style: bold;
    background: $surface;
}

Underline > .underline--bar {
    background: $surface-lighten-1;
    color: $accent;
}

/* --- cockpit (station 1) ------------------------------------------------ */
#cockpit {
    height: 1fr;
    layout: horizontal;
    background: $background;
}

#sidebar {
    width: 26%;
    height: 100%;
    padding: 0 1;
}

#workbench {
    width: 74%;
    height: 100%;
    padding: 0 1;
    layout: vertical;
}

.panel-box {
    border: round $border;
    background: $surface;
    margin-bottom: 1;
    padding: 0 1;
}

.panel-box:focus-within {
    border: round $accent;
    background: $surface-lighten-1;
}

.panel-header-row {
    height: 1;
    layout: horizontal;
}

.panel-title {
    width: 1fr;
    color: $accent;
    text-style: bold;
    padding: 0 1;
}

.panel-count {
    width: auto;
    color: $text-muted;
    padding: 0 1;
}

.panel-list {
    height: 1fr;
    background: transparent;
}

#panel-surface {
    height: 58%;
}

#panel-creds {
    height: 42%;
    margin-bottom: 0;
}

#panel-services {
    height: 54%;
}

#lower-band {
    height: 46%;
    layout: horizontal;
}

#panel-checklist {
    width: 45%;
    height: 100%;
    margin-bottom: 0;
}

#panel-notes {
    width: 55%;
    height: 100%;
    margin-bottom: 0;
    margin-left: 1;
}

/* --- console ------------------------------------------------------------ */
#guidance-box {
    height: 5;
    border: round $border;
    background: $surface;
    padding: 0 1;
    margin: 0 1;
}

#guidance-box:focus-within {
    border: round $accent;
}

#console-cmd {
    height: 1;
    color: $foreground;
}

#console-tip {
    height: 1;
    color: $text-muted;
}

#console-input-row {
    height: 1;
    layout: horizontal;
}

#console-prompt {
    width: 2;
    color: $accent;
    text-style: bold;
}

#cmd-input {
    height: 1;
    width: 1fr;
    border: none;
    background: transparent;
    color: $foreground;
}

#cmd-input:focus {
    border: none;
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
ListView > ListItem {
    padding: 0 1;
    color: $foreground;
}

ListView > ListItem:hover {
    background: $surface-lighten-1;
}

ListView > ListItem.-selected {
    background: $accent 22%;
    color: $foreground;
    text-style: bold;
}

Footer {
    background: $background;
    color: $text-muted;
}

/* --- stations 2-4 ------------------------------------------------------- */
.station-pad {
    height: 1fr;
    padding: 0 1;
}

#playbook-search-input {
    height: 3;
    border: round $border;
    background: $surface;
    margin-bottom: 1;
}

#playbook-body {
    height: 1fr;
    layout: horizontal;
}

#playbook-cat-panel {
    width: 25%;
    height: 1fr;
    border: round $border;
    background: $surface;
    padding: 0 1;
    margin-right: 1;
}

#playbook-cmd-panel {
    width: 75%;
    height: 1fr;
    border: round $border;
    background: $surface;
    padding: 0 1;
}

#cred-matrix-sub {
    height: 1;
    color: $text-muted;
    padding: 0 1;
    margin-bottom: 1;
}

#cred-matrix-list {
    height: 1fr;
    border: round $border;
    background: $surface;
}

#loot-cards-container {
    height: 9;
    layout: horizontal;
    margin-bottom: 1;
}

.loot-box {
    width: 1fr;
    height: 9;
    border: round $border;
    background: $surface;
    padding: 0 1;
    margin-right: 1;
}

#loot-failure-box {
    height: 1fr;
    border: round $border;
    background: $surface;
    padding: 0 1;
}

.loot-title {
    text-style: bold;
    color: $accent;
    margin-bottom: 1;
}

/* --- modals ------------------------------------------------------------- */
ModalScreen {
    align: center middle;
    background: rgba(6, 9, 12, 0.78);
}

.synapse-modal-dialog {
    width: 68;
    height: auto;
    max-height: 92%;
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

.modal-input {
    height: 3;
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
    width: 80%;
    height: 80%;
    border: round $accent;
    background: $surface;
    padding: 1 2;
}

#search-results {
    height: 1fr;
    border: round $border;
    background: $background;
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

Screen.compact #sidebar {
    width: 24%;
}

Screen.compact #workbench {
    width: 76%;
}

Screen.compact #lower-band {
    layout: vertical;
}

Screen.compact #panel-checklist,
Screen.compact #panel-notes {
    width: 100%;
    height: 1fr;
    margin-left: 0;
}

Screen.compact #console-tip {
    display: none;
}

Screen.compact #guidance-box {
    height: 4;
}

Screen.compact #status-strip {
    height: 2;
}
"""
