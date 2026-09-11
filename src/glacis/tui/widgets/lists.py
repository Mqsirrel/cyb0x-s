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

from glacis.tui.theme import S, current_palette


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


def elide(value: str, width: int, ellipsis: str = "…") -> str:
    """Clip ``value`` to exactly ``width`` cells and *mark* the clip.

    Panels that compose their own rows must elide in Python: letting the
    widget clip a long string cuts it mid-word with no signal that anything
    was lost (``…listing backu``), which reads as a rendering bug rather than
    as deliberate truncation.
    """
    if width <= 0:
        return ""
    clean = " ".join(str(value).split())
    if len(clean) <= width:
        return clean
    if width <= len(ellipsis):
        return ellipsis[:width]
    return clean[: width - len(ellipsis)].rstrip() + ellipsis


def elide_middle(value: str, width: int, ellipsis: str = "…") -> str:
    """Elide from the middle, keeping the discriminating tail visible.

    Paths and flags are identified by their ends (``…/proof_screenshot_01.png``,
    ``eJPT{…195ae32}``), so clipping the tail destroys the only part a reader
    actually scans for.
    """
    if width <= 0:
        return ""
    clean = " ".join(str(value).split())
    if len(clean) <= width:
        return clean
    if width <= len(ellipsis) + 1:
        return ellipsis[:width]
    keep_tail = max((width - len(ellipsis)) // 2, 1)
    keep_head = width - len(ellipsis) - keep_tail
    return clean[:keep_head].rstrip() + ellipsis + clean[-keep_tail:]


def keycap_line(*pairs: tuple[str, str]) -> Text:
    """``[a] add proof · [e] export`` — keycaps in accent, actions in muted.

    Building this as Text (instead of a markup string) is required, not
    cosmetic: ``[a]`` inside a markup string is parsed as a style tag and
    silently vanishes from the rendered row.
    """
    P = current_palette()
    t = Text()
    for i, pair in enumerate(pairs):
        key, label = pair
        if i:
            t.append(" · ", style=f"dim {P.muted}")
        t.append(f"[{key}]", style=f"bold {P.accent}")
        t.append(f" {label}", style=P.muted)
    return t


def legend_line(*entries: tuple[str, str]) -> Text:
    """Render a ``glyph MEANING · glyph MEANING`` legend strip.

    Legends are what make a dense board self-explanatory: without one a first
    time reader has to reverse-engineer ``s3 k2 e1 ✖1`` from context.
    """
    from glacis.tui.theme import S

    t = Text()
    for i, entry in enumerate(entries):
        glyph, meaning = entry
        if i:
            t.append("   ", style="")
        t.append(f"{glyph} ", style=S("accent", bold=True))
        t.append(meaning, style=S("muted", bold=False))
    return t


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
    from glacis.tui.theme import GLYPHS

    key = (status_val, theme_name)
    cached = _STATUS_ICON_CACHE.get(key)
    if cached is None:
        if status_val == "CHECKED":
            t = Text(f"{GLYPHS['done']} ", style=S("ok"))
        elif status_val == "DEFERRED":
            t = Text(f"{GLYPHS['deferred']} ", style=S("warn"))
        elif status_val == "DEAD-END":
            t = Text(f"{GLYPHS['dead_end']} ", style=S("danger"))
        else:
            t = Text(f"{GLYPHS['open']} ", style=S("accent"))
        _STATUS_ICON_CACHE[key] = t
        return t.copy()
    return cached.copy()


#: Canonical status vocabulary. Keyed by the model value, rendered as an
#: inverted pill so the state is legible from across the room.
STATUS_BADGES: Dict[str, tuple[str, str]] = {
    "TODO": ("[TODO]", "accent"),
    "CHECKED": ("[CHECKED]", "ok"),
    "DEFERRED": ("[~ DEFER]", "warn"),
    "DEAD-END": ("[DEAD-END]", "danger"),
}


def status_badge(status_val: str, width: int = 12) -> Text:
    """Uniform-width inverted status pill (``[CHECKED]``, ``[DEAD-END]`` …).

    Fixed width keeps every column in a service row on the same raster;
    hand-padded literals drift as soon as a label changes length.
    """
    P = current_palette()
    label, token = STATUS_BADGES.get(status_val, STATUS_BADGES["TODO"])
    colour = getattr(P, token)
    t = Text()
    t.append(f" {label:<{width - 2}} ", style=f"bold {P.bg} on {colour}")
    return t


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
