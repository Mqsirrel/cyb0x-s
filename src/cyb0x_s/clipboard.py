"""Clipboard copying utilities for CYB0X-S.

Supports OSC 52 terminal copy escapes (SSH/tmux/local) and desktop tools (wl-copy, xclip, pbcopy).
Does NOT generate automatic commands or payloads.
"""

from __future__ import annotations

import base64
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, List, Optional, Union

from cyb0x_s.models import (
    ChecklistItem,
    Credential,
    Evidence,
    Finding,
    Lead,
    Note,
    Service,
    Target,
)


def copy_osc52(text: str) -> bool:
    """Send OSC 52 escape sequence to copy text to system clipboard via terminal."""
    try:
        b64_payload = base64.b64encode(text.encode("utf-8")).decode("ascii")
        # Check if inside tmux or screen
        term = os.environ.get("TERM", "")
        in_tmux = "TMUX" in os.environ or term.startswith("screen") or term.startswith("tmux")

        if in_tmux:
            # DCS passthrough sequence for tmux
            seq = f"\x1bPtmux;\x1b\x1d]52;c;{b64_payload}\x07\x1b\\"
        else:
            seq = f"\x1b]52;c;{b64_payload}\x07"

        # Attempt to write directly to stdout or controlling tty
        try:
            with open("/dev/tty", "w") as tty:
                tty.write(seq)
                tty.flush()
                return True
        except (IOError, OSError):
            sys.stdout.write(seq)
            sys.stdout.flush()
            return True
    except Exception:
        return False


def copy_system_tool(text: str) -> bool:
    """Fallback to native desktop clipboard tools."""
    # Wayland
    if os.environ.get("WAYLAND_DISPLAY") and shutil.which("wl-copy"):
        try:
            p = subprocess.Popen(["wl-copy"], stdin=subprocess.PIPE)
            p.communicate(input=text.encode("utf-8"))
            return p.returncode == 0
        except Exception:
            pass

    # X11 xclip
    if os.environ.get("DISPLAY") and shutil.which("xclip"):
        try:
            p = subprocess.Popen(["xclip", "-selection", "clipboard"], stdin=subprocess.PIPE)
            p.communicate(input=text.encode("utf-8"))
            return p.returncode == 0
        except Exception:
            pass

    # X11 xsel
    if os.environ.get("DISPLAY") and shutil.which("xsel"):
        try:
            p = subprocess.Popen(["xsel", "--clipboard", "--input"], stdin=subprocess.PIPE)
            p.communicate(input=text.encode("utf-8"))
            return p.returncode == 0
        except Exception:
            pass

    # macOS pbcopy
    if sys.platform == "darwin" and shutil.which("pbcopy"):
        try:
            p = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
            p.communicate(input=text.encode("utf-8"))
            return p.returncode == 0
        except Exception:
            pass

    return False


def copy_to_clipboard(text: str) -> bool:
    """Copy text using system tool or OSC 52 sequence."""
    if not text:
        return False
    # Try native tool first if desktop display is available
    if (os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY")) and copy_system_tool(text):
        return True
    # Fallback to OSC 52
    return copy_osc52(text)


def extract_copy_value(entity: Any, target_ip: Optional[str] = None) -> str:
    """Extract strictly the requested value from an entity.

    Rules from specification:
    - Target: IP address (e.g. 10.10.10.20)
    - Service: IP:port (e.g. 10.10.10.20:445) or port if no IP
    - Credential: password / secret
    - Checklist item: only the text of the checklist item
    - Finding: title
    - Note: note text
    - Evidence: path or reference
    - Lead: title
    """
    if isinstance(entity, Target):
        return entity.ip
    elif isinstance(entity, Service):
        if target_ip:
            return f"{target_ip}:{entity.port}"
        return str(entity.port)
    elif isinstance(entity, Credential):
        return entity.secret
    elif isinstance(entity, ChecklistItem):
        return entity.title
    elif isinstance(entity, Finding):
        return entity.title
    elif isinstance(entity, Note):
        return entity.content
    elif isinstance(entity, Lead):
        return entity.title
    elif isinstance(entity, Evidence):
        return entity.path_or_ref
    elif isinstance(entity, str):
        return entity
    return str(entity)


def save_clipboard_image(dest_path: Union[str, Path]) -> bool:
    """Read image data from OS clipboard and save to destination file.

    Supports Wayland (wl-paste), X11 (xclip), and PIL ImageGrab.
    """
    dest = Path(dest_path).expanduser().resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)

    # 1. Wayland wl-paste
    if os.environ.get("WAYLAND_DISPLAY") and shutil.which("wl-paste"):
        try:
            res = subprocess.run(
                ["wl-paste", "-t", "image/png"],
                capture_output=True,
                timeout=3,
            )
            if res.returncode == 0 and res.stdout and len(res.stdout) > 100:
                dest.write_bytes(res.stdout)
                return True
        except Exception:
            pass

    # 2. X11 xclip
    if os.environ.get("DISPLAY") and shutil.which("xclip"):
        try:
            res = subprocess.run(
                ["xclip", "-selection", "clipboard", "-t", "image/png", "-out"],
                capture_output=True,
                timeout=3,
            )
            if res.returncode == 0 and res.stdout and len(res.stdout) > 100:
                dest.write_bytes(res.stdout)
                return True
        except Exception:
            pass

    # 3. PIL ImageGrab (cross-platform fallback)
    try:
        from PIL import ImageGrab

        img = ImageGrab.grabclipboard()
        if img is not None and hasattr(img, "save"):
            img.save(str(dest), "PNG")
            return True
    except Exception:
        pass

    return False


def find_latest_screenshot(
    search_dirs: Optional[List[Union[str, Path]]] = None,
    max_age_seconds: int = 14400,
) -> Optional[Path]:
    """Find the most recently modified screenshot/image file within max_age_seconds (default: 4 hours)."""
    if search_dirs is None:
        home = Path.home()
        search_dirs = [
            home / "Pictures" / "Screenshots",
            home / "Pictures",
            home / "Downloads",
            Path.cwd() / "screenshots",
        ]

    candidate_files: List[Path] = []
    valid_exts = {".png", ".jpg", ".jpeg"}

    for d in search_dirs:
        dir_path = Path(d).expanduser().resolve()
        if not dir_path.is_dir():
            continue
        try:
            for item in dir_path.iterdir():
                if item.is_file() and item.suffix.lower() in valid_exts:
                    candidate_files.append(item)
        except (PermissionError, OSError):
            continue

    if not candidate_files:
        return None

    # Sort descending by mtime
    candidate_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    newest = candidate_files[0]
    import time

    # Ensure it was touched within max_age_seconds
    if time.time() - newest.stat().st_mtime <= max_age_seconds:
        return newest
    return None

