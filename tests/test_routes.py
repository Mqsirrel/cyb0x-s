"""Tests for Multi-Hop Pivot Route Graph and ProxyChains/Chisel Generator (P3)."""

from pathlib import Path
from click.testing import CliRunner

from cyb0x_s.cli import cli
from cyb0x_s.db.store import NotebookStore
from cyb0x_s.routes import (
    build_network_topology,
    generate_proxychains_config,
    resolve_pivot_route,
)


def test_empty_network_topology(store: NotebookStore) -> None:
    topo = build_network_topology(store)
    assert topo.workspace_name == "default"
    assert len(topo.subnets) == 0
    assert len(topo.pivots) == 0


def test_single_and_multi_hop_routes(store: NotebookStore) -> None:
    # DMZ Target: initial foothold
    t1 = store.add_target("10.10.10.15", hostname="jumpbox-1", os_name="Linux")
    store.update_target_details(
        t1.id,
        is_pivot=True,
        subnet="10.10.10.0/24",
        pivot_route="192.168.1.0/24 via socks5:1080",
    )

    # Directly reachable target on 10.10.10.0/24
    t_direct = store.add_target("10.10.10.20", hostname="web-server", os_name="Linux")
    store.update_target_details(t_direct.id, subnet="10.10.10.0/24")

    # Internal Target behind Hop 1
    t2 = store.add_target("192.168.1.50", hostname="internal-srv", os_name="Windows")
    store.update_target_details(t2.id, subnet="192.168.1.0/24")

    # Route to direct target
    route_dir = resolve_pivot_route(store, "10.10.10.20")
    assert route_dir.is_direct is True
    assert route_dir.hop_count == 0

    # Route to internal target behind pivot 1
    route_hop1 = resolve_pivot_route(store, "192.168.1.50")
    assert route_hop1.is_direct is False
    assert route_hop1.hop_count == 1
    assert route_hop1.hops[0].pivot_ip == "10.10.10.15"
    assert route_hop1.hops[0].proxy_port == 1080
    assert "socks5 127.0.0.1 1080" in route_hop1.proxychains_lines[0]
    assert "ssh -J user@10.10.10.15" in route_hop1.ssh_jump_cmd


def test_two_hop_pivot_chain(store: NotebookStore) -> None:
    # Pivot 1
    t1 = store.add_target("10.10.10.5", hostname="gw1", os_name="Linux")
    store.update_target_details(t1.id, is_pivot=True, subnet="10.10.10.0/24", pivot_route="192.168.1.0/24 via socks5:1080")

    # Pivot 2
    t2 = store.add_target("192.168.1.10", hostname="gw2", os_name="Linux")
    store.update_target_details(t2.id, is_pivot=True, subnet="192.168.1.0/24", pivot_route="172.16.50.0/24 via socks5:1081")

    # Deep target
    t3 = store.add_target("172.16.50.99", hostname="vault", os_name="Linux")
    store.update_target_details(t3.id, subnet="172.16.50.0/24")

    route = resolve_pivot_route(store, "172.16.50.99")
    assert route.hop_count == 2
    assert route.hops[0].proxy_port == 1080
    assert route.hops[1].proxy_port == 1081
    assert "ssh -J user@10.10.10.5,user@192.168.1.10" in route.ssh_jump_cmd

    # Topology and Proxychains
    topo = build_network_topology(store)
    assert len(topo.pivots) == 2
    assert "172.16.50.0/24" in topo.subnets
    assert "graph LR" in topo.mermaid_diagram

    conf = generate_proxychains_config(topo)
    assert "socks5 127.0.0.1 1080" in conf
    assert "socks5 127.0.0.1 1081" in conf


def test_cli_route_command(cli_runner: CliRunner, temp_db_path: Path) -> None:
    # Add targets and pivot
    cli_runner.invoke(cli, ["--db", str(temp_db_path), "target", "10.10.10.10", "--os", "Linux"])
    cli_runner.invoke(cli, ["--db", str(temp_db_path), "target", "192.168.20.5", "--os", "Windows"])

    # Check topology overview
    res_topo = cli_runner.invoke(cli, ["--db", str(temp_db_path), "route"])
    assert res_topo.exit_code == 0
    assert "Network Topology Map" in res_topo.output

    # Check proxychains config output
    res_pc = cli_runner.invoke(cli, ["--db", str(temp_db_path), "route", "--proxychains"])
    assert res_pc.exit_code == 0
    assert "[ProxyList]" in res_pc.output

    # Check destination routing
    res_dest = cli_runner.invoke(cli, ["--db", str(temp_db_path), "route", "192.168.20.5"])
    assert res_dest.exit_code == 0
    assert "Pivot Route to Destination" in res_dest.output
