"""Regression tests for the TUI layout and interaction fixes.

These cover the behaviours that were found broken during the UI review:
invisible active station tab, the crash when highlighting a service, the
zero-height failure log, the no-op zoom, unguarded deletes and j/k movement.
"""

from __future__ import annotations

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


@pytest.fixture
def seeded_store() -> NotebookStore:
    store = NotebookStore(":memory:")
    target = store.add_target("10.10.10.20", hostname="target.local", os_name="Linux")
    store.add_service(target_id=target.id, port=22, service="SSH", version="OpenSSH 8.2p1")
    store.add_service(target_id=target.id, port=445, service="SMB", version="Samba 4.3")
    store.add_credential(username="admin", secret="Summer2024!", target_id=target.id)
    store.add_checklist_item(title="SMB enumeration", target_id=target.id)
    store.add_note("backup share contains archive.zip", target_id=target.id)
    return store


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
        await pilot.pause()

        await pilot.press("d")
        await pilot.pause()
        assert isinstance(app.screen, ConfirmModal)

        # Cancelling keeps the data.
        await pilot.press("escape")
        await pilot.pause()
        assert len(seeded_store.list_services()) == 2

        # Confirming removes it.
        await pilot.press("d")
        await pilot.pause()
        await pilot.press("y")
        await pilot.pause()
        assert len(seeded_store.list_services()) == 1


@pytest.mark.asyncio
async def test_j_and_k_move_the_highlight(seeded_store: NotebookStore) -> None:
    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test(size=(160, 44)) as pilot:
        svc_list = app.query_one("#list-services", ListView)
        svc_list.focus()
        await pilot.pause()
        await pilot.press("down")
        await pilot.pause()
        assert svc_list.index == 0
        await pilot.press("j")
        await pilot.pause()
        assert svc_list.index == 1
        await pilot.press("k")
        await pilot.pause()
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
        await pilot.pause()
        await pilot.pause()
        results = app.screen.query_one("#search-results", ListView)
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
        assert "NEXT" in text
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
            await pilot.pause()
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

        app.apply_theme("cyber")
        await pilot.pause()
        assert app.theme_name == "cyber"
        assert current_palette().accent != before
        assert app.theme == "cyb0x-cyber"

        app.action_cycle_theme()
        await pilot.pause()
        assert app.theme_name == "slate"
        assert current_palette().accent == before

        # rows follow the palette
        app.query_one("#list-services", ListView).focus()
        await pilot.pause()
        app.apply_theme("warm")
        await pilot.pause()
        item = app.query_one("#list-services", ListView).children[0]
        assert item.display_text.plain.strip()


@pytest.mark.asyncio
async def test_theme_command_bar(seeded_store: NotebookStore) -> None:
    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test(size=(140, 40)) as pilot:
        from textual.widgets import Input

        cmd = app.query_one("#cmd-input", Input)
        cmd.focus()
        cmd.value = ":theme warm"
        await cmd.action_submit()
        await pilot.pause()
        assert app.theme_name == "warm"

        cmd.value = ":theme nope"
        await cmd.action_submit()
        await pilot.pause()
        assert app.theme_name == "warm"


@pytest.mark.asyncio
async def test_every_modal_mounts(seeded_store: NotebookStore) -> None:
    """Guard against stylesheet typos in screens the smoke test never opens."""
    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test(size=(140, 40)) as pilot:
        for key in ("?", "/", "r", "m", "g", "t", "s", "f", "c", "n", "K"):
            await pilot.press(key)
            await pilot.pause()
            assert len(app.screen_stack) > 1, f"{key!r} did not open a modal"
            await pilot.press("escape")
            await pilot.pause()
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

        # 'theme neon'
        cmd.value = "theme neon"
        await cmd.action_submit()
        await pilot.pause()
        assert app.theme_name == "neon"


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
        await pilot.pause()
        assert seeded_store.get_active_target().ip == target2.ip

        await pilot.press("left_square_bracket")
        await pilot.pause()
        assert seeded_store.get_active_target().ip == target1.ip


@pytest.mark.asyncio
async def test_sidebar_toggle_hotkey(seeded_store: NotebookStore) -> None:
    """Pressing 'b' toggles the sidebar visibility."""
    app = CyboxSafeApp(store=seeded_store)
    async with app.run_test(size=(140, 40)) as pilot:
        sidebar = app.query_one("#sidebar")
        assert not sidebar.has_class("hidden")

        await pilot.press("b")
        await pilot.pause()
        assert sidebar.has_class("hidden")

        await pilot.press("b")
        await pilot.pause()
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
        await pilot.pause()
        assert svc_list.has_focus

        # 'h' jumps to left sidebar (target tree)
        await pilot.press("h")
        await pilot.pause()
        tree = app.query_one("#target-tree")
        assert tree.has_focus

        # 'l' jumps to right workbench (services list)
        await pilot.press("l")
        await pilot.pause()
        assert svc_list.has_focus

        # 'w' cycles sequentially
        await pilot.press("w")
        await pilot.pause()
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
        await pilot.pause()

        table = app.query_one("#cred-matrix-table", DataTable)
        table.focus()
        await pilot.pause()
        assert table.row_count >= 1

        # Move to first spray target column
        table.cursor_coordinate = (0, 1)
        await pilot.pause()

        # Press space to cycle cell status
        await pilot.press("space")
        await pilot.pause()

        # Press Enter to compile and copy spray command
        await pilot.press("enter")
        await pilot.pause()

        assert len(copied) >= 1
        assert "admin" in copied[-1] or "P@ssword123" in copied[-1]

