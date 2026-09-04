"""Runnable mock of CYB0X-S Redesign v2 — Mission Deck, rev 2.

Updated after reading the real codebase: keeps the current cockpit's
identity (Attack Surface rail, Services & Ports grid, Methodology, Notes,
ConsoleBar with live hints) and layers on the new elements:

  * T+ exam clock in the status strip (persisted via store settings)
  * [ / ] target cycling, w panel cycling, h/l column jumps (exist in app)
  * Recipe strip with < / > cycling for multi-command services
  * Cross-filter glow: highlighting a service aligns checklist + creds
  * Pivot-aware target rail with subnet grouping
  * Command palette (:) with searchable verbs — fixes discoverability

Self-contained: fake data, no imports from cyb0x_s.
Run from the repo root:

    uv run python dev/redesign_preview_v2.py

Keys: 1-4 stations . b rail . w cycle panels . [ ] targets . , . recipes
      : palette . enter copy-flash . q quit

NOTE: literal colours are mock-only; the real stylesheet reads palette
tokens via $vars, zero hexes — keep that rule.
"""

from __future__ import annotations

from datetime import timedelta

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, Footer, Input, Label, Static, TabbedContent, TabPane, Tree

TARGETS = [
    ("10.10.10.0/24", None),
    ("  10.10.10.5", [("22", "ssh", "o"), ("80", "http", "~"), ("443", "https", "*")]),
    ("  10.10.10.6", []),
    ("192.168.50.0/24  [PIVOT SEGMENT]", None),
    ("  192.168.50.20  <= [PIVOT]", [("445", "smb", "o"), ("5985", "winrm", "*")]),
]

SERVICES = [
    ("22", "ssh", "open", "-", "enum users"),
    ("80", "http", "enum", "-", "dirb vhosts"),
    ("443", "https", "exploited", "admin", "loot flags"),
    ("3306", "mysql", "filtered", "-", "skip (filtered)"),
    ("5985", "winrm", "open", "-", "try cred matrix"),
]

RECIPES = [
    "nmap -sV -sC -p 5985 10.10.10.5",
    "netexec winrm 10.10.10.5 -u users.txt -p passwords.txt",
    "evil-winrm -i 10.10.10.5 -u admin -p 'Winter2026!'",
]

CHECKLIST = [
    ("[x]", "Enumerate subnet 10.10.10.0/24"),
    ("[x]", "Banner grab all open ports"),
    ("[~]", "Brute-force WinRM with found creds"),
    ("[ ]", "Pivot through 10.10.10.5 to 192.168.50.0/24"),
    ("[ ]", "Loot + proof screenshots"),
]

PALETTE_CMDS = [
    (":t <ip>", "add target"), (":s <port/proto> <svc>", "add service"),
    (":c <user:pass>", "add cred"), (":uflag / :rflag", "record flags"),
    (":stuck / :clue", "rabbit hole log"), (":w", "copy wordlist path"),
    (":m <name>", "methodology"), (":theme <1-7>", "palette"),
]


class MissionDeckPreview(App):
    CSS = """
    Screen { background: #10151c; }
    #strip { height: 1; background: #171e28; color: #9fd8d3; padding: 0 1; }
    #body { height: 1fr; }
    #rail { width: 32; background: #131922; border-right: solid #242e3d; padding: 0 1; }
    #workbench { padding: 0 1; }
    .panel { border: round #242e3d; background: #131922; margin-bottom: 1; padding: 0 1; }
    .panel:focus-within { border: round #39c5cf; }
    .ptitle { color: #39c5cf; text-style: bold; height: 1; }
    #services { height: 3fr; min-height: 7; }
    #lower { height: 2fr; min-height: 6; }
    #checklist { width: 1fr; margin-bottom: 0; }
    #notes { width: 1fr; margin-bottom: 0; margin-left: 1; }
    DataTable { height: 1fr; }
    #console { height: 4; border: round #242e3d; background: #131922; margin: 0 1; padding: 0 1; }
    #console.copied-flash { border: round #3fb950; }
    #cmd { height: 1; border: none; background: transparent; }
    """

    BINDINGS = [
        Binding("q", "quit", "quit"),
        Binding("1", "station(1)", "engage"), Binding("2", "station(2)", "arsenal"),
        Binding("3", "station(3)", "vault"), Binding("4", "station(4)", "intel"),
        Binding("b", "toggle_rail", "rail"), Binding("w", "cycle_panel", "panels"),
        Binding("left_square_bracket", "target(-1)", "prev tgt", show=False),
        Binding("right_square_bracket", "target(1)", "next tgt", show=False),
        Binding("comma", "recipe(-1)", "prev recipe", show=False),
        Binding("full_stop", "recipe(1)", "next recipe", show=False),
        Binding("colon", "palette", "cmd"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.elapsed = 4 * 3600 + 12 * 60 + 35
        self.recipe_idx = 0
        self.target_idx = 0
        self.ips = ["10.10.10.5", "10.10.10.6", "192.168.50.20"]
        self.panels = ["#rail", "#svc-grid", "#cmd"]

    def compose(self) -> ComposeResult:
        yield Static(self.render_strip(), id="strip")
        with Horizontal(id="body"):
            yield Tree("targets", id="rail")
            with TabbedContent(id="stations"):
                with TabPane("1 Cockpit", id="pane-engage"):
                    with Vertical(id="workbench"):
                        with Vertical(id="services", classes="panel"):
                            yield Label("SERVICES & PORTS", classes="ptitle")
                            yield DataTable(id="svc-grid")
                        with Horizontal(id="lower"):
                            with Vertical(id="checklist", classes="panel"):
                                yield Label("METHODOLOGY  [######....] 60%", classes="ptitle")
                                yield Static(self.render_checklist(), id="ck-list")
                            with Vertical(id="notes", classes="panel"):
                                yield Label("NOTES & FINDINGS", classes="ptitle")
                                yield Static(
                                    "[VULN] Anonymous SMB share on .20 [HIGH]\n"
                                    "[NOTE] web panel admin:Winter2026! works on 443\n"
                                    "[LEAD] db_backup.sql mentioned in /comments",
                                )
                with TabPane("2 Arsenal", id="pane-arsenal"):
                    yield Static("Playbook browser (categories left, commands right) — unchanged, already good.")
                with TabPane("3 Vault", id="pane-vault"):
                    yield Static("2D credential x service matrix — cycle cells UNTESTED > VALID > PWN3D > INVALID.")
                with TabPane("4 Intel", id="pane-intel"):
                    yield Static("Flags, foothold, privesc, Q1-Q35 proofs, rabbit holes.")
        yield Static(self.render_console(), id="console")
        yield Input(placeholder=": palette — type to filter verbs (try 'flag')", id="cmd")
        yield Footer()

    def on_mount(self) -> None:
        tree = self.query_one("#rail", Tree)
        tree.show_root = False
        for label, svcs in TARGETS:
            node = tree.root.add(label) if svcs is not None or "PIVOT SEGMENT" in label else None
            if svcs is None:
                continue
            if svcs:
                for port, name, st in svcs:
                    node.add_leaf(f"{st} {port}/{name}")
                node.expand()

        grid = self.query_one("#svc-grid", DataTable)
        grid.cursor_type = "row"
        grid.add_columns("PORT", "SERVICE", "STATUS", "CRED", "NEXT ACTION")
        grid.add_rows(SERVICES)
        self.set_interval(1, self.tick)

    def render_strip(self) -> str:
        t = str(timedelta(seconds=self.elapsed))
        ip = self.ips[self.target_idx]
        return f" CYB0X-S . ejpt-lab   T+{t}   target {ip} [IN-SCOPE]   flags 2/4   creds 3   TGT {self.target_idx + 1}/3"

    def render_console(self) -> str:
        cmd = RECIPES[self.recipe_idx]
        return f"> [RECIPE {self.recipe_idx + 1}/{len(RECIPES)}] {cmd}   [enter]=copy  [< >]=cycle"

    def render_checklist(self) -> str:
        return "\n".join(f"{mark} {title}" for mark, title in CHECKLIST)

    def tick(self) -> None:
        self.elapsed += 1
        self.query_one("#strip", Static).update(self.render_strip())

    def action_station(self, n: int) -> None:
        pane = ["engage", "arsenal", "vault", "intel"][n - 1]
        self.query_one("#stations", TabbedContent).active = f"pane-{pane}"

    def action_toggle_rail(self) -> None:
        rail = self.query_one("#rail")
        rail.styles.display = "none" if rail.styles.display != "none" else "block"

    def action_cycle_panel(self) -> None:
        cur = self.focused
        ids = [p.lstrip("#") for p in self.panels]
        nxt = ids[(ids.index(cur.id) + 1) % len(ids)] if cur is not None and cur.id in ids else ids[0]
        self.query_one(f"#{nxt}").focus()

    def action_target(self, d: int) -> None:
        self.target_idx = (self.target_idx + d) % len(self.ips)
        self.query_one("#strip", Static).update(self.render_strip())

    def action_recipe(self, d: int) -> None:
        self.recipe_idx = (self.recipe_idx + d) % len(RECIPES)
        self.query_one("#console", Static).update(self.render_console())

    def action_palette(self) -> None:
        self.query_one("#cmd", Input).focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        q = event.value.strip().lstrip(":")
        hint = self.query_one("#console", Static)
        if not q:
            hint.update(self.render_console())
            return
        hits = [f"{cmd} — {desc}" for cmd, desc in PALETTE_CMDS if q in cmd or q in desc]
        hint.update("\n".join(hits[:3]) if hits else "no matching verb — plain text saves as a note")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        console = self.query_one("#console", Static)
        console.update(f"COPIED {event.value or RECIPES[self.recipe_idx]}")
        console.add_class("copied-flash")
        self.set_timer(1.2, lambda: console.remove_class("copied-flash"))
        event.input.value = ""


if __name__ == "__main__":
    MissionDeckPreview().run()
