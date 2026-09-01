"""CYB0X-S TUI Theme: warm charcoal, terracotta, kraft gold, sage green palette.

Single source of truth for the interface colours. Widgets import these tokens
instead of hard-coding colours so the whole worksheet stays visually coherent.
"""

from __future__ import annotations

from textual.theme import Theme

# --- Palette -----------------------------------------------------------------
BACKGROUND = "#211E1B"
DARK_CHARCOAL = BACKGROUND
HEADER_BG = "#191715"
SURFACE = "#2A2622"
SURFACE_RAISED = "#332E29"
TERRACOTTA = "#D97757"
TERRACOTTA_BRIGHT = "#E58767"
CREAM = "#EDE6DA"
MUTED = "#A8A099"
KRAFT = "#D4A27F"
SAGE = "#8FA876"
ERROR_RED = "#C4553B"

# Row-level text colours. Rows are built with Rich `Text` in Python (not CSS),
# so they need explicit palette values — otherwise they fall back to the
# terminal's ANSI colours and clash with the warm chrome.
OK = SAGE                 # checked / captured / success
DANGER = "#E5846B"        # findings, dead ends (lighter than ERROR_RED: 5.6:1)
WARN = KRAFT              # deferred, next action, attention
INFO = TERRACOTTA         # ports, service names, neutral accent
NOTE = MUTED              # secondary / dim text

# Semantic aliases (kept explicit so widget CSS reads clearly)
BORDER = SURFACE_RAISED
FOCUS = TERRACOTTA
PANEL_BG = SURFACE
PANEL_HEADER = KRAFT
ACCENT = TERRACOTTA
OK_GREEN = SAGE
WARN_RED = ERROR_RED

# Registering the palette as a Textual theme makes every built-in design token
# ($surface, $border, $primary, $text-muted, footer/scrollbar colours, ...)
# resolve to the CYB0X-S warm palette. Widgets then inherit one coherent look
# instead of each CSS block hard-coding its own colours.
CYBOX_WARM_THEME = Theme(
    name="cyb0x-warm",
    primary=TERRACOTTA,
    secondary=KRAFT,
    accent=TERRACOTTA,
    foreground=CREAM,
    background=BACKGROUND,
    surface=SURFACE,
    panel=SURFACE,
    success=SAGE,
    warning=KRAFT,
    error=ERROR_RED,
    dark=True,
    variables={
        "footer-background": HEADER_BG,
        "footer-foreground": MUTED,
        "border": SURFACE_RAISED,
        "border-blurred": SURFACE_RAISED,
        "block-cursor-background": TERRACOTTA,
        "block-cursor-foreground": CREAM,
        "input-selection-background": SURFACE_RAISED,
        "scrollbar": SURFACE_RAISED,
        "scrollbar-background": BACKGROUND,
    },
)

APP_CSS = f"""
Screen {{
    layout: vertical;
    background: {BACKGROUND};
    color: {CREAM};
}}

Header {{
    background: {HEADER_BG};
    color: {CREAM};
}}

Footer {{
    background: {HEADER_BG};
    color: {MUTED};
}}

WorksheetHeader {{
    height: 2;
    background: {HEADER_BG};
    color: {CREAM};
    border-bottom: solid {TERRACOTTA} 40%;
    padding: 0 2;
}}

TargetInfoPanel {{
    height: 2;
    border-bottom: solid {SURFACE_RAISED};
    padding: 0 2;
    background: {SURFACE};
    color: {CREAM};
}}

TabbedContent {{
    height: 1fr;
    background: {BACKGROUND};
}}

Tabs {{
    background: {HEADER_BG};
    border-bottom: solid {SURFACE_RAISED};
    height: 2;
}}

Tab {{
    padding: 0 2;
    background: transparent;
    color: {MUTED};
}}

Tab:hover {{
    color: {CREAM};
    background: {SURFACE};
}}

Tab.-active {{
    color: {TERRACOTTA};
    text-style: bold;
    background: {SURFACE};
}}

/* The underline is the animated "you are here" bar under the active tab.
   It must stay visible: Tabs hides the active tab's own highlight, so
   removing it makes the current station impossible to identify. */
Underline > .underline--bar {{
    background: {SURFACE_RAISED};
    color: {TERRACOTTA};
}}

#main-container {{
    height: 1fr;
    layout: horizontal;
    background: {BACKGROUND};
}}

#sidebar-tree-pane {{
    width: 28%;
    height: 100%;
    padding-right: 1;
}}

TargetTreeWidget {{
    background: {SURFACE};
    padding: 0 1;
    height: 1fr;
    border: round {SURFACE_RAISED};
    color: {CREAM};
}}

TargetTreeWidget:focus {{
    border: round {TERRACOTTA};
}}

#workbench-pane {{
    width: 72%;
    height: 100%;
    layout: horizontal;
}}

.column {{
    width: 1fr;
    height: 1fr;
    padding: 0 1;
}}

.panel-box {{
    border: round {SURFACE_RAISED};
    background: {SURFACE};
    margin-bottom: 1;
    padding: 0 1;
}}

.panel-box:focus-within {{
    border: round {TERRACOTTA};
    background: {SURFACE_RAISED};
}}

#panel-services {{
    height: 58%;
}}

#panel-creds-preview {{
    height: 42%;
}}

#panel-checklist {{
    height: 62%;
}}

#panel-notes {{
    height: 38%;
}}

.panel-header {{
    text-style: bold;
    color: {KRAFT};
    padding: 0 1;
    height: 1;
}}

.panel-list {{
    height: 1fr;
    background: transparent;
}}

ListView > ListItem {{
    padding: 0 1;
    color: {CREAM};
}}

ListView > ListItem:hover {{
    background: {SURFACE_RAISED};
}}

ListView > ListItem.-selected {{
    background: {TERRACOTTA} 30%;
    color: {CREAM};
    text-style: bold;
}}

GuidanceDrawer {{
    height: 4;
    border: solid {SURFACE_RAISED};
    background: {BACKGROUND};
    padding: 0 1;
    margin-top: 1;
    color: {CREAM};
}}

GuidanceDrawer.-active {{
    border: solid {TERRACOTTA} 60%;
}}

#cmd-input-bar {{
    height: 3;
    border-top: solid {SURFACE_RAISED};
    padding: 0 1;
    background: {HEADER_BG};
    layout: horizontal;
    align: left middle;
}}

#cmd-prompt {{
    width: 3;
    padding-top: 1;
    color: {TERRACOTTA};
}}

#cmd-input {{
    width: 1fr;
    border: none;
    background: transparent;
    color: {CREAM};
}}

#cmd-input:focus {{
    border: none;
}}

/* --- Panel zoom (z) ------------------------------------------------------- */
/* Zooming hides the sidebar and the sibling column so the focused panel
   genuinely owns the screen instead of only growing inside its column. */
#main-container.zoomed-mode > #sidebar-tree-pane {{
    display: none;
}}

#main-container.zoomed-mode > #workbench-pane {{
    width: 100%;
}}

.maximized {{
    height: 100% !important;
    border: double {TERRACOTTA} !important;
}}

/* --- Responsive layout ---------------------------------------------------- */
/* Below ~110 columns the two-column workbench stops being readable, so the
   columns stack and the sidebar gives up some width. */
Screen.compact #sidebar-tree-pane {{
    width: 24%;
}}

Screen.compact #workbench-pane {{
    layout: vertical;
    width: 76%;
}}

Screen.compact .column {{
    height: 1fr;
    width: 100%;
}}

Screen.compact .panel-box {{
    height: 1fr;
    margin-bottom: 0;
}}

Screen.compact #panel-services,
Screen.compact #panel-creds-preview,
Screen.compact #panel-checklist,
Screen.compact #panel-notes {{
    height: 1fr;
}}

Screen.compact GuidanceDrawer {{
    display: none;
}}

/* Modal Styling */
ModalScreen {{
    align: center middle;
    background: rgba(15, 13, 11, 0.75);
}}

.synapse-modal-dialog {{
    width: 68;
    height: auto;
    max-height: 90%;
    border: round {TERRACOTTA};
    background: {SURFACE};
    padding: 1 2;
    color: {CREAM};
}}

.modal-header {{
    text-style: bold;
    color: {TERRACOTTA};
    height: 2;
    border-bottom: solid {SURFACE_RAISED};
    margin-bottom: 1;
}}

.field-label {{
    color: {KRAFT};
    text-style: bold;
    margin-top: 1;
}}

Input {{
    background: {BACKGROUND};
    border: round {SURFACE_RAISED};
    color: {CREAM};
    height: 3;
}}

Input:focus {{
    border: round {TERRACOTTA};
}}

Select {{
    background: {BACKGROUND};
    border: round {SURFACE_RAISED};
    color: {CREAM};
    height: 3;
}}

Select:focus {{
    border: round {TERRACOTTA};
}}

SelectCurrent {{
    background: {BACKGROUND};
    color: {CREAM};
    border: none;
}}

SelectOverlay {{
    background: {SURFACE_RAISED};
    border: round {TERRACOTTA};
    color: {CREAM};
}}

.modal-buttons {{
    height: 3;
    margin-top: 1;
    layout: horizontal;
    align: right middle;
}}

Button {{
    background: {SURFACE_RAISED};
    color: {CREAM};
    border: none;
    margin-left: 1;
    height: 3;
    min-width: 12;
}}

Button:hover {{
    background: {KRAFT};
    color: {BACKGROUND};
    text-style: bold;
}}

Button.primary-btn {{
    background: {TERRACOTTA};
    color: {CREAM};
    text-style: bold;
}}

Button.primary-btn:hover {{
    background: {TERRACOTTA_BRIGHT};
    color: {CREAM};
}}

Button.danger-btn {{
    background: {ERROR_RED};
    color: {CREAM};
    text-style: bold;
}}

Button.danger-btn:hover {{
    background: #D9654B;
    color: {CREAM};
}}
"""
