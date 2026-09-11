"""Shared row primitives and differential list synchronization.

The diff synchronizer updates Textual :class:`ListView` widgets in place —
appending, updating or removing only the rows that changed — so scroll
position and the selection cursor are never destroyed by a full clear.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from rich.text import Text
from textual.app import ComposeResult
from textual.widgets import Label, ListItem, ListView

from glacis.tui.theme import S


def substitute_command_placeholders(
    command: str,
    target_ip: str = "",
    lhost: str = "",
    lport: str = "",
) -> str:
    """Fill static command templates with active target/attacker context.

    Purely mechanical string substitution on human-curated reference text:
    no command is ever generated, inferred or suggested.
    """
    if not command:
        return ""
    res = command
    if target_ip:
        subnet = f"{target_ip.rsplit('.', 1)[0]}.0/24" if "." in target_ip else ""
        res = res.replace("<TARGET_IP>", target_ip).replace("<TARGET_SUBNET>", subnet)
    if lhost:
        res = res.replace("<LHOST>", lhost).replace("<ATTACKER_IP>", lhost).replace("<LOCAL_IP>", lhost)
    if lport:
        res = res.replace("<LPORT>", str(lport)).replace("<LOCAL_PORT>", str(lport))
    res = res.replace("<WORDLIST>", "/usr/share/wordlists/dirb/common.txt")
    return res


class DataListItem(ListItem):
    """A ListItem wrapping a domain model (or a non-selectable placeholder)."""

    def __init__(
        self,
        data_obj: Any,
        display_text: Text,
        is_placeholder: bool = False,
        *children: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__(*children, **kwargs)
        self.data_obj = data_obj
        self.display_text = display_text
        self.is_placeholder = is_placeholder

    def compose(self) -> ComposeResult:
        yield Label(self.display_text)

    def update_display(self, new_text: Text) -> None:
        """Update the label text in place without rebuilding the ListItem."""
        self.display_text = new_text
        try:
            self.query_one(Label).update(new_text)
        except Exception:
            pass


_PROTOCOL_BADGE_CACHE: Dict[Tuple[int, str, str], Text] = {}
_STATUS_ICON_CACHE: Dict[Tuple[str, str], Text] = {}


def get_protocol_badge(port: int, protocol: str, theme_name: str = "") -> Text:
    """Return a pre-styled Rich Text badge for port/protocol, cached."""
    key = (port, protocol.lower(), theme_name)
    cached = _PROTOCOL_BADGE_CACHE.get(key)
    if cached is None:
        port_str = f"[{port}/{protocol}]"
        t = Text(f"{port_str:<11} ", style=S("accent"))
        _PROTOCOL_BADGE_CACHE[key] = t
        return t.copy()
    return cached.copy()


def get_service_status_icon(status_val: str, theme_name: str = "") -> Text:
    """Return a pre-styled Rich Text service status icon, cached."""
    key = (status_val, theme_name)
    cached = _STATUS_ICON_CACHE.get(key)
    if cached is None:
        if status_val == "CHECKED":
            t = Text("✓ ", style=S("ok"))
        elif status_val == "DEFERRED":
            t = Text("~ ", style=S("warn"))
        elif status_val == "DEAD-END":
            t = Text("✗ ", style=S("danger"))
        else:
            t = Text("→ ", style=S("accent"))
        _STATUS_ICON_CACHE[key] = t
        return t.copy()
    return cached.copy()


def clear_badge_caches() -> None:
    """Drop cached badges/icons (call on palette switch)."""
    _PROTOCOL_BADGE_CACHE.clear()
    _STATUS_ICON_CACHE.clear()


def data_key(obj: Any) -> Tuple[str, Any]:
    """Stable identity key for a domain object."""
    return (type(obj).__name__, getattr(obj, "id", None))


def _is_real_row(child: Any) -> bool:
    return isinstance(child, DataListItem) and not child.is_placeholder and child.data_obj is not None


def sync_data_list(
    list_view: ListView,
    items: Iterable[Any],
    renderer: Callable[[Any], Text],
    *,
    key_fn: Optional[Callable[[Any], Any]] = None,
    placeholder_text: Optional[Text] = None,
    force: bool = False,
    preserve_index: bool = True,
) -> int:
    """Diff ``items`` into ``list_view`` with in-place row updates.

    Rows are matched by ``key_fn`` (default: model type + id). Unchanged rows
    are left mounted (scroll and cursor survive); changed rows re-render in
    place; new rows append; vanished rows are removed. A mid-list insertion or
    reorder falls back to one controlled rebuild that restores the highlight
    by key. Returns the real row count (0 when only a placeholder is shown).
    """
    key_fn = key_fn or data_key
    wanted: List[Any] = list(items)
    current_rows = [ch for ch in list_view.children if _is_real_row(ch)]
    old_index = list_view.index if preserve_index else None

    def _safe_key(obj: Any) -> Any:
        try:
            return key_fn(obj)
        except Exception:
            return id(obj)

    def _selected_key() -> Optional[Any]:
        if not preserve_index or old_index is None:
            return None
        if 0 <= old_index < len(current_rows):
            return _safe_key(current_rows[old_index].data_obj)
        return None

    selected_key = _selected_key()

    if not wanted:
        list_view.clear()
        if placeholder_text is not None:
            list_view.append(DataListItem(data_obj=None, display_text=placeholder_text, is_placeholder=True))
        if preserve_index:
            list_view.index = None
        return 0

    wanted_keys = [_safe_key(o) for o in wanted]

    # Only a placeholder (or nothing) mounted: build fresh. Leave the cursor
    # where it is (None on first paint) so the first Down press selects row 0.
    if not current_rows:
        list_view.clear()
        for obj in wanted:
            list_view.append(DataListItem(data_obj=obj, display_text=renderer(obj)))
        return len(wanted)

    actual_keys = [_safe_key(ch.data_obj) for ch in current_rows]

    if actual_keys == wanted_keys:
        for ch, obj in zip(current_rows, wanted):
            rendered = renderer(obj)
            if force or ch.display_text.plain != rendered.plain:
                ch.update_display(rendered)
            ch.data_obj = obj
    elif actual_keys == wanted_keys[: len(actual_keys)]:
        # Pure append: update existing rows in place, append the rest.
        for ch, obj in zip(current_rows, wanted[: len(current_rows)]):
            rendered = renderer(obj)
            if force or ch.display_text.plain != rendered.plain:
                ch.update_display(rendered)
            ch.data_obj = obj
        for obj in wanted[len(current_rows):]:
            list_view.append(DataListItem(data_obj=obj, display_text=renderer(obj)))
    else:
        # Mid-list insert/delete/reorder: one deterministic rebuild, cursor
        # restored to the previously selected key.
        list_view.clear()
        for obj in wanted:
            list_view.append(DataListItem(data_obj=obj, display_text=renderer(obj)))
        if preserve_index and selected_key is not None:
            if selected_key in wanted_keys:
                list_view.index = wanted_keys.index(selected_key)
            else:
                list_view.index = min(old_index or 0, len(wanted) - 1)
        # Drop stale placeholders and return; no index clamping needed below.
        return len(wanted)

    # Remove rows/placeholders that should no longer be mounted.
    live_keys = set(wanted_keys)
    for ch in list(list_view.children):
        if isinstance(ch, DataListItem) and (ch.is_placeholder or _safe_key(ch.data_obj) not in live_keys):
            ch.remove()

    if preserve_index and list_view.index is not None:
        list_view.index = min(list_view.index, len(wanted) - 1)
    return len(wanted)
