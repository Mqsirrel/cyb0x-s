# Changelog

All notable changes to GLACIS are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.2.0] — 2026-09-09 — "Pulse"

This release was designed and implemented with AI coding assistance
(**GPT-6 Astra (medium)** via Arena.ai Agent Mode); every change is
deterministic, offline, covered by tests, and reviewed against GLACIS's
passive, human-controlled design principles.

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
