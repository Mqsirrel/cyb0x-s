"""Headless-safe timer and animation helpers.

Asynchronous Textual timers caused races under ``pytest -n auto`` in the past
(a 60 fps fade timer fired while pilot tests rebuilt the DOM). Every timer in
GLACIS therefore goes through this module:

* Under pytest (``"pytest" in sys.modules``) or when ``GLACIS_NO_ANIM=1`` is
  set, cosmetic timers are never scheduled and debounce callbacks fire
  **synchronously** — deterministic and race free for parallel tests.
* In a real terminal, helpers behave exactly like ``set_timer`` /
  ``set_interval`` (zero visual regression over SSH/tmux: GLACIS ships no
  continuous animation anyway).
"""

from __future__ import annotations

import os
import sys
from typing import Any, Callable, Optional


def animations_enabled() -> bool:
    """Return False in headless/test environments or when explicitly disabled."""
    if os.environ.get("GLACIS_NO_ANIM", "").strip().lower() in {"1", "true", "yes", "on"}:
        return False
    if "pytest" in sys.modules:
        return False
    return os.environ.get("GLACIS_ANIM", "1").strip().lower() not in {"0", "off", "false", "no"}


def guarded_timer(widget: Any, delay: float, callback: Callable[[], Any]) -> Optional[Any]:
    """Schedule ``set_timer`` only when animations are enabled."""
    if animations_enabled():
        return widget.set_timer(delay, callback)
    return None


def guarded_interval(widget: Any, interval: float, callback: Callable[[], Any]) -> Optional[Any]:
    """Schedule ``set_interval`` only when animations are enabled."""
    if animations_enabled():
        return widget.set_interval(interval, callback)
    return None


def run_debounced(widget: Any, attr: str, delay: float, callback: Callable[[], Any]) -> None:
    """Coalesce rapid events; run immediately and deterministically in tests."""
    if not animations_enabled():
        callback()
        return
    old = getattr(widget, attr, None)
    if old is not None:
        try:
            old.stop()
        except Exception:
            pass
    setattr(widget, attr, widget.set_timer(delay, callback))


def flash_class(widget: Any, class_name: str, duration: float = 1.6) -> None:
    """Briefly toggle a CSS class; permanent in headless mode (no timer races)."""
    widget.set_class(True, class_name)
    def _clear() -> None:
        try:
            widget.set_class(False, class_name)
        except Exception:
            pass

    guarded_timer(widget, duration, _clear)
