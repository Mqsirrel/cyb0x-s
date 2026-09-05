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
from textual.app import App, ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import ListView, Static, Label, Input, TabbedContent, TabPane, Tree
from rich.text import Text
from cyb0x_s.tui.theme import APP_CSS, PALETTES, current_palette, set_palette
from cyb0x_s.tui.widgets import WorksheetHeader, MachineStatusStrip, TargetTreeWidget

OUT_DIR = Path("/home/albraa/.gemini/antigravity/brain/88509fef-ff2a-469c-9481-9adbc3fa8f56")

# Concept A App: Separated Action Inspector Panel + Unified Statusline / CLI Bar
class ConceptAApp(CyboxSafeApp):
    CSS = APP_CSS + """
    #guidance-box {
        height: 3;
        border: solid $border;
        background: $surface;
        padding: 0 1;
        margin: 0 1;
    }
    #guidance-box:focus-within {
        border: solid $accent;
    }
    #cmd-cli-bar {
        height: 1;
        background: $surface-darken-1;
        padding: 0 1;
        margin: 0 1;
        layout: horizontal;
    }
    #cli-prompt-label {
        width: auto;
        color: $accent;
        text-style: bold;
    }
    #cli-input-field {
        width: 1fr;
        height: 1;
        border: none;
        background: transparent;
        color: $foreground;
    }
    #cli-hotkeys-label {
        width: auto;
        color: $text-muted;
        text-align: right;
    }
    Footer {
        display: none;
    }
    """

    def compose(self) -> ComposeResult:
        active_ws = self.store.get_active_workspace()
        yield WorksheetHeader(workspace_name=active_ws.name if active_ws else "default")
        yield MachineStatusStrip(id="target-info")

        with TabbedContent(initial="tab-worksheet", id="tabs"):
            with TabPane("1 ⌂ Cockpit", id="tab-worksheet"):
                with Horizontal(id="cockpit"):
                    with Vertical(id="sidebar"):
                        with Vertical(id="panel-surface", classes="panel-box"):
                            yield TargetTreeWidget(id="target-tree")
                        with Vertical(id="panel-creds", classes="panel-box"):
                            yield ListView(id="list-creds", classes="panel-list")
                    with Vertical(id="workbench"):
                        with Vertical(id="panel-services", classes="panel-box"):
                            yield ListView(id="list-services", classes="panel-list")
                        with Horizontal(id="lower-band"):
                            with Vertical(id="panel-checklist", classes="panel-box"):
                                yield ListView(id="list-checklist", classes="panel-list")
                            with Vertical(id="panel-notes", classes="panel-box"):
                                yield ListView(id="list-notes", classes="panel-list")

        with Vertical(id="guidance-box"):
            yield Static(id="console-cmd")
            yield Static(id="console-tip")

        with Horizontal(id="cmd-cli-bar"):
            yield Label(" [ : ] ❯ ", id="cli-prompt-label")
            yield Input(placeholder="Type command (:t, :s, :c, :m, :w) or note... (: for menu, Tab to complete)", id="cli-input-field")
            yield Label(" [w] panels  [1-4] stations  [?] help  [q] quit ", id="cli-hotkeys-label")

async def test_concept_a(theme="slate", filename="preview_concept_A_separated_deck.png"):
    set_derive_guidance(True)
    store = NotebookStore(":memory:")
    seed_demo(store)
    app = ConceptAApp(store=store, theme=theme)
    async with app.run_test(size=(160, 44)) as pilot:
        svc_list = app.query_one("#list-services", ListView)
        svc_list.focus()
        await pilot.press("down")
        await pilot.pause()
        
        P = current_palette()
        box = app.query_one("#guidance-box")
        box.border_title = " ACTION RECIPE "
        box.border_subtitle = " [Enter: Copy] · [. Next (1/3)] "
        
        cmd_text = Text()
        cmd_text.append("RUN ▸ ", style=f"bold {P.accent}")
        cmd_text.append("ssh <USER>@10.10.10.20", style=f"bold {P.text}")
        box.query_one("#console-cmd", Static).update(cmd_text)
        
        tip_text = Text()
        tip_text.append("TIP ▸ ", style=f"bold {P.muted}")
        tip_text.append("Connect using discovered credentials or private key. Check password auth status.", style=f"{P.text_soft}")
        box.query_one("#console-tip", Static).update(tip_text)
        
        await pilot.pause()
        strips = app.screen._compositor.render_strips()
        img = render_strips(strips, (160, 44))
        img.save(OUT_DIR / filename)
        print("Wrote", filename)

async def main():
    await test_concept_a("slate", "preview_concept_A_slate.png")
    await test_concept_a("sugary", "preview_concept_A_sugary.png")

if __name__ == "__main__":
    asyncio.run(main())
