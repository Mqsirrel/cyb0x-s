# CYB0X-S — TUI/UX Review & Enhancement Backlog

**Reviewed:** 2026-09-01 · **Scope:** `src/cyb0x_s/tui/` (Textual app, widgets, theme) plus the
README shortcut tables · **Branch:** `arena/01a05e3f-cyb0x-s`

> **Follow-up (same branch): the interface has since been redesigned.**
> The findings below are still the defect record and the backlog, but the
> layout, the palette and the console are new — see
> **[§0 The redesign](#0-the-redesign-cockpit--slate--console)**. Sections 4–7
> describe the state *before* that work and are kept for the record.

---

## 0. The redesign: cockpit + slate + console

Three goals, chosen with the operator in mind: **see everything that matters on
one screen**, **know what to do next without hunting**, and **never clip a
command you are about to copy**.

### Layout — station 1 becomes a cockpit

The old station 1 was a 2×2 grid of equal panels, so every row was truncated to
~50 characters and the guidance drawer was a 4-row box that clipped the very
commands it existed to show. The new station 1 is a **cockpit**:

```
┌─ header: workspace + counters ───────────────────────────────────────────────┐
│ ◆ target  hostname  OS   [SCOPE]  🏁 👑 ⚡          ports · creds · vulns     │  status strip
│ NEXT ▸ first unchecked step   ▓▓▓▓▓░░░░░ 50% (2/4)            no blockers    │
│  1 ⌂ Cockpit   2 ▸ Playbooks   3 ▸ Credentials   4 ▸ Loot & Flags            │
├──────────────────┬───────────────────────────────────────────────────────────┤
│ ATTACK SURFACE   │ SERVICES & PORTS  (full width — rows never truncate)      │
│ CREDENTIALS      ├──────────────────────────────┬────────────────────────────┤
│                  │ METHODOLOGY + progress       │ NOTES & FINDINGS           │
├──────────────────┴──────────────────────────────┴────────────────────────────┤
│ ❯ command for the highlighted row                              [Enter]=copy  │  console
│   tip                                                                        │
│ ▸ fast-capture bar                                                           │
└──────────────────────────────────────────────────────────────────────────────┘
```

* **Status strip** (2 rows) answers the four exam questions: which box, what is
  captured, what is next, what is blocking me. Flag hashes, foothold, scope and
  counters are chips on the right.
* **Services get the full width** of the workbench, so `445/tcp smb Samba 4.3 ▸ smbmap -H …`
  renders in one line instead of being cut in half.
* **Credentials moved into the sidebar**, under the attack-surface tree, so they
  are visible in every station instead of competing with services for space.
* **Methodology and notes** share the lower band; the methodology header carries
  the progress bar (`▓▓▓▓▓░░░░░ 50% 2/4`) instead of a separate drawer.

Renders of the new cockpit: `dev/previews/cockpit-slate.png` (default),
`dev/previews/cockpit-warm.png` (legacy palette), `dev/previews/playbooks-slate.png`,
`dev/previews/loot-slate.png`. Regenerate any time with
`.venv/bin/python dev/screenshot.py <out-dir> [slate|warm]`.

### The console

The 4-row guidance drawer became a **full-width console** pinned under the
stations: row 1 shows the command for whatever is highlighted (checklist step,
service, or your own "next action"), row 2 its tip, row 3 is the fast-capture
bar. Long commands are elided with `…` and never wrap mid-word, and the console
is the same place you type `:s`, `:c`, `:stuck` — one destination for "what can I
run" and "record what I found".

### Palette — slate

| Role | `slate` (default) | `warm` (legacy) |
|---|---|---|
| chrome | `#0E1418` / `#151C22` | `#211E1B` / `#2A2622` |
| text | `#DDE6EE` (13.6:1) | `#EDE6DA` (13.4:1) |
| data / focus | cyan `#4FD6E8` | terracotta `#D97757` |
| captured / ok | mint `#6FE3B0` | sage `#8FA876` |
| warn / next | amber `#F5B455` | kraft `#D4A27F` |
| danger / vuln | coral `#FF8069` | `#E5846B` |

The stylesheet now contains **no literal colours** — every rule references a
Textual design token generated from the active palette, so switching palette is
a one-line swap. Press **`T`** or type **`:theme warm`** to change it live.

### Also in the redesign

* Row colours are read from the live palette (`S("ok")`, `S("danger")`, …)
  instead of the terminal's ANSI colours, so the theme is consistent everywhere.
* Station tabs are shorter and numbered glyphs (`1 ⌂`, `2 ▸`) so the bar fits
  narrow terminals.
* Panel headers are title-left / count-right (`SERVICES & PORTS … 3 ports`).
* The sidebar tree lost its own border — panels are framed once, not twice.

---

---

## 1. TL;DR

The information architecture is genuinely good: four "stations", a live guidance drawer,
a fast-capture command bar and a sidebar attack-surface tree are exactly the right primitives
for a timed, keyboard-driven field worksheet. What let it down was the *plumbing*, not the
design. While clicking through the app I found **three defects that made features
unreachable or crashed the app**, plus a set of consistency problems that make the UI feel
less finished than it is:

| # | Severity | Symptom | Status |
|---|---|---|---|
| C1 | 🔴 Critical | Moving the cursor onto any **service** raises `NoMatches` and kills the app | ✅ Fixed |
| C2 | 🔴 Critical | The **active station tab renders as a blank gap** — you cannot see where you are | ✅ Fixed |
| C3 | 🔴 Critical | Tab 4's **rabbit-hole / failure log has zero height** and sits off-screen | ✅ Fixed |
| H1 | 🟠 High | `z` (zoom) is a **no-op** — it notifies "Maximized" but nothing changes | ✅ Fixed |
| H2 | 🟠 High | Documented **`j`/`k` navigation does not exist**; `k` instead opens the add-checklist dialog | ✅ Fixed |
| H3 | 🟠 High | Footer renders **15 keys + a clipped `^p palette`**, truncated mid-glyph at every width | ✅ Fixed |
| H4 | 🟠 High | **Three competing palettes** — stations 2–4 look like a different application | ✅ Fixed |
| H5 | 🟠 High | `d` **deletes instantly, no confirmation**, no undo | ✅ Fixed (confirm) |
| H6 | 🟠 High | Search modal: **Enter does nothing**, only `y` works | ✅ Fixed |
| H7 | 🟠 High | Below ~110 columns the two-column workbench becomes **unreadable** | ✅ Fixed (compact mode) |
| M1 | 🟡 Medium | Service rows show status glyphs (`✓ ~ ✗`) that **cannot be changed** | 🗒 Idea |
| M2 | 🟡 Medium | Credential matrix columns **misalign**; huge dead space with few creds | ✅ Fixed |
| M3 | 🟡 Medium | Command bar placeholder is 100+ chars and gets clipped; **no history** | 🗒 Idea |
| M4 | 🟡 Medium | Header wastes a full row; workspace name never displayed | ✅ Fixed |
| M5 | 🟡 Medium | Guidance drawer wraps long commands **mid-word** and eats the tip | ✅ Fixed |
| M6 | 🟡 Medium | Row colours come from the **terminal's ANSI palette**, not the CYB0X-S palette | ✅ Fixed |
| L1 | 🟢 Low | No session timer, no undo, no panel filtering, no theme variants | 🗒 Backlog |

All ✅ items are implemented on this branch with regression tests in `tests/test_tui_ui.py`
(11 new tests; full suite: **61 passed**).

---

## 2. How this was reviewed

The TUI is a terminal app, so I built two small harnesses instead of eyeballing it:

* **`dev/screentext.py`** — boots the app headless with seeded demo data, drives it with
  keystrokes and dumps the compositor output as text, one file per screen. This is what
  surfaced the blank active tab, the zero-height failure log and the clipped footer.
  ```bash
  python dev/screentext.py .arena/screens 160 44   # [dir] [cols] [rows]
  ```
* **`dev/screenshot.py`** — same idea, but rasterises each screen to PNG (needs `pillow`)
  so a human can review the visual result without a terminal.
  ```bash
  python dev/screenshot.py .arena/shots
  ```
* **`run_test()` probes** — asserted concrete widget geometry (`region`, `size`, `styles.display`)
  instead of trusting the rendered output.

---

## 3. What works well (keep it)

* **Four stations** map cleanly onto how an operator actually works: recon worksheet →
  reference → credentials → flags/loot. Station numbers as `1`–`4` are memorable.
* **Sidebar attack-surface tree** with per-service drill-down is the right mental model
  (target → ports) and the scope/tag glyphs carry a lot of signal.
* **Live guidance drawer** — highlighting a step and getting a ready-to-paste command with
  the target IP substituted is the killer feature. Worth protecting with tests (now done).
* **Fast-capture command bar** (`:s 445/tcp smb`, `:c admin:pw`, `:stuck …`) is low friction
  and correctly keeps printable keys away from single-letter hotkeys — verified by test.
* **Passive-by-construction copy**: every string in the drawer/reference comes from static
  bundled playbooks. The UX reinforces the project's core promise.

---

## 4. Critical findings in detail

### C1 — Highlighting a service crashed the worksheet 🔴

`GuidanceDrawer` is a `Static` that renders itself, but both highlight handlers tried to
update **child widgets that were never composed**:

```python
guidance_box.query_one("#drawer-cmd", Static).update(...)   # NoMatches
```

`on_tree_node_highlighted` swallowed the exception (`except Exception: pass`), so walking
the sidebar silently did nothing. `on_list_view_highlighted` did **not** swallow it, so
pressing `↓` in the Services panel tore down the app. Net effect: the headline "live
guidance" feature only ever worked for checklist items.

**Fix** — the drawer now owns its state (`show_command()` / `show_step()` / `reset()`), both
handlers call one shared `_guidance_for_service()` helper, and long commands are elided to a
single row instead of wrapping. Covered by `test_highlighting_a_service_updates_drawer` and
`test_tree_navigation_updates_drawer`.

### C2 — The active station tab was invisible 🔴

`theme.py` styled the active tab with `border-bottom: tall` **and** hid the `Underline`:

```css
Tab.-active { height: 1; border-bottom: tall #D97757; }
Underline   { display: none; }
```

A `Tab` is one row tall, so adding a one-row border left the label **zero rows of content** —
the tab bar showed a blank gap where the current station should be, and the underline that
Textual uses to draw "you are here" was hidden as well. Result: on every screen the user sees
the three stations they are *not* on.

**Fix** — dropped the border, restored the underline, and recoloured it
(`Underline > .underline--bar { background: $surface-raised; color: $primary }`).
Covered by `test_active_tab_label_is_visible`.

### C3 — The failure log had no screen space 🔴

`LootAndFlagsWidget` put a `height: auto` card row above a `height: 1fr` failure-log box.
In practice the card row absorbed the **entire** tab (measured: cards `height=33`,
failure box `height=0`, `region.y=41` — i.e. below the fold), so the rabbit-hole log, one of
the most valuable exam features, was unreachable.

**Fix** — explicit `height: 9` for the card row; the log now gets the remaining 22 rows.
Covered by `test_failure_log_panel_has_height`.

---

## 5. High findings in detail

### H1 — `z` was a no-op
`.maximized` only set `width/height: 100%` on a panel that still lived inside its column, and
the "restore" path reset `display: block` on elements that were never hidden. The panel stayed
52 columns wide while the app claimed it was maximized. Now: the sidebar and sibling column
are hidden (`#main-container.zoomed-mode`), the panel spans the workbench, and `z` restores
everything. Measured: 52 → 154 columns.

### H2 — `j`/`k` navigation
The README documented `j`/`k` for list movement and `k` for "add checklist item" — the same
key, two meanings. In reality `j` was unbound and `k` opened a modal, so an operator scanning
a list with vim muscle memory kept getting a dialog thrown at them.
**Decision:** `j`/`k` now move the cursor (matching the documented navigation); adding a
checklist item moved to **`K` (`Shift+k`)**. Printable keys still reach the command bar
because Textual gives a focused `Input` first refusal — asserted by
`test_command_bar_still_captures_shortcuts`. If you'd rather keep `k` for checklists, flip the
two bindings in `BINDINGS`; the help modal and README are the only other places to update.

### H3 — Footer overload
15 bindings plus Textual's built-in command palette overflowed the footer and cut off
mid-glyph (`… k ▏^p palette`). The footer now shows five keys (`q ? / y Space`) and the
generic command palette is disabled — `?` is the real reference.

### H4 — Three palettes in one app
* `theme.py`: warm charcoal / terracotta (`#211E1B`, `#D97757`, …)
* six widgets: hard-coded GitHub-dark (`#161b22`, `#30363d`, `#58a6ff`, `#79c0ff`)
* four modals: Textual's default `$primary`/`$surface` (blue)

Stations 2–4 and every dialog looked like a different application. The palette is now
**registered as a Textual theme** (`CYBOX_WARM_THEME`), so all 168 design tokens
(`$surface`, `$border`, `$text-muted`, footer/scrollbar colours, …) derive from the CYB0X-S
colours; widget CSS references tokens instead of hex. Row-level colours are built in Python
with Rich `Text`, so they bypassed CSS entirely — those now use the same palette tokens
(`OK`, `WARN`, `DANGER`, `INFO`, `NOTE`, `CREAM`) instead of the terminal's ANSI colours.

### H6 — Search modal dead ends
`Enter` on a result did nothing. Now: typing + `Enter` copies the top hit and closes,
`Enter`/click on a result copies it, `j`/`k`/arrows move, `Esc` closes. The header states the
keys, and the copied value is the match title rather than the truncated snippet.

### H7 — Narrow terminals
At 100 columns each panel was ~25 characters wide: service versions, notes and even the
checklist progress bar were clipped (`[50%  ██`). Below 110 columns the app now adds a
`compact` class: the workbench stacks into one column, panels split the height, the drawer is
hidden, and the sidebar gives up width. At 80×24 it is cramped but legible; previously it
was not usable at all.

---

## 6. Enhancement backlog

Ordered by *value per unit of risk* for a tool used under exam time pressure.

### Now (small, high leverage)

| Idea | Why | Notes |
|---|---|---|
| **Command-bar history** (`↑`/`↓`) | Re-running or fixing a typo'd `:s`/`:c` is the most common repeat action | ~20 lines, no state to persist |
| **Command-bar completion** for `:` verbs | Discoverability without reading the README | Could reuse `textual.autocomplete` |
| **Cycle service status with `Space`** (M1) | Rows advertise `→ ✓ ~ ✗` but only checklist items and creds react to `Space` | Needs `cycle_service_status()` on the store |
| **Persistent status line** instead of only transient toasts | Copy confirmations vanish; a one-line status strip answers "did that save?" | Replace/augment `notify()` |
| **Copy the flag hash from tab 1** | Flags are truncated to 15 chars in the target panel and only reachable via `g` | Add `y` on the target panel |

### Next (medium effort, noticeable payoff)

| Idea | Why |
|---|---|
| **Undo stack** for deletes/edits | The only destructive action is now confirmed, but a "bring it back" beats any dialog |
| **Panel-level filtering** (`/` inside a focused list) | With 14-item templates and long note lists, filtering beats scrolling |
| **Session timer / elapsed time** | Timed exams; put it in the header, start on first record |
| **Cross-target overview** (counts per target, flags captured, next unchecked step) | Switching targets is the main navigation cost; a summary row in the tree helps |
| **DataTable for the credential matrix** | Sortable columns and real alignment beat a formatted `ListView` row; enables "sprayed / not sprayed" triage |
| **Remember last station + focused panel** | Operators live in one station per phase; restore on launch |
| **Theme variants** (`--theme warm/high-contrast/ansi16`) | Exam VMs and mixed terminals; the theme registry makes this cheap now |

### Later (bigger swings)

| Idea | Why |
|---|---|
| **Pivot / network graph station** | Dual-homed hosts and routes are hard to read as a list |
| **Evidence helper** (copy `cp` / `scp` command for a screenshot path, open in viewer) | Evidence is currently a bare string |
| **Export preview inside the TUI** | Lets operators sanity-check the report before leaving the tool |
| **Attach TUI to the same store as a live CLI session** (`cyb0x-s note …` refresh) | Two entry points, one screen — needs file watching or a refresh key |
| **Mouse affordances** (click tree node → switch target; click column header → sort) | Textual supports it; currently undocumented and untested |

### Accessibility notes

* Status is encoded by **glyph + colour** (`✓ ~ ✗`). Add a short text form (`[DONE]`, `[SKIP]`,
  `[DEAD]`) so the state survives colour-blindness and monochrome terminals.
* Contrast on the warm palette is good: body text **13.4:1**, muted **5.8:1**, panel headers
  **6.6:1**, selected row **7.7:1**. The one weak pair is `ERROR_RED (#C4553B)` on the panel
  surface at **3.4:1** — rows now use the lighter `DANGER (#E5846B)` at **5.6:1**; keep the
  darker red for borders and buttons only.
* Consider a `--no-emoji` mode: panel titles and rows lean on emoji that render as tofu boxes
  on some exam terminals.

---

## 7. Appendix — current key map

| Key | Action | In footer |
|---|---|---|
| `1` `2` `3` `4` | Jump to station | – |
| `Tab` / `Shift+Tab` | Cycle panels | – |
| `j` / `k` (or `↑` / `↓`) | Move inside list or tree | – |
| `Enter` | Copy ready-to-paste command / next action | – |
| `y` | Copy value (IP, `IP:port`, secret, note text) | ✅ |
| `Space` | Cycle checklist status / reveal credential | ✅ |
| `z` | Zoom focused panel (toggle) | – |
| `g` | Record user/root flags | – |
| `r` | Cheat-sheet modal | – |
| `o` | Toggle in-scope / out-of-scope | – |
| `/` or `Ctrl+F` | Global search | ✅ |
| `t` `s` `f` `c` `n` | Add target / service / finding / credential / note | – |
| `K` (`Shift+k`) | Add checklist item | – |
| `m` | Methodology template picker | – |
| `d` | Delete (with confirmation) | – |
| `?` | Help | ✅ |
| `q` | Quit | ✅ |
