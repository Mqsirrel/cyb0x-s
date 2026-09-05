"""Mission Deck — the CYB0X-S redesign as a complete alternative interface.

Same store, same themes, same command language — a different cockpit:
zero emoji (screenshot-audit glyph set only), a persistent T+ exam clock,
full-length flags, content-sized panels, wrapped notes, a spray queue in
the Vault, and a recipe-driven console. Nothing here is a mock: it reads
and writes your real notebook database.

Run alongside the classic UI and keep the winner:

    uv run python -m cyb0x_s.tui.deck

Keys: 1-4 stations . b rail . [ ] targets . , . recipes . w panels
      y copy . space cycle . : command bar . T themes . ? help . q quit
"""

from __future__ import annotations

import time
from datetime import timedelta
from typing import Any, Dict, List, Optional

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    DataTable, Footer, Input, Label, ListItem, ListView, Static,
    TabbedContent, TabPane, Tree,
)

from cyb0x_s.clipboard import copy_to_clipboard
from cyb0x_s.db.store import NotebookStore
from cyb0x_s.models import ChecklistItem, Credential, Service, Target
from cyb0x_s.settings import derive_guidance_enabled
from cyb0x_s.templates import apply_template_to_store, get_recipes_for_service
from cyb0x_s.reference import search_reference
from cyb0x_s.tui.commands import execute_command
from cyb0x_s.tui.theme import (
    PALETTES, S, current_palette, get_default_theme,
    resolve_palette_name, save_default_theme, set_palette,
)
from cyb0x_s.tui.widgets import (
    AUTH_SERVICE_NAMES, AUTH_SERVICE_PORTS, compile_spray_command,
    substitute_command_placeholders,
)
from cyb0x_s.tui.modals import (
    AddCredentialModal, AddFindingModal, AddServiceModal, AddTargetModal,
    FastInputModal, HelpModal, SearchModal, TemplateSelectionModal,
    ThemePickerModal,
)

GLYPH = {"todo": ">", "done": "v", "defer": "~", "drop": "x", "host": "*", "idle": "o"}


def mark_for(status: str) -> str:
    s = (status or "").upper().replace("_", "-")
    if s == "CHECKED":
        return GLYPH["done"]
    if s == "DEFERRED":
        return GLYPH["defer"]
    if s in ("DEAD-END",):
        return GLYPH["drop"]
    return GLYPH["todo"]


class DeckStrip(Static):
    """Two rows: who/where/clock/counters, then next-step/progress/blockers."""

    def __init__(self, store: NotebookStore, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.store = store
        self.session_start = time.monotonic()
        self.exam_start: Optional[float] = None

    def on_mount(self) -> None:
        try:
            raw = self.store.get_setting("exam_started_at")
            if raw:
                self.exam_start = float(raw)
        except Exception:
            self.exam_start = None
        self.set_interval(1, self.refresh)

    def render(self) -> Text:
        P = current_palette()
        if self.exam_start is not None:
            elapsed_s = int(time.time() - self.exam_start)
        else:
            elapsed_s = int(time.monotonic() - self.session_start)
        clock = str(timedelta(seconds=elapsed_s))

        app = self.app
        target = getattr(app, "active_target", None)
        stats = getattr(app, "strip_stats", {})

        row1 = Text()
        row1.append("CYB0X-S DECK", style=f"bold {P.accent}")
        row1.append(f"  T+{clock}", style=f"bold {P.warn}")
        if target:
            row1.append(f"  {GLYPH['host']} {target.ip}", style=f"bold {P.text}")
            if target.hostname:
                row1.append(f" ({target.hostname})", style=f"{P.muted}")
            scope_ok = target.is_in_scope
            row1.append(
                " [IN-SCOPE]" if scope_ok else " [OUT-OF-SCOPE]",
                style=f"bold {P.ok if scope_ok else P.danger}",
            )
        else:
            row1.append("  o no target — press t or :t <ip>", style=f"{P.muted}")
        right = "  ".join(f"{v} {k}" for k, v in stats.items() if v)
        width = max(self.size.width - 2, 20)
        pad = width - len(row1.plain) - len(right)
        if right and pad > 1:
            row1.append(" " * pad + right, style=f"bold {P.muted}")

        row2 = Text()
        nxt = getattr(app, "strip_next", "")
        done, total = getattr(app, "strip_progress", (0, 0))
        if total:
            pct = int(done / total * 100)
            bar = "#" * (pct // 10) + "-" * (10 - pct // 10)
            row2.append(f"NEXT > {nxt or 'methodology complete'}", style=f"bold {P.text}")
            row2.append(f"  [{bar}] {pct}% {done}/{total}", style=f"{P.text_soft}")
        else:
            row2.append("NEXT > press m to load a methodology", style=f"{P.muted}")
        blockers = getattr(app, "strip_blockers", 0)
        if blockers:
            row2.append(f"   x {blockers} dead end{'s' if blockers != 1 else ''}", style=f"bold {P.danger}")
        row2.append(f"   flags {getattr(app, 'strip_flags', '0/0')}", style=f"bold {P.ok}")
        row2.append(f"   {getattr(app, 'clock_source', 'session')}", style=f"{P.muted}")
        return Text.assemble(row1, "\n", row2)


class DeckConsole(Static):
    """Bottom bar: active recipe/command, and the : command input."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.recipes: List[Dict[str, str]] = []
        self.recipe_index = 0
        self.recipe_ip = ""
        self.free_note = ""

    def compose(self) -> ComposeResult:
        yield Static(id="deck-cmdline")
        yield Input(
            placeholder=": command — :t :s :c :n :uflag :stuck :w :m :theme ... (plain text = note)",
            id="deck-input",
        )

    def show_recipes(self, recipes: List[Dict[str, str]], index: int, target_ip: str) -> None:
        self.recipes = recipes
        self.recipe_index = max(0, min(index, len(recipes) - 1))
        self.recipe_ip = target_ip
        self._paint()

    def show_text(self, text: str) -> None:
        self.recipes = []
        self.free_note = text
        self._paint()

    def cycle(self, delta: int) -> None:
        if not self.recipes:
            return
        self.recipe_index = (self.recipe_index + delta) % len(self.recipes)
        self._paint()

    def current_command(self) -> str:
        if self.recipes:
            return substitute_command_placeholders(
                self.recipes[self.recipe_index].get("command", ""), self.recipe_ip
            )
        return ""

    def flash_copied(self, what: str) -> None:
        self.show_text(f"[v] COPIED  {what}")
        self.add_class("copied-flash")
        self.set_timer(1.4, lambda: self.remove_class("copied-flash"))

    def _paint(self) -> None:
        P = current_palette()
        line = Text()
        if self.recipes:
            count = len(self.recipes)
            head = f"RECIPE {self.recipe_index + 1}/{count}" if count > 1 else "COMMAND"
            line.append(f"> [{head}] ", style=f"bold {P.warn}")
            line.append(self.current_command(), style=f"bold {P.text}")
            tip = self.recipes[self.recipe_index].get("tip", "")
            if tip:
                line.append(f"   {tip[:60]}", style=f"{P.muted}")
            if count > 1:
                line.append("   [< > cycle]", style=f"bold {P.accent}")
        else:
            line.append("> ", style=f"bold {P.accent}")
            line.append(self.free_note or "highlight a service to load its command", style=f"{P.muted}")
        try:
            self.query_one("#deck-cmdline", Static).update(line)
        except Exception:
            pass


class MissionDeck(App):
    """The redesigned CYB0X-S interface. Runs on the real NotebookStore."""

    CSS = """
    Screen { background: $background; }
    #strip { height: 2; background: $surface; border-bottom: solid $border; padding: 0 1; }
    #body { height: 1fr; }
    #rail { width: 30; background: $surface; border-right: solid $border; padding: 0 1; }
    .panel { border: round $border; background: $surface; margin-bottom: 1; padding: 0 1; }
    .panel:focus-within { border: round $accent; }
    .ptitle { color: $accent; text-style: bold; height: 1; }
    #svc-panel { height: auto; max-height: 12; }
    #lower { height: 1fr; }
    #ck-panel { width: 2fr; margin-bottom: 0; }
    #notes-panel { width: 3fr; margin-bottom: 0; margin-left: 1; }
    DataTable { height: 1fr; }
    #vault-grid { height: 2fr; }
    #spray-panel { height: auto; max-height: 10; }
    #console { height: 4; border: round $border; background: $surface; margin: 0 1; padding: 0 1; }
    #console.copied-flash { border: round $success; }
    #deck-input { height: 1; border: none; background: transparent; }
    .intel-col { width: 1fr; margin-right: 1; }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("question_mark", "show_help", "Help"),
        Binding("slash", "open_search", "Search"),
        Binding("colon", "focus_command", "Cmd"),
        Binding("1", "station('deck-cockpit')", "Cockpit", show=False),
        Binding("2", "station('deck-arsenal')", "Arsenal", show=False),
        Binding("3", "station('deck-vault')", "Vault", show=False),
        Binding("4", "station('deck-intel')", "Intel", show=False),
        Binding("b", "toggle_rail", "Rail", show=False),
        Binding("w", "cycle_panel", "Panels", show=False),
        Binding("y", "copy_current", "Copy", show=False),
        Binding("space", "cycle_status", "Cycle", show=False),
        Binding("left_square_bracket", "target(-1)", "Prev", show=False),
        Binding("right_square_bracket", "target(1)", "Next", show=False),
        Binding("comma", "recipe(-1)", "Recipe-", show=False),
        Binding("full_stop", "recipe(1)", "Recipe+", show=False),
        Binding("t", "add_target", "Target", show=False),
        Binding("s", "add_service", "Service", show=False),
        Binding("c", "add_credential", "Cred", show=False),
        Binding("n", "add_note", "Note", show=False),
        Binding("f", "add_finding", "Finding", show=False),
        Binding("m", "apply_template", "Methodology", show=False),
        Binding("T", "open_theme_picker", "Theme", show=False),
    ]
    ENABLE_COMMAND_PALETTE = False

    def __init__(self, store: Optional[NotebookStore] = None, theme: Optional[str] = None, **kw: Any) -> None:
        super().__init__(**kw)
        for palette in PALETTES.values():
            self.register_theme(palette.textual_theme())
        self.store = store or NotebookStore()
        self.theme_name = resolve_palette_name(theme) or get_default_theme(self.store)
        set_palette(self.theme_name)
        self.theme = PALETTES[self.theme_name].textual_theme().name
        self.active_target: Optional[Target] = None
        self.strip_stats: Dict[str, int] = {}
        self.strip_next = ""
        self.strip_progress = (0, 0)
        self.strip_blockers = 0
        self.strip_flags = "0/0"
        self.clock_source = "session"
        self._svc_rows: List[Service] = []
        self._ck_rows: List[ChecklistItem] = []
        self._cred_rows: List[Credential] = []
        self._auth_pairs: List[Any] = []
        self._cell_states: Dict[Any, str] = {}
        self._cycle = ["o UNTESTED", "v VALID", "* PWN3D", "x INVALID"]
        self._arsenal_cat_names: List[str] = []
        self._arsenal_cmd_texts: List[str] = []

    # -- layout -------------------------------------------------------------
    def compose(self) -> ComposeResult:
        yield DeckStrip(self.store, id="strip")
        with Horizontal(id="body"):
            yield Tree("targets", id="rail")
            with TabbedContent(initial="deck-cockpit", id="stations"):
                with TabPane("1 Cockpit", id="deck-cockpit"):
                    with Vertical():
                        with Vertical(id="svc-panel", classes="panel"):
                            yield Label("SERVICES & PORTS", classes="ptitle")
                            yield DataTable(id="svc-grid")
                        with Horizontal(id="lower"):
                            with Vertical(id="ck-panel", classes="panel"):
                                yield Label("METHODOLOGY", classes="ptitle")
                                yield DataTable(id="ck-grid")
                            with VerticalScroll(id="notes-panel", classes="panel"):
                                yield Label("NOTES & FINDINGS", classes="ptitle")
                                yield Static("", id="notes-body")
                with TabPane("2 Arsenal", id="deck-arsenal"):
                    with Horizontal():
                        with Vertical(classes="panel", id="arsenal-cats-panel"):
                            yield Label("CATEGORIES", classes="ptitle")
                            yield ListView(id="arsenal-cats")
                        with Vertical(classes="panel", id="arsenal-cmds-panel"):
                            yield Label("COMMANDS — enter copies", classes="ptitle")
                            yield ListView(id="arsenal-cmds")
                with TabPane("3 Vault", id="deck-vault"):
                    with Vertical():
                        with Vertical(classes="panel", id="vault-panel"):
                            yield Label("CREDENTIAL x SERVICE MATRIX — space cycles, y copies spray cmd", classes="ptitle")
                            yield DataTable(id="vault-grid")
                        with Vertical(classes="panel", id="spray-panel"):
                            yield Label("SPRAY QUEUE — untested pairs", classes="ptitle")
                            yield Static("", id="spray-body")
                with TabPane("4 Intel", id="deck-intel"):
                    with Horizontal():
                        yield Static("", classes="panel intel-col", id="intel-flags")
                        yield Static("", classes="panel intel-col", id="intel-proofs")
                        yield Static("", classes="panel intel-col", id="intel-holes")
        yield DeckConsole(id="console")
        yield Footer()

    def on_mount(self) -> None:
        self.refresh_all()
        try:
            self.query_one("#svc-grid", DataTable).focus()
        except Exception:
            pass

    # -- data ----------------------------------------------------------------
    def refresh_targets(self) -> None:
        targets = self.store.list_targets()
        active = self.store.get_active_target()
        self.active_target = active
        tree = self.query_one("#rail", Tree)
        tree.clear()
        tree.show_root = False
        services = self.store.list_services()
        by_target: Dict[int, List[Service]] = {}
        for s in services:
            by_target.setdefault(s.target_id or 0, []).append(s)
        for t in targets:
            mark = GLYPH["host"] if (t.root_flag or t.user_flag) else GLYPH["idle"]
            label = f"{mark} {t.ip}"
            if t.hostname and self.size.width >= 120:
                label += f" {t.hostname[:14]}"
            if not t.is_in_scope:
                label += " [OUT]"
            node = tree.root.add(label, data={"target_id": t.id})
            for s in by_target.get(t.id or 0, []):
                node.add_leaf(
                    f"{mark_for(s.status.value)} {s.port}/{s.protocol} {s.service}",
                    data={"target_id": t.id, "service": s},
                )
            node.expand()
        tree.root.expand()

    def refresh_all(self) -> None:
        targets = self.store.list_targets()
        if targets:
            try:
                if not self.store.get_setting("exam_started_at"):
                    self.store.set_setting("exam_started_at", str(time.time()))
            except Exception:
                pass
        self.refresh_targets()
        active = self.active_target
        tid = active.id if active else None

        services = self.store.list_services(target_id=tid) if tid else []
        grid = self.query_one("#svc-grid", DataTable)
        grid.clear(columns=True)
        grid.cursor_type = "row"
        grid.add_columns("ST", "PORT", "SERVICE", "POT", "NEXT ACTION")
        self._svc_rows = list(services)
        for s in self._svc_rows:
            grid.add_row(
                mark_for(s.status.value), f"{s.port}/{s.protocol}", s.service,
                s.access_potential or "-", s.next_action or s.version or "-",
                key=f"svc-{s.id}",
            )

        items = self.store.list_checklist_items(target_id=tid)
        ck = self.query_one("#ck-grid", DataTable)
        ck.clear(columns=True)
        ck.cursor_type = "row"
        ck.add_columns("ST", "STEP")
        self._ck_rows = list(items)
        for it in self._ck_rows:
            ck.add_row(mark_for(it.status.value), it.title, key=f"ck-{it.id}")
        done = sum(1 for i in items if i.status.value == "CHECKED")
        self.strip_progress = (done, len(items))
        pending = [i.title for i in items if i.status.value == "TODO"]
        self.strip_next = pending[0] if pending else ""

        chunks: List[str] = []
        for f in self.store.list_findings(target_id=tid):
            sev = f" [{f.severity}]" if f.severity else ""
            chunks.append(f"[!] VULN{sev}  {f.title}" + (f"\n    {f.description}" if f.description else ""))
        for n in self.store.list_notes(target_id=tid):
            chunks.append(f"[i] NOTE  {n.content}")
        for ev in self.store.list_evidence(target_id=tid):
            chunks.append(f"[#] EVID  {ev.path_or_ref}" + (f" — {ev.description}" if ev.description else ""))
        for ld in self.store.list_leads(target_id=tid):
            chunks.append(f"[>] LEAD  {ld.title}")
        self.query_one("#notes-body", Static).update("\n\n".join(chunks) or "no notes yet — press n or type below")

        failures = self.store.list_failure_logs(target_id=tid)
        self.strip_blockers = len(failures) + sum(1 for i in items if i.status.value == "DEAD-END")

        flags_done = sum(1 for t in targets for fl in (t.user_flag, t.root_flag) if fl)
        self.strip_flags = f"{flags_done}/{2 * len(targets)}"
        try:
            self.clock_source = "exam" if self.store.get_setting("exam_started_at") else "session"
        except Exception:
            self.clock_source = "session"
        self.strip_stats = {
            "ports": len(services),
            "creds": len(self.store.list_credentials(target_id=tid)),
            "vulns": len(self.store.list_findings(target_id=tid)),
            "hosts": len(targets),
        }

        self._refresh_arsenal("")
        self._refresh_vault()
        self._refresh_intel(failures)
        self.query_one("#strip", DeckStrip).refresh()

    def _refresh_arsenal(self, category: str) -> None:
        cats = self.query_one("#arsenal-cats", ListView)
        if not cats.children:
            from cyb0x_s.reference import REFERENCE_PLAYBOOK
            counts: Dict[str, int] = {}
            for item in REFERENCE_PLAYBOOK:
                counts[item["category"]] = counts.get(item["category"], 0) + 1
            self._arsenal_cat_names = ["ALL"] + sorted(counts)
            cats.append(ListItem(Label(f"* ALL ({len(REFERENCE_PLAYBOOK)})")))
            for cat in sorted(counts):
                cats.append(ListItem(Label(f"- {cat} ({counts[cat]})")))
        cmds = self.query_one("#arsenal-cmds", ListView)
        cmds.clear()
        self._arsenal_cmd_texts = []
        ip = self.active_target.ip if self.active_target else ""
        for m in search_reference("", target_ip=ip):
            if category and category != "ALL" and m["category"].lower() != category.lower():
                continue
            self._arsenal_cmd_texts.append(m["command"])
            cmds.append(ListItem(Label(f"[{m['category']}] {m['title']}\n  > {m['command']}")))

    def _refresh_vault(self) -> None:
        creds = self.store.list_credentials()
        targets = {t.id: t for t in self.store.list_targets() if t.is_in_scope}
        services = self.store.list_services()
        self._auth_pairs = [
            (targets[s.target_id], s) for s in services
            if s.target_id in targets
            and (s.service.lower() in AUTH_SERVICE_NAMES or s.port in AUTH_SERVICE_PORTS)
        ]
        self._cred_rows = list(creds)
        try:
            self._cell_states = dict(self.store.get_cred_validations())
        except Exception:
            self._cell_states = {}
        grid = self.query_one("#vault-grid", DataTable)
        grid.clear(columns=True)
        grid.cursor_type = "cell"
        grid.add_column("CREDENTIAL", key="cred")
        for t, s in self._auth_pairs:
            grid.add_column(f"{t.ip}:{s.port}", key=f"s{s.id}")
        for c in self._cred_rows:
            row = [f"{c.username} : {c.masked_secret}"]
            for t, s in self._auth_pairs:
                state = self._cell_states.get((c.id, s.id)) or (
                    "v VALID" if (c.status or "").lower() in ("valid", "tested") else self._cycle[0]
                )
                self._cell_states[(c.id, s.id)] = state
                row.append(state)
            grid.add_row(*row, key=f"c{c.id}")

        lines = []
        for c in self._cred_rows:
            for t, s in self._auth_pairs:
                if self._cell_states.get((c.id, s.id), self._cycle[0]) == self._cycle[0]:
                    cmd = compile_spray_command(c.username, c.secret, s.service, t.ip, s.port)
                    lines.append(f"o {c.username:<12} -> {t.ip}:{s.port!s:<6} $ {cmd}")
        self.query_one("#spray-body", Static).update("\n".join(lines[:8]) or "no untested pairs")

    def _refresh_intel(self, failures: List[Any]) -> None:
        t = self.active_target
        flags = ["FLAGS — full length, never elided", ""]
        if t:
            flags.append(f"[U] user.txt  {t.user_flag or '-'}")
            flags.append(f"[R] root.txt  {t.root_flag or '-'}")
            if t.initial_access_vuln:
                flags.append(f"» foothold   {t.initial_access_vuln}")
            if t.privesc_vector:
                flags.append(f"» privesc    {t.privesc_vector}")
        else:
            flags.append("no active target")
        self.query_one("#intel-flags", Static).update("\n".join(flags))

        proofs = ["EXAM PROOFS", ""]
        try:
            for p in self.store.list_exam_proofs():
                proofs.append(f"[{p.question_num}] {p.answer_proof}")
        except Exception:
            pass
        self.query_one("#intel-proofs", Static).update("\n".join(proofs))

        holes = ["RABBIT HOLES", ""]
        for fl in failures:
            holes.append(f"[x] {fl.where_stuck}")
            if fl.breakthrough_clue:
                holes.append(f"    » {fl.breakthrough_clue}")
        self.query_one("#intel-holes", Static).update("\n".join(holes))

    # -- input / commands -------------------------------------------------------
    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "deck-input":
            return
        val = event.value
        event.input.value = ""
        if val.strip():
            execute_command(self, val)
        self.refresh_all()

    def on_data_table_row_highlighted(self, event: Any) -> None:
        if event.data_table.id != "svc-grid":
            return
        row = event.cursor_row
        if row is None or row >= len(self._svc_rows):
            return
        svc = self._svc_rows[row]
        ip = self.active_target.ip if self.active_target else ""
        console = self.query_one("#console", DeckConsole)
        recipes = get_recipes_for_service(svc.service, svc.port) if derive_guidance_enabled() else []
        if recipes:
            console.show_recipes(recipes, 0, ip)
        elif svc.next_action:
            console.show_recipes([{"command": svc.next_action, "tip": "recorded next action"}], 0, ip)
        else:
            console.show_text(f"{svc.port}/{svc.protocol} {svc.service} — no command recorded")

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        lv = event.list_view
        idx = lv.index if lv.index is not None else -1
        if lv.id == "arsenal-cats" and 0 <= idx < len(self._arsenal_cat_names):
            self._refresh_arsenal(self._arsenal_cat_names[idx])
        elif lv.id == "arsenal-cmds" and 0 <= idx < len(self._arsenal_cmd_texts):
            cmd = self._arsenal_cmd_texts[idx]
            copy_to_clipboard(cmd)
            self.query_one("#console", DeckConsole).flash_copied(cmd)

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        data = event.node.data if event.node else None
        if data and data.get("target_id"):
            self.store.set_active_target(int(data["target_id"]))
            self.refresh_all()

    # -- actions ------------------------------------------------------------------
    def action_station(self, tab_id: str) -> None:
        self.query_one("#stations", TabbedContent).active = tab_id

    def action_switch_tab(self, tab_id: str) -> None:
        mapping = {
            "tab-worksheet": "deck-cockpit", "tab-playbooks": "deck-arsenal",
            "tab-creds": "deck-vault", "tab-loot": "deck-intel",
        }
        self.action_station(mapping.get(tab_id, tab_id))

    def action_toggle_rail(self) -> None:
        rail = self.query_one("#rail")
        rail.styles.display = "none" if rail.styles.display != "none" else "block"

    def action_cycle_panel(self) -> None:
        order = ["#rail", "#svc-grid", "#ck-grid", "#deck-input"]
        cur = self.focused
        ids = [o[1:] for o in order]
        nxt = ids[(ids.index(cur.id) + 1) % len(ids)] if cur is not None and cur.id in ids else ids[0]
        try:
            self.query_one(f"#{nxt}").focus()
        except Exception:
            pass

    def action_target(self, delta: int) -> None:
        targets = self.store.list_targets()
        if not targets:
            return
        ids = [t.id for t in targets]
        cur = ids.index(self.active_target.id) if self.active_target and self.active_target.id in ids else 0
        self.store.set_active_target(ids[(cur + delta) % len(ids)])
        self.refresh_all()

    def action_recipe(self, delta: int) -> None:
        self.query_one("#console", DeckConsole).cycle(delta)

    def action_copy_current(self) -> None:
        cmd = self.query_one("#console", DeckConsole).current_command()
        if cmd:
            copy_to_clipboard(cmd)
            self.query_one("#console", DeckConsole).flash_copied(cmd)
        else:
            self.notify("nothing to copy — highlight a service row")

    def action_cycle_status(self) -> None:
        focused = self.focused
        if not isinstance(focused, DataTable):
            return
        row = focused.cursor_row
        if row is None:
            return
        if focused.id == "ck-grid" and row < len(self._ck_rows):
            self.store.cycle_checklist_status(self._ck_rows[row].id)
            self.refresh_all()
        elif focused.id == "svc-grid" and row < len(self._svc_rows):
            self.store.cycle_service_status(self._svc_rows[row].id)
            self.refresh_all()
        elif focused.id == "vault-grid":
            coord = focused.cursor_coordinate
            if not coord or coord.column <= 0:
                return
            if coord.row >= len(self._cred_rows) or coord.column - 1 >= len(self._auth_pairs):
                return
            c = self._cred_rows[coord.row]
            t, s = self._auth_pairs[coord.column - 1]
            curr = self._cell_states.get((c.id, s.id), self._cycle[0])
            try:
                nxt = self._cycle[(self._cycle.index(curr) + 1) % len(self._cycle)]
            except ValueError:
                nxt = self._cycle[0]
            self._cell_states[(c.id, s.id)] = nxt
            try:
                self.store.set_cred_validation(c.id, s.id, nxt)
            except Exception:
                pass
            focused.update_cell_at(coord, nxt)
            self._refresh_vault()

    def action_focus_command(self) -> None:
        inp = self.query_one("#deck-input", Input)
        inp.value = ":"
        inp.cursor_position = 1
        inp.focus()

    def action_show_help(self) -> None:
        self.push_screen(HelpModal())

    def action_open_search(self) -> None:
        self.push_screen(SearchModal(store=self.store))

    def action_apply_template(self) -> None:
        tid = self.active_target.id if self.active_target else None

        def done(result: Any) -> None:
            if not result:
                return
            name, replace = result if isinstance(result, tuple) else (result, True)
            try:
                items = apply_template_to_store(self.store, name, target_id=tid, replace=replace)
                self.notify(f"{str(name).upper()}: {len(items)} items")
            except ValueError as e:
                self.notify(str(e), severity="error")
            self.refresh_all()

        self.push_screen(TemplateSelectionModal(), callback=done)

    def action_open_theme_picker(self) -> None:
        self.push_screen(ThemePickerModal(self.theme_name, store=self.store))

    def action_cycle_theme(self) -> None:
        names = list(PALETTES)
        idx = names.index(self.theme_name) if self.theme_name in names else 0
        self.apply_theme(names[(idx + 1) % len(names)])

    def apply_theme(self, name: str, quiet: bool = False) -> None:
        resolved = resolve_palette_name(name)
        if not resolved or resolved not in PALETTES:
            self.notify(f"unknown theme {name!r}", severity="warning")
            return
        self.theme_name = resolved
        palette = set_palette(resolved)
        self.theme = palette.textual_theme().name
        if not quiet:
            self.notify(f"Theme: {palette.label}")
        self.refresh_all()

    def set_default_theme(self, name: str) -> None:
        save_default_theme(name, self.store)
        self.apply_theme(name, quiet=True)

    # -- add modals ----------------------------------------------------------------
    def action_add_target(self) -> None:
        def done(data: Optional[dict]) -> None:
            if data and data.get("ip"):
                target = self.store.add_target(
                    ip=data["ip"], hostname=data.get("hostname", ""),
                    os_name=data.get("os", "Unknown") or "Unknown", notes=data.get("notes", ""),
                )
                if target:
                    for p in data.get("ports", []):
                        self.store.add_service(target_id=target.id, port=p, protocol="tcp", service="unknown")
                self.refresh_all()
        self.push_screen(AddTargetModal(), callback=done)

    def action_add_service(self) -> None:
        if not self.active_target:
            self.notify("add a target first (t)", severity="warning")
            return

        def done(data: Optional[dict]) -> None:
            if data and data.get("port"):
                try:
                    self.store.add_service(
                        target_id=self.active_target.id, port=int(data["port"]),
                        protocol=data.get("protocol", "tcp"), service=data.get("service", "unknown"),
                        version=data.get("version", ""), access_potential=data.get("potential", ""),
                        next_action=data.get("next", ""),
                    )
                    self.refresh_all()
                except ValueError:
                    self.notify("port must be an integer", severity="error")
        self.push_screen(AddServiceModal(target_ip=self.active_target.ip), callback=done)

    def action_add_credential(self) -> None:
        tid = self.active_target.id if self.active_target else None

        def done(data: Optional[dict]) -> None:
            if data and data.get("username"):
                self.store.add_credential(
                    username=data["username"], secret=data.get("secret", ""),
                    source=data.get("source", ""), target_id=tid,
                    service_scope=data.get("scope", ""),
                )
                self.refresh_all()
        self.push_screen(AddCredentialModal(), callback=done)

    def action_add_note(self) -> None:
        tid = self.active_target.id if self.active_target else None

        def done(data: Optional[dict]) -> None:
            if data and data.get("content"):
                self.store.add_note(content=data["content"], target_id=tid)
                self.refresh_all()
        self.push_screen(FastInputModal(title="Record Field Note", fields=[("content", "Note *", "")]), callback=done)

    def action_add_finding(self) -> None:
        tid = self.active_target.id if self.active_target else None

        def done(data: Optional[dict]) -> None:
            if data and data.get("title"):
                self.store.add_finding(
                    title=data["title"], target_id=tid,
                    description=data.get("desc", ""), severity=data.get("severity") or None,
                )
                self.refresh_all()
        self.push_screen(AddFindingModal(), callback=done)


if __name__ == "__main__":
    MissionDeck().run()
