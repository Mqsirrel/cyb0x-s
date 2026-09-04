# UI Review v2 — Screenshot Audit

Source: three live screenshots (Cockpit, Credentials, Loot & Flags) in a light
palette. These findings come from what actually renders on screen — the
companion mock `dev/redesign_preview_v3.py` demonstrates the fixes.

## Findings

| # | Where | Evidence | Problem | Fix |
|---|-------|----------|---------|-----|
| F1 | everywhere | `▯` boxes before creds, flags, vuln tags, card titles | The terminal font has no emoji glyphs; 🔑🏁👑⚠️📷🕳️ render as tofu | Purge emoji from row markup. Text tags (`[VULN]`, `[U]`, `[R]`) + the glyph set that provably renders in your shots (`✓ ✗ → ○ ◐ ● ◈ ▸ █ ░`) carry all meaning. Optional later: `CYB0X_GLYPHS=nerd` for Nerd Font users |
| F2 | status strip | `eJPT{user_f…` | Flags elided at 12 chars are unreadable — and flags are the highest-value strings in the app | Strip shows a workspace flag count (`flags 2/4`) only; full flags live in the Intel station, never elided |
| F3 | cockpit creds | `[We` | Scope chip capped at 8 chars is information-free | Widen to ≥9 or drop the chip in the mini-list; full scope lives in the Vault |
| F4 | notes panel | `…contains archive.zip and admi` (hard clip) | Long notes unreadable; no wrap, no detail view | Wrap notes to 2 lines in a VerticalScroll; Enter opens a full-text detail modal |
| F5 | services panel / vault | 3 rows in a ~15-row panel; matrix fills ~15% of the station | Fixed `fr` weights waste the tallest region of the cockpit | Services panel `height: auto; max-height: 9`; freed rows go to checklist/notes. Vault gains a SPRAY QUEUE pane below the matrix: untested cred×service pairs with the compiled command (pure display of `compile_spray_command` output — passive, copy-only) |
| F6 | loot cards | flags card hint wraps ugly; foothold/privesc cards 90% empty | Fixed `height: 9` cards don't fit their content | Cards `height: auto`; Intel becomes three columns — flags / Q-proofs / rabbit holes |
| F7 | target rail | `(targe` | Hostname cut mid-word when the rail is narrow | Hide hostname below ~36 cols of rail width instead of truncating |
| F8 | vault (light palette) | `PWN3D` reads danger-red | In caramel/sugary the accent hue is close to `danger`; the best state looks like an error | Give PWN3D the `ok` colour (or a dedicated gold) and verify semantics in all 7 palettes, including the three light ones |

## What the screenshots confirm is working

- Subnet grouping with `⇄ [PIVOT]` badges in the rail — immediately legible
- Methodology progress bar inside the panel header — right density
- Restrained footer (`q ? / y space`) — exactly enough
- Empty states that teach the next keystroke (`Type :foothold …`) — keep this pattern everywhere
- Cross-station counters in the strip (`3 ports 2 creds 2 vulns 2 notes`) — glanceable, correct

## Compliance note

Nothing here changes the posture in `docs/EXAM_COMPLIANCE.md`: the spray queue
only displays commands the operator already generated cell-by-cell; copying is
manual; zero network. F5's pane is a view, not an actor.
