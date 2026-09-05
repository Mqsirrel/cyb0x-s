"""Modal dialogs and popup screens for the CYB0X-S TUI."""

from __future__ import annotations

from typing import Any, Callable, List, Optional

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, ListItem, ListView, Select, Static

from cyb0x_s.clipboard import copy_to_clipboard
from cyb0x_s.search import SearchMatch, search_notebook
from cyb0x_s.settings import derive_guidance_enabled
from cyb0x_s.tui.theme import PALETTES, S, current_palette, get_default_theme, save_default_theme
from cyb0x_s.tui.widgets import DataListItem


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


class ThemeSwatch(Static):
    """One row in the theme picker: colour strip, name, vibe, contrast, and default badge."""

    DEFAULT_CSS = """
    ThemeSwatch {
        height: 3;
        padding: 0 1;
    }
    ThemeSwatch.selected {
        background: $surface-lighten-1;
    }
    """

    def __init__(
        self,
        palette_name: str,
        palette_label: str,
        index: int = 1,
        default_name: str = "slate",
    ) -> None:
        super().__init__(id=f"theme-{palette_name}")
        self.palette_name = palette_name
        self.palette_label = palette_label
        self.index = index
        self.default_name = default_name

    def render(self) -> Text:
        palette = PALETTES[self.palette_name]
        is_active = current_palette().name == palette.name
        is_default = self.palette_name == self.default_name

        out = Text()
        out.append(f"[{self.index}] ", style=f"bold {palette.accent}")
        if is_active:
            out.append("● ", style=f"bold {palette.accent}")
        else:
            out.append("○ ", style=palette.muted)

        # colour strip — the palette's own hues
        for _label, colour in palette.swatch():
            out.append("██", style=f"on {colour}")

        desc = palette.label.split("·", 1)[-1].strip()
        out.append("  ")
        out.append(f"{palette.name:<9}", style=f"bold {palette.text}")
        out.append(f"{desc:<18}", style=palette.text_soft)

        ratio = palette.contrast_ratio()
        grade = "AAA" if ratio >= 7 else ("AA" if ratio >= 4.5 else "low")
        out.append(f" {ratio:4.1f}:1 {grade:<3}", style=palette.ok if ratio >= 7 else palette.warn)

        if is_default:
            out.append(" ★ DEFAULT", style=f"bold {palette.warn}")
        elif is_active:
            out.append(" ● active", style=f"bold {palette.accent}")
        return out


class ThemePickerModal(ModalScreen[Optional[str]]):
    """Interactive palette picker with live preview and default persistence."""

    DEFAULT_CSS = """
    ThemePickerModal {
        align: center middle;
        background: rgba(6, 9, 12, 0.72);
    }

    #theme-picker-box {
        width: 88;
        height: auto;
        max-height: 90%;
        border: round $accent;
        background: $surface;
        padding: 1 2;
    }

    #theme-picker-title {
        width: 100%;
        padding: 0 0 1 0;
        color: $accent;
        text-style: bold;
    }

    #theme-picker-list {
        height: auto;
        max-height: 24;
        background: transparent;
        border: none;
    }

    #theme-picker-list > ListItem {
        padding: 0;
        background: transparent;
    }

    #theme-picker-list > ListItem.-selected {
        background: $surface-lighten-1;
    }

    #theme-picker-list > ListItem:hover {
        background: $surface-lighten-1;
    }

    #theme-picker-buttons {
        height: 3;
        margin-top: 1;
        layout: horizontal;
        align: right middle;
    }

    #theme-picker-buttons Button {
        margin-left: 1;
    }

    #theme-picker-hint {
        width: 100%;
        padding: 1 0 0 0;
        color: $text-soft;
    }
    """

    def __init__(self, current: str, store: Any = None) -> None:
        super().__init__()
        self.original = current
        self.store = store
        self.default_theme = get_default_theme(store)

    def compose(self) -> ComposeResult:
        with Vertical(id="theme-picker-box"):
            yield Label(
                "◈  COLOR THEMES — ↑↓/j/k Preview  •  Enter Apply  •  d Set Default",
                id="theme-picker-title",
            )
            yield ListView(
                *[
                    ListItem(
                        ThemeSwatch(
                            name,
                            palette.label,
                            index=i + 1,
                            default_name=self.default_theme,
                        )
                    )
                    for i, (name, palette) in enumerate(PALETTES.items())
                ],
                id="theme-picker-list",
            )
            with Horizontal(id="theme-picker-buttons"):
                yield Button("Set as Default (d)", variant="warning", id="btn-set-default")
                yield Button("Apply (Enter)", variant="primary", classes="primary-btn", id="btn-apply")
                yield Button("Cancel (Esc)", id="btn-cancel")
            yield Label(
                "↑↓/j/k: live preview   1-7: pick   d: save default   Enter: apply   Esc: cancel",
                id="theme-picker-hint",
            )

    def on_mount(self) -> None:
        names = list(PALETTES)
        index = names.index(self.original) if self.original in names else 0
        list_view = self.query_one("#theme-picker-list", ListView)
        list_view.index = index
        list_view.focus()

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        """Live preview: apply the palette the cursor is sitting on."""
        for row in self.query(ThemeSwatch):
            row.set_class(row.palette_name == current_palette().name, "selected")
        if event.item is None:
            return
        rows = event.item.query(ThemeSwatch)
        if not rows:
            return
        name = rows[0].palette_name
        if name != current_palette().name:
            self.app.apply_theme(name, quiet=True)  # type: ignore[attr-defined]

    def _selected_theme_name(self) -> str:
        list_view = self.query_one("#theme-picker-list", ListView)
        item = list_view.highlighted_child
        if item is not None:
            rows = item.query(ThemeSwatch)
            if rows:
                return rows[0].palette_name
        return current_palette().name

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-set-default":
            chosen = self._selected_theme_name()
            if hasattr(self.app, "set_default_theme"):
                self.app.set_default_theme(chosen)
            else:
                save_default_theme(chosen, self.store)
                self.app.apply_theme(chosen)  # type: ignore[attr-defined]
            self.dismiss(chosen)
        elif event.button.id == "btn-apply":
            chosen = self._selected_theme_name()
            self.app.apply_theme(chosen)  # type: ignore[attr-defined]
            self.dismiss(chosen)
        elif event.button.id == "btn-cancel":
            self.app.apply_theme(self.original)  # type: ignore[attr-defined]
            self.dismiss(self.original)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Click or Enter on list item selects and keeps it."""
        if event.item is not None:
            rows = event.item.query(ThemeSwatch)
            if rows:
                chosen = rows[0].palette_name
                self.app.apply_theme(chosen)  # type: ignore[attr-defined]
                self.dismiss(chosen)

    def on_key(self, event: Any) -> None:
        names = list(PALETTES)
        if event.key in "1234567":
            event.stop()
            idx = int(event.key) - 1
            if 0 <= idx < len(names):
                chosen = names[idx]
                self.app.apply_theme(chosen)  # type: ignore[attr-defined]
                self.dismiss(chosen)
            return
        if event.key in ("d", "D", "s"):
            event.stop()
            chosen = self._selected_theme_name()
            if hasattr(self.app, "set_default_theme"):
                self.app.set_default_theme(chosen)
            else:
                save_default_theme(chosen, self.store)
                self.app.apply_theme(chosen)  # type: ignore[attr-defined]
            self.dismiss(chosen)
            return
        if event.key == "escape":
            event.stop()
            self.app.apply_theme(self.original)  # type: ignore[attr-defined]
            self.dismiss(self.original)
        elif event.key == "enter":
            event.stop()
            chosen = self._selected_theme_name()
            self.app.apply_theme(chosen)  # type: ignore[attr-defined]
            self.dismiss(chosen)


class SearchModal(ModalScreen):
    """Interactive global search modal (Ctrl+F or /)."""

    DEFAULT_CSS = """
    SearchModal {
        align: center middle;
    }
    #search-box {
        width: 80%;
        height: 80%;
        border: round $accent;
        background: $surface;
        padding: 1 2;
    }
    #search-input {
        margin-bottom: 1;
    }
    #search-results {
        height: 1fr;
        border: solid $surface-lighten-1;
        background: $background;
    }
    #search-status {
        height: 1;
        margin-top: 1;
        color: $text-muted;
    }
    """

    def __init__(self, store: Any, on_select: Optional[Callable[[SearchMatch], None]] = None) -> None:
        super().__init__()
        self.store = store
        self.on_select = on_select
        self.matches: List[SearchMatch] = []
        self._debounce_timer: Any = None

    def compose(self) -> ComposeResult:
        with Vertical(id="search-box"):
            yield Label(
                f"[bold {current_palette().accent}]SEARCH WORKSHEET[/]"
                f" [{current_palette().muted}](↑↓ / j·k move, Enter copy & close, y copy, Esc close)[/]"
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
        match = self._selected_match()
        if match is not None:
            self._copy(match)
            self.dismiss(match)

    def _copy(self, match: SearchMatch) -> None:
        val = match.title or match.snippet
        copy_to_clipboard(val)
        self.notify(f"Copied: {val}")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        if self._debounce_timer is not None:
            self._debounce_timer.stop()
            self._debounce_timer = None
            self._perform_search(self.query_one("#search-input", Input).value.strip())
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
        if self._debounce_timer is not None:
            self._debounce_timer.stop()
        query = event.value.strip()
        self._debounce_timer = self.set_timer(0.05, lambda: self._perform_search(query))

    def _perform_search(self, query: str) -> None:
        self._debounce_timer = None
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
            txt.append(f"[{m.entity_type.upper()}] ", style=S("accent"))
            if m.target_ip:
                txt.append(f"{m.target_ip} ", style=S("warn"))
            txt.append(f"{m.title} — ", style=S("text"))
            txt.append(m.snippet, style=S("muted", bold=False))
            results_view.append(DataListItem(data_obj=m, display_text=txt))


class BaseFormModal(ModalScreen[Optional[dict]]):
    """Reusable base for data-capture modals with unified button handling and Esc/Enter behavior."""

    DEFAULT_CSS = """
    BaseFormModal {
        align: center middle;
    }
    BaseFormModal Input {
        height: 3;
        border: round $border;
        background: $background;
        color: $foreground;
        padding: 0 1;
    }
    BaseFormModal Input:focus {
        border: round $accent;
    }
    """

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
        self.dismiss(None)


class AddTargetModal(BaseFormModal):
    """Fast modal for creating a target host with OS dropdown and preset ports."""

    DEFAULT_CSS = BaseFormModal.DEFAULT_CSS + """
    #add-target-container {
        width: 74;
        height: auto;
        max-height: 92%;
        border: round $accent;
        background: $surface;
        padding: 1 2;
        color: $foreground;
    }
    AddTargetModal .modal-row {
        height: auto;
        layout: horizontal;
        margin-bottom: 0;
    }
    AddTargetModal .modal-col {
        width: 1fr;
        height: auto;
        margin-right: 1;
    }
    AddTargetModal .modal-col:last-child {
        margin-right: 0;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="add-target-container", classes="synapse-modal-dialog"):
            yield Label("▸ ADD TARGET HOST", classes="modal-header")

            with Horizontal(classes="modal-row"):
                with Vertical(classes="modal-col"):
                    yield Label("Target IP / Hostname *:", classes="field-label")
                    yield Input(placeholder="e.g. 10.10.11.10", id="target-ip")
                with Vertical(classes="modal-col"):
                    yield Label("FQDN / NetBIOS (optional):", classes="field-label")
                    yield Input(placeholder="e.g. dc01.corp.local", id="target-host")

            with Horizontal(classes="modal-row"):
                with Vertical(classes="modal-col"):
                    yield Label("Operating System:", classes="field-label")
                    yield Select(
                        [
                            ("Linux (Debian / Kali / Ubuntu)", "Linux"),
                            ("Windows Server / Active Directory", "Windows Server"),
                            ("Windows Workstation", "Windows"),
                            ("FreeBSD / Unix", "FreeBSD"),
                            ("Embedded / Network Device", "Embedded"),
                            ("Unknown / Other", "Unknown"),
                        ],
                        value="Linux",
                        id="target-os",
                    )
                with Vertical(classes="modal-col"):
                    yield Label("Initial Ports Preset:", classes="field-label")
                    yield Select(
                        [
                            ("None / Custom", ""),
                            ("Web Standard (80, 443)", "80,443"),
                            ("Web & SSH (22, 80, 443, 8080)", "22,80,443,8080"),
                            ("Active Directory (53, 88, 135, 389, 445)", "53,88,135,389,445"),
                            ("Top Common (21,22,25,80,443,445,3389)", "21,22,25,80,443,445,3389"),
                        ],
                        value="",
                        id="target-ports-preset",
                    )

            with Horizontal(classes="modal-row"):
                with Vertical(classes="modal-col"):
                    yield Label("Custom Ports (optional):", classes="field-label")
                    yield Input(placeholder="e.g. 22, 80, 445", id="target-ports-custom")
                with Vertical(classes="modal-col"):
                    yield Label("Target Notes (optional):", classes="field-label")
                    yield Input(placeholder="e.g. In-scope lab machine", id="target-notes")

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
        border: round $accent;
        background: $surface;
        padding: 1 2;
        color: $foreground;
    }
    AddServiceModal Input {
        height: 3;
        border: round $border;
        background: $background;
        color: $foreground;
        padding: 0 1;
    }
    AddServiceModal Input:focus {
        border: round $accent;
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
                    ("— not rated —", ""),
                    ("HIGH (Direct RCE / Credentials / Easy Win)", "HIGH"),
                    ("MED (Enumeration / Brute-force)", "MED"),
                    ("LOW (Informational / Hardened)", "LOW"),
                ],
                value="",
                id="svc-potential",
            )

            yield Label("Command Recipe / Note:", classes="field-label")
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
                if not derive_guidance_enabled():
                    # Exam-safe: don't auto-fill a rating or a next command.
                    return
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
        pot = str(self.query_one("#svc-potential", Select).value or "")
        nxt = self.query_one("#svc-next", Input).value.strip()

        self.dismiss({
            "port": port,
            "protocol": proto,
            "service": name,
            "version": ver,
            "potential": pot,
            "next": nxt,
        })


class AddCredentialModal(BaseFormModal):
    """Fast credential recording dialog with service scope and credential type pickers."""

    DEFAULT_CSS = BaseFormModal.DEFAULT_CSS + """
    #add-cred-container {
        width: 68;
        height: auto;
        max-height: 90%;
        border: round $accent;
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


class AddFindingModal(BaseFormModal):
    """Fast finding dialog with category presets and severity dropdown."""

    DEFAULT_CSS = BaseFormModal.DEFAULT_CSS + """
    #add-finding-container {
        width: 68;
        height: auto;
        max-height: 90%;
        border: round $accent;
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
            P = current_palette()
            yield Label(f"[bold {P.accent}]CYB0X-S WORKSHEET — KEYBOARD REFERENCE[/bold {P.accent}]\n")
            with VerticalScroll():
                text = f"""
[bold]Key Design Principle:[/bold]
The human decides and performs the security-testing actions. CYB0X-S records and organizes them.
Pure passive recording • Local-first SQLite store • Zero background scanning or AI.

[bold]Stations:[/bold]
  [{P.accent}]1[/]  Cockpit       attack surface, services, methodology, notes — one screen
  [{P.accent}]2[/]  Playbooks     offline command reference (Enter copies)
  [{P.accent}]3[/]  Credentials   full vault, reveal / copy, spray targets
  [{P.accent}]4[/]  Loot & Flags  user/root flags, foothold, rabbit holes

[bold]Cockpit layout:[/bold]
  The status strip under the header answers the four exam questions at a glance:
  which box, what is captured, what to do next, what is blocking me.
  The bottom console always shows the command for the highlighted row and
  doubles as the fast-capture bar. Press [{P.accent}]?[/] any time — or [{P.accent}]T[/] to change theme.

[bold]Navigation:[/bold]
  [{P.accent}]Tab / Shift+Tab[/]  : Move focus between panels
  [{P.accent}]j / k  (or ↑ / ↓)[/] : Move down / up inside the focused list or tree
  [{P.accent}]z[/]                : Zoom the focused panel, press again to restore
  [{P.accent}]Esc[/]              : Close any dialog

[bold]Working with the highlighted item:[/bold]
  [{P.accent}]Enter[/]            : Copy the ready-to-paste command / recipe
  [{P.accent}]y[/]                : Copy the value (IP, IP:port, secret, note text)
  [{P.accent}]Space[/]            : Cycle checklist status (TODO → CHECKED → DEFERRED → DEAD-END)
                     or reveal / re-mask a credential
  [{P.accent}]d[/]                : Delete it (asks for confirmation)

[bold]Capture & Modals:[/bold]
  [{P.accent}]t[/]  add target modal         [{P.accent}]s[/]  add service modal    [{P.accent}]f[/]  add finding modal
  [{P.accent}]c[/]  add credential modal     [{P.accent}]n[/]  add note modal       [{P.accent}]K[/]  (shift+k) checklist item
  [{P.accent}]m[/]  methodology templates    [{P.accent}]g[/]  record flags         [{P.accent}]r[/]  cheat sheet
  [{P.accent}]T[/]  (shift+t) theme picker   [{P.accent}]o[/]  toggle scope         [{P.accent}]/[/] or [{P.accent}]Ctrl+F[/] search
  [{P.accent}]?[/]  this help modal          [{P.accent}]q[/]  quit app

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


class TemplateSelectionModal(ModalScreen[Any]):
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
            P = current_palette()
            yield Label(
                f"[bold {P.accent}]METHODOLOGY CHECKLIST TEMPLATES[/bold {P.accent}]"
                f" [{P.muted}](Standard Assessment Workflows)[/]"
            )
            yield Label(
                f"[{P.muted}]Select a template:[/] [bold {P.accent}]Enter[/] [{P.muted}]to switch/replace checklist  • [/] "
                f"[bold {P.accent}]a[/] [{P.muted}]to append items  • [/] [bold {P.accent}]Esc[/] [{P.muted}]to cancel[/]"
            )
            yield ListView(id="template-list")
            with Horizontal(id="btn-bar"):
                yield Button("Switch Methodology (Enter)", variant="primary", id="btn-switch")
                yield Button("Append Items (a)", variant="default", id="btn-append")
                yield Button("Cancel (Esc)", variant="default", id="btn-cancel")

    def on_mount(self) -> None:
        from cyb0x_s.templates import STATIC_TEMPLATES

        t_list = self.query_one("#template-list", ListView)
        for key, tmpl in STATIC_TEMPLATES.items():
            txt = Text()
            txt.append(f"{key.upper():<16} ", style=S("accent"))
            txt.append(f"({len(tmpl['items'])} items)  ", style=S("warn"))
            txt.append(f"{tmpl['description']}", style=S("muted", bold=False))
            t_list.append(DataListItem(data_obj=key, display_text=txt))
        t_list.focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-switch":
            self._select_current(replace=True)
        elif event.button.id == "btn-append":
            self._select_current(replace=False)
        else:
            self.dismiss(None)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if isinstance(event.item, DataListItem):
            self.dismiss((event.item.data_obj, True))

    def _select_current(self, replace: bool = True) -> None:
        t_list = self.query_one("#template-list", ListView)
        if t_list.highlighted_child and isinstance(t_list.highlighted_child, DataListItem):
            self.dismiss((t_list.highlighted_child.data_obj, replace))
        else:
            self.dismiss(None)

    def on_key(self, event: Any) -> None:
        if event.key == "escape":
            self.dismiss(None)
        elif event.key == "enter":
            self._select_current(replace=True)
        elif event.key in ("a", "A"):
            self._select_current(replace=False)


class ReferenceModal(ModalScreen[Optional[str]]):
    """Searchable command reference and penetration testing playbook modal."""

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
            P = current_palette()
            yield Label(
                f"[bold {P.accent}]📖 eJPTv2 CHEAT SHEET & COMMAND REFERENCE[/bold {P.accent}]"
                f" [{P.muted}](Offline Playbook)[/]"
            )
            yield Label(
                f"[{P.muted}]Target IP: [bold {P.text}]{self.target_ip or 'None'}[/bold {P.text}]"
                f" • Type to filter, Enter to copy command, Esc to exit[/]"
            )
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
                txt.append(f"[{item['category']}] ", style=S("warn"))
                txt.append(f"{item['title']}\n", style=S("text"))
                txt.append(f"  ❯ {item['command']}\n", style=S("warn"))
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


class AddExamProofModal(ModalScreen[Optional[dict]]):
    """Dialog to record an assessment question proof / evidence."""

    DEFAULT_CSS = """
    AddExamProofModal {
        align: center middle;
    }
    #add-proof-container {
        width: 74;
        height: auto;
        border: round $accent;
        background: $surface;
        padding: 1 2;
    }
    .proof-hdr {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }
    """

    def __init__(self, target_ip: str = "", default_q: str = "Q1", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.target_ip = target_ip
        self.default_q = default_q

    def compose(self) -> ComposeResult:
        with Vertical(id="add-proof-container"):
            yield Label("📝 RECORD QUESTION PROOF / EVIDENCE", classes="proof-hdr")
            with Horizontal(classes="modal-row"):
                with Vertical(classes="modal-col"):
                    yield Label("Question / Item ID (e.g. Q1, Item-1):", classes="field-label")
                    yield Input(value=self.default_q, placeholder="e.g. Q1", id="proof-q")
                with Vertical(classes="modal-col"):
                    yield Label("Proof Category:", classes="field-label")
                    yield Select(
                        [
                            ("Captured Flag (User / Root)", "FLAG"),
                            ("Password Hash / Secret", "HASH"),
                            ("Discovered Password / Cred", "CREDENTIAL"),
                            ("Service / Software Version", "VERSION"),
                            ("Hidden Path / Directory", "FILE"),
                            ("Other Lab Evidence", "OTHER"),
                        ],
                        value="FLAG",
                        id="proof-cat",
                    )
            with Vertical(classes="modal-row"):
                yield Label("Proof / Extracted Value:", classes="field-label")
                yield Input(placeholder="e.g. flag{...} or root hash or service version", id="proof-val")
            with Vertical(classes="modal-row"):
                yield Label("Context / Methodology Notes:", classes="field-label")
                yield Input(placeholder="e.g. Discovered via anonymous FTP / shadow file", id="proof-notes")
            with Horizontal(classes="modal-buttons"):
                yield Button("Save Proof (Enter)", variant="primary", classes="primary-btn", id="btn-save")
                yield Button("Cancel (Esc)", id="btn-cancel")

    def on_mount(self) -> None:
        self.query_one("#proof-val", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-save":
            self.submit_data()
        elif event.button.id == "btn-cancel":
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.submit_data()

    def submit_data(self) -> None:
        q_val = self.query_one("#proof-q", Input).value.strip()
        val_val = self.query_one("#proof-val", Input).value.strip()
        if not q_val or not val_val:
            return
        cat_val = str(self.query_one("#proof-cat", Select).value or "FLAG")
        notes_val = self.query_one("#proof-notes", Input).value.strip()
        self.dismiss({
            "question_num": q_val if q_val.upper().startswith("Q") or not q_val.isdigit() else f"Q{q_val}",
            "category": cat_val,
            "answer_proof": val_val,
            "notes": notes_val,
        })

    def on_key(self, event: Any) -> None:
        if event.key == "escape":
            self.dismiss(None)


__all__ = [
    "ConfirmModal",
    "ThemeSwatch",
    "ThemePickerModal",
    "SearchModal",
    "BaseFormModal",
    "AddTargetModal",
    "AddServiceModal",
    "AddCredentialModal",
    "AddFindingModal",
    "AddExamProofModal",
    "FastInputModal",
    "HelpModal",
    "TemplateSelectionModal",
    "ReferenceModal",
]
