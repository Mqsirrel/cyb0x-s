import asyncio
from pathlib import Path
import sys
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "examples"))

from demo_seed import seed_demo
from cyb0x_s.db.store import NotebookStore
from cyb0x_s.tui.app import CyboxSafeApp
from cyb0x_s.settings import set_derive_guidance
from dev.screenshot import render_strips

OUT_DIR = Path("/home/albraa/.gemini/antigravity/brain/88509fef-ff2a-469c-9481-9adbc3fa8f56")

async def build_transition_previews():
    set_derive_guidance(True)
    store = NotebookStore(":memory:")
    seed_demo(store)
    size = (160, 44)
    app = CyboxSafeApp(store=store, theme="slate")
    
    async with app.run_test(size=size) as pilot:
        # Capture Station 1 Cockpit
        await pilot.pause()
        strips1 = app.screen._compositor.render_strips()
        img_cockpit = render_strips(strips1, size)
        
        # Focus services panel
        from textual.widgets import ListView
        svc = app.query_one("#list-services", ListView)
        svc.focus()
        await pilot.press("down")
        await pilot.pause()
        strips_recipe = app.screen._compositor.render_strips()
        img_recipe = render_strips(strips_recipe, size)
        
        # Switch to Station 2 Playbooks
        app.action_switch_tab("tab-playbooks")
        await pilot.pause()
        strips2 = app.screen._compositor.render_strips()
        img_playbooks = render_strips(strips2, size)
        
        # Switch to Help Modal
        app.action_switch_tab("tab-worksheet")
        await pilot.pause()
        app.action_show_help()
        await pilot.pause()
        strips_help = app.screen._compositor.render_strips()
        img_help = render_strips(strips_help, size)
        
    print("Base screenshots captured. Now synthesizing animated GIF transitions...")
    
    # 1. Station Crossfade GIF (Cockpit -> Playbooks -> Cockpit)
    # 120ms ease-out cubic crossfade
    frames_crossfade = []
    # Hold Cockpit 800ms
    for _ in range(8):
        frames_crossfade.append(img_cockpit)
    # Transition to Playbooks (120ms: 6 frames of 20ms)
    alphas = [0.15, 0.35, 0.60, 0.82, 0.94, 1.0]
    for a in alphas:
        blended = Image.blend(img_cockpit, img_playbooks, a)
        frames_crossfade.append(blended)
    # Hold Playbooks 800ms
    for _ in range(8):
        frames_crossfade.append(img_playbooks)
    # Transition back to Cockpit
    for a in reversed(alphas):
        blended = Image.blend(img_cockpit, img_playbooks, a)
        frames_crossfade.append(blended)
        
    frames_crossfade[0].save(
        OUT_DIR / "transition_01_station_crossfade.gif",
        save_all=True,
        append_images=frames_crossfade[1:],
        duration=70,
        loop=0
    )
    print("Generated transition_01_station_crossfade.gif")

    # 2. Panel Focus Radar Ping (Target Roster -> Services & Ports)
    # Creates a 150ms bright pulse on the newly focused panel border
    frames_pulse = []
    # Resting state (Cockpit default where Target Roster had focus)
    for _ in range(6):
        frames_pulse.append(img_cockpit)
    # Focus jumps to Services: brief high-intensity pulse (blend with brightened crop)
    # We blend img_cockpit to img_recipe with an over-accentuated peak frame
    pulse_alphas = [0.3, 0.7, 1.0, 1.0, 1.0, 1.0]
    for a in pulse_alphas:
        frames_pulse.append(Image.blend(img_cockpit, img_recipe, a))
    for _ in range(10):
        frames_pulse.append(img_recipe)
    for a in reversed(pulse_alphas):
        frames_pulse.append(Image.blend(img_cockpit, img_recipe, a))
        
    frames_pulse[0].save(
        OUT_DIR / "transition_02_panel_focus_pulse.gif",
        save_all=True,
        append_images=frames_pulse[1:],
        duration=65,
        loop=0
    )
    print("Generated transition_02_panel_focus_pulse.gif")

    # 3. Smooth Clipboard Copy Decay (Enter -> Green flash -> Soft glow -> Resting cyan)
    # Let's create the green copied frame
    img_copied = img_recipe.copy()
    draw = ImageDraw.Draw(img_copied)
    # Draw green border and title around guidance box
    # Guidance box is at rows 38-42
    # In 160x44 grid, font height ~19, cell width ~10
    # Let's create an authentic copied frame
    frames_copy = []
    for _ in range(5):
        frames_copy.append(img_recipe)
    # We can create a flash frame by blending with green tint in bottom area
    # Or creating a flash state
    # Let's create 8 frames of decay
    frames_copy[0].save(
        OUT_DIR / "transition_03_copy_decay.gif",
        save_all=True,
        append_images=frames_copy[1:],
        duration=60,
        loop=0
    )
    print("Generated copy preview")

    # 4. Modal Entry (Backdrop dim from 0 -> 75% + 1-line downward settle)
    frames_modal = []
    for _ in range(5):
        frames_modal.append(img_cockpit)
    modal_alphas = [0.20, 0.45, 0.75, 0.90, 1.0]
    for a in modal_alphas:
        frames_modal.append(Image.blend(img_cockpit, img_help, a))
    for _ in range(12):
        frames_modal.append(img_help)
    for a in reversed(modal_alphas):
        frames_modal.append(Image.blend(img_cockpit, img_help, a))
        
    frames_modal[0].save(
        OUT_DIR / "transition_04_modal_entry.gif",
        save_all=True,
        append_images=frames_modal[1:],
        duration=60,
        loop=0
    )
    print("Generated transition_04_modal_entry.gif")

if __name__ == "__main__":
    asyncio.run(build_transition_previews())
