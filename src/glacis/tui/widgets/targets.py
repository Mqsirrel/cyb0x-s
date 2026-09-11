"""Target roster / attack-surface tree (Cockpit sidebar)."""

from __future__ import annotations

from typing import Any, List, Optional

from textual.widgets import Tree

from glacis.models import Service, Target
from glacis.tui.theme import current_palette


class TargetTreeWidget(Tree):
    """Sidebar Tree displaying targets and their listening services."""

    # The tree lives inside a bordered panel now, so it must not draw its
    # own frame — otherwise every sidebar panel gets a double border.
    DEFAULT_CSS = """
    TargetTreeWidget {
        background: transparent;
        padding: 0;
        height: 1fr;
        color: $foreground;
        overflow-x: hidden;
        scrollbar-size-horizontal: 0;
    }
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__("Target Roster", **kwargs)
        self.show_root = False

    def populate(
        self,
        targets: List[Target],
        services: List[Service],
        selected_target_id: Optional[int] = None,
    ) -> None:
        # Preserve user's collapsed node state across refreshes
        collapsed_keys: set[tuple[str, Any]] = set()

        def _collect_collapsed(node: Any) -> None:
            for child in getattr(node, "children", []):
                if getattr(child, "data", None) and isinstance(child.data, dict):
                    ntype = child.data.get("type")
                    nkey = child.data.get("subnet") if ntype == "subnet" else child.data.get("id")
                    if ntype and nkey is not None and not child.is_expanded:
                        collapsed_keys.add((ntype, nkey))
                _collect_collapsed(child)

        try:
            _collect_collapsed(self.root)
        except Exception:
            pass

        self.clear()
        root = self.root

        svc_map: dict[int, list[Service]] = {}
        for s in services:
            svc_map.setdefault(s.target_id, []).append(s)

        P = current_palette()

        def _get_subnet(t: Target) -> str:
            if t.subnet:
                return t.subnet
            octets = t.ip.split(".")
            if len(octets) == 4 and all(o.isdigit() for o in octets):
                return f"{octets[0]}.{octets[1]}.{octets[2]}.0/24"
            return "General / External"

        subnets_set = {_get_subnet(t) for t in targets}
        use_subnet_groups = len(subnets_set) > 1 or any(t.is_pivot or t.subnet for t in targets)

        def _add_target_to_node(parent_node: Any, target: Target) -> None:
            target_svcs = svc_map.get(target.id or 0, [])
            icon = "★" if target.root_flag else ("◆" if target.initial_access_vuln or target.user_flag else "●")
            icon_style = f"bold {P.accent}" if target.root_flag else (f"bold {P.warn}" if target.user_flag else f"bold {P.ok}")
            safe_ip = target.ip
            host = target.hostname or ""
            if len(host) > 10:
                host = host[:9] + "…"
            safe_host = f" [{P.text_soft}]({host})[/]" if host else ""
            pivot_badge = f" [bold {P.bg} on {P.warn}][⇄ PIVOT][/]" if target.is_pivot else ""
            label = f"[{icon_style}]{icon}[/] [bold {P.text}]{safe_ip}[/]{safe_host}{pivot_badge} [{P.muted}][{len(target_svcs)}][/]"
            if not target.is_in_scope:
                label = f"[{P.muted} strike]{label} ⃠[/]"

            target_node = parent_node.add(
                label,
                data={
                    "type": "target",
                    "id": target.id,
                    "target": target,
                    "is_pivot": target.is_pivot,
                    "pivot_route": target.pivot_route,
                },
            )

            for svc in target_svcs:
                svc_icon = "✓" if svc.status.value == "CHECKED" else ("✖" if svc.status.value == "DEAD-END" else "●")
                icon_col = P.ok if svc.status.value == "CHECKED" else (P.danger if svc.status.value == "DEAD-END" else P.accent)
                pot_badge = (
                    f" [bold {P.bg} on {P.danger}][{svc.access_potential}][/]"
                    if svc.access_potential in ("HIGH", "CRITICAL")
                    else ""
                )
                port_text = f"[{svc.port}/{svc.protocol}]"
                svc_label = (
                    f"[{icon_col}]{svc_icon}[/] [{P.accent}]{port_text:<11}[/]"
                    f" [bold {P.text}]{svc.service}[/]{pot_badge}"
                )
                target_node.add_leaf(
                    svc_label,
                    data={"type": "service", "id": svc.id, "target_id": target.id, "service": svc, "target": target},
                )

            if ("target", target.id) in collapsed_keys:
                target_node.collapse()
            else:
                target_node.expand()

        if use_subnet_groups:
            subnet_map: dict[str, list[Target]] = {}
            for t in targets:
                subnet_map.setdefault(_get_subnet(t), []).append(t)

            for snet, t_list in subnet_map.items():
                has_pivot = any(t.is_pivot for t in t_list)
                pivot_lbl = f" [bold {P.warn}]⇄ [PIVOT SEGMENT][/]" if has_pivot else ""
                snet_label = f"[bold {P.accent}]{snet}[/]{pivot_lbl} [{P.muted}]({len(t_list)} host{'s' if len(t_list) != 1 else ''})[/]"
                snet_node = root.add(
                    snet_label,
                    data={"type": "subnet", "subnet": snet, "has_pivot": has_pivot},
                )
                for t in t_list:
                    _add_target_to_node(snet_node, t)
                if ("subnet", snet) in collapsed_keys:
                    snet_node.collapse()
                else:
                    snet_node.expand()
        else:
            for target in targets:
                _add_target_to_node(root, target)


