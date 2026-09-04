# CYB0X-S UI/UX Redesign v2 — "Mission Deck"

Status: proposed · Scope: TUI + CLI polish · Compliance: governed by
[EXAM_COMPLIANCE.md](EXAM_COMPLIANCE.md) — every rule there applies to this
redesign (fully offline, passive by design, derived guidance opt-in).

A runnable mock of this layout lives at `dev/redesign_preview.py`:

```bash
uv run python dev/redesign_preview.py
```

---

## 1. Design goals

1. **Exam speed** — every frequent action reachable in ≤ 2 keystrokes from
   anywhere. The exam clock is the real enemy.
2. **Glanceable** — after alt-tabbing back, full state is readable in < 2 s.
3. **Calm** — no visual noise. Colour carries meaning, never decoration.
4. **Keyboard-first** — complete operation without a mouse.
5. **Compliant** — passive notebook; nothing scans, suggests, or phones home.

## 2. Information architecture

Rename the four stations from nouns to verbs/questions:

| Key | Station | Question it answers |
|-----|---------|---------------------|
| 1 | Engage | What do I do next on this target? (worksheet, services) |
| 2 | Arsenal | What is the exact command? (playbooks, reference) |
| 3 | Vault | What credentials do I hold? (cred matrix, hashes) |
| 4 | Intel | What did I win, and where am I stuck? (flags, timeline, failure log) |

Names are cheap; consistent mental slots are not. Digits 1–4 keep working.

## 3. Layout

```
┌ CYB0X-S · ejpt-lab ───── T+04:12:35 ─ target 10.10.10.5 (web) ─ flags 2/4 ─ [######..] 62% ┐
│                                                                                             │
│ ┌ TARGETS ──────────┐ ┌ ENGAGE ─────────────────────────────────────────────────────────┐  │
│ │ 10.10.10.5  ●3    │ │ PORT   SERVICE   STATUS      CRED    NEXT ACTION                │  │
│ │  ├ 22  ssh   ○    │ │ 22     ssh       open        —       enum users                 │  │
│ │  ├ 80  http  ◐    │ │ 80     http      enum        —       dirb vhosts                │  │
│ │  └ 443 https ●    │ │ 443    https     exploited   admin   loot flags                 │  │
│ │ 10.10.10.6  ○0    │ │ …                                                             │  │
│ └───────────────────┘ └─────────────────────────────────────────────────────────────────┘  │
│ ┌ CONSOLE ─────────────────────────────────────────────────────────────────────────────┐  │
│ │ $ hydra -l admin -P rockyou.txt ssh://10.10.10.5     [enter] copy [e] edit [x] ran ✓ │  │
│ └───────────────────────────────────────────────────────────────────────────────────────┘  │
│ :uflag 10.10.10.5 ▎                     ghost: record user flag for active target          │
└ 1 engage · 2 arsenal · 3 vault · 4 intel · b rail · : cmd · q quit ───────────────────────┘
```

Zones, top to bottom:

- **StatusStrip (1 row)** — workspace · elapsed exam clock · active target +
  scope pill · flags x/y · methodology progress bar (done/total checklist).
- **TargetRail (≈30 cols, `b` toggles)** — tree of targets → services.
  Glyphs: `●` findings, `◐` partial, `○` untouched. Sort: most recent
  activity first. Collapses to an overlay under 110 columns.
- **Station area (1fr)** — the four tabbed stations.
- **ContextConsole (3 rows, collapsible)** — the command bound to the
  highlighted row, with `{IP}`/`{PORT}` already substituted. `enter` copies,
  `e` edits inline, `x` marks-ran (logs a timestamp to the timeline).
- **CommandBar (1 row)** — `:` focuses; ghost-text completion from the alias
  table; `↑` history. Aliases keep working: `:uflag` `:rflag` `:stuck`
  `:clue` `:m <methodology>` `:theme <name>`.
- **Footer (1 row)** — contextual: shows only the keys valid for the focused
  widget. Never more than ~7 entries.

## 4. Design tokens

Keep the current rule — zero literal colours in widget CSS — and extend it:

- **Roles**: `accent`, `accent-2`, `success`, `warning`, `danger`, `info`.
  **Surfaces**: `base` → `raised` → `overlay` (darkest to lightest).
  **Text**: `primary`, `muted`, `inverse`.
- **Status semantics are fixed across palettes** — `open=info`,
  `filtered=muted`, `exploited=success`, `failed=danger`, `partial=warning`.
  Only hues change per theme, never the meaning.
- **Spacing scale**: 0 / 1 / 2 / 4 cells. Cards `padding: 0 1`, modals
  `1 2`, section gaps `1`.
- **Typography**: bold for values, dim for labels, italic only for hints.
  Never colour+bold+underline the same element.
- **Borders**: raised cards `round`, focused card border `accent`, modals
  `thick accent`.

## 5. Component specs

- **StatusStrip** — segments separated by `·`; scope pill is green only when
  the active target passed the scope check, red-outline otherwise (scope
  safety stays visible, per the compliance charter).
- **ServiceGrid (Engage)** — DataTable, `cursor_type="row"`, zebra off
  (rows carry their own state colour). Highlighting a row drives the
  ContextConsole. Columns: PORT · SERVICE · STATUS · CRED · NEXT.
- **Arsenal** — left: category list; right: command card with substitution
  preview. `enter` on a card copies with variables filled.
- **Vault** — grouped by host; hash-type pill (NTLM / SHA-512 / …); secrets
  masked by default, `v` reveals the highlighted row only.
- **Intel** — flag cards (user/root) + reverse-chron timeline + failure log
  with a streak badge: `3 fails in 30m — rotate?` (opt-in, off by default —
  it is derived guidance).
- **ModalBase** — one base class: title left, `esc` hint right, inputs with
  dark rounded boxes and accent focus border (current style), destructive
  actions always via ConfirmModal (already fixed once — keep it).

## 6. Motion and feedback

- Transitions ≤ 100 ms, opacity/offset only. No looping animations by
  default; `CYB0X_REDUCED_MOTION=1` kills all animation.
- Copy action: console border flashes `success` for ~120 ms (see preview).
- Long operations (scan import, export) show an indeterminate bar in the
  StatusStrip, never a modal spinner that blocks keys.

## 7. Performance plan

Budgets on an exam laptop at 100 columns:

| Metric | Budget |
|---|---|
| Cold start to interactive | < 400 ms |
| Keypress → paint (p95) | < 50 ms |
| Station switch (already mounted) | < 30 ms |
| Search keystroke | debounced 150 ms |

How:

- Keep lazy tab mounting; move scan parsers to `@work(thread=True)`.
- Debounce `Input.Changed` (150 ms) on search and reference lookup.
- Row render cache keyed on `(row_id, updated_at)` — never re-render an
  unchanged row. Never call `app.refresh()`; update the minimal widget.
- SQL: covering index on `(target_id, port)`; prepared statements; one
  transaction per capture burst instead of per-row writes.
- DataTable: paginate past 500 rows.
- Add a perf smoke test: cold start < 1 s against the demo-seed fixture DB
  (generous CI threshold, catches regressions).

## 8. Precondition: split the monoliths

All of the above lands on `tui/widgets.py` (~88 KB) and `tui/app.py`
(~60 KB). Before P2, split them — no visual change, pure moves:

```
src/cyb0x_s/tui/
├── app.py            # App shell, bindings, mode routing only
├── widgets/
│   ├── __init__.py
│   ├── strip.py      # StatusStrip
│   ├── rail.py       # TargetRail tree
│   ├── grid.py       # ServiceGrid
│   ├── console.py    # ContextConsole
│   ├── command.py    # CommandBar
│   └── modals.py     # ModalBase + concrete modals
└── stations/
    ├── engage.py
    ├── arsenal.py
    ├── vault.py
    └── intel.py
```

## 9. Rollout (PR-sized phases)

1. **P1** `refactor(tui): split widgets/app into widgets/ and stations/ packages`
2. **P2** `feat(tui): mission deck layout — strip, rail, console zones`
3. **P3** `feat(tui): component polish — status semantics, modal base, motion`
4. **P4** `perf(tui): row cache, debounce, worker parsing, perf smoke test`

Each phase runs the screenshot loop (`dev/screentext.py`,
`dev/screenshot.py`) and appends findings to `docs/UI_UX_REVIEW.md`.

## 10. Test plan additions

- Snapshot-ish geometry tests per station (extend `test_tui_ui.py`):
  strip is 1 row, console is 3, rail hidden < 110 cols.
- A test asserting every binding in the keymap appears in the footer or the
  `?` modal (single source of truth).
- Perf smoke test from §7, marked into the `tui` tier.
- `test_scope_safety.py` stays untouched and green.
