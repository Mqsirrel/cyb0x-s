"""Runnable mock of the CYB0X-S Redesign v2 "Mission Deck" layout.

Self-contained: fake data, no imports from the cyb0x_s package.
Run from the repo root:

    uv run python dev/redesign_preview.py

Keys: 1-4 stations . b target rail . : command bar . enter flash . q quit

NOTE: literal colours below are for the mock only. The real implementation
must read the active palette through Textual design tokens (zero hexes in
widget CSS), the same rule the current stylesheet follows.
"""

from __future__ import annotations

from datetime import timedelta

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import DataTable, Footer, Input, Static, TabbedContent, TabPane, Tree

SERVICES = [
    ("22", "ssh", "open", "-", "enum users"),
    ("80", "http", "enum", "-", "dirb vhosts"),
    ("443", "https", "exploited", "admin", "loot flags"),
    ("3306", "mysql", "filtered", "-", "skip (filtered)"),
    ("5985", "winrm", "open", "-", "try cred matrix"),
]

CREDS = [
    ("10.10.10.5", "admin", "Winter2026!", "-", "web panel"),
    ("10.10.10.5", "svc-web", "-", "NTLM 5f4d...9c2a", "hashdump"),
    ("10.10.10.6", "-", "-", "-", "-"),
]

FLAGS = [
    ("user.txt", "10.10.10.5", "9f2c...e1", "14:02"),
    ("root.txt", "10.10.10.5", "77ab...c4", "15:47"),
]

TIMELINE = [
    ("15:47", "root flag captured on 10.10.10.5"),
    ("15:12", "winrm shell as svc-web"),
    ("14:38", "stuck: smb null sessions denied (x3)"),
    ("14:02", "user flag captured on 10.10.10.5"),
    ("13:55", "initial access via web panel creds"),
]

CATEGORIES = ["networking", "smb", "web", "winrm", "privesc", "pivoting"]

COMMAND = "hydra -l admin -P rockyou.txt ssh://10.10.10.5"

PANES = ["engage", "arsenal", "vault", "intel"]


class MissionDeckPreview(App):
    """Static mock of the redesigned cockpit with mock exam data."""

    CSS = """
    Screen { background: #10151c; }
    #strip { height: 1; background: #171e28; color: #9fd8d3; padding: 0 1; }
    #body { height: 1fr; }
    #rail { width: 30; background: #131922; border-right: solid #242e3d; padding: 0 1; }
    #stations { height: 1fr; }
    TabPane { padding: 1 2; }
    DataTable { height: 1fr; }
    #arsenal-cats { width: 18; color: #7d8794; }
    #arsenal-card { border: round #242e3d; padding: 1 2; width: 1fr; height: auto; }
    #flag-cards, #timeline { width: 1fr; border: round #242e3d; padding: 1 2; margin-right: 1; }
    #console { height: 3; background: #131922; border-top: solid #242e3d; color: #d6dde6; padding: 1 2; }
    #console.flashed { border-top: solid #3fb950; }
    #cmd { height: 3; background: #0c1016; border: none; color: #d6dde6; }
    """

    BINDINGS = [
        Binding("q", "quit", "quit"),
        Binding("1", "station(1)", "engage"),
        Binding("2", "station(2)", "arsenal"),
        Binding("3", "station(3)", "vault"),
        Binding("4", "station(4)", "intel"),
        Binding("b", "toggle_rail", "rail"),
        Binding("colon", "cmd", "cmd"),
        Binding("escape", "blur", "", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.elapsed = 4 * 3600 + 12 * 60 + 35

    def compose(self) -> ComposeResult:
        yield Static(self.render_strip(), id="strip")
        with Horizontal(id="body"):
            yield Tree("targets", id="rail")
            with TabbedContent(id="stations"):
                with TabPane("1 Engage", id="pane-engage"):
                    yield DataTable(id="engage-grid")
                with TabPane("2 Arsenal", id="pane-arsenal"):
                    with Horizontal():
                        yield Static("\n".join(f"  {c}" for c in CATEGORIES), id="arsenal-cats")
                        yield Static(
                            f"$ {COMMAND}\n\nssh brute -- {{IP}}/{{PORT}} substituted on copy",
                            id="arsenal-card",
                        )
                with TabPane("3 Vault", id="pane-vault"):
                    yield DataTable(id="vault-grid")
                with TabPane("4 Intel", id="pane-intel"):
                    with Horizontal():
                        yield Static(self.render_flags(), id="flag-cards")
                        yield Static(self.render_timeline(), id="timeline")
        yield Static(f"$ {COMMAND}    [enter] copy  [e] edit  [x] mark ran", id="console")
        yield Input(placeholder=": command bar -- try :uflag, :stuck, :m web, :theme slate", id="cmd")
        yield Footer()

    def on_mount(self) -> None:
        tree = self.query_one("#rail", Tree)
        tree.show_root = False
        host5 = tree.root.add("10.10.10.5  *3")
        host5.add_leaf("22    ssh    o")
        host5.add_leaf("80    http   ~")
        host5.add_leaf("443   https  *")
        host5.expand()
        tree.root.add_leaf("10.10.10.6  o0")

        grid = self.query_one("#engage-grid", DataTable)
        grid.cursor_type = "row"
        grid.zebra_stripes = True
        grid.add_columns("PORT", "SERVICE", "STATUS", "CRED", "NEXT ACTION")
        grid.add_rows(SERVICES)

        vault = self.query_one("#vault-grid", DataTable)
        vault.cursor_type = "row"
        vault.zebra_stripes = True
        vault.add_columns("HOST", "USER", "PASSWORD", "HASH", "SOURCE")
        vault.add_rows(CREDS)

        self.set_interval(1, self.tick)

    def render_strip(self) -> str:
        t = str(timedelta(seconds=self.elapsed))
        return (
            f" CYB0X-S . ejpt-lab    T+{t}    target 10.10.10.5 (web)    "
            f"flags 2/4    [######..] 62%"
        )

    def render_flags(self) -> str:
        lines = ["FLAGS", ""]
        for name, host, value, when in FLAGS:
            lines.append(f"  [x] {name}  {host}")
            lines.append(f"      {value}  at {when}")
        return "\n".join(lines)

    def render_timeline(self) -> str:
        lines = ["TIMELINE", ""]
        for when, what in TIMELINE:
            lines.append(f"  {when}  {what}")
        return "\n".join(lines)

    def tick(self) -> None:
        self.elapsed += 1
        self.query_one("#strip", Static).update(self.render_strip())

    def action_station(self, n: int) -> None:
        self.query_one("#stations", TabbedContent).active = f"pane-{PANES[n - 1]}"

    def action_toggle_rail(self) -> None:
        rail = self.query_one("#rail")
        rail.styles.display = "none" if rail.styles.display != "none" else "block"

    def action_cmd(self) -> None:
        self.query_one("#cmd", Input).focus()

    def action_blur(self) -> None:
        if isinstance(self.focused, Input):
            self.set_focus(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        console = self.query_one("#console", Static)
        console.update(f"$ {event.value or COMMAND}    [enter] copy  [e] edit  [x] mark ran")
        console.add_class("flashed")
        self.set_timer(0.15, lambda: console.remove_class("flashed"))
        event.input.value = ""


if __name__ == "__main__":
    MissionDeckPreview().run()
