"""GLACIS Pulse — the offline engagement-intelligence layer.

Pulse turns the raw records you typed into *situation awareness*:

* :func:`compute_workspace_pulse`  — headline stats, coverage and momentum.
* :func:`compute_target_scorecards` — per-target progress grades (A–F).
* :func:`build_timeline`           — one unified chronological journal of
  everything recorded, across all record types.
* :func:`compute_next_actions`     — a deterministic triage queue assembled
  purely from your own open items (untested services, open leads, TODO
  checklist steps, missing proof invariants).

Design guardrails (unchanged):

* **100% local and offline** — pure functions over the local SQLite store.
* **Nothing is inferred about security posture** — Pulse only counts, sorts,
  and timestamps what *you* already recorded. It never probes a target,
  never rates vulnerability exploitability, and never suggests exploits.
* **Deterministic** — same records in, same answer out. No randomness, no
  network, no background jobs.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from glacis.db.store import NotebookStore
from glacis.models import ChecklistStatus, ServiceStatus

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _to_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Normalise a datetime to UTC (naive datetimes are assumed UTC)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _age_days(dt: Optional[datetime], now: Optional[datetime] = None) -> Optional[float]:
    dt = _to_utc(dt)
    if dt is None:
        return None
    now = _to_utc(now or _utcnow())
    return (now - dt).total_seconds() / 86400.0


def _pct(part: int, total: int) -> int:
    return 0 if total <= 0 else int(round(100.0 * part / total))


# ---------------------------------------------------------------------------
# Change detection (cheap fingerprint cache)
# ---------------------------------------------------------------------------
#
# The TUI recomputes Pulse views on every activation. Rather than re-hydrate
# every model each time, we fingerprint the database with a handful of
# indexed aggregate queries (COUNT / MAX rowid / MAX timestamps per table)
# and cache the computed views per store. Any insert, update or delete
# changes the fingerprint and invalidates the cache naturally — no hooks,
# no manual invalidation, always correct.

_FINGERPRINT_TABLES = (
    "workspaces", "settings", "targets", "services", "findings",
    "credentials", "evidence", "notes", "checklist", "leads",
    "command_history", "failure_log", "exam_proofs", "cred_validation",
    "scan_imports",
)


def workspace_fingerprint(store: NotebookStore) -> tuple:
    """Cheap change-digest of the whole database.

    Runs ~15 indexed aggregate queries (sub-millisecond on exam-sized
    workspaces) and returns a tuple that changes whenever any recorded
    datum changes. Used to cache Pulse computations between keystrokes.
    """
    parts: List[Any] = []
    cur = store.conn.cursor()
    for table in _FINGERPRINT_TABLES:
        try:
            cur.execute(
                f"SELECT COUNT(*), COALESCE(MAX(rowid), 0), "
                f"COALESCE(MAX(created_at), ''), COALESCE(MAX(updated_at), '') "
                f"FROM {table}"
            )
            row = cur.fetchone()
            parts.append(tuple(row) if row else (0, 0, "", ""))
        except Exception:
            # Table missing (older DB): fall back to a bare count.
            try:
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                parts.append((cur.fetchone()[0], 0, "", ""))
            except Exception:
                parts.append((0, 0, "", ""))
    return tuple(parts)


def _pulse_cache(store: NotebookStore) -> dict:
    """Per-store cache dict for computed Pulse views."""
    cache = getattr(store, "_pulse_cache", None)
    if cache is None:
        cache = {}
        try:
            store._pulse_cache = cache
        except Exception:
            pass
    return cache


def _cached(store: NotebookStore, key: tuple, compute):
    """Return ``compute()`` result from cache when the DB is unchanged."""
    cache = _pulse_cache(store)
    fingerprint = workspace_fingerprint(store)
    hit = cache.get(key)
    if hit is not None and hit[0] == fingerprint:
        return hit[1]
    result = compute()
    cache[key] = (workspace_fingerprint(store), result)
    return result


# ---------------------------------------------------------------------------
# Workspace pulse
# ---------------------------------------------------------------------------

SEVERITY_ORDER = ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO")


class WorkspacePulse(BaseModel):
    """Headline statistics for a whole workspace."""

    workspace_id: Optional[int] = None
    workspace_name: str = ""
    targets: int = 0
    in_scope_targets: int = 0
    services: int = 0
    services_tested: int = 0          # status CHECKED or DEAD-END
    services_dead_ends: int = 0
    findings: int = 0
    severity_counts: Dict[str, int] = Field(default_factory=dict)
    credentials: int = 0
    evidence: int = 0
    notes: int = 0
    leads_open: int = 0
    leads_total: int = 0
    checklist_total: int = 0
    checklist_checked: int = 0
    checklist_dead_ends: int = 0
    commands_logged: int = 0
    failure_logs: int = 0
    coverage_pct: int = 0             # services_tested / services
    checklist_pct: int = 0            # checklist_checked / checklist_total
    momentum_24h: int = 0             # records created in the last 24 hours
    momentum_7d: int = 0
    activity_14d: List[int] = Field(default_factory=list)  # oldest -> today
    busiest_target: str = ""          # label like "10.10.10.20"
    busiest_target_count: int = 0
    stalest_target: str = ""
    stale_days: float = 0.0
    generated_at: datetime = Field(default_factory=_utcnow)

    @property
    def sparkline_blocks(self) -> str:
        """A compact unicode block sparkline of the 14-day activity series."""
        return render_sparkline(self.activity_14d)


def _activity_series(store: NotebookStore, workspace_id: int, days: int = 14) -> List[int]:
    """Count records created per day over the last ``days`` days (oldest first).

    Counts all user-authored record types so the series reflects real work.
    """
    cutoff = _utcnow() - timedelta(days=days - 1)
    cutoff = cutoff.replace(hour=0, minute=0, second=0, microsecond=0)

    per_day: Dict[int, int] = {i: 0 for i in range(days)}
    queries = [
        "SELECT created_at FROM targets WHERE workspace_id = ?",
        """SELECT s.created_at FROM services s
           JOIN targets t ON s.target_id = t.id WHERE t.workspace_id = ?""",
        """SELECT f.created_at FROM findings f
           LEFT JOIN targets t ON f.target_id = t.id
           WHERE t.workspace_id = ? OR f.target_id IS NULL""",
        """SELECT n.created_at FROM notes n
           LEFT JOIN targets t ON n.target_id = t.id
           WHERE t.workspace_id = ? OR n.target_id IS NULL""",
        """SELECT c.created_at FROM credentials c
           LEFT JOIN targets t ON c.target_id = t.id
           WHERE t.workspace_id = ? OR c.target_id IS NULL""",
        """SELECT e.created_at FROM evidence e
           LEFT JOIN targets t ON e.target_id = t.id
           WHERE t.workspace_id = ? OR e.target_id IS NULL""",
        """SELECT k.created_at FROM checklist k
           LEFT JOIN targets t ON k.target_id = t.id
           WHERE t.workspace_id = ? OR k.target_id IS NULL""",
        "SELECT created_at FROM command_history",
        "SELECT created_at FROM failure_log",
    ]
    for sql in queries:
        try:
            cur = store.conn.cursor()
            cur.execute(sql, (workspace_id,))
        except Exception:
            continue
        for (raw,) in cur.fetchall():
            dt = _parse_ts(raw)
            if dt is None:
                continue
            dt = _to_utc(dt)
            day_idx = (dt.date() - cutoff.date()).days
            if 0 <= day_idx < days:
                per_day[day_idx] += 1
    return [per_day[i] for i in range(days)]


def _parse_ts(raw: Any) -> Optional[datetime]:
    """Parse SQLite TIMESTAMP / ISO strings / datetime objects safely."""
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw
    text = str(raw).strip()
    if not text:
        return None
    normalised = text.replace("Z", "+00:00")
    for candidate in (normalised, normalised.replace(" ", "T", 1)):
        try:
            return datetime.fromisoformat(candidate)
        except ValueError:
            continue
    return None


def compute_workspace_pulse(
    store: NotebookStore,
    workspace_id: Optional[int] = None,
) -> WorkspacePulse:
    """Compute headline workspace statistics from recorded data only."""
    ws = store.get_workspace(workspace_id) if workspace_id else store.get_active_workspace()
    if not ws:
        return WorkspacePulse(workspace_name="")
    return _cached(store, ("pulse", ws.id), lambda: _compute_pulse(store, ws))


def _compute_pulse(store: NotebookStore, ws: Any) -> WorkspacePulse:
    targets = store.list_targets(workspace_id=ws.id)
    target_ids = [t.id for t in targets]

    services: List[Any] = []
    for tid in target_ids:
        services.extend(store.list_services(target_id=tid))

    findings = store.list_findings() if not target_ids else []
    for tid in target_ids:
        findings.extend(store.list_findings(target_id=tid))

    credentials: List[Any] = []
    for tid in target_ids:
        credentials.extend(store.list_credentials(target_id=tid))

    evidence: List[Any] = []
    notes: List[Any] = []
    leads: List[Any] = []
    checklist: List[Any] = []
    failures: List[Any] = []
    for tid in target_ids:
        evidence.extend(store.list_evidence(target_id=tid))
        notes.extend(store.list_notes(target_id=tid))
        leads.extend(store.list_leads(target_id=tid))
        checklist.extend(store.list_checklist_items(target_id=tid))
        failures.extend(store.list_failure_logs(target_id=tid))
    if not target_ids:
        notes.extend(store.list_notes())
        evidence.extend(store.list_evidence())

    commands = store.list_commands(limit=100000)

    severity_counts: Dict[str, int] = {sev: 0 for sev in SEVERITY_ORDER}
    severity_counts["UNRATED"] = 0
    for f in findings:
        sev = (f.severity or "").strip().upper() if f.severity else ""
        if sev in severity_counts:
            severity_counts[sev] += 1
        else:
            severity_counts["UNRATED"] += 1

    services_tested = sum(
        1 for s in services if s.status in (ServiceStatus.CHECKED, ServiceStatus.DEAD_END)
    )
    services_dead_ends = sum(1 for s in services if s.status == ServiceStatus.DEAD_END)
    checklist_checked = sum(1 for k in checklist if k.status == ChecklistStatus.CHECKED)
    checklist_dead_ends = sum(1 for k in checklist if k.status == ChecklistStatus.DEAD_END)
    leads_open = sum(1 for ld in leads if (ld.status or "open") == "open")

    # Momentum: records created in the trailing windows.
    activity = _activity_series(store, ws.id)
    momentum_24h = activity[-1]
    momentum_7d = sum(activity[-7:])

    # Busiest target by recorded artefacts.
    busiest_label, busiest_count = "", 0
    for t in targets:
        counts = store.get_target_counts(t.id)
        total = counts.get("ports", 0) + counts.get("creds", 0) + counts.get("vulns", 0) + counts.get("notes", 0)
        if total > busiest_count:
            busiest_label, busiest_count = t.ip, total

    # Staleness: days since the most recent update on any target.
    stale_label, stale_days = "", 0.0
    for t in targets:
        age = _age_days(t.updated_at) or 0.0
        if age > stale_days:
            stale_label, stale_days = t.ip, age

    return WorkspacePulse(
        workspace_id=ws.id,
        workspace_name=ws.name,
        targets=len(targets),
        in_scope_targets=sum(1 for t in targets if t.is_in_scope),
        services=len(services),
        services_tested=services_tested,
        services_dead_ends=services_dead_ends,
        findings=len(findings),
        severity_counts=severity_counts,
        credentials=len(credentials),
        evidence=len(evidence),
        notes=len(notes),
        leads_open=leads_open,
        leads_total=len(leads),
        checklist_total=len(checklist),
        checklist_checked=checklist_checked,
        checklist_dead_ends=checklist_dead_ends,
        commands_logged=len(commands),
        failure_logs=len(failures),
        coverage_pct=_pct(services_tested, len(services)),
        checklist_pct=_pct(checklist_checked, len(checklist)),
        momentum_24h=momentum_24h,
        momentum_7d=momentum_7d,
        activity_14d=activity,
        busiest_target=busiest_label,
        busiest_target_count=busiest_count,
        stalest_target=stale_label,
        stale_days=round(stale_days, 1),
    )


# ---------------------------------------------------------------------------
# Target scorecards
# ---------------------------------------------------------------------------

class TargetScorecard(BaseModel):
    """Per-target progress snapshot with a simple engagement grade."""

    target_id: Optional[int] = None
    ip: str = ""
    hostname: str = ""
    os: str = "Unknown"
    is_in_scope: bool = True
    user_flag: str = ""
    root_flag: str = ""
    foothold: str = ""
    services: int = 0
    services_tested: int = 0
    findings: int = 0
    credentials: int = 0
    evidence: int = 0
    notes: int = 0
    checklist_total: int = 0
    checklist_checked: int = 0
    coverage_pct: int = 0
    checklist_pct: int = 0
    grade: str = "—"

    @property
    def label(self) -> str:
        return f"{self.ip}{f' ({self.hostname})' if self.hostname else ''}"

    @property
    def flags_captured(self) -> int:
        return int(bool(self.user_flag)) + int(bool(self.root_flag))


def _engagement_grade(coverage: int, checklist: int, flags: int, findings: int) -> str:
    """Letter grade from recorded progress only (transparent arithmetic)."""
    score = 0.55 * coverage + 0.45 * checklist
    score = min(100.0, score + 7.5 * flags + min(findings, 4) * 2.5)
    if score >= 85:
        return "A"
    if score >= 70:
        return "B"
    if score >= 55:
        return "C"
    if score >= 35:
        return "D"
    if score > 0:
        return "E"
    return "F"


def compute_target_scorecards(
    store: NotebookStore,
    workspace_id: Optional[int] = None,
) -> List[TargetScorecard]:
    """Per-target scorecards, busiest first."""
    ws = store.get_workspace(workspace_id) if workspace_id else store.get_active_workspace()
    if not ws:
        return []
    return _cached(store, ("scorecards", ws.id), lambda: _compute_scorecards(store, ws))


def _compute_scorecards(store: NotebookStore, ws: Any) -> List[TargetScorecard]:
    cards: List[TargetScorecard] = []
    for t in store.list_targets(workspace_id=ws.id):
        services = store.list_services(target_id=t.id)
        findings = store.list_findings(target_id=t.id)
        creds = store.list_credentials(target_id=t.id)
        evidence = store.list_evidence(target_id=t.id)
        notes = store.list_notes(target_id=t.id)
        checklist = store.list_checklist_items(target_id=t.id)

        tested = sum(
            1 for s in services if s.status in (ServiceStatus.CHECKED, ServiceStatus.DEAD_END)
        )
        checked = sum(1 for k in checklist if k.status == ChecklistStatus.CHECKED)
        coverage = _pct(tested, len(services))
        ck_pct = _pct(checked, len(checklist))
        flags = int(bool(t.user_flag)) + int(bool(t.root_flag))

        cards.append(
            TargetScorecard(
                target_id=t.id,
                ip=t.ip,
                hostname=t.hostname,
                os=t.os,
                is_in_scope=t.is_in_scope,
                user_flag=t.user_flag,
                root_flag=t.root_flag,
                foothold=t.foothold_cmd or t.initial_access_vuln,
                services=len(services),
                services_tested=tested,
                findings=len(findings),
                credentials=len(creds),
                evidence=len(evidence),
                notes=len(notes),
                checklist_total=len(checklist),
                checklist_checked=checked,
                coverage_pct=coverage,
                checklist_pct=ck_pct,
                grade=_engagement_grade(coverage, ck_pct, flags, len(findings)),
            )
        )

    cards.sort(
        key=lambda c: (c.flags_captured, c.coverage_pct + c.checklist_pct, c.services, c.findings),
        reverse=True,
    )
    return cards


# ---------------------------------------------------------------------------
# Unified timeline
# ---------------------------------------------------------------------------

class EventType(str, Enum):
    TARGET = "target"
    SERVICE = "service"
    FINDING = "finding"
    CREDENTIAL = "credential"
    NOTE = "note"
    EVIDENCE = "evidence"
    CHECKLIST = "checklist"
    LEAD = "lead"
    COMMAND = "command"
    FAILURE = "failure"


class TimelineEvent(BaseModel):
    """One entry in the unified chronological journal."""

    when: datetime
    kind: EventType
    icon: str
    label: str
    detail: str = ""
    target_ip: str = ""
    target_id: Optional[int] = None
    record_id: Optional[int] = None

    @property
    def when_iso(self) -> str:
        return _to_utc(self.when).strftime("%Y-%m-%d %H:%M") if self.when else ""


# icon/kind pairs for every record type — keeps build_timeline declarative.
_EVENT_STYLE: Dict[str, Tuple[EventType, str]] = {
    "target": (EventType.TARGET, "◈"),
    "service": (EventType.SERVICE, "◆"),
    "finding": (EventType.FINDING, "▲"),
    "credential": (EventType.CREDENTIAL, "⚷"),
    "note": (EventType.NOTE, "✎"),
    "evidence": (EventType.EVIDENCE, "❐"),
    "checklist": (EventType.CHECKLIST, "☑"),
    "lead": (EventType.LEAD, "→"),
    "command": (EventType.COMMAND, "$"),
    "failure": (EventType.FAILURE, "✗"),
}


def _tlabel(t: Optional[Any]) -> str:
    if t is None:
        return ""
    return t.ip if not t.hostname else f"{t.ip} ({t.hostname})"


def build_timeline(
    store: NotebookStore,
    workspace_id: Optional[int] = None,
    limit: int = 200,
) -> List[TimelineEvent]:
    """Merge every record type into one chronological journal (newest first).

    Includes records regardless of which target they hang off so the journal
    reads like a session log of the whole engagement. Cached against the
    workspace fingerprint like every other Pulse view.
    """
    ws = store.get_workspace(workspace_id) if workspace_id else store.get_active_workspace()
    if not ws:
        return []
    return _cached(store, ("timeline", ws.id, limit), lambda: _build_timeline(store, ws, limit))


def _build_timeline(store: NotebookStore, ws: Any, limit: int) -> List[TimelineEvent]:
    targets = {t.id: t for t in store.list_targets(workspace_id=ws.id)}
    events: List[TimelineEvent] = []

    def add(kind_key: str, when: Optional[datetime], label: str, detail: str = "",
            target_id: Optional[int] = None, record_id: Optional[int] = None) -> None:
        ts = _to_utc(when)
        if ts is None:
            return
        kind, icon = _EVENT_STYLE[kind_key]
        events.append(
            TimelineEvent(
                when=ts,
                kind=kind,
                icon=icon,
                label=label,
                detail=detail,
                target_ip=targets[target_id].ip if target_id in targets else "",
                target_id=target_id if target_id in targets else None,
                record_id=record_id,
            )
        )

    for t in targets.values():
        add("target", t.created_at, f"Target added {t.ip}",
            detail=t.hostname or t.os, target_id=t.id, record_id=t.id)

    for tid, t in targets.items():
        for s in store.list_services(target_id=tid):
            label = f"Service {s.port}/{s.protocol} {s.service}"
            if s.version:
                label += f" — {s.version}"
            add("service", s.created_at, label, target_id=tid, record_id=s.id)

        for f in store.list_findings(target_id=tid):
            sev = f"[{f.severity}] " if f.severity else ""
            add("finding", f.created_at, f"Finding: {sev}{f.title}",
                detail=(f.notes or f.description)[:120], target_id=tid, record_id=f.id)

        for c in store.list_credentials(target_id=tid):
            add("credential", c.created_at, f"Credential {c.username}",
                detail=c.source or c.service_scope, target_id=tid, record_id=c.id)

        for e in store.list_evidence(target_id=tid):
            add("evidence", e.created_at, f"Evidence [{e.evidence_type}] {e.path_or_ref}",
                detail=e.description[:120], target_id=tid, record_id=e.id)

        for n in store.list_notes(target_id=tid):
            add("note", n.created_at, "Note", detail=n.content[:140], target_id=tid, record_id=n.id)

        for k in store.list_checklist_items(target_id=tid):
            add("checklist", k.created_at, f"Checklist [{k.status.value}] {k.title}",
                target_id=tid, record_id=k.id)

        for ld in store.list_leads(target_id=tid):
            add("lead", ld.created_at, f"Lead [{ld.status}] {ld.title}",
                target_id=tid, record_id=ld.id)

        for fl in store.list_failure_logs(target_id=tid):
            detail = fl.breakthrough_clue or fl.where_stuck
            add("failure", fl.created_at, "Failure log", detail=detail[:120],
                target_id=tid, record_id=fl.id)

    for cmd in store.list_commands(limit=500):
        add("command", cmd.created_at, cmd.command[:120],
            target_id=cmd.target_id if cmd.target_id in targets else None,
            record_id=cmd.id)

    events.sort(key=lambda e: e.when, reverse=True)
    return events[:limit]


# ---------------------------------------------------------------------------
# Next-action triage queue
# ---------------------------------------------------------------------------

class ActionPriority(str, Enum):
    NOW = "now"
    NEXT = "next"
    LATER = "later"


class NextAction(BaseModel):
    """One item of the deterministic triage queue."""

    priority: ActionPriority
    category: str          # "service" | "lead" | "checklist" | "proof"
    title: str
    detail: str = ""
    target_ip: str = ""
    reason: str = ""


def compute_next_actions(
    store: NotebookStore,
    workspace_id: Optional[int] = None,
    limit: int = 25,
) -> List[NextAction]:
    """Build a triage queue from the user's *own* open items only.

    Pure bookkeeping over recorded data:

    * **now**      — untested services on hosts where a foothold exists, then
      untested services anywhere, then missing user/root proof on hosts with a
      foothold.
    * **next**     — open leads, untested services on remaining hosts.
    * **later**    — untouched checklist steps on the most-worked hosts.

    No vulnerability inference, no exploit suggestion — the queue is simply
    your TODOs in a stable order.
    """
    ws = store.get_workspace(workspace_id) if workspace_id else store.get_active_workspace()
    if not ws:
        return []
    return _cached(store, ("actions", ws.id, limit), lambda: _compute_actions(store, ws, limit))


def _compute_actions(store: NotebookStore, ws: Any, limit: int = 25) -> List[NextAction]:
    actions: List[NextAction] = []

    for t in store.list_targets(workspace_id=ws.id):
        has_foothold = bool(t.foothold_cmd or t.initial_access_vuln)

        for s in store.list_services(target_id=t.id):
            if s.status != ServiceStatus.UNTESTED:
                continue
            nxt = NextAction(
                priority=ActionPriority.NOW if has_foothold else ActionPriority.NEXT,
                category="service",
                title=f"Test {s.port}/{s.protocol} {s.service}",
                detail=s.next_action or s.notes,
                target_ip=t.ip,
                reason="foothold exists — enumerate this" if has_foothold else "never tested",
            )
            actions.append(nxt)

        if has_foothold and not t.user_flag:
            actions.append(NextAction(
                priority=ActionPriority.NOW, category="proof",
                title="Capture user proof", target_ip=t.ip,
                reason="foothold recorded but no user proof yet",
            ))
        if t.user_flag and not t.root_flag and bool(t.privesc_vector or t.foothold_cmd):
            actions.append(NextAction(
                priority=ActionPriority.NOW, category="proof",
                title="Capture root proof", target_ip=t.ip,
                reason="user proof captured — privesc vector recorded",
            ))

        for ld in store.list_leads(target_id=t.id):
            if (ld.status or "open") == "open":
                actions.append(NextAction(
                    priority=ActionPriority.NEXT, category="lead",
                    title=ld.title, detail=ld.notes[:120], target_ip=t.ip,
                    reason="open lead you recorded",
                ))

        for k in store.list_checklist_items(target_id=t.id):
            if k.status == ChecklistStatus.TODO:
                actions.append(NextAction(
                    priority=ActionPriority.LATER, category="checklist",
                    title=k.title, target_ip=t.ip,
                    reason=f"methodology step ({k.category}) still TODO",
                ))

    rank = {ActionPriority.NOW: 0, ActionPriority.NEXT: 1, ActionPriority.LATER: 2}
    actions.sort(key=lambda a: (rank[a.priority], a.target_ip, a.category, a.title))
    return actions[:limit]


# ---------------------------------------------------------------------------
# Rendering helpers (shared by TUI, CLI and HTML report)
# ---------------------------------------------------------------------------

def render_sparkline(series: List[int], blocks: str = "▁▂▃▄▅▆▇█") -> str:
    """Render a numeric series as a unicode block sparkline."""
    if not series:
        return ""
    peak = max(series)
    if peak <= 0:
        return blocks[0] * len(series)
    return "".join(blocks[round((len(blocks) - 1) * v / peak)] for v in series)


def progress_bar(pct: int, width: int = 10, fill: str = "█", empty: str = "░") -> str:
    """A fixed-width progress bar string."""
    pct = max(0, min(100, int(pct)))
    filled = int(round(width * pct / 100))
    return fill * filled + empty * (width - filled)
