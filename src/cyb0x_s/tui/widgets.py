"""Textual widgets and modal dialogs for CYB0X-S Worksheet."""

from __future__ import annotations

from typing import Any, Callable, List, Optional, Set
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, ListItem, ListView, Select, Static, Tree

from cyb0x_s.clipboard import copy_to_clipboard, extract_copy_value
from cyb0x_s.models import (
    ChecklistItem,
    ChecklistStatus,
    Credential,
    Evidence,
    Finding,
    Lead,
    Note,
    Service,
    Target,
)
from cyb0x_s.search import SearchMatch, search_notebook
from cyb0x_s.templates import get_template_guidance_for_title
from cyb0x_s.tui.theme import (
    BACKGROUND,
    CREAM,
    DANGER,
    INFO,
    MUTED,
    NOTE,
    OK,
    SURFACE,
    SURFACE_RAISED,
    TERRACOTTA,
    WARN,
)


def substitute_command_placeholders(command: str, target_ip: str = "") -> str:
    """Fill the static command templates with the active target context.

    Purely mechanical string substitution on human-curated reference text:
    no command is ever generated, inferred or suggested.
    """
    if not command or not target_ip:
        return command
    subnet = f"{target_ip.rsplit('.', 1)[0]}.0/24" if "." in target_ip else ""
    return command.replace("<TARGET_IP>", target_ip).replace("<TARGET_SUBNET>", subnet)


class TargetTreeWidget(Tree):
    """Sidebar Tree displaying targets and their listening services."""

    DEFAULT_CSS = f"""
    TargetTreeWidget {{
        background: {SURFACE};
        padding: 0 1;
        height: 1fr;
        border: round {SURFACE_RAISED};
        color: {CREAM};
    }}
    TargetTreeWidget:focus {{
        border: round {TERRACOTTA};
    }}
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__("Targets & Attack Surface", **kwargs)
        self.show_root = False

    def populate(
        self,
        targets: List[Target],
        services: List[Service],
        selected_target_id: Optional[int] = None,
    ) -> None:
        self.clear()
        root = self.root

        svc_map: dict[int, list[Service]] = {}
        for s in services:
            svc_map.setdefault(s.target_id, []).append(s)

        for target in targets:
            target_svcs = svc_map.get(target.id or 0, [])
            icon = "✔" if target.root_flag else ("★" if target.initial_access_vuln or target.user_flag else "○")
            safe_ip = target.ip
            # Sidebar is narrow: keep hostnames short so IPs never scroll away.
            host = target.hostname or ""
            if len(host) > 12:
                host = host[:11] + "…"
            safe_host = f" ({host})" if host else ""
            label = f"{icon} [bold]{safe_ip}[/bold]{safe_host} [#A8A099]({len(target_svcs)})[/]"
            if not target.is_in_scope:
                label = f"[#A8A099 strike]{label} ⃠[/]"

            target_node = root.add(label, data={"type": "target", "id": target.id, "target": target})

            for svc in target_svcs:
                svc_icon = "✓" if svc.status.value == "CHECKED" else ("✗" if svc.status.value == "DEAD-END" else "→")
                pot_badge = f" [bold #E5846B][{svc.access_potential}][/bold #E5846B]" if svc.access_potential in ("HIGH", "CRITICAL") else ""
                svc_label = f"  {svc_icon} [bold #D4A27F]{svc.port}/{svc.protocol}[/bold #D4A27F] [bold #EDE6DA]{svc.service}[/bold #EDE6DA]{pot_badge}"
                if svc.version:
                    svc_label += f" [#A8A099]{svc.version[:20]}[/]"
                target_node.add_leaf(
                    svc_label,
                    data={"type": "service", "id": svc.id, "target_id": target.id, "service": svc, "target": target},
                )

            target_node.expand()


class WorksheetHeader(Static):
    """High-density header: identity on the left, live counters on the right."""

    DEFAULT_CSS = f"""
    WorksheetHeader {{
        height: 2;
        background: {BACKGROUND};
        color: {CREAM};
        border-bottom: solid {TERRACOTTA} 30%;
        padding: 0 2;
    }}
    """

    def __init__(self, workspace_name: str = "default", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.workspace_name = workspace_name
        self.counts: dict[str, int] = {}
        self.active_ip: str = ""

    def update_status(
        self,
        workspace_name: str = "",
        counts: Optional[dict[str, int]] = None,
        active_ip: str = "",
    ) -> None:
        """Refresh the header meta information (workspace, counters, target)."""
        if workspace_name:
            self.workspace_name = workspace_name
        if counts is not None:
            self.counts = counts
        self.active_ip = active_ip
        self.refresh()

    def render(self) -> Text:
        t = Text()
        t.append("CYB0X-S ", style=f"bold {TERRACOTTA}")
        t.append("WORKSHEET", style=f"bold {CREAM}")
        t.append("  │  ", style=NOTE)
        t.append(self.workspace_name, style=f"bold {INFO}")

        if not (self.counts or self.active_ip):
            return t

        counter_text = "  ".join(f"{k} {v}" for k, v in self.counts.items())
        # Degrade gracefully on narrow terminals: counters first, then just
        # the active target, then nothing at all.
        candidates = [
            f"▸ {self.active_ip}   {counter_text}".rstrip() if self.active_ip else counter_text,
            f"▸ {self.active_ip}" if self.active_ip else "",
        ]
        width = max(self.size.width - 2, 1)
        for meta in candidates:
            if not meta:
                break
            padding = width - len(t.plain) - len(meta)
            if padding > 1:
                t.append(" " * padding)
                t.append(meta, style=NOTE)
                break
        return t


class TargetInfoPanel(Static):
    """Displays compact, clean status for the currently active target."""

    DEFAULT_CSS = f"""
    TargetInfoPanel {{
        height: 2;
        border-bottom: solid {SURFACE_RAISED};
        padding: 0 2;
        background: {SURFACE};
        color: {CREAM};
    }}
    """

    target: Optional[Target] = None

    def update_target(self, target: Optional[Target]) -> None:
        self.target = target
        self.refresh()

    @staticmethod
    def _elide(value: str, width: int) -> str:
        if width <= 1:
            return ""
        if len(value) <= width:
            return value
        return value[: max(width - 1, 1)] + "…"

    def render(self) -> Text:
        t = Text()
        if not self.target:
            t.append("○ ", style="dim yellow")
            t.append("TARGET: ", style=f"bold {WARN}")
            t.append("No active target selected", style=f"bold {WARN}")
            t.append("  (Press 't' to add target or type ':t <ip>')", style=NOTE)
            return t

        t.append("● ", style=f"bold {OK}")
        scope_style = OK if self.target.is_in_scope else DANGER
        scope_txt = "[IN-SCOPE] " if self.target.is_in_scope else "[OUT-OF-SCOPE] "
        t.append(scope_txt, style=scope_style)
        t.append("TARGET: ", style=f"bold {WARN}")
        t.append(self.target.ip, style=f"bold {CREAM}")
        if self.target.hostname:
            t.append(f" ({self.target.hostname})", style=f"bold {INFO}")
        if self.target.os and self.target.os != "Unknown":
            t.append(f" [{self.target.os}]", style=NOTE)

        # Flags are elided to whatever room is left so the row never overflows.
        remaining = max(self.size.width - 2 - len(t.plain) - 2, 0)
        t.append("  │  ", style=NOTE)
        remaining -= 5
        for label, flag, style in (
            ("🏁 User: ", self.target.user_flag, OK),
            ("👑 Root: ", self.target.root_flag, WARN),
        ):
            if remaining <= 0:
                break
            t.append(label, style=style)
            if flag:
                room = max(remaining - len(label) - 1, 4)
                t.append(self._elide(flag, room), style=f"bold {CREAM}")
                remaining -= len(label) + len(self._elide(flag, room)) + 1
            else:
                t.append("[ ] ", style=NOTE)
                remaining -= len(label) + 4

        if self.target.initial_access_vuln and remaining > 12:
            t.append(" │ ⚡ ", style=NOTE)
            t.append(self._elide(self.target.initial_access_vuln, remaining - 6), style=f"bold {INFO}")
        return t


class GuidanceDrawer(Static):
    """Dynamic command & methodology tips inspector.

    Shows the static reference command + tip for whatever the operator has
    highlighted (checklist step or discovered service). Everything shown here
    comes from the bundled static playbooks — nothing is inferred.
    """

    DEFAULT_CSS = f"""
    GuidanceDrawer {{
        height: 4;
        border: solid {SURFACE_RAISED};
        background: {BACKGROUND};
        padding: 0 1;
        margin-top: 1;
        color: {CREAM};
    }}
    GuidanceDrawer.-active {{
        border: solid {TERRACOTTA} 60%;
    }}
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.item_title: str = ""
        self.target_ip: str = ""
        self.command: str = ""
        self.tip: str = ""
        self.heading: str = "STEP GUIDANCE"

    @staticmethod
    def elide(value: str, width: int) -> str:
        """Shorten `value` to `width` cells, marking the cut with an ellipsis."""
        if width <= 1:
            return ""
        if len(value) <= width:
            return value
        return value[: max(width - 1, 1)] + "…"

    def reset(self) -> None:
        """Return the drawer to its idle hint state."""
        self.item_title = ""
        self.command = ""
        self.tip = ""
        self.heading = "STEP GUIDANCE"
        self.remove_class("-active")
        self.refresh()

    def show_command(self, command: str, tip: str, target_ip: str = "", heading: str = "CMD") -> None:
        """Display a ready-to-copy reference command and its tip."""
        self.item_title = ""
        self.heading = heading
        self.command = substitute_command_placeholders(command or "", target_ip)
        self.tip = tip or ""
        self.add_class("-active")
        self.refresh()

    def show_step(self, title: str, target_ip: str = "") -> None:
        """Display guidance for a checklist step (checklist templates only)."""
        self.heading = "STEP"
        self.item_title = title
        self.command = ""
        self.tip = ""
        guidance = get_template_guidance_for_title(title)
        if guidance:
            self.heading = "CMD"
            self.command = substitute_command_placeholders(guidance.get("command", ""), target_ip)
            self.tip = guidance.get("tip", "")
        self.remove_class("-active")
        self.refresh()

    def update_guidance(self, item_title: str, target_ip: str = "") -> None:
        """Backwards-compatible entry point for checklist steps."""
        self.show_step(item_title, target_ip)

    def render(self) -> Text:
        t = Text()
        if self.command:
            inner = max(self.size.width - 6, 12)
            heading = f"💡 {self.heading}: "
            t.append(heading, style=f"bold {OK}")
            # One row per idea: elide rather than let a long command wrap and
            # push the tip out of the 4-row drawer.
            t.append(self.elide(self.command, inner - len(heading)) + "\n", style=f"bold {CREAM}")
            t.append("ℹ️  TIP: ", style=f"bold {WARN}")
            hint = "  [Enter=Copy]"
            tip_room = max(inner - 9 - len(hint), 6)
            tip = self.tip if len(self.tip) <= tip_room else self.tip[: max(tip_room - 1, 1)] + "…"
            t.append(tip, style=NOTE)
            t.append(hint, style=f"bold {TERRACOTTA}")
            return t

        if self.item_title:
            t.append("💡 STEP: ", style=f"bold {INFO}")
            t.append(f"{self.item_title}\n", style=f"bold {CREAM}")
            t.append("Shortcuts: [Space] Cycle status  •  [y] Copy item  •  [d] Delete item", style=NOTE)
            return t

        t.append("💡 STEP GUIDANCE: ", style=f"bold {INFO}")
        t.append("Highlight a checklist step or service to inspect its commands & tips.\n", style="dim italic")
        t.append("Shortcuts: [Space] Cycle status  •  [Enter] Copy command  •  [y] Copy title", style=NOTE)
        return t


class DataListItem(ListItem):
    """Custom ListItem wrapping a specific data model or placeholder."""

    def __init__(
        self,
        data_obj: Any,
        display_text: Text,
        is_placeholder: bool = False,
        *children: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__(*children, **kwargs)
        self.data_obj = data_obj
        self.display_text = display_text
        self.is_placeholder = is_placeholder

    def compose(self) -> ComposeResult:
        yield Label(self.display_text)


class ConfirmModal(ModalScreen[bool]):
    """Small yes/no guard for destructive actions (delete, quit, ...)."""

    DEFAULT_CSS = """
    ConfirmModal {
        align: center middle;
    }
    #confirm-box {
        width: 60;
        height: auto;
        border: round $error;
        background: $surface;
        padding: 1 2;
        color: $foreground;
    }
    #confirm-message {
        height: auto;
        margin-bottom: 1;
    }
    """

    def __init__(self, title: str, message: str, confirm_label: str = "Delete") -> None:
        super().__init__()
        self.modal_title = title
        self.message = message
        self.confirm_label = confirm_label

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-box"):
            yield Label(f"▸ {self.modal_title}", classes="modal-header")
            yield Label(self.message, id="confirm-message")
            with Horizontal(classes="modal-buttons"):
                yield Button(
                    f"{self.confirm_label} (y)", variant="error", classes="danger-btn", id="btn-confirm"
                )
                yield Button("Cancel (Esc)", id="btn-cancel")

    def on_mount(self) -> None:
        self.query_one("#btn-cancel", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "btn-confirm")

    def on_key(self, event: Any) -> None:
        if event.key in ("escape", "n", "N"):
            self.dismiss(False)
        elif event.key in ("y", "Y", "enter"):
            self.dismiss(True)


class SearchModal(ModalScreen):
    """Interactive global search modal (Ctrl+F or /)."""

    DEFAULT_CSS = f"""
    SearchModal {{
        align: center middle;
    }}
    #search-box {{
        width: 80%;
        height: 80%;
        border: round {TERRACOTTA};
        background: {SURFACE};
        padding: 1 2;
    }}
    #search-input {{
        margin-bottom: 1;
    }}
    #search-results {{
        height: 1fr;
        border: solid {SURFACE_RAISED};
        background: {BACKGROUND};
    }}
    #search-status {{
        height: 1;
        margin-top: 1;
        color: {MUTED};
    }}
    """

    def __init__(self, store: Any, on_select: Optional[Callable[[SearchMatch], None]] = None) -> None:
        super().__init__()
        self.store = store
        self.on_select = on_select
        self.matches: List[SearchMatch] = []

    def compose(self) -> ComposeResult:
        with Vertical(id="search-box"):
            yield Label(
                f"[bold {TERRACOTTA}]SEARCH WORKSHEET[/] [#A8A099](↑↓ / j·k move, Enter copy & close, y copy, Esc close)[/]"
            )
            yield Input(placeholder="Type keywords to search across notes, services, creds, findings...", id="search-input")
            yield ListView(id="search-results")
            yield Label("0 results", id="search-status")

    def on_mount(self) -> None:
        self.query_one("#search-input", Input).focus()

    def _selected_match(self) -> Optional[SearchMatch]:
        results_view = self.query_one("#search-results", ListView)
        child = results_view.highlighted_child
        if isinstance(child, DataListItem) and not child.is_placeholder and child.data_obj:
            return child.data_obj  # type: ignore[return-value]
        return None

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Enter / click on a result copies it and closes the dialog."""
        match = self._selected_match()
        if match is not None:
            self._copy(match)
            self.dismiss(match)

    def _copy(self, match: SearchMatch) -> None:
        val = match.title or match.snippet
        copy_to_clipboard(val)
        self.notify(f"Copied: {val}")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Enter while typing copies the top hit — the fastest capture path."""
        event.stop()
        match = self._selected_match() or (self.matches[0] if self.matches else None)
        if match is not None:
            self._copy(match)
            self.dismiss(match)
        else:
            self.query_one("#search-results", ListView).focus()

    def on_key(self, event: Any) -> None:
        if event.key == "escape":
            self.dismiss(None)
            return
        if isinstance(self.focused, Input):
            return
        if event.key in ("j", "down"):
            self.query_one("#search-results", ListView).action_cursor_down()
            event.stop()
        elif event.key in ("k", "up"):
            self.query_one("#search-results", ListView).action_cursor_up()
            event.stop()
        elif event.key == "y":
            match = self._selected_match()
            if match is not None:
                self._copy(match)

    def on_input_changed(self, event: Input.Changed) -> None:
        query = event.value.strip()
        results_view = self.query_one("#search-results", ListView)
        status_label = self.query_one("#search-status", Label)
        results_view.clear()

        if not query:
            status_label.update("0 results")
            self.matches = []
            return

        self.matches = search_notebook(self.store, query)
        status_label.update(f"{len(self.matches)} results found")

        for m in self.matches:
            txt = Text()
            txt.append(f"[{m.entity_type.upper()}] ", style=f"bold {INFO}")
            if m.target_ip:
                txt.append(f"{m.target_ip} ", style=f"bold {WARN}")
            txt.append(f"{m.title} — ", style=f"bold {CREAM}")
            txt.append(m.snippet, style=NOTE)
            results_view.append(DataListItem(data_obj=m, display_text=txt))


class AddTargetModal(ModalScreen[Optional[dict]]):
    """Fast modal for creating a target host with OS dropdown and preset ports."""

    DEFAULT_CSS = """
    AddTargetModal {
        align: center middle;
    }
    #add-target-container {
        width: 68;
        height: auto;
        max-height: 90%;
        border: round $primary;
        background: $surface;
        padding: 1 2;
        color: $foreground;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="add-target-container", classes="synapse-modal-dialog"):
            yield Label("▸ ADD TARGET HOST", classes="modal-header")

            yield Label("Target IP / Hostname *:", classes="field-label")
            yield Input(placeholder="e.g. 10.10.11.10", id="target-ip")

            yield Label("FQDN / NetBIOS Hostname (optional):", classes="field-label")
            yield Input(placeholder="e.g. dc01.corp.local", id="target-host")

            yield Label("Operating System:", classes="field-label")
            yield Select(
                [
                    ("Linux (Debian / Ubuntu / Kali / Arch)", "Linux"),
                    ("Windows Server / Active Directory", "Windows Server"),
                    ("Windows 10 / 11 Workstation", "Windows"),
                    ("FreeBSD / Unix", "FreeBSD"),
                    ("Embedded / Network Device", "Embedded"),
                    ("Unknown / Other", "Unknown"),
                ],
                value="Linux",
                id="target-os",
            )

            yield Label("Common Initial Ports Preset:", classes="field-label")
            yield Select(
                [
                    ("None / Custom", ""),
                    ("Web Standard (80, 443)", "80,443"),
                    ("Web & SSH (22, 80, 443, 8080)", "22,80,443,8080"),
                    ("Windows Active Directory (53, 88, 135, 139, 389, 445, 5985)", "53,88,135,139,389,445,5985"),
                    ("Top Common TCP (21,22,25,53,80,110,139,443,445,1433,3306,3389,5985,8080)", "21,22,25,53,80,110,139,443,445,1433,3306,3389,5985,8080"),
                ],
                value="",
                id="target-ports-preset",
            )

            yield Label("Custom Ports (comma-separated, optional):", classes="field-label")
            yield Input(placeholder="e.g. 22, 80, 445", id="target-ports-custom")

            yield Label("Target Notes (optional):", classes="field-label")
            yield Input(placeholder="e.g. In-scope lab machine, potential DC", id="target-notes")

            with Horizontal(classes="modal-buttons"):
                yield Button("Save Target (Enter)", variant="primary", classes="primary-btn", id="btn-save")
                yield Button("Cancel (Esc)", id="btn-cancel")

    def on_mount(self) -> None:
        self.query_one("#target-ip", Input).focus()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "target-ports-preset" and event.value:
            curr = self.query_one("#target-ports-custom", Input)
            if not curr.value:
                curr.value = str(event.value)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-save":
            self.submit_data()
        else:
            self.dismiss(None)

    def on_key(self, event: Any) -> None:
        if event.key == "escape":
            self.dismiss(None)
        elif event.key == "enter" and not isinstance(self.focused, Select):
            self.submit_data()

    def submit_data(self) -> None:
        ip_val = self.query_one("#target-ip", Input).value.strip()
        if not ip_val:
            return
        host_val = self.query_one("#target-host", Input).value.strip()
        os_val = str(self.query_one("#target-os", Select).value or "Linux")
        ports_preset = str(self.query_one("#target-ports-preset", Select).value or "")
        ports_custom = self.query_one("#target-ports-custom", Input).value.strip()
        notes_val = self.query_one("#target-notes", Input).value.strip()

        ports_raw = ports_custom or ports_preset
        ports = []
        if ports_raw:
            for p in ports_raw.split(","):
                p = p.strip()
                if p.isdigit() and 1 <= int(p) <= 65535:
                    ports.append(int(p))

        self.dismiss({
            "ip": ip_val,
            "hostname": host_val,
            "os": os_val,
            "ports": ports,
            "notes": notes_val,
        })


class AddServiceModal(ModalScreen[Optional[dict]]):
    """Fast service creation dialog with auto-filling presets and access potential."""

    DEFAULT_CSS = """
    AddServiceModal {
        align: center middle;
    }
    #add-service-container {
        width: 72;
        height: auto;
        max-height: 92%;
        border: round $primary;
        background: $surface;
        padding: 1 2;
        color: $foreground;
    }
    """

    SERVICE_PRESETS = [
        ("Custom / Manual Entry", "custom"),
        ("21 / FTP (Anonymous / vsftpd)", "21/tcp/ftp/HIGH/ftp <TARGET_IP>"),
        ("22 / SSH (OpenSSH / Brute-force)", "22/tcp/ssh/MED/hydra -l user -P rockyou.txt ssh://<TARGET_IP>"),
        ("23 / Telnet (Unencrypted CLI)", "23/tcp/telnet/HIGH/telnet <TARGET_IP>"),
        ("25 / SMTP (User Enum / VRFY)", "25/tcp/smtp/MED/smtp-user-enum -M VRFY -U users.txt -t <TARGET_IP>"),
        ("53 / DNS (Zone Transfer / axfr)", "53/tcp/domain/MED/dig axfr @<TARGET_IP> <DOMAIN>"),
        ("80 / HTTP (Web / Directory Busting)", "80/tcp/http/HIGH/feroxbuster -u http://<TARGET_IP>/ -w /usr/share/wordlists/dirb/common.txt"),
        ("88 / Kerberos (Active Directory)", "88/tcp/kerberos/HIGH/GetNPUsers.py <DOMAIN>/ -no-pass -usersfile users.txt"),
        ("110 / POP3 (Mail Server)", "110/tcp/pop3/MED/nc -vn <TARGET_IP> 110"),
        ("139 / NetBIOS (Session)", "139/tcp/netbios-ssn/MED/nbtscan <TARGET_IP>"),
        ("389 / LDAP (Active Directory)", "389/tcp/ldap/HIGH/ldapsearch -x -H ldap://<TARGET_IP> -b 'DC=corp,DC=local'"),
        ("443 / HTTPS (SSL Web Server)", "443/tcp/https/HIGH/feroxbuster -u https://<TARGET_IP>/ -k"),
        ("445 / SMB (Samba / Shares / Null Session)", "445/tcp/microsoft-ds/HIGH/netexec smb <TARGET_IP> -u '' -p '' --shares"),
        ("1433 / MSSQL (SQL Server)", "1433/tcp/ms-sql-s/HIGH/mssqlclient.py <DOMAIN>/user:pass@<TARGET_IP> -windows-auth"),
        ("3306 / MySQL (Database)", "3306/tcp/mysql/MED/mysql -h <TARGET_IP> -u root -p"),
        ("3389 / RDP (Remote Desktop)", "3389/tcp/ms-wbt-server/MED/xfreerdp /u:user /p:pass /v:<TARGET_IP> /smart-sizing"),
        ("5985 / WinRM (PowerShell Remoting)", "5985/tcp/wsman/HIGH/evil-winrm -i <TARGET_IP> -u user -p 'pass'"),
        ("8080 / HTTP-Proxy / Tomcat Manager", "8080/tcp/http-proxy/HIGH/curl -s http://<TARGET_IP>:8080/manager/html"),
    ]

    def __init__(self, target_ip: str = "", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.target_ip = target_ip

    def compose(self) -> ComposeResult:
        with Vertical(id="add-service-container", classes="synapse-modal-dialog"):
            yield Label(f"▸ ADD SERVICE — {self.target_ip or 'Active Target'}", classes="modal-header")

            yield Label("Quick Service Preset (Auto-fills below fields):", classes="field-label")
            yield Select(
                self.SERVICE_PRESETS,
                value="custom",
                id="svc-preset",
            )

            with Horizontal():
                with Vertical(classes="column"):
                    yield Label("Port Number *:", classes="field-label")
                    yield Input(value="80", id="svc-port")
                with Vertical(classes="column"):
                    yield Label("Protocol:", classes="field-label")
                    yield Select([("tcp", "tcp"), ("udp", "udp")], value="tcp", id="svc-proto")

            yield Label("Service Name *:", classes="field-label")
            yield Input(value="HTTP", id="svc-name")

            yield Label("Version / Banner (optional):", classes="field-label")
            yield Input(placeholder="e.g. Apache 2.4.52, Samba 4.3, OpenSSH 8.9", id="svc-ver")

            yield Label("Initial Access Potential:", classes="field-label")
            yield Select(
                [
                    ("HIGH (Direct RCE / Credentials / Easy Win)", "HIGH"),
                    ("MED (Enumeration / Brute-force)", "MED"),
                    ("LOW (Informational / Hardened)", "LOW"),
                ],
                value="HIGH",
                id="svc-potential",
            )

            yield Label("Next Action / Command Recipe:", classes="field-label")
            yield Input(placeholder="e.g. feroxbuster, smbmap, hydra...", id="svc-next")

            with Horizontal(classes="modal-buttons"):
                yield Button("Save Service (Enter)", variant="primary", classes="primary-btn", id="btn-save")
                yield Button("Cancel (Esc)", id="btn-cancel")

    def on_mount(self) -> None:
        self.query_one("#svc-preset", Select).focus()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "svc-preset" and event.value and event.value != "custom":
            val = str(event.value)
            parts = val.split("/")
            if len(parts) >= 5:
                port, proto, name, pot, nxt = parts[0], parts[1], parts[2], parts[3], "/".join(parts[4:])
                self.query_one("#svc-port", Input).value = port
                self.query_one("#svc-proto", Select).value = proto
                self.query_one("#svc-name", Input).value = name.upper()
                self.query_one("#svc-potential", Select).value = pot
                if self.target_ip:
                    nxt = nxt.replace("<TARGET_IP>", self.target_ip)
                self.query_one("#svc-next", Input).value = nxt

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-save":
            self.submit_data()
        else:
            self.dismiss(None)

    def on_key(self, event: Any) -> None:
        if event.key == "escape":
            self.dismiss(None)
        elif event.key == "enter" and not isinstance(self.focused, Select):
            self.submit_data()

    def submit_data(self) -> None:
        port_raw = self.query_one("#svc-port", Input).value.strip()
        if not port_raw.isdigit():
            return
        port = int(port_raw)
        proto = str(self.query_one("#svc-proto", Select).value or "tcp")
        name = self.query_one("#svc-name", Input).value.strip() or "unknown"
        ver = self.query_one("#svc-ver", Input).value.strip()
        pot = str(self.query_one("#svc-potential", Select).value or "MED")
        nxt = self.query_one("#svc-next", Input).value.strip()

        self.dismiss({
            "port": port,
            "protocol": proto,
            "service": name,
            "version": ver,
            "potential": pot,
            "next": nxt,
        })


class AddCredentialModal(ModalScreen[Optional[dict]]):
    """Fast credential recording dialog with service scope and credential type pickers."""

    DEFAULT_CSS = """
    AddCredentialModal {
        align: center middle;
    }
    #add-cred-container {
        width: 68;
        height: auto;
        max-height: 90%;
        border: round $primary;
        background: $surface;
        padding: 1 2;
        color: $foreground;
    }
    """

    SCOPE_PRESETS = [
        ("GLOBAL / All Services", "GLOBAL"),
        ("SMB (Windows / Samba Shares)", "SMB"),
        ("SSH (Linux Shell)", "SSH"),
        ("HTTP / Web Application", "HTTP"),
        ("WinRM (PowerShell Remoting)", "WinRM"),
        ("MSSQL (Database)", "MSSQL"),
        ("MySQL (Database)", "MySQL"),
        ("RDP (Remote Desktop)", "RDP"),
        ("FTP (File Transfer)", "FTP"),
    ]

    TYPE_PRESETS = [
        ("Cleartext Password", "password"),
        ("NTLM Hash (LM:NTLM or NTLM)", "ntlm_hash"),
        ("Kerberos Ticket (TGT / TGS ccache)", "kerberos"),
        ("SSH Private Key", "ssh_key"),
        ("API Token / Session Cookie", "token"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="add-cred-container", classes="synapse-modal-dialog"):
            yield Label("▸ RECORD CREDENTIAL", classes="modal-header")

            yield Label("Username *:", classes="field-label")
            yield Input(placeholder="e.g. administrator, root, tomcat", id="cred-user")

            yield Label("Secret / Password / Hash *:", classes="field-label")
            yield Input(placeholder="e.g. Password123!, aad3b435b51404eeaad3b435b51404ee:...", id="cred-secret")

            yield Label("Service Scope / Protocol:", classes="field-label")
            yield Select(self.SCOPE_PRESETS, value="SMB", id="cred-scope")

            yield Label("Credential Type:", classes="field-label")
            yield Select(self.TYPE_PRESETS, value="password", id="cred-type")

            yield Label("Source / Origin (optional):", classes="field-label")
            yield Input(placeholder="e.g. SAM dump, /etc/shadow, backup.zip, tomcat-users.xml", id="cred-source")

            with Horizontal(classes="modal-buttons"):
                yield Button("Save Credential (Enter)", variant="primary", classes="primary-btn", id="btn-save")
                yield Button("Cancel (Esc)", id="btn-cancel")

    def on_mount(self) -> None:
        self.query_one("#cred-user", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-save":
            self.submit_data()
        else:
            self.dismiss(None)

    def on_key(self, event: Any) -> None:
        if event.key == "escape":
            self.dismiss(None)
        elif event.key == "enter" and not isinstance(self.focused, Select):
            self.submit_data()

    def submit_data(self) -> None:
        u = self.query_one("#cred-user", Input).value.strip()
        p = self.query_one("#cred-secret", Input).value.strip()
        if not u:
            return
        scope = str(self.query_one("#cred-scope", Select).value or "GLOBAL")
        source = self.query_one("#cred-source", Input).value.strip()

        self.dismiss({
            "username": u,
            "secret": p,
            "scope": scope,
            "source": source,
        })


class AddFindingModal(ModalScreen[Optional[dict]]):
    """Fast finding dialog with category presets and severity dropdown."""

    DEFAULT_CSS = """
    AddFindingModal {
        align: center middle;
    }
    #add-finding-container {
        width: 68;
        height: auto;
        max-height: 90%;
        border: round $primary;
        background: $surface;
        padding: 1 2;
        color: $foreground;
    }
    """

    FINDING_PRESETS = [
        ("Custom Finding", "", "MEDIUM"),
        ("Default Administrative Credentials", "Default credentials identified allowing privileged access.", "CRITICAL"),
        ("Anonymous / Guest SMB Share Access", "Unauthenticated guest access permits reading sensitive shares.", "HIGH"),
        ("Unauthenticated Remote Code Execution (RCE)", "Vulnerability allows direct arbitrary code execution.", "CRITICAL"),
        ("SQL Injection (Auth Bypass / Exfiltration)", "SQL injection allows database dump or login bypass.", "HIGH"),
        ("Weak / Predictable Password", "Service vulnerable to dictionary brute-force.", "HIGH"),
        ("Unquoted Service Path Privilege Escalation", "Windows service path contains unquoted space allowing binary planting.", "HIGH"),
        ("SUID Binary Exploitation PrivEsc", "Linux SUID binary with GTFOBins exploitation path.", "HIGH"),
        ("Sudo NOPASSWD Misconfiguration PrivEsc", "User can run command as root without password.", "HIGH"),
        ("Kerberoasting (SPN Hash Exfiltration)", "Service principal accounts requestable for offline cracking.", "HIGH"),
        ("AS-REP Roasting (No Pre-Authentication)", "User account DONT_REQ_PREAUTH allows offline TGT crack.", "HIGH"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="add-finding-container", classes="synapse-modal-dialog"):
            yield Label("▸ RECORD VULNERABILITY / FINDING", classes="modal-header")

            yield Label("Category Preset (Auto-fills title and severity):", classes="field-label")
            yield Select(
                [(p[0], f"{p[0]}|{p[1]}|{p[2]}") for p in self.FINDING_PRESETS],
                value=f"{self.FINDING_PRESETS[0][0]}||MEDIUM",
                id="finding-preset",
            )

            yield Label("Finding Title *:", classes="field-label")
            yield Input(placeholder="e.g. Apache Tomcat Default Credentials", id="finding-title")

            yield Label("Severity Level:", classes="field-label")
            yield Select(
                [
                    ("CRITICAL (Direct Foothold / Domain Admin)", "CRITICAL"),
                    ("HIGH (Privilege Escalation / Sensitive Data)", "HIGH"),
                    ("MEDIUM (Misconfiguration / Brute-force)", "MEDIUM"),
                    ("LOW (Information Leak)", "LOW"),
                    ("INFO (Recon Observation)", "INFO"),
                ],
                value="HIGH",
                id="finding-sev",
            )

            yield Label("Exploitation Details / Description (optional):", classes="field-label")
            yield Input(placeholder="e.g. tomcat:s3cret_p4ss allows uploading WAR reverse shell", id="finding-desc")

            with Horizontal(classes="modal-buttons"):
                yield Button("Save Finding (Enter)", variant="primary", classes="primary-btn", id="btn-save")
                yield Button("Cancel (Esc)", id="btn-cancel")

    def on_mount(self) -> None:
        self.query_one("#finding-preset", Select).focus()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "finding-preset" and event.value:
            val = str(event.value)
            parts = val.split("|", 2)
            if len(parts) == 3:
                title, desc, sev = parts[0], parts[1], parts[2]
                if title != "Custom Finding":
                    self.query_one("#finding-title", Input).value = title
                    self.query_one("#finding-desc", Input).value = desc
                    self.query_one("#finding-sev", Select).value = sev

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-save":
            self.submit_data()
        else:
            self.dismiss(None)

    def on_key(self, event: Any) -> None:
        if event.key == "escape":
            self.dismiss(None)
        elif event.key == "enter" and not isinstance(self.focused, Select):
            self.submit_data()

    def submit_data(self) -> None:
        title = self.query_one("#finding-title", Input).value.strip()
        if not title:
            return
        sev = str(self.query_one("#finding-sev", Select).value or "MEDIUM")
        desc = self.query_one("#finding-desc", Input).value.strip()

        self.dismiss({
            "title": title,
            "severity": sev,
            "desc": desc,
        })


class FastInputModal(ModalScreen[Optional[dict]]):
    """Generic quick-entry modal for simple key-value inputs."""

    DEFAULT_CSS = """
    FastInputModal {
        align: center middle;
    }
    #input-container {
        width: 65%;
        height: auto;
        border: round $primary;
        background: $surface;
        padding: 1 2;
        color: $foreground;
    }
    #modal-title {
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
    }
    .input-field {
        margin-bottom: 1;
        background: $background;
        border: round $surface-lighten-1;
        color: $foreground;
    }
    .input-field:focus {
        border: round $primary;
    }
    #button-bar {
        height: 3;
        margin-top: 1;
        layout: horizontal;
        align: right middle;
    }
    """

    def __init__(self, title: str, fields: List[tuple[str, str, str]]) -> None:
        super().__init__()
        self.modal_title = title
        self.fields = fields

    def compose(self) -> ComposeResult:
        with Vertical(id="input-container"):
            yield Label(f"▸ {self.modal_title}", id="modal-title")
            for key, label_text, default_val in self.fields:
                yield Label(label_text, classes="field-label")
                yield Input(value=default_val, id=f"field-{key}", classes="input-field")
            with Horizontal(id="button-bar"):
                yield Button("Save (Enter)", variant="primary", classes="primary-btn", id="btn-save")
                yield Button("Cancel (Esc)", id="btn-cancel")

    def on_mount(self) -> None:
        first_input = self.query(Input).first()
        if first_input:
            first_input.focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-save":
            data = {}
            for key, _, _ in self.fields:
                inp = self.query_one(f"#field-{key}", Input)
                data[key] = inp.value.strip()
            self.dismiss(data)
        else:
            self.dismiss(None)

    def on_key(self, event: Any) -> None:
        if event.key == "escape":
            self.dismiss(None)
        elif event.key == "enter":
            data = {}
            for key, _, _ in self.fields:
                inp = self.query_one(f"#field-{key}", Input)
                data[key] = inp.value.strip()
            self.dismiss(data)


class HelpModal(ModalScreen):
    """Modal displaying keyboard shortcuts and workflow reference."""

    DEFAULT_CSS = """
    HelpModal {
        align: center middle;
    }
    #help-box {
        width: 75%;
        height: 80%;
        border: round $primary;
        background: $surface;
        padding: 1 2;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="help-box"):
            yield Label(f"[bold {TERRACOTTA}]CYB0X-S WORKSHEET — KEYBOARD REFERENCE[/bold {TERRACOTTA}]\n")
            with VerticalScroll():
                text = """
[bold]Key Design Principle:[/bold]
The human decides and performs the security-testing actions. CYB0X-S records and organizes them.
Pure passive recording • Local-first SQLite store • Zero background scanning or AI.

[bold]Stations:[/bold]
  [#D97757]1[/]  Field Worksheet      services, credentials, methodology roadmap, notes
  [#D97757]2[/]  Playbooks & Cheatsheet   offline command reference (Enter copies)
  [#D97757]3[/]  Credential Matrix    vault, reveal/copy, spray targets
  [#D97757]4[/]  Flags & Failure Log  user/root flags, foothold, rabbit holes

[bold]Navigation:[/bold]
  [#D97757]Tab / Shift+Tab[/]  : Move focus between panels
  [#D97757]j / k  (or ↑ / ↓)[/] : Move down / up inside the focused list or tree
  [#D97757]z[/]                : Zoom the focused panel, press again to restore
  [#D97757]Esc[/]              : Close any dialog

[bold]Working with the highlighted item:[/bold]
  [#D97757]Enter[/]            : Copy the ready-to-paste command / next action
  [#D97757]y[/]                : Copy the value (IP, IP:port, secret, note text)
  [#D97757]Space[/]            : Cycle checklist status (TODO → CHECKED → DEFERRED → DEAD-END)
                     or reveal / re-mask a credential
  [#D97757]d[/]                : Delete it (asks for confirmation)

[bold]Capture:[/bold]
  [#D97757]t[/]  target    [#D97757]s[/]  service    [#D97757]f[/]  finding
  [#D97757]c[/]  credential  [#D97757]n[/]  note      [#D97757]K[/]  (shift+k) checklist item
  [#D97757]m[/]  methodology template    [#D97757]g[/]  record flags
  [#D97757]r[/]  cheat sheet            [#D97757]o[/]  toggle in-scope / out-of-scope
  [#D97757]/[/] or [#D97757]Ctrl+F[/]  search     [#D97757]?[/]  this help      [#D97757]q[/]  quit

[bold]Fast capture commands (bottom bar):[/bold]
  :t 10.10.10.20          add a target
  :s 445/tcp smb          add a service
  :c admin:password123    add a credential
  :n found backup.zip     add a note
  :f smb null session     add a finding
  :uflag / :rflag <hash>  record user / root flag
  :foothold / :privesc    record foothold & privilege escalation vector
  :stuck <why> / :clue    log a rabbit hole or the breakthrough clue
  :ref <term>             offline cheat sheet       :1 :2 :3 :4  stations

[bold]Shell equivalents:[/bold]
  cyb0x-s target 10.10.10.20
  cyb0x-s service 10.10.10.20 445/tcp SMB --version "Samba 4.3"
  cyb0x-s finding "SMB anonymous access enabled" --severity HIGH
  cyb0x-s cred admin:password --source backup.zip
  cyb0x-s export --format md -o notes.md

Press [bold]Esc[/bold] or [bold]q[/bold] to return to the worksheet.
"""
                yield Static(text)
            yield Button("Close", id="btn-close", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(None)

    def on_key(self, event: Any) -> None:
        if event.key in ("escape", "q", "enter"):
            self.dismiss(None)


class TemplateSelectionModal(ModalScreen[Optional[str]]):
    """Interactive selector for eJPTv2 & standard penetration testing methodology templates."""

    DEFAULT_CSS = """
    TemplateSelectionModal {
        align: center middle;
    }
    #template-box {
        width: 80%;
        height: 80%;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }
    #template-list {
        height: 1fr;
        border: solid $secondary 40%;
        margin-top: 1;
        margin-bottom: 1;
    }
    #btn-bar {
        height: 3;
        layout: horizontal;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="template-box"):
            yield Label("[bold #D97757]METHODOLOGY CHECKLIST TEMPLATES[/bold #D97757] [#A8A099](eJPTv2 & Reddit Curated)[/]")
            yield Label("[#A8A099]Select a template using ↑ / ↓ and press Enter (or click Apply)[/]")
            yield ListView(id="template-list")
            with Horizontal(id="btn-bar"):
                yield Button("Apply Template (Enter)", variant="primary", id="btn-apply")
                yield Button("Cancel (Esc)", variant="default", id="btn-cancel")

    def on_mount(self) -> None:
        from cyb0x_s.templates import STATIC_TEMPLATES

        t_list = self.query_one("#template-list", ListView)
        for key, tmpl in STATIC_TEMPLATES.items():
            txt = Text()
            txt.append(f"{key.upper():<16} ", style=f"bold {INFO}")
            txt.append(f"({len(tmpl['items'])} items)  ", style=f"bold {WARN}")
            txt.append(f"{tmpl['description']}", style=NOTE)
            t_list.append(DataListItem(data_obj=key, display_text=txt))
        t_list.focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-apply":
            self._select_current()
        else:
            self.dismiss(None)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if isinstance(event.item, DataListItem):
            self.dismiss(event.item.data_obj)

    def _select_current(self) -> None:
        t_list = self.query_one("#template-list", ListView)
        if t_list.highlighted_child and isinstance(t_list.highlighted_child, DataListItem):
            self.dismiss(t_list.highlighted_child.data_obj)
        else:
            self.dismiss(None)

    def on_key(self, event: Any) -> None:
        if event.key == "escape":
            self.dismiss(None)
        elif event.key == "enter":
            self._select_current()


class ReferenceModal(ModalScreen[Optional[str]]):
    """Searchable command reference and playbook modal (dev-angelist / eJPTv2 curated)."""

    DEFAULT_CSS = """
    ReferenceModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.75);
    }
    #ref-box {
        width: 85%;
        height: 85%;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    #ref-filter-input {
        margin-top: 1;
        margin-bottom: 1;
        border: solid $border;
        background: $background;
    }
    #ref-list {
        height: 1fr;
        border: solid $border;
        margin-bottom: 1;
    }
    #ref-btn-bar {
        height: 3;
        layout: horizontal;
    }
    """

    def __init__(self, target_ip: str = "", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.target_ip = target_ip

    def compose(self) -> ComposeResult:
        with Vertical(id="ref-box"):
            yield Label("[bold #D97757]📖 eJPTv2 CHEAT SHEET & COMMAND REFERENCE[/bold #D97757] [#A8A099](Offline Playbook)[/]")
            yield Label(f"[#A8A099]Target IP: [bold]{self.target_ip or 'None'}[/bold] • Type to filter, Enter to copy command, Esc to exit[/]")
            yield Input(placeholder="Search commands: smb, winrm, mimikatz, pivot, privesc, sql, hydra...", id="ref-filter-input")
            yield ListView(id="ref-list")
            with Horizontal(id="ref-btn-bar"):
                yield Button("Copy Selected Command (Enter)", variant="primary", id="btn-copy-ref")
                yield Button("Close (Esc)", variant="default", id="btn-close-ref")

    def on_mount(self) -> None:
        self._populate_list("")
        inp = self.query_one("#ref-filter-input", Input)
        inp.focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        self._populate_list(event.value)

    def _populate_list(self, query: str) -> None:
        from cyb0x_s.reference import search_reference

        ref_list = self.query_one("#ref-list", ListView)
        ref_list.clear()
        matches = search_reference(query, target_ip=self.target_ip)
        if matches:
            for item in matches:
                txt = Text()
                txt.append(f"[{item['category']}] ", style=f"bold {WARN}")
                txt.append(f"{item['title']}\n", style=f"bold {CREAM}")
                txt.append(f"  ❯ {item['command']}\n", style=f"bold {WARN}")
                txt.append(f"    ℹ {item['desc']}", style="dim italic")
                ref_list.append(DataListItem(data_obj=item["command"], display_text=txt))
        else:
            txt = Text("  • No matching commands found. Try 'smb', 'web', 'sql', 'privesc'...", style="dim italic")
            ref_list.append(DataListItem(data_obj=None, display_text=txt, is_placeholder=True))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-copy-ref":
            self._select_current()
        else:
            self.dismiss(None)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if isinstance(event.item, DataListItem) and not event.item.is_placeholder and event.item.data_obj:
            self.dismiss(str(event.item.data_obj))

    def _select_current(self) -> None:
        ref_list = self.query_one("#ref-list", ListView)
        if ref_list.highlighted_child and isinstance(ref_list.highlighted_child, DataListItem) and not ref_list.highlighted_child.is_placeholder:
            self.dismiss(str(ref_list.highlighted_child.data_obj))
        else:
            self.dismiss(None)

    def on_key(self, event: Any) -> None:
        if event.key == "escape":
            self.dismiss(None)


class PlaybookBrowserWidget(Static):
    """Interactive full-screen playbook and command cheat sheet browser."""

    DEFAULT_CSS = """
    PlaybookBrowserWidget {
        height: 1fr;
        layout: vertical;
        padding: 0 1;
    }
    #playbook-top-bar {
        height: 3;
        layout: horizontal;
        margin-bottom: 1;
    }
    #playbook-search-input {
        width: 1fr;
        border: solid $border;
        background: $surface;
    }
    #playbook-body {
        height: 1fr;
        layout: horizontal;
    }
    #playbook-cat-panel {
        width: 25%;
        height: 1fr;
        border: round $border;
        background: $surface;
        padding: 0 1;
        margin-right: 1;
    }
    #playbook-cmd-panel {
        width: 75%;
        height: 1fr;
        border: round $border;
        background: $surface;
        padding: 0 1;
    }
    .panel-hdr {
        text-style: bold;
        color: $accent;
        padding: 0 1;
        height: 1;
    }
    """

    def __init__(self, target_ip: str = "", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.target_ip = target_ip
        self.selected_category = "ALL"
        self.search_query = ""

    def compose(self) -> ComposeResult:
        with Horizontal(id="playbook-top-bar"):
            yield Input(placeholder="Search all commands: smb, winrm, mimikatz, pivot, privesc, sql, hydra...", id="playbook-search-input")
        with Horizontal(id="playbook-body"):
            with Vertical(id="playbook-cat-panel"):
                yield Label("CATEGORIES", classes="panel-hdr")
                yield ListView(id="playbook-cat-list")
            with Vertical(id="playbook-cmd-panel"):
                yield Label("READY-TO-PASTE COMMANDS", id="playbook-cmd-hdr", classes="panel-hdr")
                yield ListView(id="playbook-cmd-list")

    def on_mount(self) -> None:
        self._populate_categories()
        self._populate_commands()

    def update_target_ip(self, target_ip: str) -> None:
        self.target_ip = target_ip
        self._populate_commands()

    def _populate_categories(self) -> None:
        from cyb0x_s.reference import REFERENCE_PLAYBOOK

        cat_list = self.query_one("#playbook-cat-list", ListView)
        cat_list.clear()

        # Count per category
        counts: dict[str, int] = {}
        for item in REFERENCE_PLAYBOOK:
            c = item["category"]
            counts[c] = counts.get(c, 0) + 1

        all_txt = Text(f"★ ALL PLAYBOOKS ({len(REFERENCE_PLAYBOOK)})", style=f"bold {INFO}")
        cat_list.append(DataListItem(data_obj="ALL", display_text=all_txt))

        for cat, cnt in sorted(counts.items()):
            txt = Text(f"• {cat} ({cnt})", style=f"bold {CREAM}")
            cat_list.append(DataListItem(data_obj=cat, display_text=txt))

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "playbook-search-input":
            self.search_query = event.value
            self._populate_commands()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.list_view.id == "playbook-cat-list" and isinstance(event.item, DataListItem):
            self.selected_category = str(event.item.data_obj)
            self._populate_commands()
        elif event.list_view.id == "playbook-cmd-list" and isinstance(event.item, DataListItem):
            if event.item.data_obj and not event.item.is_placeholder:
                cmd = str(event.item.data_obj)
                copy_to_clipboard(cmd)
                self.app.notify(f"Copied command: {cmd}")

    def _populate_commands(self) -> None:
        from cyb0x_s.reference import search_reference

        cmd_list = self.query_one("#playbook-cmd-list", ListView)
        cmd_list.clear()

        matches = search_reference(self.search_query, target_ip=self.target_ip)
        if self.selected_category != "ALL":
            matches = [m for m in matches if m["category"].lower() == self.selected_category.lower()]

        hdr = self.query_one("#playbook-cmd-hdr", Label)
        hdr.update(f"COMMAND REFERENCE: {self.selected_category} ({len(matches)} ready commands)")

        if matches:
            for item in matches:
                txt = Text()
                txt.append(f"[{item['category']}] ", style=f"bold {WARN}")
                txt.append(f"{item['title']}\n", style=f"bold {CREAM}")
                txt.append(f"  ❯ {item['command']}\n", style=f"bold {WARN}")
                txt.append(f"    ℹ {item['desc']}  [Press Enter to copy]", style="dim italic")
                cmd_list.append(DataListItem(data_obj=item["command"], display_text=txt))
        else:
            txt = Text("  • No matching commands found.", style="dim italic")
            cmd_list.append(DataListItem(data_obj=None, display_text=txt, is_placeholder=True))


class LootAndFlagsWidget(Static):
    """Dedicated status dashboard for Flags, Foothold proofs, and Failure Log."""

    DEFAULT_CSS = """
    LootAndFlagsWidget {
        height: 1fr;
        layout: vertical;
        padding: 0 1;
    }
    #loot-cards-container {
        /* Explicit height: with `auto` the cards stretched over the whole
           tab and pushed the failure log off-screen. */
        height: 9;
        layout: horizontal;
        margin-bottom: 1;
    }
    .loot-box {
        width: 1fr;
        height: 9;
        border: round $border;
        background: $surface;
        padding: 0 1;
        margin-right: 1;
    }
    #loot-failure-box {
        height: 1fr;
        border: round $border;
        background: $surface;
        padding: 0 1;
    }
    .loot-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.target: Optional[Target] = None

    def compose(self) -> ComposeResult:
        with Horizontal(id="loot-cards-container"):
            with Vertical(classes="loot-box"):
                yield Label("🏁 CAPTURED EXAM FLAGS", classes="loot-title")
                yield Static(id="loot-flags-content")
            with Vertical(classes="loot-box"):
                yield Label("⚡ INITIAL FOOTHOLD & EXPLOIT", classes="loot-title")
                yield Static(id="loot-foothold-content")
            with Vertical(classes="loot-box"):
                yield Label("👑 PRIVILEGE ESCALATION & ROOT PROOF", classes="loot-title")
                yield Static(id="loot-privesc-content")
        with Vertical(id="loot-failure-box"):
            yield Label("🧠 RABBIT HOLE & BREAKTHROUGH ANALYSIS (FAILURE LOG)", classes="loot-title")
            yield ListView(id="loot-failure-list")

    def update_data(self, target: Optional[Target], failures: List[Any]) -> None:
        self.target = target

        # Flags Card
        f_txt = Text()
        if target:
            f_txt.append("User Flag: ", style=f"bold {INFO}")
            f_txt.append(f"{target.user_flag or '<NOT CAPTURED YET>'}\n", style=f"bold {OK}" if target.user_flag else NOTE)
            f_txt.append("Root Flag: ", style=f"bold {WARN}")
            f_txt.append(f"{target.root_flag or '<NOT CAPTURED YET>'}\n\n", style=f"bold {OK}" if target.root_flag else NOTE)
            f_txt.append("[Press 'g' or type :uflag / :rflag to set flags]", style="dim italic")
        else:
            f_txt.append("No active target selected.", style="dim italic")
        self.query_one("#loot-flags-content", Static).update(f_txt)

        # Foothold Card
        fh_txt = Text()
        if target and (target.initial_access_vuln or target.foothold_cmd):
            fh_txt.append("Vulnerability: ", style=f"bold {INFO}")
            fh_txt.append(f"{target.initial_access_vuln or 'N/A'}\n", style=f"bold {CREAM}")
            fh_txt.append("Context: ", style=f"bold {INFO}")
            fh_txt.append(f"{target.foothold_context or 'N/A'}\n", style=f"bold {CREAM}")
            fh_txt.append(f"Command:\n❯ {target.foothold_cmd or 'N/A'}", style=f"bold {WARN}")
        else:
            fh_txt.append("No foothold recorded yet.\nType :foothold <vuln> to record.", style="dim italic")
        self.query_one("#loot-foothold-content", Static).update(fh_txt)

        # PrivEsc Card
        pe_txt = Text()
        if target and (target.privesc_vector or target.root_proof):
            pe_txt.append("PrivEsc Vector: ", style=f"bold {INFO}")
            pe_txt.append(f"{target.privesc_vector or 'N/A'}\n", style=f"bold {CREAM}")
            pe_txt.append(f"Root Proof:\n❯ {target.root_proof or 'whoami && id && ip a'}", style=f"bold {WARN}")
        else:
            pe_txt.append("No PrivEsc recorded yet.\nType :privesc <vector> to record.", style="dim italic")
        self.query_one("#loot-privesc-content", Static).update(pe_txt)

        # Failure Log List
        f_list = self.query_one("#loot-failure-list", ListView)
        f_list.clear()
        if failures:
            for fl in failures:
                txt = Text()
                txt.append("🕳️ [DEAD-END] ", style=f"bold {DANGER}")
                txt.append(f"{fl.where_stuck}\n", style=f"bold {CREAM}")
                if fl.breakthrough_clue:
                    txt.append(f"   🔑 Breakthrough Clue: {fl.breakthrough_clue}\n", style=f"bold {OK}")
                if fl.rule_for_next_time:
                    txt.append(f"   📌 Permanent Rule: {fl.rule_for_next_time}", style="dim italic")
                f_list.append(DataListItem(data_obj=fl, display_text=txt))
        else:
            txt = Text("  • No rabbit holes or failure logs recorded. Type :stuck <where> / :clue <breakthrough>", style="dim italic")
            f_list.append(DataListItem(data_obj=None, display_text=txt, is_placeholder=True))


class CredentialMatrixWidget(Static):
    """Full-screen matrix of discovered credentials, lateral movement targets, and spray gaps."""

    DEFAULT_CSS = """
    CredentialMatrixWidget {
        height: 1fr;
        layout: vertical;
        padding: 0 1;
    }
    #cred-matrix-hdr {
        height: 1;
    }
    #cred-matrix-sub {
        height: 1;
        color: $text-muted;
        padding: 0 1;
        margin-bottom: 1;
    }
    #cred-matrix-list {
        height: 1fr;
        border: round $border;
        background: $surface;
    }
    """

    def compose(self) -> ComposeResult:
        yield Label(
            Text("CREDENTIAL VAULT & LATERAL MOVEMENT MATRIX"),
            id="cred-matrix-hdr",
            classes="panel-header",
        )
        yield Label("", id="cred-matrix-sub", classes="panel-subtitle")
        yield ListView(id="cred-matrix-list")

    def update_data(
        self,
        credentials: List[Credential],
        targets: List[Target],
        services: List[Service],
        revealed_ids: Set[int],
    ) -> None:
        c_list = self.query_one("#cred-matrix-list", ListView)
        c_list.clear()

        # Build in-scope targets mapping per service
        in_scope_targets = [t for t in targets if t.is_in_scope]
        svc_target_map: dict[str, list[str]] = {}
        for s in services:
            t = next((tgt for tgt in in_scope_targets if tgt.id == s.target_id), None)
            if t:
                svc_target_map.setdefault(s.service.lower(), []).append(t.ip)

        # Summary line: how much of the vault has actually been tried.
        tested = sum(1 for c in credentials if (c.status or "").lower() in ("valid", "tested"))
        subtitle = self.query_one("#cred-matrix-sub", Label)
        if credentials:
            subtitle.update(
                f"{len(credentials)} credential(s) • {tested} validated • "
                f"{len(credentials) - tested} untested   [Space]=Reveal  [y]=Copy  [c]=Add"
            )
        else:
            subtitle.update("No credentials recorded yet — press 'c' to add one.")

        if credentials:
            for c in credentials:
                txt = Text()
                txt.append("🔑 ", style=f"bold {OK}")
                scope = (c.service_scope or "GLOBAL").upper()
                scope = scope if len(scope) <= 8 else scope[:7] + "…"
                txt.append(f"[{scope:<8}] ", style=f"bold {WARN}")
                user = c.username if len(c.username) <= 16 else c.username[:15] + "…"
                txt.append(f"{user:<16} : ", style=f"bold {INFO}")
                secret = c.secret if c.id in revealed_ids else c.masked_secret
                txt.append(f"{secret:<20} ", style=f"bold {CREAM}")

                # Tested vs Unsprayed
                scope_key = (c.service_scope or "").lower()
                applicable_hosts = svc_target_map.get(scope_key, [t.ip for t in in_scope_targets])
                if c.source:
                    txt.append(f" Source: {c.source} │ ", style=NOTE)
                txt.append(f"Status: {c.status.upper()} │ ", style=f"bold {WARN}")
                if len(applicable_hosts) > 1:
                    txt.append(f"⚠ Spray Target(s): {', '.join(applicable_hosts[:3])}", style=f"bold {WARN}")

                c_list.append(DataListItem(data_obj=c, display_text=txt))
        else:
            for line in (
                "  • Nothing in the vault yet.",
                "  • Press 'c' to record a credential, or type :c user:pass below.",
                "  • Secrets stay masked until you reveal them with Space.",
            ):
                txt = Text(line, style="dim italic")
                c_list.append(DataListItem(data_obj=None, display_text=txt, is_placeholder=True))




