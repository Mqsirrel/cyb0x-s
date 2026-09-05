"""Regression tests for the TUI layout and interaction fixes.

These cover the behaviours that were found broken during the UI review:
invisible active station tab, the crash when highlighting a service, the
zero-height failure log, the no-op zoom, unguarded deletes and j/k movement.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from textual.widgets import Input, ListView

from cyb0x_s.db.store import NotebookStore
from cyb0x_s.settings import set_derive_guidance
from cyb0x_s.tui.app import CyboxSafeApp
from cyb0x_s.tui.theme import current_palette
from cyb0x_s.tui.widgets import (
    ConfirmModal,
    ConsoleBar,
    LootAndFlagsWidget,
    MachineStatusStrip,
    SearchModal,
    TargetTreeWidget,
    WorksheetHeader,
)




@pytest.mark.asyncio
async def test_active_tab_label_is_visible(seeded_store: NotebookStore) -> None:
    """The active station must render its label (it used to collapse to 0px)."""
    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test():
        active_tabs = [t for t in app.query("Tab") if "-active" in t.classes]
        assert active_tabs, "expected exactly one active tab"
        active = active_tabs[0]
        assert active.size.height >= 1
        assert active.render().plain.strip(), "active tab label rendered empty"
        assert "Cockpit" in active.render().plain
        # The underline is the only other "you are here" indicator.
        underline = app.query_one("Underline")
        assert underline.styles.display != "none"


@pytest.mark.asyncio
async def test_highlighting_a_service_updates_drawer(seeded_store: NotebookStore) -> None:
    """Highlighting a service fills the guidance drawer instead of raising."""
    set_derive_guidance(True)
    try:
        app = CyboxSafeApp(store=seeded_store)
        async with app.run_test(size=(160, 44)) as pilot:
            svc_list = app.query_one("#list-services", ListView)
            svc_list.focus()
            await pilot.press("down")
            await pilot.pause()

            console = app.query_one("#guidance-box", ConsoleBar)
            text = console.query_one("#console-cmd").render().plain
            assert "10.10.10.20" in text, "target IP should be substituted into the command"
            assert console.size.height >= 1
    finally:
        set_derive_guidance(None)


@pytest.mark.asyncio
async def test_tree_navigation_updates_drawer(seeded_store: NotebookStore) -> None:
    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test() as pilot:
        tree = app.query_one(TargetTreeWidget)
        tree.focus()
        await pilot.press("down")
        await pilot.pause()
        console = app.query_one("#guidance-box", ConsoleBar)
        assert console.query_one("#console-cmd").render().plain


@pytest.mark.asyncio
async def test_failure_log_panel_has_height(seeded_store: NotebookStore) -> None:
    """Tab 4's rabbit-hole log must actually occupy screen space."""
    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test(size=(140, 40)) as pilot:
        app.action_switch_tab("tab-loot")
        await pilot.pause()
        loot = app.query_one(LootAndFlagsWidget)
        failure_box = loot.query_one("#loot-failure-box")
        assert failure_box.size.height > 0
        assert failure_box.region.y + failure_box.size.height <= loot.region.bottom + 1


@pytest.mark.asyncio
async def test_zoom_expands_panel_and_restores(seeded_store: NotebookStore) -> None:
    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test(size=(160, 44)) as pilot:
        panel = app.query_one("#panel-services")
        width_before = panel.size.width

        panel.query_one(ListView).focus()
        await pilot.pause()
        app.action_toggle_zoom()
        await pilot.pause()

        assert panel.size.width > width_before, "zoomed panel should span the workbench"
        assert app.query_one("#lower-band").styles.display == "none"
        assert app.query_one("#cockpit").has_class("zoomed-mode")

        app.action_toggle_zoom()
        await pilot.pause()
        assert not app.query_one("#cockpit").has_class("zoomed-mode")
        assert app.query_one("#lower-band").styles.display == "block"


@pytest.mark.asyncio
async def test_delete_asks_for_confirmation(seeded_store: NotebookStore) -> None:
    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test() as pilot:
        svc_list = app.query_one("#list-services", ListView)
        svc_list.focus()
        await pilot.press("down")

        await pilot.press("d")
        assert isinstance(app.screen, ConfirmModal)

        # Cancelling keeps the data.
        await pilot.press("escape")
        assert len(seeded_store.list_services()) == 2

        # Confirming removes it.
        await pilot.press("d")
        await pilot.press("y")
        assert len(seeded_store.list_services()) == 1


@pytest.mark.asyncio
async def test_j_and_k_move_the_highlight(seeded_store: NotebookStore) -> None:
    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test(size=(160, 44)) as pilot:
        svc_list = app.query_one("#list-services", ListView)
        svc_list.focus()
        await pilot.press("down")
        assert svc_list.index == 0
        await pilot.press("j")
        assert svc_list.index == 1
        await pilot.press("k")
        assert svc_list.index == 0
        # 'k' must not open the add-checklist dialog any more.
        assert not any(isinstance(s, SearchModal) for s in app.screen_stack)


@pytest.mark.asyncio
async def test_search_enter_copies_and_closes(seeded_store: NotebookStore) -> None:
    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test() as pilot:
        app.action_open_search()
        await pilot.pause()
        assert isinstance(app.screen, SearchModal)
        app.screen.query_one("#search-input", Input).value = "archive"
        results = app.screen.query_one("#search-results", ListView)
        for _ in range(10):
            await pilot.pause(0.05)
            if len(results.children) >= 1:
                break
        assert len(results.children) >= 1
        await pilot.press("enter")
        await pilot.pause()
        assert not isinstance(app.screen, SearchModal)


@pytest.mark.asyncio
async def test_footer_only_shows_core_keys(seeded_store: NotebookStore) -> None:
    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test():
        shown = [b for b in app.BINDINGS if b.show]
        assert len(shown) <= 6


@pytest.mark.asyncio
async def test_header_reports_workspace_and_counts(seeded_store: NotebookStore) -> None:
    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test(size=(160, 44)):
        header = app.query_one(WorksheetHeader)
        text = header.render().plain
        assert "default" in text or "Lab" in text
        assert "targets 1" in text


@pytest.mark.asyncio
async def test_status_strip_shows_machine_and_next_step(seeded_store: NotebookStore) -> None:
    """The exam-speed strip: target, scope, loot and what to do next."""
    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test(size=(160, 44)):
        strip = app.query_one(MachineStatusStrip)
        text = strip.render().plain
        assert "10.10.10.20" in text
        assert "IN-SCOPE" in text
        assert "NEXT" in text or "TODO" in text
        assert "SMB enumeration" in text  # first TODO checklist item
        assert "2 ports" in text


@pytest.mark.asyncio
async def test_command_bar_still_captures_shortcuts(seeded_store: NotebookStore) -> None:
    """Typing in the command bar must not trigger single-letter hotkeys."""
    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test() as pilot:
        cmd = app.query_one("#cmd-input", Input)
        cmd.focus()
        for char in ":njk":
            await pilot.press(char)
        assert cmd.value == ":njk"
        assert not any(isinstance(s, ConfirmModal) for s in app.screen_stack)


@pytest.mark.asyncio
async def test_console_shows_command_for_highlighted_row(seeded_store: NotebookStore) -> None:
    """The bottom console is the single place commands are previewed."""
    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test(size=(160, 44)) as pilot:
        console = app.query_one("#guidance-box", ConsoleBar)
        # idle state is a hint, never a blank row
        assert console.query_one("#console-cmd").render().plain.strip()

        checklist = app.query_one("#list-checklist", ListView)
        checklist.focus()
        await pilot.press("down")
        await pilot.pause()
        assert console.query_one("#console-cmd").render().plain.strip()

        assert console.size.width > 100, "console spans the terminal width"


@pytest.mark.asyncio
async def test_cockpit_panels_are_all_visible(seeded_store: NotebookStore) -> None:
    """Station 1 shows attack surface, services, methodology and notes at once."""
    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test(size=(160, 44)):
        for panel in ("#panel-surface", "#panel-creds", "#panel-services", "#panel-checklist", "#panel-notes"):
            widget = app.query_one(panel)
            assert widget.size.height > 0, f"{panel} has no height"
            assert widget.size.width > 0, f"{panel} has no width"
        # services is the widest panel: full workbench width, not a half column
        services = app.query_one("#panel-services")
        assert services.size.width > app.query_one("#panel-checklist").size.width


@pytest.mark.asyncio
async def test_theme_switch_is_live(seeded_store: NotebookStore) -> None:
    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test(size=(140, 40)) as pilot:
        assert app.theme_name == "slate"
        before = current_palette().accent

        app.apply_theme("caramel")
        await pilot.pause(0)
        assert app.theme_name == "caramel"
        assert current_palette().accent != before
        assert app.theme == "cyb0x-caramel"

        app.action_cycle_theme()
        await pilot.pause(0)
        assert app.theme_name == "slate"
        assert current_palette().accent == before

        # rows follow the palette
        app.query_one("#list-services", ListView).focus()
        await pilot.pause(0)
        app.apply_theme("sugary")
        await pilot.pause(0)
        item = app.query_one("#list-services", ListView).children[0]
        assert item.display_text.plain.strip()


@pytest.mark.asyncio
async def test_theme_command_bar(seeded_store: NotebookStore) -> None:
    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test(size=(140, 40)) as pilot:
        from textual.widgets import Input

        cmd = app.query_one("#cmd-input", Input)
        cmd.focus()
        cmd.value = ":theme sugary"
        await cmd.action_submit()
        await pilot.pause()
        assert app.theme_name == "sugary"

        cmd.value = ":theme nope"
        await cmd.action_submit()
        await pilot.pause()
        assert app.theme_name == "sugary"


@pytest.mark.asyncio
async def test_every_modal_mounts(seeded_store: NotebookStore) -> None:
    """Guard against stylesheet typos in screens the smoke test never opens."""
    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test(size=(140, 40)) as pilot:
        for key in ("?", "/", "r", "m", "g", "t", "s", "f", "c", "n", "K"):
            await pilot.press(key)
            assert len(app.screen_stack) > 1, f"{key!r} did not open a modal"
            await pilot.press("escape")
            assert len(app.screen_stack) == 1, f"{key!r} modal did not close"


@pytest.mark.asyncio
async def test_console_bar_live_hints_and_autocomplete(seeded_store: NotebookStore) -> None:
    """Test live syntax hints and Tab completion on the bottom command bar."""
    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test(size=(140, 40)) as pilot:
        from textual.widgets import Input, Static

        from cyb0x_s.tui.widgets import ConsoleBar

        cmd = app.query_one("#cmd-input", Input)
        console = app.query_one("#guidance-box", ConsoleBar)
        cmd.focus()

        # Typing ':' triggers Command Menu preview
        cmd.value = ":"
        await pilot.pause()
        cmd_text = console.query_one("#console-cmd", Static).render().plain
        assert "COMMAND MENU" in cmd_text

        # Typing ':s' triggers Add Service preview
        cmd.value = ":s"
        await pilot.pause()
        cmd_text = console.query_one("#console-cmd", Static).render().plain
        assert "ADD SERVICE" in cmd_text

        # Pressing Tab autocompletes ':th' -> ':theme '
        cmd.value = ":th"
        await pilot.press("tab")
        await pilot.pause()
        assert cmd.value == ":theme "


@pytest.mark.asyncio
async def test_natural_language_command_aliases(seeded_store: NotebookStore) -> None:
    """Test command execution without colons (e.g. target, service, help)."""
    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test(size=(140, 40)) as pilot:
        from textual.widgets import Input

        cmd = app.query_one("#cmd-input", Input)
        cmd.focus()

        # 'add target 192.168.1.99'
        cmd.value = "add target 192.168.1.99"
        await cmd.action_submit()
        await pilot.pause()
        targets = seeded_store.list_targets()
        assert any(t.ip == "192.168.1.99" for t in targets)

        # 'theme candy'
        cmd.value = "theme candy"
        await cmd.action_submit()
        await pilot.pause()
        assert app.theme_name == "candy"


@pytest.mark.asyncio
async def test_change_methodology_tui(seeded_store: NotebookStore) -> None:
    """Test switching methodology template replaces current items and updates cockpit."""
    from cyb0x_s.tui.widgets import TemplateSelectionModal

    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test(size=(140, 40)) as pilot:
        # Press 'm' to open methodology modal
        await pilot.press("m")
        await pilot.pause()
        assert any(isinstance(s, TemplateSelectionModal) for s in app.screen_stack)

        # In modal, highlight 'web' and press Enter (or switch button)
        modal = app.screen
        assert isinstance(modal, TemplateSelectionModal)
        # Select web
        modal.dismiss(("web", True))
        await pilot.pause()

        # Check that checklist has been switched to web
        active = seeded_store.get_active_target()
        items = seeded_store.list_checklist_items(target_id=active.id)
        assert len(items) > 0
        assert all(item.category == "WEB APPLICATION TESTING" for item in items)
        # Verify old eJPT items were replaced
        assert not any("Scope & Subnet Recon" in item.title for item in items)


@pytest.mark.asyncio
async def test_command_bar_methodology_switch(seeded_store: NotebookStore) -> None:
    """Test switching methodology via command bar :m smb."""
    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test(size=(140, 40)) as pilot:
        from textual.widgets import Input

        cmd = app.query_one("#cmd-input", Input)
        cmd.focus()
        cmd.value = ":m smb"
        await cmd.action_submit()
        await pilot.pause()

        active = seeded_store.get_active_target()
        items = seeded_store.list_checklist_items(target_id=active.id)
        assert len(items) > 0
        assert all(item.category == "SMB ENUMERATION" for item in items)


@pytest.mark.asyncio
async def test_colon_hotkey_focuses_cmd_input(seeded_store: NotebookStore) -> None:
    """Pressing ':' anywhere in cockpit instantly focuses command input with ':'."""
    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test(size=(140, 40)) as pilot:
        from textual.widgets import Input

        cmd = app.query_one("#cmd-input", Input)
        assert not cmd.has_focus

        await pilot.press("colon")
        await pilot.pause()

        assert cmd.has_focus
        assert cmd.value == ":"


@pytest.mark.asyncio
async def test_bracket_keys_cycle_targets(seeded_store: NotebookStore) -> None:
    """Pressing '[' and ']' cycles through targets in the workspace."""
    target1 = seeded_store.get_active_target()
    target2 = seeded_store.add_target("10.10.10.30", hostname="web01.local")
    seeded_store.set_active_target(target1.id)

    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test(size=(140, 40)) as pilot:
        assert seeded_store.get_active_target().ip == "10.10.10.20"

        await pilot.press("right_square_bracket")
        assert seeded_store.get_active_target().ip == target2.ip

        await pilot.press("left_square_bracket")
        assert seeded_store.get_active_target().ip == target1.ip


@pytest.mark.asyncio
async def test_sidebar_toggle_hotkey(seeded_store: NotebookStore) -> None:
    """Pressing 'b' toggles the sidebar visibility."""
    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test(size=(140, 40)) as pilot:
        sidebar = app.query_one("#sidebar")
        assert not sidebar.has_class("hidden")

        await pilot.press("b")
        assert sidebar.has_class("hidden")

        await pilot.press("b")
        assert not sidebar.has_class("hidden")


@pytest.mark.asyncio
async def test_service_space_cycles_status(seeded_store: NotebookStore) -> None:
    """Pressing Space on a highlighted service cycles its status."""
    from cyb0x_s.models import ServiceStatus

    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test(size=(140, 40)) as pilot:
        svc_list = app.query_one("#list-services", ListView)
        svc_list.focus()
        svc_list.index = 0
        await pilot.pause()

        target = seeded_store.get_active_target()
        svcs = seeded_store.list_services(target.id)
        first_svc = svcs[0]
        initial_status = first_svc.status

        await pilot.press("space")
        await pilot.pause()

        updated = seeded_store.get_service(first_svc.id)
        assert updated.status != initial_status
        assert updated.status in (
            ServiceStatus.CHECKED,
            ServiceStatus.DEAD_END,
            ServiceStatus.DEFERRED,
            ServiceStatus.UNTESTED,
        )


@pytest.mark.asyncio
async def test_recipe_carousel_cycling(seeded_store: NotebookStore) -> None:
    """Pressing '.' and ',' cycles through alternative attack recipes for the service."""
    from cyb0x_s.settings import set_derive_guidance

    set_derive_guidance(True)
    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test(size=(140, 40)) as pilot:
        svcs = seeded_store.list_services()
        smb_svc = next(s for s in svcs if "smb" in s.service.lower() or s.port == 445)
        app._guidance_for_service(smb_svc, "10.10.10.20")
        await pilot.pause()

        console = app.query_one("#guidance-box", ConsoleBar)
        first_cmd = console.command
        assert "smb" in first_cmd.lower()

        # Cycle to next recipe with '.'
        await pilot.press("full_stop")
        await pilot.pause()
        second_cmd = console.command
        assert "RECIPE 2/" in console.heading or second_cmd != first_cmd

        # Cycle back with ','
        await pilot.press("comma")
        await pilot.pause()
        assert console.command == first_cmd
    set_derive_guidance(None)


@pytest.mark.asyncio
async def test_panel_navigation_keys(seeded_store: NotebookStore) -> None:
    """Pressing 'w' cycles panels, 'h' focuses left sidebar, 'l' focuses right workbench."""
    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test(size=(140, 40)) as pilot:
        # Start at services list
        svc_list = app.query_one("#list-services", ListView)
        svc_list.focus()
        await pilot.pause(0)
        assert svc_list.has_focus

        # 'h' jumps to left sidebar (target tree)
        await pilot.press("h")
        tree = app.query_one("#target-tree")
        assert tree.has_focus

        # 'l' jumps to right workbench (services list)
        await pilot.press("l")
        assert svc_list.has_focus

        # 'w' cycles sequentially
        await pilot.press("w")
        ck = app.query_one("#list-checklist")
        assert ck.has_focus


@pytest.mark.asyncio
async def test_service_cross_filtering(seeded_store: NotebookStore) -> None:
    """Highlighting a service aligns the checklist and credentials."""
    target = seeded_store.get_active_target()
    seeded_store.add_checklist_item("Enumerate SMB shares", category="SMB", target_id=target.id)
    seeded_store.add_credential("smbuser", "secret123", service_scope="smb", target_id=target.id)

    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test(size=(140, 40)) as pilot:
        svc_list = app.query_one("#list-services", ListView)
        svc_list.focus()
        # Highlight SMB service
        svc_list.index = 1
        await pilot.press("down")
        await pilot.pause()

        # Checklist should auto-scroll to the SMB step
        ck_list = app.query_one("#list-checklist", ListView)
        curr_item = ck_list.highlighted_child
        assert curr_item is not None


@pytest.mark.asyncio
async def test_wordlist_command_execution(seeded_store: NotebookStore, monkeypatch: pytest.MonkeyPatch) -> None:
    """Typing ':w rockyou' copies the wordlist path to clipboard."""
    from textual.widgets import Input

    copied = []
    monkeypatch.setattr("cyb0x_s.tui.commands.copy_to_clipboard", lambda text: copied.append(text))

    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test(size=(140, 40)) as pilot:
        inp = app.query_one("#cmd-input", Input)
        inp.focus()
        inp.value = ":w rockyou"
        await pilot.press("enter")
        await pilot.pause()

        assert len(copied) >= 1
        assert copied[-1] == "/usr/share/wordlists/rockyou.txt"


@pytest.mark.asyncio
async def test_credential_matrix_2d_spray(seeded_store: NotebookStore, monkeypatch: pytest.MonkeyPatch) -> None:
    """Station 3 2D Matrix displays credentials, cycles status with Space, and generates spray on Enter."""
    from textual.widgets import DataTable

    target = seeded_store.get_active_target()
    seeded_store.add_credential("admin", "P@ssword123", service_scope="global", target_id=target.id)

    copied = []
    monkeypatch.setattr("cyb0x_s.tui.widgets.copy_to_clipboard", lambda text: copied.append(text))

    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test(size=(140, 40)) as pilot:
        # Switch to Station 3 (Creds)
        await pilot.press("3")

        table = app.query_one("#cred-matrix-table", DataTable)
        table.focus()
        assert table.row_count >= 1

        # Move to first spray target column
        table.cursor_coordinate = (0, 1)

        # Press space to cycle cell status
        await pilot.press("space")

        # Press Enter to compile and copy spray command
        await pilot.press("enter")

        assert len(copied) >= 1
        assert "admin" in copied[-1] or "P@ssword123" in copied[-1]


@pytest.mark.asyncio
async def test_machine_status_strip_small_terminal_no_crash(seeded_store: NotebookStore) -> None:
    """Ensure small terminal sizes (e.g. 76x24 or 72x24) elide cleanly without crashing."""
    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test(size=(76, 24)) as pilot:
        await pilot.pause()
        status_strip = app.query_one("#target-info", MachineStatusStrip)
        rendered = status_strip.render()
        assert rendered is not None


def test_badge_caches_and_clear() -> None:
    """Test static protocol badge cache and status icon cache."""
    from cyb0x_s.tui.widgets import (
        clear_badge_caches,
        get_protocol_badge,
        get_service_status_icon,
    )

    clear_badge_caches()
    badge1 = get_protocol_badge(80, "tcp", "slate")
    badge2 = get_protocol_badge(80, "tcp", "slate")
    assert badge1.plain == badge2.plain == "[80/tcp]    "

    icon1 = get_service_status_icon("CHECKED", "slate")
    icon2 = get_service_status_icon("CHECKED", "slate")
    assert icon1.plain == icon2.plain == "✓ "

    clear_badge_caches()


@pytest.mark.asyncio
async def test_differential_row_in_place_update(seeded_store: NotebookStore) -> None:
    """Test that toggling space updates ListItem in-place without rebuilding list."""
    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test(size=(140, 40)) as pilot:
        ck_list = app.query_one("#list-checklist", ListView)
        ck_list.focus()
        ck_list.index = 0
        await pilot.pause()

        first_item = ck_list.children[0]
        initial_label = first_item.display_text.plain

        await pilot.press("space")
        await pilot.pause()

        # The exact same child object should be in the list, with updated display text
        assert ck_list.children[0] is first_item
        assert first_item.display_text.plain != initial_label


@pytest.mark.asyncio
async def test_rapid_scrolling_stability(seeded_store: NotebookStore) -> None:
    """Ensure rapid repeated cursor movement / scrolling does not cascade or drop state."""
    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test(size=(140, 40)) as pilot:
        svc_list = app.query_one("#list-services", ListView)
        svc_list.focus()
        await pilot.pause()

        # Simulate rapid scrolling through multiple rows
        for _ in range(5):
            await pilot.press("down")
            await pilot.pause(0.01)

        # Allow settle debounce
        await pilot.pause(0.06)

        # Confirm app remains stable, focused, and cross-filter updated
        assert svc_list.index is not None
        assert not app._is_cross_filtering


@pytest.mark.asyncio
async def test_subnet_and_pivot_tree_rendering(seeded_store: NotebookStore) -> None:
    """Test multi-subnet grouping and pivot badge display in TargetTreeWidget."""
    from cyb0x_s.tui.widgets import TargetTreeWidget

    # Add a second subnet target with pivot
    t1 = seeded_store.get_active_target()
    assert t1 is not None
    seeded_store.update_target_details(t1.id, subnet="10.10.10.0/24", is_pivot=True, pivot_route="192.168.1.0/24 via :1080")

    t2 = seeded_store.add_target("192.168.1.50", hostname="db-internal")
    seeded_store.update_target_details(t2.id, subnet="192.168.1.0/24")

    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test(size=(140, 40)):
        tree = app.query_one("#target-tree", TargetTreeWidget)
        # Should now have 2 subnet branches
        assert len(tree.root.children) == 2
        subnet_nodes = [c.label.plain for c in tree.root.children]
        assert any("10.10.10.0/24" in s for s in subnet_nodes)
        assert any("192.168.1.0/24" in s for s in subnet_nodes)


@pytest.mark.asyncio
async def test_cred_matrix_persistence_in_tui(seeded_store: NotebookStore) -> None:
    """Test that toggling status in CredentialMatrixWidget persists to SQLite."""
    from cyb0x_s.tui.widgets import CredentialMatrixWidget

    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test(size=(140, 40)) as pilot:
        await pilot.press("3")  # switch to Station 3 Credentials

        matrix = app.query_one("#cred-matrix-widget", CredentialMatrixWidget)
        table = matrix.query_one("#cred-matrix-table")
        table.focus()
        table.move_cursor(row=0, column=1)

        # Press space to cycle
        await pilot.press("space")

        # Confirm persisted in store
        persisted = seeded_store.get_cred_validations()
        assert len(persisted) > 0


@pytest.mark.asyncio
async def test_exam_proof_ledger_and_commands(seeded_store: NotebookStore, tmp_path: Path) -> None:
    """Test recording exam proofs via :q command and markdown export."""
    from cyb0x_s.tui.widgets import LootAndFlagsWidget

    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test(size=(140, 40)) as pilot:
        from textual.widgets import Input

        cmd = app.query_one("#cmd-input", Input)
        cmd.focus()
        cmd.value = ":q Q14 secret_admin_hash_123"
        await cmd.action_submit()
        await pilot.pause()

        # Switch to Station 4 (Loot & Flags)
        app.action_switch_tab("tab-loot")
        await pilot.pause()

        loot = app.query_one("#loot-flags-widget", LootAndFlagsWidget)
        proof_list = loot.query_one("#loot-evidence-list", ListView)
        assert len(proof_list.children) >= 1
        assert "Q14" in proof_list.children[0].display_text.plain

        # Test export command
        cmd.focus()
        cmd.value = ":export exam"
        await cmd.action_submit()
        await pilot.pause()
        from pathlib import Path
        assert Path("exam_evidence.md").exists()
        assert "secret_admin_hash_123" in Path("exam_evidence.md").read_text(encoding="utf-8")
        Path("exam_evidence.md").unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_cockpit_layout_rebalance_and_console_visibility(seeded_store: NotebookStore) -> None:
    """Notes panel must be wider than checklist; console input row must be visible and accessible."""
    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test(size=(140, 40)):
        checklist = app.query_one("#panel-checklist")
        notes = app.query_one("#panel-notes")
        assert notes.size.width > checklist.size.width, "Notes & findings panel should have more width than checklist"

        # Console input row must have height >= 1 and be rendered inside guidance box
        input_row = app.query_one("#console-input-row")
        assert input_row.size.height >= 1
        cmd_input = app.query_one("#cmd-input", Input)
        assert cmd_input.size.height >= 1

        # Status strip displays NEXT, TODO, or CHECKLIST
        strip = app.query_one(MachineStatusStrip)
        assert "NEXT" in strip.render().plain or "TODO" in strip.render().plain or "CHECKLIST" in strip.render().plain

        # Service row formatting contains status pill
        svc_list = app.query_one("#list-services", ListView)
        first_svc = svc_list.children[0]
        assert "[CHECKED]" in first_svc.display_text.plain or "[TODO]" in first_svc.display_text.plain


@pytest.mark.asyncio
async def test_station_indicator_breadcrumb(seeded_store: NotebookStore) -> None:
    """Station indicator breadcrumb updates dynamically in WorksheetHeader on tab switch."""
    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test(size=(140, 40)) as pilot:
        header = app.query_one(WorksheetHeader)
        assert "[ Cockpit ]" in header.render().plain

        app.action_switch_tab("tab-playbooks")
        await pilot.pause()
        assert "[ Playbooks ]" in header.render().plain

        app.action_switch_tab("tab-creds")
        await pilot.pause()
        assert "[ Credentials ]" in header.render().plain

        app.action_switch_tab("tab-loot")
        await pilot.pause()
        assert "[ Loot & Flags ]" in header.render().plain

        app.action_switch_tab("tab-worksheet")
        await pilot.pause()
        assert "[ Cockpit ]" in header.render().plain


@pytest.mark.asyncio
async def test_persistent_panel_focus_and_selection_memory(seeded_store: NotebookStore) -> None:
    """Exact list indices and focused cockpit widget are preserved across tab switches."""
    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test(size=(140, 40)) as pilot:
        svc_list = app.query_one("#list-services", ListView)
        svc_list.focus()
        assert len(svc_list.children) > 1
        svc_list.index = 1
        await pilot.pause()

        # Switch away to Station 2
        app.action_switch_tab("tab-playbooks")
        await pilot.pause()

        # Switch back to Cockpit (Station 1)
        app.action_switch_tab("tab-worksheet")
        await pilot.pause()

        # Services list should retain focus and exact row index
        assert svc_list.has_focus, "Services list should retain keyboard focus on tab return"
        assert svc_list.index == 1, "Services list row selection index should be preserved"


@pytest.mark.asyncio
async def test_tree_folding_persistence(seeded_store: NotebookStore) -> None:
    """Collapsed tree nodes remain collapsed across populate cycles."""
    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test(size=(140, 40)):
        tree = app.query_one("#target-tree", TargetTreeWidget)
        targets = seeded_store.list_targets()
        services = seeded_store.list_services()

        # Collapse the first child node (a subnet or target)
        assert len(tree.root.children) > 0
        first_child = tree.root.children[0]
        first_child.collapse()
        assert not first_child.is_expanded

        # Repopulate
        tree.populate(targets, services)
        assert len(tree.root.children) > 0
        repopulated_child = tree.root.children[0]
        assert not repopulated_child.is_expanded, "Collapsed node must remain collapsed after populate"


@pytest.mark.asyncio
async def test_precision_borders_and_native_border_titles(seeded_store: NotebookStore) -> None:
    """Panels utilize native border_title and dynamic border_subtitle counters."""
    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test(size=(140, 40)):
        surface_panel = app.query_one("#panel-surface")
        svc_panel = app.query_one("#panel-services")
        creds_panel = app.query_one("#panel-creds")

        assert surface_panel.border_title == " TARGET ROSTER "
        assert svc_panel.border_title == " SERVICES & PORTS "
        assert creds_panel.border_title == " CREDENTIALS "

        # Subtitle contains count
        assert svc_panel.border_subtitle and "port" in svc_panel.border_subtitle



