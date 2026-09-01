"""CYB0X-S TUI Theme: warm charcoal, terracotta, kraft gold, sage green palette."""

from __future__ import annotations

BACKGROUND = "#211E1B"
DARK_CHARCOAL = BACKGROUND
SURFACE = "#2A2622"
SURFACE_RAISED = "#332E29"
TERRACOTTA = "#D97757"
CREAM = "#EDE6DA"
MUTED = "#A8A099"
KRAFT = "#D4A27F"
SAGE = "#8FA876"
ERROR_RED = "#C4553B"

APP_CSS = f"""
Screen {{
    layout: vertical;
    background: {BACKGROUND};
    color: {CREAM};
}}

Header {{
    background: #191715;
    color: {CREAM};
}}

Footer {{
    background: #191715;
    color: {MUTED};
}}

WorksheetHeader {{
    height: 2;
    background: #191715;
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
    background: #191715;
    border-bottom: solid {SURFACE_RAISED};
    height: 3;
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
    border-bottom: tall {TERRACOTTA};
}}

Underline {{
    display: none;
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

#cmd-input-bar {{
    height: 3;
    border-top: solid {SURFACE_RAISED};
    padding: 0 1;
    background: #191715;
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

.maximized {{
    width: 100% !important;
    height: 100% !important;
    border: double {TERRACOTTA} !important;
    layer: top;
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
    background: #E58767;
    color: {CREAM};
}}
"""
