# Changelog

## [0.2.0] — "Pulse"

### Added

* **Station 0 — Pulse dashboard (TUI)**: press `0` for a live engagement
  dashboard: stat cards (targets, services, findings, creds, methodology,
  momentum), a 14-day sparkline, per-target **scorecards** with transparent
  A–F grades, the deterministic **next-actions triage queue**, and the newest
  **timeline** events. Read-only arithmetic over records you captured.
* **`glacis stats` / `glacis timeline`**: the Pulse layer from the shell.
* **Snapshot safety net**: `glacis backup [--label L] [--keep N]` (timestamped
  JSON snapshots with rotation), `glacis backups`, `glacis restore` keeps
  creating *new* workspaces — never overwrites.
* **Exam Mode for AI-proctored exams** (press `E` or `:exam on`): a persistent
  `EXAM MODE · OFFLINE NOTES` header badge, persisted across sessions — built
  for INE's AI-proctored eJPT v2. `glacis exam-check` audits the installed
  build and proves zero network imports in GLACIS sources.
* **Guided first run**: a quick-start welcome card opens on first launch of an
  empty workspace; `:welcome` reopens it anytime.
* **Standalone HTML report**: `glacis export --format html [-o file]
  [--palette name] [--reveal-creds]` — fully self-contained, zero JavaScript,
  no network fetches.

### Performance

* Workspace Pulse computations are fingerprint-cached (~0.2 ms warm on a
  600-row worksheet) and the timeline is cached the same way.
* Cockpit rosters (services, credentials, checklist, combined notes panel)
  diff-append or update in place instead of rebuilding: scroll and selection
  survive every refresh, and status toggles (TODO→CHECKED) reformat only the
  changed row.
* Station switches fade with one opacity write per frame (~60 fps, 8-step
  out-cubic ramp), generation-guarded so fast flipping never stacks fades.
  Reduced-motion guard: `GLACIS_ANIMATE=0`, `:anim`, and automatic off for
  SSH sessions.
* Composite indexes on every roster query path + tuned WAL auto-checkpoint.

### Design guarantees (unchanged)

* Zero network access, zero telemetry, zero autonomous behaviour.
* Pulse is read-only over data you recorded; the derivation-free default
  posture is intact.
