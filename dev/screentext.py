"""Dump the rendered text of CYB0X-S TUI screens for layout review.

Dev tool: boots the app headless, drives it with keystrokes, and writes the
compositor output as plain text (one file per screen) plus a report of lines
that are visually truncated / clipped.

Usage:
    python dev/screentext.py [output_dir] [width] [height]
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Iterable, Sequence

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "examples"))

from demo_seed import seed_demo  # noqa: E402

from cyb0x_s.db.store import NotebookStore  # noqa: E402
from cyb0x_s.tui.app import CyboxSafeApp  # noqa: E402


def strips_to_lines(strips: Sequence, cols: int) -> list[str]:
    lines = []
    for strip in strips:
        buf: list[str] = []
        for segment in strip._segments:
            buf.append(segment.text)
        line = "".join(buf)
        # Trim only trailing spaces for readability.
        lines.append(line.rstrip())
    return lines


async def capture(
    out_dir: Path, shots: Iterable[tuple[str, Sequence[str], str]], size
) -> None:
    store = NotebookStore(":memory:")
    seed_demo(store)
    app = CyboxSafeApp(store=store)

    async with app.run_test(size=size) as pilot:
        for name, keys, note in shots:
            for key in keys:
                if isinstance(key, tuple):
                    await pilot.press(*key)
                else:
                    await pilot.press(key)
                await pilot.pause()
            await pilot.pause()
            strips = app.screen._compositor.render_strips()
            lines = strips_to_lines(strips, size[0])
            path = out_dir / f"{name}.txt"
            path.write_text("\n".join(lines) + "\n")
            print(f"wrote {path}  ({note})")


SHOTS = [
    ("01-worksheet", [], "tab 1 default view"),
    ("02-playbooks", ["2"], "tab 2 playbooks"),
    ("03-creds", ["3"], "tab 3 credential matrix"),
    ("04-loot", ["4"], "tab 4 flags & failure log"),
    ("05-help", ["1", "question_mark"], "help modal"),
    ("06-search", ["escape", "slash"], "search modal"),
    ("07-reference", ["escape", "r"], "cheat sheet modal"),
    ("08-add-target", ["escape", "t"], "add target modal"),
    ("09-add-service", ["escape", "s"], "add service modal"),
    ("10-templates", ["escape", "m"], "template picker"),
]


def main() -> None:
    args = sys.argv[1:]
    out_dir = Path(args[0]) if args else Path(".arena/screens")
    cols = int(args[1]) if len(args) > 1 else 160
    rows = int(args[2]) if len(args) > 2 else 44
    out_dir.mkdir(parents=True, exist_ok=True)
    asyncio.run(capture(out_dir, SHOTS, (cols, rows)))


if __name__ == "__main__":
    main()
