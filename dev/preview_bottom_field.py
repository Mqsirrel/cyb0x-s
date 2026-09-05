import asyncio
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "examples"))

from demo_seed import seed_demo
from cyb0x_s.db.store import NotebookStore
from cyb0x_s.tui.app import CyboxSafeApp
from cyb0x_s.settings import set_derive_guidance
from dev.screenshot import render_strips
from textual.widgets import ListView

async def main():
    set_derive_guidance(True)
    store = NotebookStore(":memory:")
    seed_demo(store)
    app = CyboxSafeApp(store=store, theme="slate")
    async with app.run_test(size=(160, 44)) as pilot:
        svc_list = app.query_one("#list-services", ListView)
        svc_list.focus()
        await pilot.press("down")
        await pilot.pause()
        
        strips = app.screen._compositor.render_strips()
        img = render_strips(strips, (160, 44))
        out_path = Path("/home/albraa/.gemini/antigravity/brain/88509fef-ff2a-469c-9481-9adbc3fa8f56/preview_bottom_with_recipe.png")
        img.save(out_path)
        print("Saved with recipe to", out_path)

if __name__ == "__main__":
    asyncio.run(main())
