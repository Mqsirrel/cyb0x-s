"""Deterministic, explainable situation-awareness and triage engine.

The triage engine never touches a network and never executes anything. It is
a pure function over the operator's own recorded notebook state:

    NotebookStore  ->  TriageReport (host phases + ordered advisories)

Every advisory is produced by an explicit, named, deterministic rule — there
are no scores from a model, no timers and no background scans. The same
notebook always yields the exact same report.

Two kinds of advisory exist, mirroring ``docs/EXAM_COMPLIANCE.md``:

* ``state``       — transparent arithmetic over recorded data ("host X has no
                    services recorded", "3 enumeration steps remain TODO",
                    "no evidence attached to the captured user flag"). These
                    are always shown, just like the checklist progress bar.
* ``direction``   — a suggested *focus shift* ("spend time on the untouched
                    host instead of this dead end", "this credential has not
                    been tried on that service", "a pivot may be required").
                    These are **off by default** and only appear when the
                    operator explicitly enables derived suggestions (``G`` in
                    the TUI / ``GLACIS_DERIVE_GUIDANCE=1``). The tool never
                    acts on them itself; it only offers navigation to the
                    relevant station. The human performs every action in their
                    own terminal.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from glacis.db.store import NotebookStore
from glacis.models import ChecklistStatus, ServiceStatus
from glacis.services_meta import auth_service_pairs
from glacis.settings import derive_guidance_enabled


class HostPhase(str, Enum):
    """Coarse, deterministic position of a host in the kill chain."""

    UNTOUCHED = "UNTOUCHED"      # nothing recorded
    RECON = "RECON"              # surface mapped, no foothold
    FOOTHOLD = "FOOTHOLD"        # initial access vector / shell recorded
    USER = "USER"                # user-level proof captured
    ROOT = "ROOT"                # privileged access / privesc recorded
    COMPLETE = "COMPLETE"        # root proof captured with evidence attached


class AdvisorySeverity(str, Enum):
    INFO = "INFO"
    HINT = "HINT"
    WARN = "WARN"
    CRIT = "CRIT"


class AdvisoryKind(str, Enum):
    STATE = "state"              # arithmetic fact about recorded data
    DIRECTION = "direction"      # suggested focus shift (opt-in)


# Station ids used for one-keystroke navigation from an advisory.
STATION_PULSE = "tab-pulse"
STATION_COCKPIT = "tab-worksheet"
STATION_PLAYBOOKS = "tab-playbooks"
STATION_CREDS = "tab-creds"
STATION_NETWORK = "tab-network"
STATION_LOOT = "tab-loot"

_SEVERITY_RANK = {
    AdvisorySeverity.INFO: 0,
    AdvisorySeverity.HINT: 1,
    AdvisorySeverity.WARN: 2,
    AdvisorySeverity.CRIT: 3,
}


class HostTriage(BaseModel):
    """Triage snapshot for a single target host."""

    target_id: int
    ip: str
    hostname: str = ""
    os: str = "Unknown"
    is_in_scope: bool = True
    is_pivot: bool = False
    subnet: str = ""
    phase: HostPhase = HostPhase.UNTOUCHED
    completion_pct: float = 0.0
    services_total: int = 0
    services_untested: int = 0
    services_dead_end: int = 0
    services_high_value: int = 0
    creds_count: int = 0
    findings_count: int = 0
    checklist_done: int = 0
    checklist_total: int = 0
    evidence_count: int = 0
    failure_count: int = 0
    has_user_flag: bool = False
    has_root_flag: bool = False
    proofs_count: int = 0
    phase_reason: str = ""

    @property
    def progress_bar(self) -> str:
        """Render a stable 8-cell progress bar for terminals."""
        width = 8
        filled = int(round(width * self.completion_pct / 100.0))
        return "█" * filled + "░" * (width - filled)


class TriageAdvisory(BaseModel):
    """A single, explainable triage signal."""

    rule_id: str
    severity: AdvisorySeverity
    kind: AdvisoryKind
    title: str
    detail: str = ""
    station: str = STATION_COCKPIT
    target_id: Optional[int] = None
    host_ip: str = ""
    action_text: str = ""

    def key(self) -> tuple[Any, ...]:
        return (self.rule_id, self.target_id or -1, self.title)


class TriageReport(BaseModel):
    """Complete situation report for a workspace."""

    workspace_name: str = "default"
    hosts: List[HostTriage] = Field(default_factory=list)
    advisories: List[TriageAdvisory] = Field(default_factory=list)
    totals: Dict[str, int] = Field(default_factory=dict)
    overall_pct: float = 0.0
    direction_enabled: bool = False

    def advisories_for(self, target_id: Optional[int]) -> List[TriageAdvisory]:
        if target_id is None:
            return list(self.advisories)
        return [a for a in self.advisories if a.target_id == target_id]

    def next_advisory(self) -> Optional[TriageAdvisory]:
        return self.advisories[0] if self.advisories else None


# ---------------------------------------------------------------------------
# Host phase arithmetic
# ---------------------------------------------------------------------------


def _classify_phase(host: HostTriage, target: Any) -> HostPhase:
    """Pure decision table mapping recorded state to a kill-chain phase."""
    has_foothold = bool(
        (target.initial_access_vuln or "").strip()
        or (target.foothold_cmd or "").strip()
        or host.findings_count > 0
    )
    has_user = has_foothold and (host.has_user_flag or host.proofs_count > 0)
    has_root = bool((target.privesc_vector or "").strip() or (target.root_proof or "").strip()
                    or host.has_root_flag)
    if host.has_root_flag and host.evidence_count > 0:
        return HostPhase.COMPLETE
    if has_root:
        return HostPhase.ROOT
    if has_user:
        return HostPhase.USER
    if has_foothold:
        return HostPhase.FOOTHOLD
    if host.services_total > 0 or host.checklist_total > 0:
        return HostPhase.RECON
    return HostPhase.UNTOUCHED


_PHASE_REASONS = {
    HostPhase.UNTOUCHED: "No services recorded yet",
    HostPhase.RECON: "Attack surface mapped; no foothold recorded",
    HostPhase.FOOTHOLD: "Initial access recorded; no user proof yet",
    HostPhase.USER: "User proof captured; privilege escalation pending",
    HostPhase.ROOT: "Privilege escalation recorded; evidence still pending",
    HostPhase.COMPLETE: "Root flag and evidence recorded",
}


def _completion_pct(target: Any, host: HostTriage) -> float:
    """Weighted, transparent completion arithmetic (sums to 100).

    Stages: surface 15, foothold 25, user proof 20, privesc 20, root 10,
    evidence 10. Every weight is visible here and in the UI.
    """
    score = 0.0
    if host.services_total > 0:
        score += 15
    if (target.initial_access_vuln or "").strip() or (target.foothold_cmd or "").strip() or host.findings_count:
        score += 25
    if host.has_user_flag or host.proofs_count > 0:
        score += 20
    if (target.privesc_vector or "").strip() or (target.root_proof or "").strip():
        score += 20
    if host.has_root_flag:
        score += 10
    if host.evidence_count > 0:
        score += 10
    return round(score, 1)


def build_host_triage(store: NotebookStore, target: Any) -> HostTriage:
    """Compute the deterministic :class:`HostTriage` for one target."""
    tid = target.id
    services = store.list_services(target_id=tid)
    checklist = store.list_checklist_items(target_id=tid)
    creds = store.list_credentials(target_id=tid)
    findings = store.list_findings(target_id=tid)
    evidence = store.list_evidence(target_id=tid)
    failures = store.list_failure_logs(target_id=tid)
    proofs = store.list_exam_proofs(target_id=tid)

    high_value = sum(1 for s in services if (s.access_potential or "").upper() in ("HIGH", "CRITICAL"))
    host = HostTriage(
        target_id=tid,
        ip=target.ip,
        hostname=target.hostname or "",
        os=target.os or "Unknown",
        is_in_scope=bool(target.is_in_scope),
        is_pivot=bool(target.is_pivot),
        subnet=target.subnet or "",
        services_total=len(services),
        services_untested=sum(1 for s in services if s.status == ServiceStatus.UNTESTED),
        services_dead_end=sum(1 for s in services if s.status == ServiceStatus.DEAD_END),
        services_high_value=high_value,
        creds_count=len(creds),
        findings_count=len(findings),
        checklist_done=sum(1 for i in checklist if i.status == ChecklistStatus.CHECKED),
        checklist_total=len(checklist),
        evidence_count=len(evidence),
        failure_count=len(failures),
        has_user_flag=bool((target.user_flag or "").strip()),
        has_root_flag=bool((target.root_flag or "").strip()),
        proofs_count=len(proofs),
    )
    host.phase = _classify_phase(host, target)
    host.phase_reason = _PHASE_REASONS[host.phase]
    host.completion_pct = _completion_pct(target, host)
    return host


# ---------------------------------------------------------------------------
# Advisory rules
# ---------------------------------------------------------------------------


def _infer_subnet(ip: str) -> str:
    parts = (ip or "").split(".")
    if len(parts) == 4 and all(p.isdigit() for p in parts):
        return f"{parts[0]}.{parts[1]}.{parts[2]}.0/24"
    return "General/External"


def _advisory_state_rules(
    store: NotebookStore,
    targets: List[Any],
    hosts: List[HostTriage],
) -> List[TriageAdvisory]:
    """Rules that only report arithmetic facts about recorded state."""
    out: List[TriageAdvisory] = []

    for h in hosts:
        target = next(t for t in targets if t.id == h.target_id)

        # S1 — untouched host: a scope target with zero recorded surface.
        if h.is_in_scope and h.phase == HostPhase.UNTOUCHED:
            out.append(
                TriageAdvisory(
                    rule_id="S1-untouched-host",
                    severity=AdvisorySeverity.WARN,
                    kind=AdvisoryKind.STATE,
                    title=f"{h.ip} is untouched — no services recorded",
                    detail="Run your own port scan externally, then record results "
                           "(:s or import an nmap file with :import).",
                    station=STATION_COCKPIT,
                    target_id=h.target_id,
                    host_ip=h.ip,
                    action_text="Open Cockpit",
                )
            )

        # S2 — services still marked UNTESTED.
        if h.services_untested > 0:
            out.append(
                TriageAdvisory(
                    rule_id="S2-untested-services",
                    severity=AdvisorySeverity.HINT,
                    kind=AdvisoryKind.STATE,
                    title=f"{h.ip}: {h.services_untested} service(s) still UNTESTED",
                    detail="Space cycles a service through TODO → CHECKED → DEAD-END → DEFER.",
                    station=STATION_COCKPIT,
                    target_id=h.target_id,
                    host_ip=h.ip,
                    action_text="Review services",
                )
            )

        # S3 — foundational checklist items outstanding.
        remaining = [
            i for i in store.list_checklist_items(target_id=h.target_id)
            if i.status == ChecklistStatus.TODO
        ]
        if remaining:
            nxt = remaining[0]
            out.append(
                TriageAdvisory(
                    rule_id="S3-checklist-next",
                    severity=AdvisorySeverity.INFO,
                    kind=AdvisoryKind.STATE,
                    title=f"{h.ip}: next methodology step — {nxt.title}",
                    detail=f"{h.checklist_done}/{h.checklist_total} steps complete; "
                           "Enter copies the step's reference command.",
                    station=STATION_COCKPIT,
                    target_id=h.target_id,
                    host_ip=h.ip,
                    action_text="Open roadmap",
                )
            )

        # S4 — captured a user flag but attached no evidence.
        if h.has_user_flag and h.evidence_count == 0:
            out.append(
                TriageAdvisory(
                    rule_id="S4-flag-without-evidence",
                    severity=AdvisorySeverity.WARN,
                    kind=AdvisoryKind.STATE,
                    title=f"{h.ip}: user flag recorded but no evidence attached",
                    detail="Attach a screenshot/output (:ev <path> or :paste-ev) before any VM reset.",
                    station=STATION_LOOT,
                    target_id=h.target_id,
                    host_ip=h.ip,
                    action_text="Open Loot ledger",
                )
            )

        # S5 — root flag but no privesc vector documented.
        if h.has_root_flag and not (target.privesc_vector or "").strip():
            out.append(
                TriageAdvisory(
                    rule_id="S5-root-without-vector",
                    severity=AdvisorySeverity.WARN,
                    kind=AdvisoryKind.STATE,
                    title=f"{h.ip}: root flag recorded but privesc vector is blank",
                    detail="Report graders ask how root was reached — :privesc <vector>.",
                    station=STATION_LOOT,
                    target_id=h.target_id,
                    host_ip=h.ip,
                    action_text="Document privesc",
                )
            )

        # S6 — foothold noted but no golden/reproduction command saved.
        if ((target.initial_access_vuln or "").strip() or (target.foothold_cmd or "").strip()) \
                and not [c for c in store.list_commands(target_id=h.target_id, golden_only=True)]:
            out.append(
                TriageAdvisory(
                    rule_id="S6-foothold-no-golden",
                    severity=AdvisorySeverity.HINT,
                    kind=AdvisoryKind.STATE,
                    title=f"{h.ip}: foothold recorded without a golden reproduction command",
                    detail="Save the working exploit syntax (glacis cmd --golden) so a VM reset is recoverable.",
                    station=STATION_LOOT,
                    target_id=h.target_id,
                    host_ip=h.ip,
                    action_text="Open Loot ledger",
                )
            )

        # S7 — out-of-scope target warning (defensive reminder, not a block).
        if not h.is_in_scope:
            out.append(
                TriageAdvisory(
                    rule_id="S7-out-of-scope",
                    severity=AdvisorySeverity.CRIT,
                    kind=AdvisoryKind.STATE,
                    title=f"{h.ip} is marked OUT-OF-SCOPE",
                    detail="Do not test this host. Press 'o' on the host to toggle scope.",
                    station=STATION_COCKPIT,
                    target_id=h.target_id,
                    host_ip=h.ip,
                    action_text="Review scope",
                )
            )

    # S8 — recorded flags but empty objective-proof ledger.
    total_user = sum(1 for h in hosts if h.has_user_flag)
    total_proofs = sum(h.proofs_count for h in hosts)
    if total_user and total_proofs == 0:
        out.append(
            TriageAdvisory(
                rule_id="S8-proof-ledger-empty",
                severity=AdvisorySeverity.HINT,
                kind=AdvisoryKind.STATE,
                title="Flags captured but the objective proof ledger is empty",
                detail="Exam answers are tracked separately from flags — :q <num> <proof>.",
                station=STATION_LOOT,
                action_text="Open proof ledger",
            )
        )
    return out


def _advisory_direction_rules(
    store: NotebookStore,
    targets: List[Any],
    hosts: List[HostTriage],
) -> List[TriageAdvisory]:
    """Opt-in rules that propose where the operator should focus next.

    These correlate data the operator already recorded; they never run
    anything and never emit attack commands — only navigation hints.
    """
    out: List[TriageAdvisory] = []
    services = store.list_services()
    credentials = store.list_credentials()
    cell_states = {}
    try:
        cell_states = store.get_cred_validations()
    except Exception:
        cell_states = {}

    # D1 — credential reuse: recorded cred with an untested auth surface.
    # Focus-shift rules never target out-of-scope hosts (scope safety).
    pairs = auth_service_pairs([t for t in targets if t.is_in_scope], services)
    for c in credentials:
        for t, s in pairs:
            state = (cell_states.get((c.id, s.id)) or "").upper()
            if "PWN" in state or "VALID" in state:
                continue
            scope = (c.service_scope or "").strip().lower()
            if scope and scope not in ("global", s.service.lower()):
                continue
            out.append(
                TriageAdvisory(
                    rule_id="D1-cred-reuse",
                    severity=AdvisorySeverity.HINT,
                    kind=AdvisoryKind.DIRECTION,
                    title=f"'{c.username}' not yet tried on {t.ip}:{s.port} ({s.service.upper()})",
                    detail="Open the spray matrix; Enter on the cell copies the verification "
                           "command for you to run yourself.",
                    station=STATION_CREDS,
                    target_id=t.id,
                    host_ip=t.ip,
                    action_text="Open spray matrix",
                )
            )

    # D2 — validated credential on one host and an untouched auth surface elsewhere.
    owned: Dict[str, int] = {}  # username -> target id where valid/pwned
    for (cid, sid), state in cell_states.items():
        if "VALID" in state.upper() or "PWN" in state.upper():
            cred = next((c for c in credentials if c.id == cid), None)
            svc = next((s for s in services if s.id == sid), None)
            if cred and svc:
                owned[cred.username] = svc.target_id
    for username, proven_tid in owned.items():
        for t, s in pairs:
            if t.id == proven_tid:
                continue
            cred = next((c for c in credentials if c.username == username), None)
            if cred is None:
                continue
            state = (cell_states.get((cred.id, s.id)) or "").upper()
            if state:
                continue
            out.append(
                TriageAdvisory(
                    rule_id="D2-lateral-reuse",
                    severity=AdvisorySeverity.WARN,
                    kind=AdvisoryKind.DIRECTION,
                    title=f"Lateral move: '{username}' worked once; {t.ip}:{s.port} is untested",
                    detail="Password reuse across hosts is the single most common exam pivot.",
                    station=STATION_CREDS,
                    target_id=t.id,
                    host_ip=t.ip,
                    action_text="Open spray matrix",
                )
            )

    # D3 — rabbit hole: dead ends dominate a host while another host is fresh.
    for h in hosts:
        if not h.is_in_scope or h.phase in (HostPhase.ROOT, HostPhase.COMPLETE):
            continue
        checked_out = h.services_total > 0
        blocked = (h.services_dead_end + h.failure_count) >= 2 and h.phase in (
            HostPhase.RECON,
            HostPhase.UNTOUCHED,
        )
        if not (checked_out and blocked):
            continue
        fresh = [
            o for o in hosts
            if o.target_id != h.target_id and o.is_in_scope and o.phase in (
                HostPhase.UNTOUCHED, HostPhase.RECON
            ) and (o.phase == HostPhase.UNTOUCHED or o.services_high_value > 0)
        ]
        if fresh:
            alt = fresh[0]
            out.append(
                TriageAdvisory(
                    rule_id="D3-rabbit-hole-switch",
                    severity=AdvisorySeverity.WARN,
                    kind=AdvisoryKind.DIRECTION,
                    title=f"Possible rabbit hole on {h.ip} — {alt.ip} still has open avenues",
                    detail=f"{h.services_dead_end} dead-end service(s) and {h.failure_count} logged "
                           f"dead-end(s) on {h.ip}; log the false path (:stuck) and rotate.",
                    station=STATION_PULSE,
                    target_id=alt.target_id,
                    host_ip=alt.ip,
                    action_text=f"Focus {alt.ip}",
                )
            )

    # D4 — hosts on more than one inferred subnet but no documented pivot.
    subnets = {_infer_subnet(t.ip) for t in targets if t.is_in_scope}
    documented_pivot = any(t.is_pivot for t in targets)
    if len(subnets) > 1 and not documented_pivot:
        out.append(
            TriageAdvisory(
                rule_id="D4-pivot-undocumented",
                severity=AdvisorySeverity.HINT,
                kind=AdvisoryKind.DIRECTION,
                title="Targets span multiple subnets with no pivot documented",
                detail="When a compromised host is dual-homed, record it with :pivot <route>; "
                       "the Network station calculates the SOCKS hop chain.",
                station=STATION_NETWORK,
                action_text="Open network topology",
            )
        )
    return out


# Stable order: severity desc, then rule id, then host ip, then title.
def _sort_key(a: TriageAdvisory) -> tuple[Any, ...]:
    return (-_SEVERITY_RANK[a.severity], a.rule_id, a.host_ip, a.title)


def evaluate_workspace(
    store: NotebookStore,
    workspace_id: Optional[int] = None,
    *,
    include_direction: Optional[bool] = None,
) -> TriageReport:
    """Evaluate the active workspace and return the full triage report.

    Deterministic: identical store state always produces an identical report.
    Directional advisories are gated on the opt-in derived-guidance switch
    unless ``include_direction`` is passed explicitly.
    """
    ws = store.get_workspace(workspace_id) if workspace_id else store.get_active_workspace()
    ws_id = ws.id if ws else 1
    ws_name = ws.name if ws else "default"
    targets = store.list_targets(workspace_id=ws_id)
    hosts = [build_host_triage(store, t) for t in targets]

    # Host ordering: untouched/early-phase hosts with high-value services
    # float up, completed hosts sink. Fully deterministic.
    hosts.sort(key=lambda h: (h.phase == HostPhase.COMPLETE, _phase_rank(h), h.ip))

    advisories = _advisory_state_rules(store, targets, hosts)
    direction_on = (
        derive_guidance_enabled() if include_direction is None else include_direction
    )
    if direction_on:
        advisories.extend(_advisory_direction_rules(store, targets, hosts))
    advisories.sort(key=_sort_key)

    totals = {
        "targets": len(hosts),
        "in_scope": sum(1 for h in hosts if h.is_in_scope),
        "services": sum(h.services_total for h in hosts),
        "credentials": sum(h.creds_count for h in hosts),
        "findings": sum(h.findings_count for h in hosts),
        "evidence": sum(h.evidence_count for h in hosts),
        "proofs": sum(h.proofs_count for h in hosts),
        "dead_ends": sum(h.services_dead_end + h.failure_count for h in hosts),
        "untouched": sum(1 for h in hosts if h.phase == HostPhase.UNTOUCHED and h.is_in_scope),
        "complete": sum(1 for h in hosts if h.phase == HostPhase.COMPLETE),
    }
    overall = round(sum(h.completion_pct for h in hosts) / len(hosts), 1) if hosts else 0.0

    return TriageReport(
        workspace_name=ws_name,
        hosts=hosts,
        advisories=advisories,
        totals=totals,
        overall_pct=overall,
        direction_enabled=direction_on,
    )


def _phase_rank(host: HostTriage) -> int:
    """Lower = more urgent (needs the operator sooner)."""
    order = {
        HostPhase.UNTOUCHED: 0,
        HostPhase.RECON: 1,
        HostPhase.FOOTHOLD: 2,
        HostPhase.USER: 3,
        HostPhase.ROOT: 4,
        HostPhase.COMPLETE: 5,
    }
    return order[host.phase]


def phase_counts(report: TriageReport) -> Dict[str, int]:
    """Tally hosts per phase (handy for KPI strips and the HTML report)."""
    counts: Dict[str, int] = {p.value: 0 for p in HostPhase}
    for h in report.hosts:
        counts[h.phase.value] += 1
    return counts
