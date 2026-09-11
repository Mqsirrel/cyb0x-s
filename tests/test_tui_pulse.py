"""Headless tests for the Pulse and Network stations.

The filename prefix ``test_tui_`` ensures these only run in the TUI test lane
(see pyproject markers), where textual's headless runner is available.
"""

from __future__ import annotations

import pytest
from rich.text import Text
from textual.widgets import ListView, TabbedContent

from glacis.db.store import NotebookStore
from glacis.settings import set_derive_guidance
from glacis.tui.app import GlacisApp
from glacis.tui.stations.network import NetworkStation
from glacis.tui.stations.pulse import PulseStation
from glacis.tui.widgets.lists import DataListItem, sync_data_list


@pytest.fixture(autouse=True)
def _state_guidance_off():
    set_derive_guidance(False)
    yield
    set_derive_guidance(False)


@pytest.mark.asyncio
async def test_stations_mount(seeded_store: NotebookStore) -> None:
    app = GlacisApp(store=seeded_store)
    async with app.run_test(size=(160, 44)) as pilot:
        pulse = app.query_one(PulseStation)
        network = app.query_one(NetworkStation)
        assert pulse.id == "pulse-station"
        assert network.id == "network-station"
        await pilot.pause()


@pytest.mark.asyncio
async def test_digit_keys_open_new_stations(seeded_store: NotebookStore) -> None:
    app = GlacisApp(store=seeded_store)
    async with app.run_test(size=(160, 44)) as pilot:
        await pilot.press("0")
        await pilot.pause()
        tabs = app.query_one(TabbedContent)
        assert tabs.active == "tab-pulse"
        await pilot.press("5")
        await pilot.pause()
        assert tabs.active == "tab-network"
        await pilot.press("1")
        await pilot.pause()
        assert tabs.active == "tab-worksheet"


@pytest.mark.asyncio
async def test_pulse_populates_hosts_and_advisories(seeded_store: NotebookStore) -> None:
    app = GlacisApp(store=seeded_store)
    async with app.run_test(size=(160, 44)) as pilot:
        await pilot.press("0")
        await pilot.pause(0.05)
        pulse = app.query_one(PulseStation)
        hosts = pulse.query_one("#pulse-hosts", ListView)
        advisories = pulse.query_one("#pulse-advisories", ListView)
        assert len(hosts.children) == 1
        row_text = hosts.children[0].data_obj.ip if hasattr(hosts.children[0], "data_obj") else ""
        assert row_text == "10.10.10.20"
        # Seeded checklist has an open item -> S3 advisory must be visible.
        rule_ids = [ch.data_obj.rule_id for ch in advisories.children if
                    isinstance(ch, DataListItem) and ch.data_obj is not None]
        assert "S3-checklist-next" in rule_ids
        # Default mode is STATE-only; directional D rules hidden.
        assert not any(r.startswith("D") for r in rule_ids)
        mode_text = pulse.query_one("#pulse-mode").render().plain
        assert "STATE" in mode_text


@pytest.mark.asyncio
async def test_pulse_g_toggles_direction(seeded_store: NotebookStore) -> None:
    app = GlacisApp(store=seeded_store)
    async with app.run_test(size=(160, 44)) as pilot:
        await pilot.press("0")
        await pilot.pause(0.05)
        pulse = app.query_one(PulseStation)
        advisories = pulse.query_one("#pulse-advisories", ListView)
        before = [ch.data_obj.rule_id for ch in advisories.children
                  if isinstance(ch, DataListItem) and ch.data_obj is not None]
        assert not any(r.startswith("D") for r in before)

        await pilot.press("G")
        await pilot.pause(0.05)
        after = [ch.data_obj.rule_id for ch in advisories.children
                 if isinstance(ch, DataListItem) and ch.data_obj is not None]
        assert "D1-cred-reuse" in after  # seeded admin cred vs SSH/SMB surfaces


@pytest.mark.asyncio
async def test_pulse_host_enter_focuses_target(seeded_store: NotebookStore) -> None:
    second = seeded_store.add_target("10.10.10.21")
    seeded_store.add_note("other host", target_id=second.id)
    app = GlacisApp(store=seeded_store)
    async with app.run_test(size=(160, 44)) as pilot:
        await pilot.press("0")
        await pilot.pause(0.05)
        pulse = app.query_one(PulseStation)
        hosts = pulse.query_one("#pulse-hosts", ListView)
        # Hosts sort untouched-first; locate the freshly added host by IP.
        idx = next(
            i for i, ch in enumerate(hosts.children)
            if isinstance(ch, DataListItem)
            and ch.data_obj is not None and ch.data_obj.ip == "10.10.10.21"
        )
        hosts.focus()
        hosts.index = idx
        await pilot.press("enter")
        await pilot.pause()
        tabs = app.query_one(TabbedContent)
        assert tabs.active == "tab-worksheet"
        assert app.get_current_target().ip == "10.10.10.21"


@pytest.mark.asyncio
async def test_pulse_advisory_enter_routes_to_station(seeded_store: NotebookStore) -> None:
    app = GlacisApp(store=seeded_store)
    async with app.run_test(size=(160, 44)) as pilot:
        await pilot.press("0")
        await pilot.pause(0.05)
        pulse = app.query_one(PulseStation)
        advisories = pulse.query_one("#pulse-advisories", ListView)
        advisories.focus()
        # First advisory in the seeded feed is a state rule routed to the worksheet.
        advisories.index = 0
        await pilot.press("enter")
        await pilot.pause()
        tabs = app.query_one(TabbedContent)
        assert tabs.active == "tab-worksheet"


@pytest.mark.asyncio
async def test_network_renders_single_segment_actions(
    seeded_store: NotebookStore, monkeypatch
) -> None:
    copied: list[str] = []
    monkeypatch.setattr("glacis.tui.widgets.copy_to_clipboard", lambda text: copied.append(text))
    app = GlacisApp(store=seeded_store)
    async with app.run_test(size=(160, 44)) as pilot:
        await pilot.press("5")
        await pilot.pause(0.05)
        network = app.query_one(NetworkStation)
        map_text = network.query_one("#network-map").render().plain
        assert "10.10.10.20" in map_text
        actions = network.query_one("#network-actions", ListView)
        assert len(actions.children) >= 1
        # Single segment -> proxychains regeneration action present and copies.
        labels = [ch.data_obj.label for ch in actions.children if
                  isinstance(ch, DataListItem) and ch.data_obj is not None]
        assert any("proxychains" in label.lower() for label in labels)
        actions.focus()
        actions.index = 0
        await pilot.press("enter")
        await pilot.pause()
        assert copied and ("socks" in copied[-1] or "chain" in copied[-1].lower())


@pytest.mark.asyncio
async def test_network_pivot_commands_render_and_copy(
    seeded_store: NotebookStore, monkeypatch
) -> None:
    copied: list[str] = []
    monkeypatch.setattr("glacis.tui.widgets.copy_to_clipboard", lambda text: copied.append(text))
    pivot_t = seeded_store.list_targets()[0]
    seeded_store.update_target_details(
        pivot_t.id, is_pivot=True,
        pivot_route="192.168.50.0/24 via socks5:1080",
    )
    seeded_store.add_target("192.168.50.10")
    app = GlacisApp(store=seeded_store)
    async with app.run_test(size=(160, 44)) as pilot:
        await pilot.press("5")
        await pilot.pause(0.05)
        network = app.query_one(NetworkStation)
        map_text = network.query_one("#network-map").render().plain
        assert "192.168.50" in map_text
        actions = network.query_one("#network-actions", ListView)
        action_specs = [ch.data_obj for ch in actions.children
                        if isinstance(ch, DataListItem) and ch.data_obj is not None]
        labels = " ".join(a.label.lower() for a in action_specs)
        assert "proxychains" in labels
        # A pivot-routed action must carry the destination address in its command.
        routed = [i for i, a in enumerate(action_specs) if "192.168.50" in a.cmd]
        assert routed, labels
        actions.focus()
        actions.index = routed[0]
        await pilot.press("enter")
        await pilot.pause()
        assert copied and "192.168.50" in copied[-1]


@pytest.mark.asyncio
async def test_snap_command_survives_memory_store(seeded_store: NotebookStore) -> None:
    from glacis.tui.commands import execute_command

    app = GlacisApp(store=seeded_store)
    async with app.run_test(size=(160, 44)) as pilot:
        execute_command(app, ":snap sanity check")
        await pilot.pause()
        # No crash; app still interactive.
        assert app.is_running


@pytest.mark.asyncio
async def test_differential_sync_preserves_selection(seeded_store: NotebookStore) -> None:
    app = GlacisApp(store=seeded_store)
    async with app.run_test(size=(160, 44)) as pilot:
        await pilot.pause(0.05)
        svc_list = app.query_one("#list-services", ListView)
        svc_list.index = 1
        # Adding a new row must not reset the operator's highlight.
        seeded_store.add_service(seeded_store.list_targets()[0].id, port=8080, service="http-alt")
        app.refresh_all()
        await pilot.pause()
        assert svc_list.index == 1
        # Re-rendering unchanged lists must not disturb the cursor either.
        app.refresh_all()
        await pilot.pause()
        assert svc_list.index == 1


@pytest.mark.asyncio
async def test_sync_data_list_switches_datasets_restores_key() -> None:
    from textual.app import App, ComposeResult

    class _Host(App):
        def compose(self) -> ComposeResult:
            yield ListView()

    async with _Host().run_test() as pilot:
        lv = pilot.app.query_one(ListView)

        class Obj:
            def __init__(self, id_: int) -> None:
                self.id = id_

        def render(o: Obj) -> Text:
            return Text(f"row {o.id}")

        def key(o: Obj) -> tuple:
            return ("Obj", o.id)

        a, b, c = Obj(1), Obj(2), Obj(3)
        sync_data_list(lv, [a, b, c], render, key_fn=key)
        await pilot.pause()
        lv.index = 2
        # Full reorder rebuild must restore selection by key.
        sync_data_list(lv, [c, b, a], render, key_fn=key)
        await pilot.pause()
        assert lv.children[lv.index].data_obj.id == 3
        assert lv.index == 0
        # New trailing row takes the pure-append path; cursor key is preserved.
        sync_data_list(lv, [c, b, a, Obj(4)], render, key_fn=key)
        await pilot.pause()
        assert lv.children[lv.index].data_obj.id == 3
        # Selected row vanished: highlight settles on the row that shifted
        # into its old slot rather than jumping the cursor around.
        sync_data_list(lv, [b, a], render, key_fn=key)
        await pilot.pause()
        assert lv.index == 0
        assert lv.children[0].data_obj.id == 2
        # Placeholder for an empty dataset never carries a selection.
        sync_data_list(lv, [], render, placeholder_text=Text("empty"))
        await pilot.pause()
        assert all(not getattr(ch, "data_obj", None) for ch in lv.children)
