"""Mission Deck rev 3 — answers the screenshot audit (IMG_1682/83/84).

Fixes demonstrated:
  * ZERO emoji — every glyph is from the safe set that rendered correctly in
    the real terminal shots (check/cross/arrows/blocks). No more tofu boxes.
  * Flags never elided in the strip — strip shows workspace flag COUNT only;
    full flags live in Intel where there is room for 30+ chars.
  * Notes wrap to two lines instead of clipping at the panel edge.
  * Services panel sized to content; freed rows go to checklist/notes.
  * Vault gains a lower SPRAY QUEUE pane filling the dead space.
  * Credential scope chip widened so [WEB/SSH] never becomes "[We".

Self-contained mock, no cyb0x_s imports. Run:
    uv run python dev/redesign_preview_v3.py
Keys: 1-4 stations . b rail . : palette . enter copy-flash . q quit
"""

from __future__ import annotations

from datetime import timedelta

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import DataTable, Footer, Input, Label, Static, TabbedContent, TabPane, Tree

SERVICES = [
    ("22/tcp", "SSH", "open", "OpenSSH 8.2p1 (password auth allowed)"),
    ("80/tcp", "HTTP", "open", "Apache 2.4.41 (redirects to /login)"),
    ("445/tcp", "SMB", "pwned", "Samba 4.3 (anonymous read access)"),
]

NOTES = [
    ("[!] VULN", "SMB anonymous access enabled [HIGH] — read access to backup share without creds"),
    ("[!] VULN", "HTTP redirects to /login [INFO] — landing page enumeration only"),
    ("[i] NOTE", "backup share contains archive.zip with old site configs and admin credentials"),
    ("[i] NOTE", "archive.zip password cracked with rockyou.txt in under 2 minutes"),
    ("[#] EVID", "evidence/proof_screenshot_01.png — anonymous SMB listing captured"),
]

SPRAY_QUEUE = [
    ("admin", "10.10.10.20:80 (HTTP)", "curl -s -u 'admin:W1nter!2026' -I http://10.10.10.20:80/"),
    ("admin", "172.16.1.50:3306 (MYSQL)", "mysql -h 172.16.1.50 -u admin -p'W1nter!2026'"),
    ("root", "10.10.10.20:445 (SMB)", "netexec smb 10.10.10.20 -u 'root' -p 'R0ck3t!' --shares"),
]

CRED_ROWS = [
    ("[WEB/SSH] admin : ********", "VALID", "o UNTESTED", "PWN3D", "o UNTESTED"),
    ("[SSH]     root  : ********", "VALID", "o UNTESTED", "o UNTESTED", "o UNTESTED"),
]
CRED_COLS = ["CREDENTIAL (USER : SECRET)", "10.10.10.20:22 SSH", "10.10.10.20:80 HTTP", "10.10.10.20:445 SMB", "172.16.1.50:3306 MYSQL"]

FLAGS = [
    ("[U] user.txt", "eJPT{user_flag_7a9e2b104c81f}", "captured 14:02"),
    ("[R] root.txt", "eJPT{root_flag_f04b8d195ae32}", "captured 15:47"),
]

PROOFS = [
    ("Q7  [CRED]", "dbpass: R0ck3t_L4unch!#2024 — /var/www/html/wp-config.php"),
    ("Q14 [HASH]", "root:$6$qZ8jL1... shadow hash — cracked offline"),
]

HOLES = [
    ("[x] DEAD-END", "wp-login.php hydra brute force — account lockouts triggered;"),
    ("", "switched to SMB backup share instead (see Q7)"),
    ("    RULE", "inspect unauthenticated network shares before brute-forcing logins"),
]


class MissionDeckV3(App):
    CSS = """
    Screen { background: #10151c; }
    #strip { height: 2; background: #171e28; color: #9fd8d3; padding: 0 1; }
    #body { height: 1fr; }
    #rail { width: 30; background: #131922; border-right: solid #242e3d; padding: 0 1; }
    .panel { border: round #242e3d; background: #131922; margin-bottom: 1; padding: 0 1; }
    .panel:focus-within { border: round #39c5cf; }
    .ptitle { color: #39c5cf; text-style: bold; height: 1; }
    #services { height: auto; max-height: 9; }
    #lower { height: 1fr; }
    #checklist { width: 2fr; margin-bottom: 0; }
    #notes { width: 3fr; margin-bottom: 0; margin-left: 1; }
    DataTable { height: 1fr; }
    #vault-grid { height: 2fr; }
    #spray { height: 9; border: round #242e3d; background: #131922; padding: 0 1; }
    #console { height: 4; border: round #242e3d; background: #131922; margin: 0 1; padding: 0 1; }
    #console.copied-flash { border: round #3fb950; }
    #cmd { height: 1; border: none; background: transparent; }
    .dim { color: #7d8794; }
    """

    BINDINGS = [
        Binding("q", "quit", "quit"),
        Binding("1", "station(1)", "cockpit"), Binding("2", "station(2)", "arsenal"),
        Binding("3", "station(3)", "vault"), Binding("4", "station(4)", "intel"),
        Binding("b", "toggle_rail", "rail"), Binding("colon", "palette", "cmd"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.elapsed = 4 * 3600 + 12 * 60 + 35

    def compose(self) -> ComposeResult:
        yield Static(self.render_strip(), id="strip")
        with Horizontal(id="body"):
            yield Tree("targets", id="rail")
            with TabbedContent(id="stations"):
                with TabPane("1 Cockpit", id="pane-engage"):
                    with Vertical():
                        with Vertical(id="services", classes="panel"):
                            yield Label("SERVICES & PORTS   3", classes="ptitle")
                            yield Static(self.render_services())
                        with Horizontal(id="lower"):
                            with Vertical(id="checklist", classes="panel"):
                                yield Label("METHODOLOGY   [##########] 100% 3/3", classes="ptitle")
                                yield Static("[v] TCP enumeration\n[v] SMB enumeration\n[v] Pivoting & route discovery\n\nnext: loot + proofs (see Intel)")
                            with VerticalScroll(id="notes", classes="panel"):
                                yield Label("NOTES & FINDINGS   5", classes="ptitle")
                                yield Static(self.render_notes())
                with TabPane("2 Arsenal", id="pane-arsenal"):
                    yield Static("Playbook browser — unchanged.")
                with TabPane("3 Vault", id="pane-vault"):
                    with Vertical():
                        yield DataTable(id="vault-grid")
                        with Vertical(id="spray"):
                            yield Label("SPRAY QUEUE — untested credential x service pairs", classes="ptitle")
                            yield Static(self.render_spray())
                with TabPane("4 Intel", id="pane-intel"):
                    with Horizontal():
                        yield Static(self.render_flags(), classes="panel")
                        yield Static(self.render_proofs(), classes="panel")
                        yield Static(self.render_holes(), classes="panel")
        yield Static("> highlight a row to preview its command — [enter] copy", id="console")
        yield Input(placeholder=": palette — try 'flag' or 'theme'", id="cmd")
        yield Footer()

    def on_mount(self) -> None:
        tree = self.query_one("#rail", Tree)
        tree.show_root = False
        net1 = tree.root.add("v 10.10.10.0/24 (1 host)")
        t1 = net1.add("* 10.10.10.20 target.local")
        for port, name in (("22/tcp", "SSH"), ("80/tcp", "HTTP"), ("445/tcp", "SMB")):
            t1.add_leaf(f"v {port}  {name}")
        net2 = tree.root.add("v 172.16.1.0/24 (1 host)")
        t2 = net2.add("o 172.16.1.50 db01")
        t2.add_leaf("> 3306/tcp  MySQL")
        tree.root.expand_all()

        grid = self.query_one("#vault-grid", DataTable)
        grid.cursor_type = "cell"
        grid.add_columns(*CRED_COLS)
        grid.add_rows(CRED_ROWS)
        self.set_interval(1, self.tick)

    def render_strip(self) -> str:
        t = str(timedelta(seconds=self.elapsed))
        return (
            f"CYB0X-S > [Lab-Assessment-01]   T+{t}\n"
            f"* 10.10.10.20 target.local (Linux) [IN-SCOPE]   "
            f"ports 3  creds 2  vulns 2  flags 2/2 workspace-wide   dead-ends 1"
        )

    def render_services(self) -> str:
        out = []
        for port, name, st, banner in SERVICES:
            mark = {"open": ">", "pwned": "*"}.get(st, "v")
            out.append(f"{mark} [{port:<7}] {name:<6} {banner}")
        return "\n".join(out)

    def render_notes(self) -> str:
        return "\n\n".join(f"{tag}  {text}" for tag, text in NOTES)

    def render_spray(self) -> str:
        return "\n".join(f"o {u:<8} -> {tgt:<28} $ {cmd}" for u, tgt, cmd in SPRAY_QUEUE)

    def render_flags(self) -> str:
        lines = ["FLAGS (full, never elided)", ""]
        for tag, value, when in FLAGS:
            lines.append(f"{tag}  {value}")
            lines.append(f"        {when}")
        return "\n".join(lines)

    def render_proofs(self) -> str:
        lines = ["QUESTION PROOFS", ""]
        for q, p in PROOFS:
            lines.append(f"[{q}]  {p}")
        return "\n".join(lines)

    def render_holes(self) -> str:
        return "RABBIT HOLES\n\n" + "\n".join(f"{t} {x}".rstrip() for t, x in HOLES)

    def tick(self) -> None:
        self.elapsed += 1
        self.query_one("#strip", Static).update(self.render_strip())

    def action_station(self, n: int) -> None:
        pane = ["engage", "arsenal", "vault", "intel"][n - 1]
        self.query_one("#stations", TabbedContent).active = f"pane-{pane}"

    def action_toggle_rail(self) -> None:
        rail = self.query_one("#rail")
        rail.styles.display = "none" if rail.styles.display != "none" else "block"

    def action_palette(self) -> None:
        self.query_one("#cmd", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        console = self.query_one("#console", Static)
        console.update(f"[v] COPIED {event.value or 'netexec smb 10.10.10.20 -u admin -p W1nter!2026 --shares'}")
        console.add_class("copied-flash")
        self.set_timer(1.2, lambda: console.remove_class("copied-flash"))
        event.input.value = ""


if __name__ == "__main__":
    MissionDeckV3().run()
