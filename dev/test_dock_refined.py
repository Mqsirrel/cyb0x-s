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
from rich.text import Text
from cyb0x_s.tui.theme import current_palette

OUT_DIR = Path("/home/albraa/.gemini/antigravity/brain/88509fef-ff2a-469c-9481-9adbc3fa8f56")

async def test_theme(theme_name: str, filename: str):
    set_derive_guidance(True)
    store = NotebookStore(":memory:")
    seed_demo(store)
    app = CyboxSafeApp(store=store, theme=theme_name)
    async with app.run_test(size=(160, 44)) as pilot:
        # Hide footer
        footer = app.query_one("Footer")
        footer.styles.display = "none"
        
        svc_list = app.query_one("#list-services", ListView)
        svc_list.focus()
        await pilot.press("down")
        await pilot.pause()
        
        P = current_palette()
        cb = app.query_one("#guidance-box")
        cb.styles.height = 5
        cb.styles.padding = (0, 0)
        cb.styles.margin = (0, 1)
        cb.styles.border = ("solid", P.border)
        cb.styles.border_top = ("solid", P.accent)
        cb.border_title = " ACTION RECIPE & LIVE GUIDANCE "
        cb.border_subtitle = " [Enter: Copy] · [. Next (1/3)] "
        
        cmd_static = cb.query_one("#console-cmd", Static)
        cmd_static.styles.height = 1
        cmd_static.styles.padding = (0, 1)
        cmd_text = Text()
        cmd_text.append("RUN ▸ ", style=f"bold {P.accent}")
        cmd_text.append("ssh <USER>@10.10.10.20", style=f"bold {P.text}")
        cmd_static.update(cmd_text)
        
        tip_static = cb.query_one("#console-tip", Static)
        tip_static.styles.height = 1
        tip_static.styles.padding = (0, 1)
        tip_text = Text()
        tip_text.append("TIP ▸ ", style=f"bold {P.muted}")
        tip_text.append("Connect using discovered credentials or private key. Check allowed auth methods.", style=f"{P.text_soft}")
        tip_static.update(tip_text)
        
        input_row = cb.query_one("#console-input-row")
        input_row.styles.height = 1
        input_row.styles.padding = (0, 1)
        input_row.styles.background = P.surface_darken_1 if hasattr(P, "surface_darken_1") else P.bg
        
        prompt = cb.query_one("#console-prompt", Label)
        prompt.styles.width = "auto"
        prompt.update(" [ : ] ❯ ")
        
        inp = cb.query_one("#cmd-input", Input)
        inp.placeholder = "Type command (:t, :s, :c, :m, :w) or note... (: for menu, Tab to complete)"
        inp.styles.border = "none"
        inp.styles.background = "transparent"
        inp.styles.padding = (0, 0)
        
        # Add hotkey strip to the right of input_row
        try:
            hotkeys_lbl = input_row.query_one("#console-hotkeys", Label)
        except Exception:
            hotkeys_text = Text()
            hotkeys_text.append(" [w]", style=f"bold {P.warn}")
            hotkeys_text.append(" panels ", style=f"{P.muted}")
            hotkeys_text.append(" [1-4]", style=f"bold {P.warn}")
            hotkeys_text.append(" stations ", style=f"{P.muted}")
            hotkeys_text.append(" [?]", style=f"bold {P.warn}")
            hotkeys_text.append(" help ", style=f"{P.muted}")
            hotkeys_text.append(" [q]", style=f"bold {P.warn}")
            hotkeys_text.append(" quit", style=f"{P.muted}")
            hotkeys_lbl = Label(hotkeys_text, id="console-hotkeys")
            hotkeys_lbl.styles.width = "auto"
            input_row.mount(hotkeys_lbl)
        
        await pilot.pause()
        strips = app.screen._compositor.render_strips()
        img = render_strips(strips, (160, 44))
        img.save(OUT_DIR / filename)
        print("Saved", filename)

async def main():
    await test_theme("slate", "test_dock_refined_slate.png")
    await test_theme("sugary", "test_dock_refined_sugary.png")

if __name__ == "__main__":
    asyncio.run(main())
