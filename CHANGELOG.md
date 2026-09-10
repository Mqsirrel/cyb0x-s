# Changelog

All notable changes to GLACIS are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.2.0] — 2026-09-09 — "Pulse"


### Added

* **Station 0 — Pulse dashboard (TUI)**: a new fifth station (press `0` or
  `:0`) showing live stat cards (targets, services, findings, creds,
  methodology, momentum), a 14-day activity sparkline, per-target
  **scorecards** with transparent A–F engagement grades, the deterministic
  **next-actions triage queue**, and the newest **timeline** events.
* **Pulse intelligence layer** (`glacis/pulse.py`, fully offline):
  * `glacis stats` — headline workspace statistics, scorecards and triage in
    one screen.
  * `glacis timeline [-n N]` — a unified chronological journal merging all
    ten record types (targets, services, findings, credentials, notes,
    evidence, checklist, leads, command history, failure logs).
  * Workspace pulse: service coverage %, methodology %, momentum (24h / 7d /
    14-day series), busiest & stalest targets.
  * Target scorecards: coverage %, methodology %, flags captured, and a
    transparent A–F grade computed only from recorded progress.
  * Next-action queue: deterministic prioritisation (NOW / NEXT / LATER) of
    *your own* open items — untested services, missing proof invariants,
    open leads, TODO methodology steps. No inference, no scanning, no
    exploit suggestions.
* **Standalone HTML report** (`glacis report.py`):
  * `glacis export --format html [-o report.html] [--palette <name>]` — a
    fully self-contained report (zero external assets, zero JavaScript, no
    network fetches) with sidebar navigation, stat cards, inline SVG
    sparkline, scorecard table, timeline, triage queue and per-host detail
    sections. It honours the active TUI palette, masks credentials by default
    (`--reveal-creds` to unmask), and includes a print stylesheet.
* **Snapshot safety net** (`glacis/backup.py`):
  * `glacis backup [--label label] [--keep N]` — timestamped JSON snapshots
    under `<workspace root>/backups/` with automatic rotation (newest 20 by
    default). Rotation only ever touches machine-generated snapshot files.
  * `glacis backups` — list snapshots newest-first.
  * `glacis restore <file>` (existing command) now pairs with snapshots;
    restores always create a *new* workspace and never overwrite data.
* **Guided first run**: a quick-start welcome card (three steps) opens
  automatically on first launch of an empty workspace; `:welcome` reopens it.
* **Self-explanatory empty states**: every empty panel, the target tree and
  the Pulse dashboard now say which key fills them; the cockpit console tip
  points at the first action for brand-new workspaces.
* **Exam Mode for AI-proctored exams** (press `E` or `:exam on` in the TUI):
  a persistent `EXAM MODE · OFFLINE NOTES` badge in the header (persisted
  across sessions) plus an `[E]` console-bar key — built for INE's
  AI-proctored eJPT v2 where a reviewer may watch your screen. The posture
  rules are documented in `docs/EXAM_COMPLIANCE.md` and
  `docs/INE_EJPT_GUIDE.md`.
* **`glacis exam-check`** — a self-audit subcommand that scans GLACIS's own
  sources for network imports and prints a PASS/FAIL exam-safety report.
* **Socket-free by construction**: the only socket use (lhost auto-detection
  fallback) was replaced with a local interface-table lookup — GLACIS now
  contains zero networking code paths.
* **Performance**: workspace Pulse computations are fingerprint-cached (only
  rebuild when recorded data changes — ~0.2 ms warm on a 600-row worksheet),
  the timeline is cached the same way, all cockpit rosters (services, creds,
  checklist, and the combined notes/evidence/findings panel) diff-append
  instead of rebuilding lists (scroll/selection preserved, O(changes) cost),
  Station 0 skips repaints entirely unless data, palette or size changed,
  station switches fade at one opacity write per frame (~60 fps, 8-step
  out-cubic ramp, generation-guarded so fast flipping never stacks fades),
  and per-list composite indexes keep queries fast on large worksheets (WAL
  auto-checkpoint tuned to avoid write stalls).
* 30 new tests (212 total, up from 182) covering the pulse layer, HTML
  report (self-containment, masking, XSS escaping, theming), snapshot
  lifecycle, new CLI commands, and the Pulse TUI station.

### Changed

* New stations are numbered `0`–`4` (Pulse is now station 0; Cockpit is 1).
  Help modal and console-bar hints updated accordingly.
* `glacis export` gained the `html` format and a `--palette` option.
* Version bumped to 0.2.0.

### Design guarantees (unchanged)

* Zero network access, zero telemetry, zero autonomous behaviour.
* Pulse and reports are read-only views over data you recorded; the
  derivation-free default posture (`GLACIS_DERIVE_GUIDANCE=0`) is intact.
* Local SQLite only; snapshots live inside your workspace folder.

## [0.1.0] — initial field worksheet

* Local, human-controlled terminal field worksheet (TUI + CLI).
* Targets, services, findings, credentials, evidence, notes, methodology
  checklists, failure logs, leads, command history, objective proofs.
* Offline scan import (Nmap XML/text/gnmap/NetExec) with human-in-the-loop
  candidate staging.
* Fast FTS5 search, Markdown/JSON/TXT export, multi-workspace support,
  pivot route documentation, proof-invariant audits, seven palettes.
