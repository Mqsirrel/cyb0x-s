"""Runtime switches that control how much CYB0X-S derives on its own.

CYB0X-S is a *passive* notebook. Some convenience helpers would make it do more
than record: rating a newly imported service (``HIGH``/``MED``/``LOW`` "access
potential") and pre-filling a suggested command for it are both derived from
data you captured during an assessment.

They are genuinely useful in a practice lab, so they still exist — but they are
**off by default**. With them off the tool never classifies what you recorded
and never proposes a next step; it only stores, organises, searches and exports
what you typed, and looks up references when *you* ask for them.

Enable them explicitly with::

    export CYB0X_DERIVE_GUIDANCE=1      # shell / shell profile
    CYB0X_DERIVE_GUIDANCE=1 cyb0x-s     # single run

or press ``G`` inside the TUI to toggle for the current session.

This module is deliberately dependency-free and side-effect free at import time
(apart from reading the environment once).
"""

from __future__ import annotations

import os
from typing import Optional

ENV_VAR = "CYB0X_DERIVE_GUIDANCE"

_TRUTHY = {"1", "true", "yes", "on", "enabled"}
_FALSY = {"0", "false", "no", "off", "disabled", ""}

# Session-level override, set by set_derive_guidance() (e.g. the TUI toggle).
_override: Optional[bool] = None


def _from_env() -> bool:
    raw = os.environ.get(ENV_VAR, "")
    return raw.strip().lower() in _TRUTHY


def derive_guidance_enabled() -> bool:
    """True when CYB0X-S may derive ratings/suggestions from recorded data.

    Default: **False** (exam-safe posture).
    """
    if _override is not None:
        return _override
    return _from_env()


def set_derive_guidance(enabled: Optional[bool]) -> None:
    """Override the environment for the current process/session.

    Pass ``None`` to fall back to the environment variable.
    """
    global _override
    _override = None if enabled is None else bool(enabled)


def describe_derive_guidance() -> str:
    """Short human-readable state, for UI notifications and exports."""
    return "on" if derive_guidance_enabled() else "off"
