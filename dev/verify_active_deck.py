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
from textual.widgets import ListView, Input

OUT_DIR = Path("/home/albraa/.gemini/antigravity/brain/88509fef-ff2a-469c-9481-9adbc3fa8f56")

async def capture_views():
    set_derive_guidance(True)
    
    # 1. Slate theme captures
    store = NotebookStore(":memory:")
    seed_demo(store)
    app = CyboxSafeApp(store=store, theme="slate")
    size = (160, 44)
    
    async with app.run_test(size=size) as pilot:
        # Shot 1: Cockpit idle
        await pilot.pause()
        strips = app.screen._compositor.render_strips()
        img = render_strips(strips, size)
        img.save(OUT_DIR / "final_deck_01_cockpit_idle_slate.png")
        
        # Shot 2: Cockpit service selected (recipe active)
        svc_list = app.query_one("#list-services", ListView)
        svc_list.focus()
        await pilot.press("down")
        await pilot.pause()
        strips = app.screen._compositor.render_strips()
        img = render_strips(strips, size)
        img.save(OUT_DIR / "final_deck_02_cockpit_recipe_slate.png")
        
        # Shot 3: Command typing
        inp = app.query_one("#cmd-input", Input)
        inp.focus()
        inp.value = ":s 80/tcp http"
        await pilot.pause()
        strips = app.screen._compositor.render_strips()
        img = render_strips(strips, size)
        img.save(OUT_DIR / "final_deck_03_command_runner_slate.png")
        
        # Clear input and switch to Station 2
        inp.value = ""
        app.action_switch_tab("tab-playbooks")
        await pilot.pause()
        strips = app.screen._compositor.render_strips()
        img = render_strips(strips, size)
        img.save(OUT_DIR / "final_deck_04_playbooks_slate.png")
        
        # Station 3
        app.action_switch_tab("tab-creds")
        await pilot.pause()
        strips = app.screen._compositor.render_strips()
        img = render_strips(strips, size)
        img.save(OUT_DIR / "final_deck_05_creds_slate.png")
        
        # Station 4
        app.action_switch_tab("tab-loot")
        await pilot.pause()
        strips = app.screen._compositor.render_strips()
        img = render_strips(strips, size)
        img.save(OUT_DIR / "final_deck_06_loot_slate.png")

    # 2. Sugary theme capture
    store_sugary = NotebookStore(":memory:")
    seed_demo(store_sugary)
    app_sugary = CyboxSafeApp(store=store_sugary, theme="sugary")
    async with app_sugary.run_test(size=size) as pilot:
        svc_list = app_sugary.query_one("#list-services", ListView)
        svc_list.focus()
        await pilot.press("down")
        await pilot.pause()
        strips = app_sugary.screen._compositor.render_strips()
        img = render_strips(strips, size)
        img.save(OUT_DIR / "final_deck_07_cockpit_recipe_sugary.png")
        
    print("All screenshots generated successfully!")

if __name__ == "__main__":
    asyncio.run(capture_views())
