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
from textual.widgets import ListView, Static, Label, Input
from textual.containers import Vertical, Horizontal, Container
from textual.app import ComposeResult
from rich.text import Text
from cyb0x_s.tui.theme import current_palette

OUT_DIR = Path("/home/albraa/.gemini/antigravity/brain/88509fef-ff2a-469c-9481-9adbc3fa8f56")

# Concept 1: Structured HUD Container (Single well-formed precision industrial box with native border-title, border-subtitle, distinct command badge, tip, and styled CLI row)
async def preview_concept_1():
    set_derive_guidance(True)
    store = NotebookStore(":memory:")
    seed_demo(store)
    
    # We will test how it looks by modifying ConsoleBar in the running instance or via CSS
    app = CyboxSafeApp(store=store, theme="slate")
    async with app.run_test(size=(160, 44)) as pilot:
        svc_list = app.query_one("#list-services", ListView)
        svc_list.focus()
        await pilot.press("down")
        await pilot.pause()
        
        # Apply Concept 1 styling to ConsoleBar
        cb = app.query_one("#guidance-box")
        cb.border_title = " ACTION RECIPE & INSPECTOR "
        cb.border_subtitle = " [Enter: Copy] · [. Next (1/3)] "
        
        P = current_palette()
        # Format cmd line with a crisp tag
        cmd_text = Text()
        cmd_text.append(" RUN ▸ ", style=f"bold black on {P.accent}")
        cmd_text.append("  ssh <USER>@10.10.10.20", style=f"bold {P.text}")
        cb.query_one("#console-cmd", Static).update(cmd_text)
        
        tip_text = Text()
        tip_text.append(" TIP ▸ ", style=f"bold {P.muted}")
        tip_text.append("Connect using discovered credentials or private key. Check password auth methods.", style=f"{P.text_soft}")
        cb.query_one("#console-tip", Static).update(tip_text)
        
        inp = cb.query_one("#cmd-input", Input)
        inp.placeholder = "Type command (:t, :s, :c, :m, :w, :theme) or note... (: for menu, Tab to complete)"
        
        prompt = cb.query_one("#console-prompt", Label)
        prompt.update(" [ : ] ❯")
        
        await pilot.pause()
        strips = app.screen._compositor.render_strips()
        img = render_strips(strips, (160, 44))
        img.save(OUT_DIR / "preview_bottom_idea1_structured_hud.png")
        print("Saved Idea 1 preview")

# Concept 2: Sugary version of Concept 1
async def preview_concept_1_sugary():
    set_derive_guidance(True)
    store = NotebookStore(":memory:")
    seed_demo(store)
    
    app = CyboxSafeApp(store=store, theme="sugary")
    async with app.run_test(size=(160, 44)) as pilot:
        svc_list = app.query_one("#list-services", ListView)
        svc_list.focus()
        await pilot.press("down")
        await pilot.pause()
        
        cb = app.query_one("#guidance-box")
        cb.border_title = " ACTION RECIPE & INSPECTOR "
        cb.border_subtitle = " [Enter: Copy] · [. Next (1/3)] "
        
        P = current_palette()
        cmd_text = Text()
        cmd_text.append(" RUN ▸ ", style=f"bold #FFFFFF on {P.accent}")
        cmd_text.append("  ssh <USER>@10.10.10.20", style=f"bold {P.text}")
        cb.query_one("#console-cmd", Static).update(cmd_text)
        
        tip_text = Text()
        tip_text.append(" TIP ▸ ", style=f"bold {P.muted}")
        tip_text.append("Connect using discovered credentials or private key. Check password auth methods.", style=f"{P.text_soft}")
        cb.query_one("#console-tip", Static).update(tip_text)
        
        inp = cb.query_one("#cmd-input", Input)
        inp.placeholder = "Type command (:t, :s, :c, :m, :w, :theme) or note... (: for menu, Tab to complete)"
        
        prompt = cb.query_one("#console-prompt", Label)
        prompt.update(" [ : ] ❯")
        
        await pilot.pause()
        strips = app.screen._compositor.render_strips()
        img = render_strips(strips, (160, 44))
        img.save(OUT_DIR / "preview_bottom_idea1_sugary.png")
        print("Saved Idea 1 Sugary preview")

async def main():
    await preview_concept_1()
    await preview_concept_1_sugary()

if __name__ == "__main__":
    asyncio.run(main())
