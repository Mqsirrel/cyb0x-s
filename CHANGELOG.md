# Changelog

All notable changes to GLACIS are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added — station architecture

- **Station 0 · Pulse (`0`)**: a deterministic situation-awareness board.
  One row per host shows its kill-chain phase (`UNTOUCHED → RECON →
  FOOTHOLD → USER → ROOT → COMPLETE`), transparent progress arithmetic,
  service/credential/evidence counts and dead-end heat. The signal feed is
  explainable: state rules `S1`–`S8` always run, focus-shift rules
  `D1`–`D4` (credential reuse, lateral reuse, rabbit-hole switch,
  undocumented pivots) are opt-in via `G` and ship **off** by default.
  Enter on a host focuses it in the Cockpit; Enter on a signal jumps to the
  station that owns the gap.
- **Station 5 · Network (`5`)**: a passive map of operator-documented
  subnets and dual-homed pivots with copy-ready actions (ProxyChains
  config, Chisel server/client, SSH ProxyJump, SOCKS dynamic forwarding,
  proxied TCP scan hints). Nothing is probed; route math derives solely
  from recorded IPs and `:pivot` notes.
- New triage engine `glacis/triage.py`: pure, deterministic functions over
  the notebook store with stable rule ids, fixed sort order and no wall
  clock or network inputs.
- New shared service metadata `glacis/services_meta.py` (auth-service
  names/ports) as a single source of truth for triage and the spray matrix.
- New packages `glacis/tui/stations/` and `glacis/tui/widgets/`, replacing
  the former widget monolith with focused modules (`lists`, `chrome`,
  `targets`, `playbooks`, `loot`).

### Added — safety, export and CLI

- **Snapshot safety net** (`glacis/snapshot.py`): consistent online SQLite
  backups with rotation (newest 5 kept by default). `:snap [note]` in the
  TUI, `glacis snapshot create|list|restore` in the shell. Scan imports
  trigger an automatic pre-import snapshot; restores take an automatic
  safety snapshot first. In-memory databases are explicitly guarded.
- **Self-contained HTML handover** (`glacis/exporter_html.py`):
  `glacis export -f html` / `:export html` produces a printable report with
  inlined CSS and **zero** external URLs, scripts or fonts; user content is
  HTML-escaped and credentials stay masked unless `--reveal-creds`.
- **`glacis exam-check`** (`glacis/offline_audit.py`): a static AST audit of
  the shipped package that exits non-zero on any network/telemetry import
  or call (socket, requests, httpx, urllib, ftplib, websockets, analytics
  SDKs, …). CI and the operator can prove offline posture without running
  anything.
- `glacis triage [--direction] [--all]`: Pulse report from the shell.
- `glacis pivot <ip> "<route>" [--unmark]`: shell parity for `:pivot`.
- TUI commands `:pivot <route>`, `:snap [note]`, `:export html [file]`,
  plus `:0`/`:5`/`:pulse`/`:network` station jumps and autocomplete
  entries.

### Changed

- All Cockpit list refreshes now **reconcile differentially**
  (`sync_data_list`): rows are matched by stable model keys and updated,
  appended or removed in place, so scroll position and the highlighted row
  survive every refresh — no more full clears that lose selection mid-exam.
- Palette switches force an in-place restyle of every row (colors are baked
  into Rich Text at render time) and refresh all stations.
- The help screen, footer and console bar document stations `0`–`5`, the
  new commands and the `G` state/focus mode; the Loot station tab is now
  `4 ★`.
- Documentation: README station architecture and ASCII layout diagrams,
  expanded keyboard/command matrices, `docs/WORKFLOW.md` Pulse/Network/
  snapshot/HTML flow, and an expanded `docs/EXAM_COMPLIANCE.md`.

### Removed

- The last stdlib `socket` use in `db/store.py`; local VPN/attacker IP
  detection now uses `ip -o addr` with a `/proc/net/fib_trie` fallback
  (subprocess + procfs only), keeping `glacis exam-check` fully clean.

### Fixed

- `SyntaxError` in the HTML exporter caused by escaped quotes inside an
  f-string expression (caught by the scope-safety AST tests); the affected
  markup is now built outside the f-string.
- The remaining 50 ms search-modal debounce used a raw `set_timer`; all
  timers now route through `glacis/tui/anim.py`, which never schedules
  cosmetic timers under pytest (debounces fire synchronously), eliminating
  timer races under `pytest -n auto`.

### Performance

- Measured budgets: cold CLI launch ≈190 ms; per-keystroke `refresh_all`
  ≈12 ms with a 51-host/51-service/51-note stress database; full
  `evaluate_workspace` ≈2.7 ms. Heavy stations (Pulse/Network) only
  recompute while visible.

### Tests

- 236 deterministic tests (up from 189): triage rules and opt-in gating,
  snapshot create/rotate/restore round-trips, offline-audit including a
  self-scan of the shipped tree, HTML self-containment/escaping, and
  headless coverage of both new stations plus differential-selection
  guarantees. The whole suite is green under repeated `pytest -n auto`
  runs with zero flakes.

[Unreleased]: https://github.com/Mqsirrel/cyb0x-s/commits/main
