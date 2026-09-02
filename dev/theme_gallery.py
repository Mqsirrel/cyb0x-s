"""Render all CYB0X-S palettes as a single PNG gallery (headless).

Dev tool: boots the Textual app once per palette, rasterises each compositor
frame, and tiles the thumbnails 2-up with a label in each palette's own accent.

Usage:
    python dev/theme_gallery.py [out_dir]

Requires Pillow. Reads the palettes from ``cyb0x_s.tui.theme``; the per-frame
rendering is delegated to :func:`screenshot.render_strips` (which reads the
active palette via :func:`screenshot._defaults`).
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "examples"))

from demo_seed import seed_demo  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402
from screenshot import render_strips  # noqa: E402

from cyb0x_s.db.store import NotebookStore  # noqa: E402
from cyb0x_s.tui.app import CyboxSafeApp  # noqa: E402
from cyb0x_s.tui.theme import PALETTES  # noqa: E402

SIZE = (150, 34)
FONT_DIR = Path("/usr/share/fonts/truetype/dejavu")
FONT_BOLD = str(FONT_DIR / "DejaVuSansMono-Bold.ttf")
FONT_REGULAR = str(FONT_DIR / "DejaVuSansMono.ttf")
LABEL_SIZE = 16
PREVIEW_PAD = 20


def _rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return (int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))


async def _capture_palette(theme: str, out_dir: Path) -> tuple[Image.Image, ImageFont.FreeTypeFont]:
    """Render one palette's cockpit, return (img, label_font)."""
    store = NotebookStore(":memory:")
    seed_demo(store)
    app = CyboxSafeApp(store=store, theme=theme)

    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        strips = app.screen._compositor.render_strips()
        img = render_strips(strips, SIZE)

    font = ImageFont.truetype(FONT_BOLD, LABEL_SIZE)
    return img, font


async def main() -> None:
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(ROOT / "dev" / "previews")
    out_dir.mkdir(parents=True, exist_ok=True)

    # Tile 2-up. Each tile = label bar + preview, sized to the biggest cell.
    cell_w = SIZE[0] * 8 + 8  # monospace cell width is ~8px per char
    cell_h = SIZE[1] * (17 + 2) + LABEL_SIZE + PREVIEW_PAD
    thumbs: dict[str, Image.Image] = {}

    # Render order matches the palette dict.
    names = list(PALETTES)
    for i, name in enumerate(names):
        img, _ = await _capture_palette(name, out_dir)
        thumbs[name] = img
        print(f"rendered {name} ({i + 1}/{len(names)})")

    cols = 2
    rows = (len(names) + 1) // 2
    canvas = Image.new("RGB", (cell_w * cols, cell_h * rows), (10, 10, 12))
    draw = ImageDraw.Draw(canvas)

    for idx, name in enumerate(names):
        row, col = divmod(idx, cols)
        x, y = col * cell_w, row * cell_h
        palette = PALETTES[name]

        ratio = palette.contrast_ratio()
        label = f"{palette.name}  {palette.label}  {ratio:.1f}:1"
        accent = _rgb(palette.accent)
        font = ImageFont.truetype(FONT_REGULAR, LABEL_SIZE)
        draw.text((x + 6, y + 2), label, fill=accent, font=font)

        pre = thumbs[name]
        canvas.paste(pre, (x + 4, y + LABEL_SIZE + 6))

    out = out_dir / "theme-gallery.png"
    canvas.save(out)
    print(f"wrote {out}")


if __name__ == "__main__":
    asyncio.run(main())
