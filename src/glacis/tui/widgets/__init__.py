"""GLACIS Textual widgets, split into focused submodules.

The package re-exports every public widget so existing imports
(``from glacis.tui.widgets import ConsoleBar`` etc.) keep working.

NOTE: import order here is deliberate and must not be isorted
(``# ruff: noqa: I001``): the clipboard helper is bound first, the leaf
widget submodules come next (``modals`` imports ``DataListItem`` from this
package while it is still initializing), and the modal re-exports come last.
"""

# ruff: noqa: I001

from __future__ import annotations

# Bound first so submodules can resolve the clipboard helper through the
# package namespace (and tests can monkeypatch ``glacis.tui.widgets.copy_to_clipboard``).
from glacis.clipboard import copy_to_clipboard

# Leaf widget modules before modals: modals.py does
# ``from glacis.tui.widgets import DataListItem`` while this package is
# still initializing, so these names must already exist.
from glacis.tui.widgets.lists import (
    DataListItem,
    clear_badge_caches,
    data_key,
    get_protocol_badge,
    get_service_status_icon,
    substitute_command_placeholders,
    sync_data_list,
)
from glacis.tui.widgets.chrome import ConsoleBar, MachineStatusStrip, WorksheetHeader
from glacis.tui.widgets.loot import (
    AUTH_SERVICE_NAMES,
    AUTH_SERVICE_PORTS,
    CredentialMatrixWidget,
    LootAndFlagsWidget,
    compile_spray_command,
)
from glacis.tui.widgets.playbooks import PlaybookBrowserWidget
from glacis.tui.widgets.targets import TargetTreeWidget

# Modal dialogs live in the sibling modals module; re-exported for the
# historical single-import surface.
from glacis.tui.modals import (  # noqa: E402, F401
    AddCredentialModal,
    AddFindingModal,
    AddServiceModal,
    AddTargetModal,
    BaseFormModal,
    ConfirmModal,
    FastInputModal,
    HelpModal,
    ReferenceModal,
    ScanImportModal,
    SearchModal,
    TemplateSelectionModal,
    ThemePickerModal,
    ThemeSwatch,
    WorkspaceModal,
)

__all__ = [
    "ConsoleBar",
    "MachineStatusStrip",
    "WorksheetHeader",
    "DataListItem",
    "clear_badge_caches",
    "data_key",
    "get_protocol_badge",
    "get_service_status_icon",
    "substitute_command_placeholders",
    "sync_data_list",
    "AUTH_SERVICE_NAMES",
    "AUTH_SERVICE_PORTS",
    "CredentialMatrixWidget",
    "LootAndFlagsWidget",
    "compile_spray_command",
    "PlaybookBrowserWidget",
    "TargetTreeWidget",
    "copy_to_clipboard",
    "AddCredentialModal",
    "AddFindingModal",
    "AddServiceModal",
    "AddTargetModal",
    "BaseFormModal",
    "ConfirmModal",
    "FastInputModal",
    "HelpModal",
    "ReferenceModal",
    "ScanImportModal",
    "SearchModal",
    "TemplateSelectionModal",
    "ThemePickerModal",
    "ThemeSwatch",
    "WorkspaceModal",
]
