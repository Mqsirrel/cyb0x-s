# GLACIS — Terminal UI Visual Design & UX Audit

**Scope:** every station and modal of the GLACIS TUI, rendered at **160 × 44**.
**Method:** the audit was performed against the *compositor text* of each screen
(`python dev/screentext.py <dir> 160 44`), not only the PNGs. Text output is the
ground truth for a TUI: it exposes exact column alignment, truncation points,
whitespace and border joins that a raster hides. Every finding below is
reproducible; every fix quoted in Part 4 is **already implemented on this
branch** and covered by `tests/test_visual_design.py`.

Review lenses: **Aesthetic polish** · **Clarity & self-explanation** ·
**Usability under exam pressure (the 2-second rule)**.

---

## 0. Executive summary

| # | Finding | Severity | Status |
|---|---|---|---|
| 1 | Console bar on Station 2 crashed its own repaint (`MarkupError: closing tag '[/Search]'`) and silently displayed Station 1's guidance | **Critical** | Fixed |
| 2 | All 8 palettes failed WCAG AAA for `muted`; the three light palettes failed *AA* for `ok`/`warn` (`candy` ok = **2.14:1**) | **Critical** | Fixed |
| 3 | Panel borders sat at **1.34 – 1.56:1** against their own surface — the layout grid was barely drawn | High | Fixed (2.20:1) |
| 4 | 9 emoji + 4 non-glyph codepoints used in chrome are **absent from DejaVu Sans Mono**, the default Linux terminal font | High | Fixed |
| 5 | ~25 rows of dead space on Pulse / Credentials, ~20 on Network, ~17 per card on Loot | High | Reduced (legends + 2-line rows) |
| 6 | Rows guillotined mid-word with no ellipsis (`…listing backu`) | Medium | Fixed |
| 7 | Two-up dialogs had 32/33-wide columns whose inputs never lined up | Medium | Fixed |
| 8 | Same key hints printed up to **four times** on one screen (Credentials) | Medium | Fixed |
| 9 | Glyph collisions: `★` meant "Loot", "root", "pwned" *and* "credential count" | Medium | Fixed |
| 10 | Modal scrim hard-coded to `rgba(6,9,12,0.78)` — fought every light palette | Low | Fixed |

Measured before/after contrast (worst case across `bg` **and** `surface`):

```text
palette       text  soft  muted accent    ok  warn danger   border/surface
slate        13.62  9.93  7.05*  9.92 10.88  9.45   7.04*   2.21*
midnight     13.46  8.91  7.03*  7.16 11.57 10.36   7.05*   2.21*
ember        14.55 10.50  7.03*  9.69 11.33  7.68   7.06*   2.21*
cyber        15.76  9.61  7.02* 11.51 12.29 10.21   7.06*   2.22*
sugary       12.55  8.75  7.04*  7.03* 7.04* 7.03*  7.04*   2.21*
candy        13.43  7.71  7.06*  7.03* 7.07* 7.05*  7.05*   2.21*
caramel      13.13  7.47  7.05*  7.73  7.08* 7.02*  7.02*   2.21*
catppuccin   12.14  9.91  7.02*  8.34 11.81  9.92   7.58    2.21*
                                    * = changed by this audit
```

---

## 1. Station-by-station audit

### Station 0 — Pulse (`docs/screenshots/00-pulse.png`)

**What works well**

- The board concept is right: *hosts left, named next-focus signals right* is
  exactly the "what do I do next" panel an exam needs.
- Advisories carry a rule ID (`[S5-root-without-vector]`), a reason, and a
  concrete action. That is genuinely explainable — keep this structure.
- Phase glyphs (◇ ◐ ▸ ◆ ★ ✔) form a real kill-chain ramp.

**Design flaws & clutter**

1. **25 of 27 board rows were empty.** With two hosts the panel reads as a
   broken render, not as a short list.
2. **Counters were unreadable codes.** `s1/u1 ✖1` requires the manual; `svc`
   and `todo` do not.
3. **The KPI band's two boxes touched each other** — `┐┌` with no gutter:
   ```text
   ┌──…──┐┌────…────┐
   │ OVERALL 47.5% … ││  STATE ONLY …  │
   ```
4. The hosts panel had **no legend**, so the glyph ramp and the counters both
   had to be inferred.
5. Panel subtitles said only `2 hosts` / `2 signals` — true, but the only number
   that changes a decision is *how many ports are still untested*.

**Implemented**

- Host rows became **two lines**: identity/phase on top, inventory below.
- Counters spell themselves out and the actionable one is the only one in
  warning colour:
  ```text
  ◐ 172.16.1.50      db01.corp.intern…  █░░░░░░░  15% [RECON   ]
    █░░░░░░░  svc 1 · todo 1 · cred 0 · ev 0 · ✖1 dead
  ```
- Anchored legend pinned to each panel floor (`.panel-legend`).
- Subtitles now carry the decision number: ` 2 hosts · 1 untested · 2 dead `.
- `· end of signals` terminal marker so a short list reads as *complete*.
- `margin-left: 1` on `#pulse-mode` to open the KPI gutter.

---

### Station 1 — Cockpit (`docs/screenshots/01-cockpit.png`)

**What works well**

- The 2 × 3 grid is the correct information architecture: surface → services →
  methodology/notes, with the console pinned at the bottom.
- Double-border on `:focus-within` is a strong, glare-free focus cue.
- The status strip answers "which box / what's captured / what's next / what
  blocks me" in three lines.

**Design flaws & clutter**

1. **Emoji in panel titles** (`★ ATTACK SURFACE TREE`, `🔑 QUICK CREDS`,
   `📋 METHODOLOGY ROADMAP`, `📝 FIELD NOTES & FINDINGS`) — see §2.4: five of
   these are missing from the default terminal font.
2. `🕳 1 dead end` used an emoji where the rest of the app uses `✖`.
3. **Status pills had hand-tuned padding** (`"[CHECKED] "`, `"[DEFER]   "`,
   `"[DEAD-END]"`, `"[TODO]    "`) — a different width per state, so the port
   column shifted between rows.
4. Checklists used `⏸` and `⏳`, both absent from DejaVu Sans Mono.
5. Long note/evidence rows were cut mid-word with no marker.

**Implemented**

- Panel titles use the shared glyph taxonomy (`▣ ▥ ☰ ▤ ◆`).
- One status vocabulary, one pill width:

  ```python
  # src/glacis/tui/widgets/lists.py
  STATUS_BADGES = {
      "TODO":     ("[TODO]",     "accent"),
      "CHECKED":  ("[CHECKED]",  "ok"),
      "DEFERRED": ("[~ DEFER]",  "warn"),
      "DEAD-END": ("[DEAD-END]", "danger"),
  }

  def status_badge(status_val: str, width: int = 12) -> Text:
      label, token = STATUS_BADGES.get(status_val, STATUS_BADGES["TODO"])
      return Text(f" {label:<{width - 2}} ", style=f"bold {P.bg} on {getattr(P, token)}")
  ```
- Checklist pills: `[✔ DONE]` / `[~ DEFER]` / `[✖ DROP]` / `[▸ TODO]`.
- CSS ellipsis on single-line lists (see §3.2):
  ```text
  before: [EVID] evidence/proof_screenshot_01.png — Anonymous SMB access listing backu
  after:  [EVID] evidence/proof_screenshot_01.png — Anonymous SMB access listing back…
  ```

---

### Station 2 — Playbooks (`docs/screenshots/02-playbooks.png`)

**What works well**

- The category rail + command list split is fast and predictable; recipe rows
  show the command *and* why you would run it.

**Design flaws & clutter**

1. **Critical bug.** The console bar's Station-2 subtitle was
   `" [/ Search] · [Enter: Copy] "`. Textual parses a `str` border title as
   console markup, so `[/` was read as a closing tag:
   ```text
   textual.markup.MarkupError: closing tag '[/Search]' does not match any open tag
   ```
   The exception was raised *inside* `_paint()`, which the caller wrapped in
   `try/except Exception: pass` — so the console silently kept **Station 1's**
   copy while showing Station 2's title. Pressing `2` produced:
   ```text
   ┌─ STATION 2 · ATTACK PLAYBOOKS ─…─┐
   │ COCKPIT ▸ Highlight a service or step to preview & copy commands …     │
   ```
2. The `QUICK SEARCH` box consumed three full rows for one placeholder with a
   `🔍` emoji.
3. Category rows had no selection marker (`[★ ALL]` vs `●`), and `★` collided
   with the "root/pwned" meaning used elsewhere.

**Implemented**

- `set_border_text()` assigns `Text` objects, never markup strings; the whole
  idle-title table routes through it (Part 4.1).
- Search placeholder is plain text with a typographic ellipsis.
- Station copy rewritten so it names the interaction, not the keys:
  *PLAYBOOKS ▸ Pick a category, highlight a recipe, Enter copies it — then run
  it in your own shell.*
- Regression test: `test_console_bar_follows_the_active_station` walks `0…5`
  and asserts the console bar's tag matches the station.

---

### Station 3 — Credential Matrix (`docs/screenshots/03-creds.png`)

**What works well**

- The 2-D credential × service matrix is the right mental model for spraying,
  and the empty-state guide is genuinely instructive.

**Design flaws & clutter**

1. **26 empty rows** below two credential rows.
2. **The same four keys printed four times** on one screen: top bar, panel
   subtitle, console body, console subtitle.
3. **Glyph collision:** the KPI pills used `★` for *both* the credential count
   and the pwned count; `👑 PWN3D` (emoji) in the guide vs `[★ PWN3D]` in the
   cells.
4. **Column misalignment:** auto-sized `DataTable` columns let a 9-char
   `[✔ VALID]` sit in the same column as a 12-char `[○ UNTESTED]`, so the
   header drifted 1–3 cells away from its data.
5. `PWNED` (top bar) vs `PWN3D` (cells) — two spellings of one state.

**Implemented**

- KPI pills: `◆ CREDS` · `✔ VALIDATED` · `★ PWN3D` · `▸ SPRAY TARGETS`.
- The duplicate shortcut strip was **removed**; the top bar now shows the one
  number available nowhere else — `3/8 cells tested`.
- Fixed column widths (`32` + `20` per service) and state pills padded to a
  uniform 14 cells, so every column starts on the same raster:
  ```text
  CREDENTIAL (USER : SECRET)        10.10.10.20:22 SSH    10.10.10.20:80 HTTP
  [WEB / SSH]  admin : •••••••••••   [✔ VALID]             [○ UNTESTED]
  ```
- The table is wrapped in `#cred-matrix-panel` so the legend sits **inside** the
  frame (it previously rendered outside the border), and no longer draws a
  second, nested border.
- Pinned legend: `CELL ▸ ○ UNTESTED → ✔ VALID → ★ PWN3D → ✗ INVALID   [Space]
  cycle · [Enter] copy spray · [x] reveal · [c] add cred`.

---

### Station 4 — Loot & Flags (`docs/screenshots/04-loot.png`)

**What works well**

- Six cards, each with an empty state that states the exact command to run
  (`:foothold <vuln>`, `:privesc <vector>`, `:stuck`, `:clue`). Excellent.

**Design flaws & clutter**

1. **17 blank rows in each lower card.**
2. **Two cards shared the `★` glyph** (Objectives *and* PrivEsc).
3. Wrapped empty-state copy lost its bullet on line two:
   ```text
   • Type :foothold <vuln> or :foot <cmd> to
   record.
   ```
4. `[▸ PASTE]  Press 'v' or :paste-ev from clipbo` — clipped mid-word.
5. The `Press 'a' / :q …` hint lines were **composed and then hidden**
   (`display: none`), so the panels had no affordance at all.

**Implemented**

- One glyph per card: `★ OBJECTIVES` · `▸ FOOTHOLD` · `▲ PRIVESC` ·
  `◆ PROOFS` · `▤ FILES` · `▼ RABBIT HOLES`.
- `.loot-sub` un-hidden, moved below the list and restyled as the panel's floor
  legend — with real keycaps built as `Text` (a markup string silently drops
  `[a]`, `[e]`, `[Enter]`):
  ```text
  │ [a] add proof · [e] export · [Enter] copy        │
  │ [Enter] copy path · [Space] preview · [v] paste  │
  │ [Space] cycle · [:stuck <where>] log it …        │
  ```
- Empty-state copy shortened to fit its card; no orphaned continuation lines.

---

### Station 5 — Network (`docs/screenshots/05-network.png`)

**What works well**

- Copy-ready tunnel syntax ordered from scaffolding (ProxyChains) → hops → scan
  hint is the correct sequence, and `Enter` copying is frictionless.

**Design flaws & clutter**

1. **Half-drawn ASCII boxes.** `┌─ Subnet: …` followed by a dangling
   `└───────────────` ruler with no right edge reads as a rendering fault.
2. **Double framing:** an `=== NETWORK TOPOLOGY: LAB-01 ===` banner inside a
   panel already titled `DOCUMENTED NETWORK TOPOLOGY`.
3. 22 empty rows under a two-subnet map; the map panel had no subtitle while
   the actions panel did.
4. Multi-line commands were clipped (`… (+6 lines)` on an un-elided line).

**Implemented** (`src/glacis/routes.py` + `stations/network.py`)

- The map is now drawn **closed** and measured: every subnet box is sized to its
  widest line, so top/bottom/body all end on the same column:
  ```text
    ┌─ Subnet: 10.10.10.0/24 ─────────────────────────────┐
    │   • 10.10.10.20 (target.local) [⇄ DUAL-HOMED PIVOT] │
    └─────────────────────────────────────────────────────┘
  ```
- The banner is gone; its counts moved into the panel subtitle
  (` 2 subnet(s) · 1 pivot(s) · 2 host(s) `).
- Anchored legend explains the notation *and* the safety boundary:
  *"Enter copies the highlighted tunnel command — GLACIS sends nothing itself"*.
- Action labels and every command line are elided to the panel width.

---

### Help (`06`) · Reference (`07`) · Dialogs (`08`–`10`)

**What works well** — the help content is genuinely complete (stations,
navigation, capture commands, shell equivalents) and both dialogs front-load
the most important field.

**Design flaws & clutter**

1. `ModalScreen` dimmed with a **hard-coded** `rgba(6, 9, 12, 0.78)` — a
   near-black scrim over the cream/lilac light palettes.
2. Add-target / add-service columns were `1fr` + `margin-right: 1`, which
   Textual rounds to **32 / 33** — the input boxes never lined up:
   ```text
   │  ╭──────────────────────────────╮ ╭───────────────────────────────╮  │
   ```
3. `*` marked required fields with **no legend explaining it**.
4. Buttons read `Save Target (Enter)` / `Cancel (Esc)` in prose while the rest
   of the app uses `[Enter]` keycaps.
5. `📖` / `📝` / `🔍` in modal headers (absent from the default font).
6. The help modal's `Close` button had no key hint; the body had no scroll hint.

**Implemented**

- `ModalScreen { background: $background 82%; }` — palette-derived scrim.
- Two-up forms moved to a real `Grid` (`grid-columns: 1fr 1fr`), and the shared
  dialog width is **odd** (73) so the inner width minus the gutter splits into
  two *equal* columns:
  ```text
  │  ╭───────────────────────────────╮ ╭───────────────────────────────╮  │
  │  │ e.g. 10.10.11.10              │ │ e.g. dc01.corp.local          │  │
  ```
- `required_legend()` line on every form: `* required · [Enter] saves · [Esc]
  cancels · [Tab] next field`.
- Help modal gained a keycap hint row: `[↑ ↓] scroll · [Esc] close · [/]
  search · [T] theme`, and the button reads `Close  (Esc)`.
- Emoji removed from all modal headers.

---

## 2. Top 5 high-impact enhancements

### 2.1 Fix the invisible crash — markup-safe chrome

The Station-2 `MarkupError` is the highest-severity finding because it is
*silent*: a user on Station 2 was reading Station 1's guidance. The general rule
is now enforced by one helper used everywhere (Part 4.1): **border titles and
subtitles are `Text`, never `str`.**

### 2.2 Earn the AAA claim — measured, not asserted

`muted` failed 7:1 in **all eight** palettes, and the light palettes were far
worse (`candy.ok` = 2.14:1 — the `[✔ VALID]` pill was effectively invisible).
All 56 semantic token/background pairs now clear 7:1, and
`contrast_audit()` + a parametrised test keep them there. On light palettes this
meant moving to 700/800-level hues; `caramel`'s accent moved to a deep teal so
the focus colour stays distinguishable from `warn` amber at AAA darkness.

### 2.3 One glyph, one meaning — no emoji

Chrome glyphs now come from a single `GLYPHS` taxonomy, verified to exist in
DejaVu Sans Mono and to advance exactly one cell. `SAFE_CHROME_GLYPHS` plus two
tests enforce it. Every duplicate meaning inside a vocabulary was resolved
(`★` = root/pwned/Loot-station only, never "credential count").

### 2.4 Turn dead space into explanation

A board with 25 empty rows is worse than no board: it reads as breakage. Three
moves, applied consistently:

- **Legends pinned to the panel floor** (`.panel-legend`, `.loot-sub`) — the
  panel now decodes itself *and* gains a bottom edge.
- **Two-line rows** where the second line carries the inventory (Pulse hosts).
- **Terminal markers** (`· end of signals`) so short lists read as complete.

### 2.5 The 2-second raster

Under exam pressure the reader scans columns, not sentences. So:

- Fixed-width status pills → port/service/version columns never shift.
- Fixed-width matrix columns → header stays above its data.
- CSS ellipsis on single-line rows → truncation is *marked*.
- Uniform keycap language (`[Space]`, `[Enter]`) rendered as `Text` so brackets
  survive.
- Duplicated hint strips deleted (four copies on one screen → two).

---

## 3. Concrete implementation changes

### 3.1 `src/glacis/tui/theme.py` — tokens, contrast, glyphs

```python
#: WCAG 2.1 "enhanced" (AAA) threshold for body text.
AAA_CONTRAST = 7.0
#: Non-text contrast (SC 1.4.11) — the floor we hold panel borders to.
STRUCTURE_CONTRAST = 2.0

def contrast_audit(*, text_target=AAA_CONTRAST,
                   structure_target=STRUCTURE_CONTRAST) -> dict[str, list[tuple]]:
    """Every palette/token pair that misses its target (empty == clean)."""
```

- 8 palettes retuned (§0 table) + `border` raised to ~2.2:1 vs `surface`.
- `border-strong` exposed as a CSS variable (`$border-strong`) for scrollbars.
- `GLYPHS` / `SAFE_CHROME_GLYPHS` added (§2.3).

### 3.2 Stylesheet (`APP_CSS`)

```css
/* Rows are composed in Python, so a long value must be *elided* by the
   renderer instead of being guillotined mid-word by the widget edge.
   Only single-line lists get this: advisory / recipe / proof rows are
   deliberately multi-line and must keep wrapping. */
#list-services ListItem, #list-creds ListItem, #list-checklist ListItem,
#list-notes ListItem, #list-targets ListItem, .single-line { width: 100%; }

#list-services Label, #list-creds Label, #list-checklist Label,
#list-notes Label, #list-targets Label, .single-line {
    width: 100%;
    text-overflow: ellipsis;
    text-wrap: nowrap;
}

/* Station identity is a hard, inverted pill: colour alone is not an
   affordance, and a stressed reader must find "where am I" in one glance. */
Tab.-active { color: $background; background: $accent; text-style: bold; }
Underline > .underline--bar { background: $border; color: $accent; }

/* Panel legends: a key pinned to the floor of a board. */
.panel-legend, .loot-sub {
    height: 3;            /* .loot-sub: 2 */
    padding: 0 1;
    color: $text-muted;
    border-top: solid $border;
}

/* Palette-derived scrim instead of a hard-coded near-black. */
ModalScreen { background: $background 82%; }

/* Odd width so a two-column form grid splits into two *equal* columns. */
.glacis-modal-dialog, .synapse-modal-dialog {
    width: 73; height: auto; max-height: 92%; overflow-y: auto;
}
.form-grid { layout: grid; grid-size: 2; grid-columns: 1fr 1fr; grid-gutter: 1 1; }
```

Also: `scrollbar-color*` (the previous `scrollbar:` rule name was invalid and
broke the stylesheet), and `#cred-matrix-table { border: none }` to remove the
nested double frame.

### 3.3 `src/glacis/tui/widgets/chrome.py`

```python
def set_border_text(widget, *, title=None, subtitle=None) -> None:
    """Assign a border title/subtitle as Rich Text, never as markup."""
    if title is not None:
        widget.border_title = Text(title)
    if subtitle is not None:
        widget.border_subtitle = Text(subtitle)
```

- Every `ConsoleBar` title/subtitle goes through it.
- The idle-title table gained an explicit `tab-worksheet` entry, so the
  `else` branch can no longer masquerade as another station.
- `🕳 N dead end` → `✖ N dead end`; `◇ TARGET` / `◈ <ip>` / `[USER: ✔]` read
  from `GLYPHS`.
- `_elide()` now delegates to the shared `lists.elide`.

### 3.4 `src/glacis/tui/widgets/lists.py`

```python
def elide(value, width, ellipsis="…") -> str: ...
def elide_middle(value, width, ellipsis="…") -> str: ...   # keeps paths/flags tails
def keycap_line(*pairs) -> Text: ...      # "[a] add proof · [Enter] copy"
def legend_line(*entries) -> Text: ...    # "★ root   ◆ user"
def status_badge(status_val, width=12) -> Text: ...
```

`elide_middle` matters for the two string types where the tail is the identity:

```text
elide_middle("evidence/proof_screenshot_01.png", 24) -> "evidence/pro…shot_01.png"
elide_middle("eJPT{root_flag_f04b8d195ae32}", 20)    -> "eJPT{root_…d195ae32}"
```

### 3.5 Stations

- `stations/pulse.py` — two-line host rows, per-panel legends, decision-bearing
  subtitles, `· end of signals`, KPI gutter, `48/52` split.
- `stations/network.py` — elided action rows, panel subtitle counts, legend.
- `src/glacis/routes.py` — closed, measured subnet boxes; banner removed.

### 3.6 Widgets & modals

- `widgets/loot.py` — unique card glyphs, `.loot-sub` legends with real
  keycaps, `👑 → ★`, `PWNED → PWN3D`, uniform 14-cell state pills, fixed
  column widths, matrix wrapped so the legend is inside the frame.
- `modals.py` — `Grid`-based forms, `required_legend()`, `Close  (Esc)`,
  help-modal keycap hint, emoji-free headers.

---

## 4. Verification & regeneration

```bash
python -m pytest tests/test_visual_design.py -q     # 33 design regressions
python -m pytest -q                                 # 269 passed
python dev/screentext.py .arena/screens 160 44      # text renders (alignment)
python dev/screenshot.py docs/screenshots slate     # 11 PNGs, manifest names
```

New tests (`tests/test_visual_design.py`) lock in: AAA contrast per palette and
per token, border contrast, accent↔background legibility for the active-tab
pill, glyph verification and per-domain uniqueness, markup-safe keycap titles,
console-bar-per-station behaviour, and the elide/pill-width contracts.

---

## 5. Recommended next steps (not implemented)

1. **Density mode.** A `compact` screen class already exists; extend it to
   collapse legends and the second line of Pulse host rows below ~40 rows.
2. **Right-aligned numeric columns** in the Pulse inventory line, so `svc 12`
   and `svc 3` align when a workspace has many hosts.
3. **Advisory grouping** by severity with a one-line summary header per group
   once a workspace produces more than ~8 signals.
4. **Secret masking** currently leaks length (`•••••` vs `••••••••`); mask to a
   fixed 8 bullets and reveal on demand.
5. **Keyboard-only legend tour**: a single `?`-reachable card showing the glyph
   taxonomy with live palette swatches.
