"""Passive Multi-Hop Pivot Route Graph and Network Topology Engine for CYB0X-S.

Models operator-documented network segments, dual-homed jumpboxes,
and multi-hop routing paths. Generates ProxyChains, Chisel, and SSH configs.

100% passive: purely documents and calculates routes based on operator observations.
No automated network probing, no prescriptive attack planning.
"""

from __future__ import annotations

import ipaddress
import re
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from cyb0x_s.db.store import NotebookStore
from cyb0x_s.models import Target


class RouteHop(BaseModel):
    """An individual hop in a multi-hop pivot chain."""
    hop_num: int
    pivot_ip: str
    pivot_hostname: str = ""
    proxy_type: str = "socks5"
    proxy_host: str = "127.0.0.1"
    proxy_port: int = 1080
    dest_subnet: str = ""
    notes: str = ""


class PivotRoute(BaseModel):
    """A verified multi-hop route to a destination target or subnet."""
    destination: str
    destination_subnet: str = ""
    hops: List[RouteHop] = Field(default_factory=list)
    hop_count: int = 0
    is_direct: bool = True
    proxychains_lines: List[str] = Field(default_factory=list)
    ssh_jump_cmd: str = ""
    chisel_server_cmd: str = ""
    chisel_client_cmd: str = ""
    ascii_diagram: str = ""


class NetworkTopology(BaseModel):
    """Documented network topology across all targets and subnets in a workspace."""
    workspace_name: str
    subnets: Dict[str, List[str]] = Field(default_factory=dict)   # subnet -> [target_ips]
    pivots: List[Dict[str, Any]] = Field(default_factory=list)      # [{ip, subnet, route}]
    routes_by_target: Dict[str, PivotRoute] = Field(default_factory=dict)
    mermaid_diagram: str = ""
    ascii_map: str = ""


def _extract_proxy_port(route_str: str, default_port: int = 1080) -> int:
    """Parse port number from pivot route strings like 'socks5:1080' or 'chisel 8000:1080'."""
    match = re.search(r":(\d{2,5})", route_str)
    if match:
        return int(match.group(1))
    match_num = re.search(r"\b(\d{4,5})\b", route_str)
    if match_num:
        return int(match_num.group(1))
    return default_port


def _infer_subnet(ip: str) -> str:
    """Derive standard /24 IPv4 CIDR from target IP if no subnet explicitly logged."""
    try:
        addr = ipaddress.IPv4Address(ip.strip())
        network = ipaddress.IPv4Network(f"{addr}/24", strict=False)
        return str(network)
    except Exception:
        return "Unknown"


def build_network_topology(store: NotebookStore, workspace_id: Optional[int] = None) -> NetworkTopology:
    """Analyze all operator-recorded targets, subnets, and pivot routes to construct topology."""
    ws = store.get_workspace(workspace_id) if workspace_id else store.get_active_workspace()
    ws_id = ws.id if ws and ws.id else 1
    ws_name = ws.name if ws else "default"

    targets = store.list_targets(workspace_id=ws_id)
    subnets: Dict[str, List[str]] = {}
    pivots: List[Dict[str, Any]] = []

    for t in targets:
        snet = t.subnet.strip() if t.subnet and t.subnet.strip() else _infer_subnet(t.ip)
        if snet not in subnets:
            subnets[snet] = []
        subnets[snet].append(t.ip)

        if t.is_pivot:
            pivots.append({
                "id": t.id,
                "ip": t.ip,
                "hostname": t.hostname,
                "subnet": snet,
                "pivot_route": t.pivot_route,
                "port": _extract_proxy_port(t.pivot_route, 1080 + len(pivots)),
            })

    # Build route per target
    routes: Dict[str, PivotRoute] = {}
    for t in targets:
        routes[t.ip] = resolve_pivot_route(store, t.ip, workspace_id=ws_id)

    # Generate Mermaid diagram
    mermaid_lines = [
        "graph LR",
        "    classDef attacker fill:#1e293b,stroke:#38bdf8,stroke-width:2px,color:#fff;",
        "    classDef pivot fill:#78350f,stroke:#f59e0b,stroke-width:2px,color:#fff;",
        "    classDef host fill:#0f172a,stroke:#64748b,stroke-width:1px,color:#cbd5e1;",
        "    Attacker[Operator / Attacker Host]:::attacker",
    ]

    # Render Subnets and Hosts
    for snet, ip_list in subnets.items():
        snet_slug = snet.replace(".", "_").replace("/", "_")
        mermaid_lines.append(f"    subgraph Subnet_{snet_slug}[\"Subnet: {snet}\"]")
        for ip in ip_list:
            node_id = f"Host_{ip.replace('.', '_')}"
            target_obj = next((t for t in targets if t.ip == ip), None)
            is_p = target_obj.is_pivot if target_obj else False
            label = f"{ip}" + (f" ({target_obj.hostname})" if target_obj and target_obj.hostname else "")
            if is_p:
                mermaid_lines.append(f"        {node_id}[\"{label} ⇄ PIVOT\"]:::pivot")
            else:
                mermaid_lines.append(f"        {node_id}[\"{label}\"]:::host")
        mermaid_lines.append("    end")

    # Connect Attacker to primary subnet or pivots
    if pivots:
        for p in pivots:
            p_node = f"Host_{p['ip'].replace('.', '_')}"
            mermaid_lines.append(f"    Attacker -->|Entry / Initial Access| {p_node}")
            if p["pivot_route"]:
                mermaid_lines.append(f"    {p_node} -.->|Tunnel: {p['pivot_route']}| Subnet_{p['subnet'].replace('.', '_').replace('/', '_')}")
    else:
        mermaid_lines.append("    Attacker -->|Direct Network Access| Subnet_" + list(subnets.keys())[0].replace(".", "_").replace("/", "_") if subnets else "")

    # Generate ASCII Map
    ascii_lines = [
        f"=== NETWORK TOPOLOGY: {ws_name.upper()} ===",
        f"Total Targets: {len(targets)} | Subnets: {len(subnets)} | Documented Pivots: {len(pivots)}",
        "",
    ]
    for snet, ips in subnets.items():
        ascii_lines.append(f"  ┌─ Subnet: {snet}")
        for ip in ips:
            target_obj = next((t for t in targets if t.ip == ip), None)
            is_p = target_obj.is_pivot if target_obj else False
            p_mark = " [⇄ DUAL-HOMED PIVOT]" if is_p else ""
            h_mark = f" ({target_obj.hostname})" if target_obj and target_obj.hostname else ""
            ascii_lines.append(f"  │   • {ip}{h_mark}{p_mark}")
        ascii_lines.append("  └───────────────────────────────")

    return NetworkTopology(
        workspace_name=ws_name,
        subnets=subnets,
        pivots=pivots,
        routes_by_target=routes,
        mermaid_diagram="\n".join(mermaid_lines),
        ascii_map="\n".join(ascii_lines),
    )


def resolve_pivot_route(
    store: NotebookStore,
    target_ip_or_subnet: str,
    workspace_id: Optional[int] = None,
) -> PivotRoute:
    """Calculate multi-hop pivot routing chain to reach a given target IP or subnet."""
    ws = store.get_workspace(workspace_id) if workspace_id else store.get_active_workspace()
    ws_id = ws.id if ws and ws.id else 1

    target = store.get_target_by_ip(target_ip_or_subnet, workspace_id=ws_id)
    target_subnet = target.subnet.strip() if target and target.subnet else _infer_subnet(target_ip_or_subnet)

    pivots = [t for t in store.list_targets(workspace_id=ws_id) if t.is_pivot]

    # Check if target is itself on initial entry subnet or directly reachable
    is_pivot_host = target.is_pivot if target else False
    hops: List[RouteHop] = []

    # If target is on a different subnet than entry and pivots exist:
    # A pivot is an upstream gateway if its pivot_route references this target's subnet,
    # or if target is in a segmented subnet.
    matched_pivots: List[Target] = []
    for p in pivots:
        if p.ip == target_ip_or_subnet:
            continue
        # If target is on the same subnet as this pivot's local interface, no pivot hop needed through p
        if p.subnet and target_subnet and p.subnet == target_subnet:
            continue
        # Check if pivot explicitly routes to target subnet or bridges between subnets
        if target_subnet in p.pivot_route or (p.pivot_route and p.subnet != target_subnet):
            matched_pivots.append(p)

    if not matched_pivots:
        # Direct connection / zero hops
        ascii_diag = f"[Attacker / Kali] ──────── Direct ────────> [{target_ip_or_subnet}]"
        return PivotRoute(
            destination=target_ip_or_subnet,
            destination_subnet=target_subnet,
            hops=[],
            hop_count=0,
            is_direct=True,
            proxychains_lines=[],
            ssh_jump_cmd="",
            chisel_server_cmd="",
            chisel_client_cmd="",
            ascii_diagram=ascii_diag,
        )

    # Build hops from matched pivots
    proxychains_lines: List[str] = []
    chisel_clients: List[str] = []
    diagram_parts = ["[Attacker / Kali]"]

    for idx, p in enumerate(matched_pivots, start=1):
        port = _extract_proxy_port(p.pivot_route, 1080 + (idx - 1))
        hop = RouteHop(
            hop_num=idx,
            pivot_ip=p.ip,
            pivot_hostname=p.hostname,
            proxy_type="socks5",
            proxy_host="127.0.0.1",
            proxy_port=port,
            dest_subnet=p.subnet or target_subnet,
            notes=p.pivot_route or f"Pivot Gateway {p.ip}",
        )
        hops.append(hop)
        proxychains_lines.append(f"socks5 127.0.0.1 {port}")
        chisel_clients.append(f"chisel client 10.10.14.x:8000 R:{port}:socks")
        diagram_parts.append(f"──(SOCKS5 127.0.0.1:{port})──> [Hop {idx}: {p.ip}]")

    diagram_parts.append(f"────> [{target_ip_or_subnet} in {target_subnet}]")
    ascii_diag = " ".join(diagram_parts)

    # SSH Jump Command
    jump_hosts = ",".join(f"user@{p.ip}" for p in matched_pivots)
    ssh_jump_cmd = f"ssh -J {jump_hosts} user@{target_ip_or_subnet}" if matched_pivots else f"ssh user@{target_ip_or_subnet}"

    # Chisel Commands
    server_cmd = "chisel server -p 8000 --reverse"
    client_cmd = chisel_clients[0] if chisel_clients else ""

    return PivotRoute(
        destination=target_ip_or_subnet,
        destination_subnet=target_subnet,
        hops=hops,
        hop_count=len(hops),
        is_direct=False,
        proxychains_lines=proxychains_lines,
        ssh_jump_cmd=ssh_jump_cmd,
        chisel_server_cmd=server_cmd,
        chisel_client_cmd=client_cmd,
        ascii_diagram=ascii_diag,
    )


def generate_proxychains_config(topology: NetworkTopology) -> str:
    """Generate a clean, copy-pasteable proxychains4.conf configuration block."""
    lines = [
        "# =============================================================================",
        f"# CYB0X-S Generated Proxychains Configuration ({topology.workspace_name})",
        "# Multi-Hop Dynamic Proxy Chain for Documented Pivots",
        "# =============================================================================",
        "",
        "strict_chain",
        "proxy_dns",
        "tcp_read_time_out 15000",
        "tcp_connect_time_out 8000",
        "",
        "[ProxyList]",
    ]

    if not topology.pivots:
        lines.append("# No active pivots documented in this workspace.")
        lines.append("# Add a pivot using: :pivot <route> (e.g. :pivot socks5:1080)")
        lines.append("socks5 127.0.0.1 1080")
    else:
        for p in topology.pivots:
            port = p.get("port", 1080)
            ip = p.get("ip", "unknown")
            lines.append(f"# Pivot Hop via {ip} ({p.get('hostname') or 'gateway'})")
            lines.append(f"socks5 127.0.0.1 {port}")

    return "\n".join(lines)
