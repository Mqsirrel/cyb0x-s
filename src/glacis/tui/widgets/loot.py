"""Station 3 credential spray matrix and Station 4 loot/flags/proof ledger."""

from __future__ import annotations

import shlex
from typing import Any, Dict, List, Optional, Set

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, Label, ListView, Static

from glacis.models import Credential, Service, Target
from glacis.services_meta import AUTH_SERVICE_NAMES, AUTH_SERVICE_PORTS
from glacis.tui import widgets as _pkg
from glacis.tui.theme import GLYPHS as G, current_palette
from glacis.tui.widgets.chrome import set_border_text
from glacis.tui.widgets.lists import DataListItem, elide, keycap_line

__all__ = [
    "AUTH_SERVICE_NAMES",
    "AUTH_SERVICE_PORTS",
    "compile_spray_command",
    "CredentialMatrixWidget",
    "LootAndFlagsWidget",
]


class LootAndFlagsWidget(Static):
    """Dedicated status dashboard for Flags, Foothold proofs, and Failure Log."""

    DEFAULT_CSS = """
    LootAndFlagsWidget {
        height: 1fr;
        layout: vertical;
        padding: 0 1;
    }
    #loot-cards-container {
        height: 9;
        layout: horizontal;
        margin-bottom: 1;
    }
    .loot-box {
        width: 1fr;
        height: 9;
        border: solid $border;
        border-title-color: $text-soft;
        border-title-style: bold;
        border-subtitle-color: $text-muted;
        border-subtitle-align: right;
        background: $surface;
        padding: 0 1;
        margin-right: 1;
    }
    .loot-box:last-child {
        margin-right: 0;
    }
    .loot-box:focus-within {
        border: double $accent;
        border-title-color: $accent;
        border-subtitle-color: $accent;
    }
    #loot-lower-container {
        height: 1fr;
        layout: horizontal;
    }
    .loot-lower-box {
        width: 1fr;
        height: 1fr;
        border: solid $border;
        border-title-color: $text-soft;
        border-title-style: bold;
        border-subtitle-color: $text-muted;
        border-subtitle-align: right;
        background: $surface;
        padding: 0;
        margin-right: 1;
    }
    .loot-lower-box:last-child {
        margin-right: 0;
    }
    .loot-lower-box:focus-within {
        border: double $accent;
        border-title-color: $accent;
        border-subtitle-color: $accent;
    }
    .loot-title {
        display: none;
    }
    /* The per-panel hint line used to be composed and then hidden, which left
       three tall panels with no explanation of what belongs in them. Pinned to
       the panel floor it doubles as the legend and the empty-state guide. */
    .loot-sub {
        height: 2;
        padding: 0 1;
        color: $text-muted;
        border-top: solid $border;
    }
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.target: Optional[Target] = None

    def on_mount(self) -> None:
        """Ensure Loot & Flags data is populated as soon as the station is mounted."""
        try:
            # One glyph per concept: ★ is "flag captured", ▲ is "escalation",
            # ▼ is "rabbit hole". Re-using ★ for two different cards (as it
            # did) forces the reader to disambiguate by text alone.
            _titles = {
                "#loot-flags-box": (f" {G['loot']} OBJECTIVES & CAPTURED FLAGS ", " [g: Flags] "),
                "#loot-foothold-box": (f" {G['host_foothold']} INITIAL FOOTHOLD & EXPLOIT ", " [:foothold] "),
                "#loot-privesc-box": (f" {G['warn']} PRIVILEGE ESCALATION & ROOT ", " [:privesc] "),
                "#loot-evidence-box": (f" {G['credentials']} QUESTION & EVIDENCE PROOFS ", " [a: Add · e: Export] "),
                "#loot-files-box": (f" {G['notes']} DISK LOOT & EVIDENCE FILES ", " [Space: View · v: Paste] "),
                "#loot-failure-box": (f" ▼ RABBIT HOLES & BREAKTHROUGHS ", " [:stuck · :clue] "),
            }
            for selector, (title, sub) in _titles.items():
                set_border_text(self.query_one(selector, Vertical), title=title, subtitle=sub)
        except Exception:
            pass

        if hasattr(self.app, "store"):
            try:
                active = self.app.store.get_active_target()
                failures = self.app.store.list_failure_logs(target_id=active.id if active else None)
                proofs = self.app.store.list_exam_proofs()
                self.update_data(active, failures, proofs=proofs)
            except Exception:
                pass

    def compose(self) -> ComposeResult:
        with Horizontal(id="loot-cards-container"):
            with Vertical(id="loot-flags-box", classes="loot-box"):
                yield Label("OBJECTIVES & CAPTURED FLAGS", classes="loot-title")
                yield Static(id="loot-flags-content")
            with Vertical(id="loot-foothold-box", classes="loot-box"):
                yield Label("INITIAL FOOTHOLD & EXPLOIT", classes="loot-title")
                yield Static(id="loot-foothold-content")
            with Vertical(id="loot-privesc-box", classes="loot-box"):
                yield Label("PRIVILEGE ESCALATION & ROOT PROOF", classes="loot-title")
                yield Static(id="loot-privesc-content")
        with Horizontal(id="loot-lower-container"):
            with Vertical(id="loot-evidence-box", classes="loot-lower-box"):
                yield Label("QUESTION & EVIDENCE PROOFS", classes="loot-title")
                yield ListView(id="loot-evidence-list")
                yield Static(keycap_line(("a", "add proof"), ("e", "export"), ("Enter", "copy")),
                             classes="loot-sub")
            with Vertical(id="loot-files-box", classes="loot-lower-box"):
                yield Label("DISK LOOT & EVIDENCE FILES", classes="loot-title")
                yield ListView(id="loot-files-list")
                yield Static(keycap_line(("Enter", "copy path"), ("Space", "preview"), ("v", "paste")),
                             classes="loot-sub")
            with Vertical(id="loot-failure-box", classes="loot-lower-box"):
                yield Label("RABBIT HOLES & BREAKTHROUGHS", classes="loot-title")
                yield ListView(id="loot-failure-list")
                yield Static(keycap_line(("Space", "cycle"), (":stuck <where>", "log it"),
                                        (":clue <breakthrough>", "log it")),
                             classes="loot-sub")

    def update_data(
        self,
        target: Optional[Target],
        failures: List[Any],
        proofs: Optional[List[Any]] = None,
    ) -> None:
        self.target = target
        P = current_palette()

        # Flags Card
        f_txt = Text()
        if target:
            if target.user_flag:
                f_txt.append(" [✓ CAPTURED] ", style=f"bold {P.bg} on {P.ok}")
                f_txt.append(" USER FLAG:\n", style=f"bold {P.text}")
                f_txt.append(f" ❯ {target.user_flag}\n\n", style=f"bold {P.ok}")
            else:
                f_txt.append(" [· PENDING]  ", style=f"bold {P.bg} on {P.muted}")
                f_txt.append(" USER FLAG:\n", style=f"bold {P.text}")
                f_txt.append(" ❯ <NOT CAPTURED YET>\n\n", style="dim italic")

            if target.root_flag:
                f_txt.append(" [★ ROOT CAPTURED] ", style=f"bold {P.bg} on {P.accent}")
                f_txt.append(" ROOT FLAG:\n", style=f"bold {P.text}")
                f_txt.append(f" ❯ {target.root_flag}\n", style=f"bold {P.accent}")
            else:
                f_txt.append(" [· PENDING]  ", style=f"bold {P.bg} on {P.muted}")
                f_txt.append(" ROOT FLAG:\n", style=f"bold {P.text}")
                f_txt.append(" ❯ <NOT CAPTURED YET>\n", style="dim italic")
        else:
            f_txt.append("\n  • No active target selected.\n  • Press 't' to add a target machine or switch with [ / ].", style="dim italic")
        self.query_one("#loot-flags-content", Static).update(f_txt)

        # Foothold Card
        fh_txt = Text()
        if target and (target.initial_access_vuln or target.foothold_cmd):
            if target.initial_access_vuln:
                fh_txt.append(" [VULN] ", style=f"bold {P.bg} on {P.danger}")
                fh_txt.append(f" {target.initial_access_vuln}\n", style=f"bold {P.text}")
            if target.foothold_context:
                fh_txt.append(" [VECT] ", style=f"bold {P.bg} on {P.accent}")
                fh_txt.append(f" {target.foothold_context}\n", style=f"bold {P.text_soft}")
            if target.foothold_cmd:
                fh_txt.append(" [CMD]  ", style=f"bold {P.bg} on {P.warn}")
                fh_txt.append(f" ❯ {target.foothold_cmd}", style=f"bold {P.warn}")
        else:
            fh_txt.append("\n  • No foothold recorded yet.\n  • :foothold <vuln> records it.", style="dim italic")
        self.query_one("#loot-foothold-content", Static).update(fh_txt)

        # PrivEsc Card
        pe_txt = Text()
        if target and (target.privesc_vector or target.root_proof):
            if target.privesc_vector:
                pe_txt.append(" [VECT] ", style=f"bold {P.bg} on {P.warn}")
                pe_txt.append(f" {target.privesc_vector}\n", style=f"bold {P.text}")
            proof = target.root_proof or "whoami && id && ip a"
            pe_txt.append(" [ROOT] ", style=f"bold {P.bg} on {P.ok}")
            pe_txt.append(f" ❯ {proof}", style=f"bold {P.accent}")
        else:
            pe_txt.append("\n  • No PrivEsc recorded yet.\n  • :privesc <vector> records it.", style="dim italic")
        self.query_one("#loot-privesc-content", Static).update(pe_txt)

        # Question Proofs List
        p_list = self.query_one("#loot-evidence-list", ListView)
        p_list.clear()
        if proofs is None and hasattr(self.app, "store"):
            try:
                proofs = self.app.store.list_exam_proofs()
            except Exception:
                proofs = []
        if proofs:
            def sort_key(p: Any) -> tuple[int, str]:
                q = getattr(p, "question_num", "").lstrip("Qq")
                return (int(q) if q.isdigit() else 9999, getattr(p, "question_num", ""))

            for p in sorted(proofs, key=sort_key):
                txt = Text()
                txt.append(f"[{p.question_num}] ", style=f"bold {P.bg} on {P.accent}")
                txt.append(f"[{p.category}] ", style=f"bold {P.bg} on {P.warn}")
                txt.append(f" {p.answer_proof}\n", style=f"bold {P.ok}")
                if p.notes:
                    txt.append(f"   • {p.notes}", style="dim italic")
                p_list.append(DataListItem(data_obj=p.answer_proof, display_text=txt))
        else:
            txt = Text()
            txt.append("  [+ PROOF]  ", style=f"bold {P.bg} on {P.accent}")
            txt.append("Press 'a' or :q <num> <proof>\n", style=f"bold {P.text}")
            txt.append("  [▸ EXPORT] ", style=f"bold {P.bg} on {P.warn}")
            txt.append("Press 'e' to export exam report", style=f"{P.muted}")
            p_list.append(DataListItem(data_obj=None, display_text=txt, is_placeholder=True))

        # Disk Loot & Evidence Files List
        f_list = self.query_one("#loot-files-list", ListView)
        f_list.clear()
        disk_files = []
        if hasattr(self.app, "store"):
            from pathlib import Path
            ws = self.app.store.get_active_workspace()
            ws_root = Path(ws.root_path).resolve() if ws and ws.root_path else Path.cwd()
            for sub in ("loot", "screenshots", "enum", "scans"):
                d = ws_root / sub
                if d.is_dir():
                    try:
                        for f in d.iterdir():
                            if f.is_file():
                                disk_files.append((sub, f))
                    except (PermissionError, OSError):
                        pass

        if disk_files:
            disk_files.sort(key=lambda x: x[1].stat().st_mtime, reverse=True)
            for sub, fp in disk_files:
                st = fp.stat()
                size_str = f"{st.st_size} B" if st.st_size < 1024 else f"{st.st_size / 1024.0:.1f} KB"
                rel = f"{sub}/{fp.name}"
                txt = Text()
                folder_bg = P.accent if sub == "loot" else (P.ok if sub == "screenshots" else P.warn)
                txt.append(f"[{sub.upper()}] ", style=f"bold {P.bg} on {folder_bg}")
                txt.append(f" {fp.name} ", style=f"bold {P.text}")
                txt.append(f"[{size_str}]\n", style=f"{P.muted}")
                txt.append("   ❯ Enter: Copy path · Space: Preview", style="dim italic")
                f_list.append(DataListItem(data_obj=rel, display_text=txt))
        else:
            txt = Text()
            txt.append("  [LOOT DIR] ", style=f"bold {P.bg} on {P.accent}")
            txt.append("No files in loot/ or screenshots/\n", style=f"bold {P.text}")
            txt.append("  [▸ PASTE]  ", style=f"bold {P.bg} on {P.ok}")
            txt.append("Press 'v' to paste from clipboard", style=f"{P.muted}")
            f_list.append(DataListItem(data_obj=None, display_text=txt, is_placeholder=True))

        # Failure Log List
        fail_list = self.query_one("#loot-failure-list", ListView)
        fail_list.clear()
        if failures:
            for fl in failures:
                txt = Text()
                txt.append("[✖ DEAD-END] ", style=f"bold {P.bg} on {P.danger}")
                txt.append(f" {fl.where_stuck}\n", style=f"bold {P.text}")
                if fl.breakthrough_clue:
                    txt.append("   [✓ CLUE] ", style=f"bold {P.bg} on {P.ok}")
                    txt.append(f" {fl.breakthrough_clue}\n", style=f"bold {P.ok}")
                if fl.rule_for_next_time:
                    txt.append("   [• RULE] ", style=f"bold {P.bg} on {P.accent}")
                    txt.append(f" {fl.rule_for_next_time}", style="dim italic")
                fail_list.append(DataListItem(data_obj=fl, display_text=txt))
        else:
            txt = Text()
            txt.append("  [+ DEAD-END] ", style=f"bold {P.bg} on {P.danger}")
            txt.append("Type :stuck <where/why>\n", style=f"bold {P.text}")
            txt.append("  [+ CLUE]     ", style=f"bold {P.bg} on {P.ok}")
            txt.append("Type :clue <breakthrough>", style=f"{P.muted}")
            fail_list.append(DataListItem(data_obj=None, display_text=txt, is_placeholder=True))

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.list_view.id == "loot-evidence-list" and isinstance(event.item, DataListItem):
            if event.item.data_obj and not event.item.is_placeholder:
                _pkg.copy_to_clipboard(str(event.item.data_obj))
                if hasattr(self.app, "notify"):
                    self.app.notify(f"Copied proof: {event.item.data_obj}")
        elif event.list_view.id == "loot-files-list" and isinstance(event.item, DataListItem):
            if event.item.data_obj and not event.item.is_placeholder:
                _pkg.copy_to_clipboard(str(event.item.data_obj))
                if hasattr(self.app, "notify"):
                    self.app.notify(f"Copied file path: {event.item.data_obj}")

    def on_key(self, event: Any) -> None:
        if event.key == "a":
            self.action_add_proof()
            event.stop()
        elif event.key == "e":
            self.action_export_proofs()
            event.stop()
        elif event.key in ("v", "V"):
            if hasattr(self.app, "execute_command"):
                from glacis.tui.commands import execute_command
                execute_command(self.app, ":paste-ev")
            event.stop()
        elif event.key == "space":
            f_list = self.query_one("#loot-files-list", ListView)
            if f_list.has_focus and f_list.highlighted_child and isinstance(f_list.highlighted_child, DataListItem):
                item = f_list.highlighted_child
                if item.data_obj and not item.is_placeholder:
                    from pathlib import Path

                    from glacis.tui.modals import LootPreviewModal
                    ws = self.app.store.get_active_workspace()
                    ws_root = Path(ws.root_path).resolve() if ws and ws.root_path else Path.cwd()
                    full_p = ws_root / str(item.data_obj)
                    self.app.push_screen(LootPreviewModal(full_p))
                    event.stop()

    def action_add_proof(self) -> None:
        from glacis.tui.modals import AddExamProofModal

        def on_proof_submitted(data: Optional[dict]) -> None:
            if data and hasattr(self.app, "store"):
                tgt_id = self.target.id if self.target else None
                self.app.store.add_exam_proof(
                    question_num=data["question_num"],
                    answer_proof=data["answer_proof"],
                    category=data["category"],
                    notes=data["notes"],
                    target_id=tgt_id,
                )
                if hasattr(self.app, "refresh_loot_widget"):
                    self.app.refresh_loot_widget()
                if hasattr(self.app, "notify"):
                    self.app.notify(f"Recorded {data['question_num']} proof!")

        tip = self.target.ip if self.target else ""
        self.app.push_screen(AddExamProofModal(target_ip=tip), callback=on_proof_submitted)

    def action_export_proofs(self) -> None:
        if hasattr(self.app, "store"):
            from pathlib import Path
            md = self.app.store.export_exam_evidence_markdown()
            out_file = Path("exam_evidence.md")
            out_file.write_text(md, encoding="utf-8")
            if hasattr(self.app, "notify"):
                self.app.notify(f"Exported exam evidence to {out_file.resolve()}")


def compile_spray_command(user: str, secret: str, service: str, ip: str, port: int) -> str:
    """Generate ready-to-run credential verification or lateral spray command."""
    s_low = service.strip().lower()
    clean_u = shlex.quote(user.strip())
    clean_p = shlex.quote(secret.strip())
    if s_low in ("smb", "microsoft-ds", "netbios-ssn") or port in (139, 445):
        return f"netexec smb {ip} -u {clean_u} -p {clean_p}"
    elif s_low == "ssh" or port == 22:
        return f"sshpass -p {clean_p} ssh -o StrictHostKeyChecking=no {clean_u}@{ip}"
    elif s_low in ("winrm", "wsman") or port in (5985, 5986):
        return f"evil-winrm -i {ip} -u {clean_u} -p {clean_p}"
    elif s_low in ("rdp", "ms-wbt-server") or port == 3389:
        return f"xfreerdp /u:{clean_u} /p:{clean_p} /v:{ip} /cert:ignore /smart-sizing"
    elif s_low in ("mssql", "ms-sql-s") or port == 1433:
        return f"netexec mssql {ip} -u {clean_u} -p {clean_p}"
    elif s_low in ("mysql",) or port == 3306:
        return f"mysql -h {ip} -u {clean_u} -p{clean_p}"
    elif s_low in ("ftp",) or port == 21:
        return f"hydra -l {clean_u} -p {clean_p} ftp://{ip}"
    elif s_low in ("http", "https", "web") or port in (80, 443, 8080):
        proto = "https" if port == 443 or "https" in s_low else "http"
        return f"curl -s -u {clean_u}:{clean_p} -I {proto}://{ip}:{port}/"
    return f"# Test credential {clean_u}:{clean_p} against {ip}:{port} ({service})"


class CredentialMatrixWidget(Static):
    """Interactive 2D matrix of discovered credentials, lateral movement targets, and verification states."""

    DEFAULT_CSS = """
    CredentialMatrixWidget {
        height: 1fr;
        layout: vertical;
        padding: 0 1;
    }
    #cred-matrix-top-bar {
        height: 1;
        layout: horizontal;
        margin-bottom: 1;
        padding: 0 1;
    }
    #cred-matrix-hdr {
        width: 1fr;
        height: 1;
    }
    #cred-matrix-sub {
        width: auto;
        height: 1;
        color: $text-muted;
        text-align: right;
    }
    #cred-matrix-panel {
        height: 1fr;
        border: solid $border;
        border-title-color: $text-soft;
        border-title-style: bold;
        border-subtitle-color: $accent;
        border-subtitle-align: right;
        background: $surface;
    }
    #cred-matrix-panel:focus-within {
        border: double $accent;
        border-title-color: $accent;
        border-subtitle-color: $accent;
    }
    #cred-matrix-table {
        height: 1fr;
        border: none;
        background: transparent;
    }
    #cred-matrix-empty {
        height: 1fr;
        border: solid $border;
        border-title-color: $text-soft;
        border-title-style: bold;
        background: $surface;
        padding: 1 3;
        display: none;
    }
    """

    CELL_CYCLE = ["○ UNTESTED", "✔ VALID", "★ PWN3D", "✗ INVALID"]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.credentials: List[Credential] = []
        self.auth_services: List[tuple[Target, Service]] = []
        self.revealed_ids: Set[int] = set()
        self.cell_states: Dict[tuple[int, int], str] = {}

    def on_mount(self) -> None:
        """Ensure Credential Matrix data is populated as soon as mounted."""
        try:
            set_border_text(
                self.query_one("#cred-matrix-panel"),
                title=" CREDENTIAL VAULT & LATERAL MOVEMENT MATRIX ",
                subtitle=" [Space: Cycle] · [Enter: Copy Spray Cmd] ",
            )
        except Exception:
            pass
        if hasattr(self.app, "store"):
            try:
                creds = self.app.store.list_credentials()
                targets = self.app.store.list_targets()
                services = self.app.store.list_services()
                self.update_data(creds, targets, services, getattr(self.app, "revealed_creds", set()))
            except Exception:
                pass

    def compose(self) -> ComposeResult:
        with Horizontal(id="cred-matrix-top-bar"):
            yield Label("", id="cred-matrix-hdr")
            yield Label("", id="cred-matrix-sub")
        yield Static(id="cred-matrix-empty")
        with Vertical(id="cred-matrix-panel"):
            table = DataTable(id="cred-matrix-table", cursor_type="cell")
            table.zebra_stripes = True
            yield table
            yield Static(id="cred-matrix-legend", classes="panel-legend")

    def _render_empty_guide(self) -> Text:
        P = current_palette()
        t = Text()
        t.append("\n")
        t.append("  ◆ CREDENTIAL SPRAY & LATERAL MOVEMENT MATRIX\n", style=f"bold {P.accent}")
        t.append("  ──────────────────────────────────────────────────────────────────────────────────────────\n", style=f"{P.border}")
        t.append("  This 2D matrix automatically maps discovered credentials against authenticating services\n", style=f"{P.text}")
        t.append("  across all in-scope target machines (SSH, SMB, RDP, WinRM, FTP, databases).\n\n", style=f"{P.text_soft}")
        t.append("  OPERATIONAL WORKFLOW:\n", style=f"bold {P.warn}")
        t.append("  1. Record Credentials:\n", style=f"bold {P.text}")
        t.append("     • Press 'c' to open credential modal, or type in bottom console:\n", style=f"{P.text_soft}")
        t.append("       :c <username:password> [scope]       e.g. :c admin:Summer2024! smb\n", style=f"bold {P.accent}")
        t.append("     • Secrets are masked by default (press [Space] to reveal/mask).\n\n", style=f"{P.muted}")
        t.append("  2. Map Target Services:\n", style=f"bold {P.text}")
        t.append("     • Discover open ports in Station 1 (:s 445 smb, :s 22 ssh, :s 3389 rdp).\n", style=f"{P.text_soft}")
        t.append("     • Every service accepting credentials becomes a matrix column.\n\n", style=f"{P.text_soft}")
        t.append("  3. Test & Track Lateral Movement:\n", style=f"bold {P.text}")
        t.append("     • Move between cells using Arrow keys or j / k / h / l.\n", style=f"{P.text_soft}")
        t.append("     • Press [Space] on any cell to cycle verification state:\n", style=f"{P.text_soft}")
        t.append("       ○ UNTESTED  →  ✔ VALID  →  ★ PWN3D  →  ✗ INVALID\n", style=f"bold {P.ok}")
        t.append("     • Press [Enter] on any cell to compile & copy ready-to-run spray command (netexec, hydra).\n\n", style=f"bold {P.accent}")
        t.append("  [Press 'c' now to record a credential, or press '1' to return to Cockpit]", style="dim italic")
        return t

    def update_data(
        self,
        credentials: List[Credential],
        targets: List[Target],
        services: List[Service],
        revealed_ids: Set[int],
    ) -> None:
        self.credentials = credentials
        self.revealed_ids = revealed_ids
        if hasattr(self.app, "store"):
            try:
                self.cell_states.update(self.app.store.get_cred_validations())
            except Exception:
                pass

        table = self.query_one("#cred-matrix-table", DataTable)
        table.clear(columns=True)

        empty_box = self.query_one("#cred-matrix-empty", Static)

        # Build in-scope authenticating service pairs
        in_scope_targets = {t.id: t for t in targets if t.is_in_scope}
        auth_pairs: List[tuple[Target, Service]] = []
        for s in services:
            t = in_scope_targets.get(s.target_id)
            if t and (s.service.lower() in AUTH_SERVICE_NAMES or s.port in AUTH_SERVICE_PORTS):
                auth_pairs.append((t, s))
        self.auth_services = auth_pairs

        # Summary subtitle & KPI HUD
        tested = sum(1 for c in credentials if (c.status or "").lower() in ("valid", "tested"))
        pwned = sum(
            1 for c in credentials
            if "pwn" in (c.status or "").lower()
            or any("pwn" in (self.cell_states.get((c.id, s.id), "")).lower() for _, s in auth_pairs)
        )

        hdr_label = self.query_one("#cred-matrix-hdr", Label)
        subtitle = self.query_one("#cred-matrix-sub", Label)

        P = current_palette()

        if not credentials:
            hdr_label.update(Text("CREDENTIAL VAULT & LATERAL MOVEMENT MATRIX", style=f"bold {P.accent}"))
            subtitle.update("No credentials recorded yet — press 'c' to add one or :c user:pass [scope]")
            empty_box.styles.display = "block"
            table.styles.display = "none"
            empty_box.update(self._render_empty_guide())
            return

        empty_box.styles.display = "none"
        table.styles.display = "block"

        # KPI Badges
        hdr_txt = Text()
        hdr_txt.append(f" [ ◆ {len(credentials)} CREDS ] ", style=f"bold {P.bg} on {P.accent}")
        hdr_txt.append(" ")
        hdr_txt.append(f" [ ✔ {tested} VALIDATED ] ", style=f"bold {P.bg} on {P.ok}")
        if pwned:
            hdr_txt.append(" ")
            hdr_txt.append(f" [ ★ {pwned} PWN3D ] ", style=f"bold {P.bg} on {P.warn}")
        if auth_pairs:
            hdr_txt.append(" ")
            hdr_txt.append(f" [ ▸ {len(auth_pairs)} SPRAY TARGETS ] ", style=f"bold {P.bg} on {P.raised}")
        hdr_label.update(hdr_txt)

        # The same four keys were printed here, in the panel subtitle and in
        # the console bar. Two of the three go: the panel subtitle and the
        # console are standard furniture on every station, so the matrix keeps
        # only the coverage figure that exists nowhere else.
        covered = sum(
            1
            for c in credentials
            for _, s in auth_pairs
            if self.cell_states.get((c.id, s.id), "○ UNTESTED") != "○ UNTESTED"
        )
        cells = max(len(credentials) * len(auth_pairs), 1)
        sub_text = Text()
        sub_text.append(f"{covered}/{cells} cells tested", style=f"bold {P.text_soft}")
        subtitle.update(sub_text)

        # Setup Table Columns — fixed widths, centred state cells. AutoSized
        # columns let a 9-char "[✔ VALID]" and a 12-char "[○ UNTESTED]" shift
        # every following column, so the header never sat above its data.
        table.add_column("CREDENTIAL (USER : SECRET)", key="cred", width=32)
        if auth_pairs:
            for t, s in auth_pairs:
                col_title = f"{t.ip}:{s.port} {s.service.upper()}"
                table.add_column(elide(col_title, 20), key=f"svc_{s.id}", width=20)
        else:
            table.add_column("SCOPE", key="scope", width=12)
            table.add_column("STATUS", key="status", width=14)
            table.add_column("SOURCE", key="source", width=18)
            table.add_column("LATERAL TARGETS", key="note", width=34)

        # Setup Table Rows
        for c in credentials:
            is_rev = c.id in revealed_ids
            secret = c.secret if is_rev else ("•" * min(max(len(c.secret or "password"), 8), 16))
            scope = c.service_scope.upper() if c.service_scope else "GLOBAL"
            scope_color = P.accent if scope == "GLOBAL" else (P.warn if scope in ("SMB", "WINRM") else P.ok)

            cred_txt = Text()
            cred_txt.append(f"[{scope}] ", style=f"bold {P.bg} on {scope_color}")
            cred_txt.append(f" {c.username} ", style=f"bold {P.text}")
            cred_txt.append(": ", style=f"{P.muted}")
            if is_rev:
                cred_txt.append(f"{secret}", style=f"bold {P.warn}")
            else:
                cred_txt.append(f"{secret}", style=f"{P.muted}")

            if auth_pairs:
                row_vals: List[Any] = [cred_txt]
                for t, s in auth_pairs:
                    state = self.cell_states.get((c.id, s.id))
                    if not state:
                        if (c.service_scope or "").lower() in (s.service.lower(), "global") and (c.status or "").lower() in ("valid", "tested"):
                            state = "✔ VALID"
                        else:
                            state = "○ UNTESTED"
                        self.cell_states[(c.id, s.id)] = state
                    row_vals.append(self._format_state(state))
                table.add_row(*row_vals, key=f"cred_{c.id}")
            else:
                table.add_row(cred_txt, c.service_scope or "GLOBAL", c.status.upper(), c.source or "-", "Add SSH/SMB/RDP in Cockpit to spray", key=f"cred_{c.id}")

        self._paint_legend(auth_pairs)

    def _paint_legend(self, auth_pairs: List[tuple[Target, Service]]) -> None:
        """Pin the cell-state key to the floor of the matrix.

        Without it the reader has to learn four states and two keys by
        trial and error; with it the station explains itself in one line.
        """
        P = current_palette()
        try:
            legend = self.query_one("#cred-matrix-legend", Static)
        except Exception:
            return
        t = Text()
        t.append("CELL ▸ ", style=f"bold {P.accent}")
        for i, state in enumerate(self.CELL_CYCLE):
            if i:
                t.append(" → ", style=f"dim {P.muted}")
            t.append(state, style=f"bold {P.text_soft}")
        t.append("   ", style="")
        t.append_text(keycap_line(("Space", "cycle"), ("Enter", "copy spray"), ("x", "reveal"), ("c", "add cred")))
        if not auth_pairs:
            t.append("\n", style="")
            t.append("No authenticating services recorded yet — add SSH / SMB / RDP / WinRM "
                     "ports in Cockpit to turn this into a spray matrix.", style=f"{P.muted}")
        legend.update(t)

    def _format_state(self, state: str) -> Text:
        P = current_palette()
        # Every pill is padded to the same width: a 9-char [✔ VALID] next to a
        # 12-char [○ UNTESTED] shifts the whole column and breaks the raster.
        txt = Text()
        if "VALID" in state or "✔" in state:
            txt.append(" [✔ VALID]".ljust(14), style=f"bold {P.bg} on {P.ok}")
        elif "PWN" in state or "★" in state:
            txt.append(" [★ PWN3D]".ljust(14), style=f"bold {P.bg} on {P.accent}")
        elif "INVALID" in state or "✗" in state:
            txt.append(" [✗ FAIL]".ljust(14), style=f"bold {P.bg} on {P.danger}")
        else:
            txt.append(" [○ UNTESTED]".ljust(14), style=f"dim {P.muted}")
        return txt

    def on_key(self, event: Any) -> None:
        if event.key == "space":
            self.action_cycle_current_cell()
            event.stop()
        elif event.key == "enter":
            self.action_spray_current_cell()
            event.stop()

    def action_cycle_current_cell(self) -> None:
        """Cycle cell state between UNTESTED -> VALID -> PWN3D -> INVALID."""
        table = self.query_one("#cred-matrix-table", DataTable)
        coord = table.cursor_coordinate
        if not coord or coord.column <= 0 or not self.auth_services:
            return
        row_idx = coord.row
        col_idx = coord.column - 1
        if row_idx < 0 or row_idx >= len(self.credentials) or col_idx < 0 or col_idx >= len(self.auth_services):
            return
        c = self.credentials[row_idx]
        t, s = self.auth_services[col_idx]

        curr = self.cell_states.get((c.id, s.id), "○ UNTESTED")
        try:
            next_idx = (self.CELL_CYCLE.index(curr) + 1) % len(self.CELL_CYCLE)
        except ValueError:
            next_idx = 0
        new_state = self.CELL_CYCLE[next_idx]
        self.cell_states[(c.id, s.id)] = new_state
        table.update_cell_at(coord, self._format_state(new_state))
        if hasattr(self.app, "store") and c.id is not None and s.id is not None:
            try:
                self.app.store.set_cred_validation(c.id, s.id, new_state)
            except Exception:
                pass
        if hasattr(self.app, "notify"):
            self.app.notify(f"{c.username} on {t.ip}:{s.port} -> {new_state}")

    def action_spray_current_cell(self) -> None:
        """Generate and copy spray command for highlighted credential and service."""
        table = self.query_one("#cred-matrix-table", DataTable)
        coord = table.cursor_coordinate
        if not coord or coord.column <= 0 or not self.auth_services:
            return
        row_idx = coord.row
        col_idx = coord.column - 1
        if row_idx < 0 or row_idx >= len(self.credentials) or col_idx < 0 or col_idx >= len(self.auth_services):
            return
        c = self.credentials[row_idx]
        t, s = self.auth_services[col_idx]

        cmd = compile_spray_command(c.username, c.secret, s.service, t.ip, s.port)
        _pkg.copy_to_clipboard(cmd)
        if hasattr(self.app, "notify"):
            self.app.notify(f"Copied spray command: {cmd}")




