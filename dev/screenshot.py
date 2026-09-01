"""Render CYB0X-S TUI screens to PNG images (headless).

Dev tool: boots the Textual app with seeded demo data, drives it through a
sequence of keystrokes, and rasterises the compositor output to PNG so the UI
can be reviewed without a terminal.

Usage:
    python dev/screenshot.py [output_dir]
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Iterable, Sequence

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "examples"))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from demo_seed import seed_demo  # noqa: E402

from cyb0x_s.db.store import NotebookStore  # noqa: E402
from cyb0x_s.tui.app import CyboxSafeApp  # noqa: E402

FONT_DIR = Path("/usr/share/fonts/truetype/dejavu")
FONT_REGULAR = str(FONT_DIR / "DejaVuSansMono.ttf")
FONT_BOLD = str(FONT_DIR / "DejaVuSansMono-Bold.ttf")

DEFAULT_FG = (237, 230, 218)
DEFAULT_BG = (33, 30, 27)

FONT_SIZE = 17
LINE_PAD = 1


def _load_fonts() -> tuple[ImageFont.FreeTypeFont, ImageFont.FreeTypeFont]:
    regular = ImageFont.truetype(FONT_REGULAR, FONT_SIZE)
    bold = ImageFont.truetype(FONT_BOLD, FONT_SIZE)
    return regular, bold


def _rgb(color, default: tuple[int, int, int]) -> tuple[int, int, int]:
    if color is None:
        return default
    try:
        tc = color.get_truecolor()
    except Exception:  # pragma: no cover - defensive
        return default
    if tc is None:
        return default
    return (tc.red, tc.green, tc.blue)


def render_strips(strips: Sequence, size) -> Image.Image:
    regular, bold = _load_fonts()
    cell_w = int(round(regular.getlength("M")))
    cell_h = FONT_SIZE + LINE_PAD * 2
    cols, rows = size

    img = Image.new("RGB", (cols * cell_w + 8, rows * cell_h + 8), DEFAULT_BG)
    draw = ImageDraw.Draw(img)

    for y, strip in enumerate(strips):
        if y >= rows:
            break
        top = 4 + y * cell_h
        x = 4
        try:
            segments = strip._segments
        except Exception:  # pragma: no cover - defensive
            segments = []
        # Some strips are shorter than the screen: pad with default bg.
        for segment in segments:
            text = segment.text
            if not text:
                continue
            style = getattr(segment, "style", None)
            fg = _rgb(getattr(style, "color", None), DEFAULT_FG)
            bg = _rgb(getattr(style, "bgcolor", None), DEFAULT_BG)
            if getattr(style, "reverse", False):
                fg, bg = bg, fg
            if getattr(style, "dim", False):
                fg = tuple(int(c * 0.62) for c in fg)  # type: ignore[arg-type]
            font = bold if getattr(style, "bold", False) else regular
            for ch in text:
                draw.rectangle([x, top, x + cell_w - 1, top + cell_h - 1], fill=bg)
                if ch != " ":
                    draw.text(
                        (x, top + LINE_PAD - 2),
                        ch,
                        font=font,
                        fill=fg,
                    )
                if getattr(style, "underline", False):
                    draw.line(
                        [x, top + cell_h - 2, x + cell_w - 1, top + cell_h - 2],
                        fill=fg,
                    )
                x += cell_w
        if x < cols * cell_w + 4:
            draw.rectangle(
                [x, top, cols * cell_w + 4, top + cell_h - 1], fill=DEFAULT_BG
            )
    return img


async def capture(
    out_dir: Path, shots: Iterable[tuple[str, Sequence[str], str]], size=(160, 44)
) -> None:
    store = NotebookStore(":memory:")
    seed_demo(store)
    app = CyboxSafeApp(store=store)

    async with app.run_test(size=size) as pilot:
        for name, keys, note in shots:
            for key in keys:
                await pilot.press(*key) if isinstance(key, tuple) else await pilot.press(key)
                await pilot.pause()
            await pilot.pause()
            strips = app.screen._compositor.render_strips()
            img = render_strips(strips, size)
            path = out_dir / f"{name}.png"
            img.save(path)
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
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".arena/shots")
    out_dir.mkdir(parents=True, exist_ok=True)
    asyncio.run(capture(out_dir, SHOTS))


if __name__ == "__main__":
    main()
