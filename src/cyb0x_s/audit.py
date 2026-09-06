"""Proof Invariant Completeness Audit Engine for CYB0X-S.

Verifies the operational proof chain across all assessment targets:
    Host -> Service -> Foothold -> User Proof -> Root Proof

100% passive verification tool that enforces operational hygiene
and prevents losing work or evidence prior to lab target resets.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from cyb0x_s.db.store import NotebookStore
from cyb0x_s.models import ServiceStatus, Target


class AuditStatus(str, Enum):
    """Status of an individual invariant check."""
    SATISFIED = "PASS"
    MISSING = "MISSING"
    PARTIAL = "PARTIAL"
    SKIPPED = "SKIPPED"


class AuditCheck(BaseModel):
    """An individual invariant requirement."""
    stage: str                  # Host, Service, Foothold, User, Root
    name: str                   # Human-readable check title
    status: AuditStatus
    details: str                # Current observed state
    remediation_hint: str       # Precise action or command to satisfy the invariant
    is_critical: bool = False   # If True, target cannot be safely reset without this


class TargetAudit(BaseModel):
    """Comprehensive audit report for a single target."""
    target_id: int
    ip: str
    hostname: str = ""
    os: str = "Unknown"
    is_in_scope: bool = True
    is_pivot: bool = False
    checks: List[AuditCheck] = Field(default_factory=list)
    satisfied_count: int = 0
    total_count: int = 0
    completion_percentage: float = 0.0
    is_complete: bool = False
    missing_critical_proofs: List[str] = Field(default_factory=list)
    pre_reset_warnings: List[str] = Field(default_factory=list)


class WorkspaceAudit(BaseModel):
    """Workspace-wide assessment readiness and proof audit summary."""
    workspace_id: int
    workspace_name: str
    targets: List[TargetAudit] = Field(default_factory=list)
    total_targets: int = 0
    complete_targets: int = 0
    overall_readiness_pct: float = 0.0


def audit_target(store: NotebookStore, target_id: int) -> Optional[TargetAudit]:
    """Audit proof chain invariants for a single target."""
    target = store.get_target(target_id)
    if not target or target.id is None:
        return None

    services = store.list_services(target_id=target.id)
    credentials = store.list_credentials(target_id=target.id)
    commands = store.list_commands(target_id=target.id)
    findings = store.list_findings(target_id=target.id)
    proofs = store.list_exam_proofs(target_id=target.id)
    notes = store.list_notes(target_id=target.id)

    checks: List[AuditCheck] = []

    # -------------------------------------------------------------------------
    # 1. Host Stage: Scope & OS Fingerprint
    # -------------------------------------------------------------------------
    has_os = bool(target.os and target.os.lower() != "unknown")
    checks.append(
        AuditCheck(
            stage="Host",
            name="OS Fingerprint",
            status=AuditStatus.SATISFIED if has_os else AuditStatus.MISSING,
            details=f"OS: {target.os}" if has_os else "OS unrecorded / Unknown",
            remediation_hint=":t details (record Windows, Linux, etc.)",
            is_critical=False,
        )
    )

    # -------------------------------------------------------------------------
    # 2. Service Stage: Service Discovery & Enumeration
    # -------------------------------------------------------------------------
    has_services = len(services) > 0
    checked_services = [s for s in services if s.status != ServiceStatus.UNTESTED]
    service_status = AuditStatus.SATISFIED if len(checked_services) > 0 else (
        AuditStatus.PARTIAL if has_services else AuditStatus.MISSING
    )
    checks.append(
        AuditCheck(
            stage="Service",
            name="Service Mapping",
            status=service_status,
            details=f"{len(services)} services logged ({len(checked_services)} verified)",
            remediation_hint=":s <port> <service> [version] to map open ports",
            is_critical=True,
        )
    )

    # -------------------------------------------------------------------------
    # 3. Foothold Stage: Vulnerability, Execution Command, and Context
    # -------------------------------------------------------------------------
    # 3a. Initial Access Vulnerability
    has_vuln = bool(target.initial_access_vuln.strip()) or len(findings) > 0
    vuln_detail = (
        target.initial_access_vuln.strip()
        if target.initial_access_vuln.strip()
        else (f"Via finding: {findings[0].title}" if findings else "No vulnerability recorded")
    )
    checks.append(
        AuditCheck(
            stage="Foothold",
            name="Initial Access Vulnerability",
            status=AuditStatus.SATISFIED if has_vuln else AuditStatus.MISSING,
            details=vuln_detail,
            remediation_hint=":foothold <vulnerability_name_or_cve>",
            is_critical=True,
        )
    )

    # 3b. Foothold Command Payload
    golden_cmds = [c for c in commands if c.is_golden or (c.step and c.step.lower() in ("foothold", "exploit"))]
    has_cmd = bool(target.foothold_cmd.strip()) or len(golden_cmds) > 0
    cmd_detail = (
        target.foothold_cmd.strip()
        if target.foothold_cmd.strip()
        else (f"Golden command: {golden_cmds[0].command[:40]}..." if golden_cmds else "No exploit command recorded")
    )
    checks.append(
        AuditCheck(
            stage="Foothold",
            name="Exploit Command Payload",
            status=AuditStatus.SATISFIED if has_cmd else AuditStatus.MISSING,
            details=cmd_detail,
            remediation_hint=":foothold-cmd <command> (record working exploit syntax)",
            is_critical=True,
        )
    )

    # 3c. Foothold Context (whoami / shell level)
    has_ctx = bool(target.foothold_context.strip()) or any("whoami" in c.command.lower() for c in commands)
    checks.append(
        AuditCheck(
            stage="Foothold",
            name="Shell Context (whoami)",
            status=AuditStatus.SATISFIED if has_ctx else AuditStatus.MISSING,
            details=target.foothold_context if target.foothold_context else ("Recorded in commands" if has_ctx else "Initial whoami not documented"),
            remediation_hint=":whoami <username/context> (e.g. www-data, iusr)",
            is_critical=False,
        )
    )

    # -------------------------------------------------------------------------
    # 4. User Stage: User Proof / Flag & Extracted Loot
    # -------------------------------------------------------------------------
    has_user_flag = bool(target.user_flag.strip()) or any(
        "user" in p.objective_id.lower() or p.category.upper() == "FLAG" for p in proofs
    )
    flag_detail = (
        f"Flag: {target.user_flag[:20]}..."
        if target.user_flag
        else ("Proof artifact recorded" if has_user_flag else "No user flag recorded")
    )
    checks.append(
        AuditCheck(
            stage="User",
            name="User Flag / Proof",
            status=AuditStatus.SATISFIED if has_user_flag else AuditStatus.MISSING,
            details=flag_detail,
            remediation_hint=":uflag <user_flag_value>",
            is_critical=True,
        )
    )

    # -------------------------------------------------------------------------
    # 5. Root Stage: PrivEsc Vector, Root Proof Command/Output, and Root Flag
    # -------------------------------------------------------------------------
    # 5a. PrivEsc Vector
    has_privesc = bool(target.privesc_vector.strip())
    checks.append(
        AuditCheck(
            stage="Root",
            name="Privilege Escalation Vector",
            status=AuditStatus.SATISFIED if has_privesc else AuditStatus.MISSING,
            details=target.privesc_vector if has_privesc else "No PrivEsc vector documented",
            remediation_hint=":privesc <vector> (e.g. sudo NOPASSWD, SUID, SeImpersonatePrivilege)",
            is_critical=True,
        )
    )

    # 5b. Root Proof Command / Evidence
    priv_cmds = [c for c in commands if c.step and c.step.lower() in ("privesc", "root")]
    has_root_proof = bool(target.root_proof.strip()) or len(priv_cmds) > 0
    checks.append(
        AuditCheck(
            stage="Root",
            name="Root Proof Command / Output",
            status=AuditStatus.SATISFIED if has_root_proof else AuditStatus.MISSING,
            details=target.root_proof if target.root_proof else ("Recorded in command history" if priv_cmds else "Root verification (id/whoami) missing"),
            remediation_hint=":rootproof <output> (e.g. 'uid=0(root) gid=0(root) ip=10.10.10.x')",
            is_critical=True,
        )
    )

    # 5c. Root Flag
    has_root_flag = bool(target.root_flag.strip()) or any(
        "root" in p.objective_id.lower() for p in proofs
    )
    root_flag_detail = (
        f"Flag: {target.root_flag[:20]}..."
        if target.root_flag
        else ("Proof artifact recorded" if has_root_flag else "No root flag recorded")
    )
    checks.append(
        AuditCheck(
            stage="Root",
            name="Root Flag",
            status=AuditStatus.SATISFIED if has_root_flag else AuditStatus.MISSING,
            details=root_flag_detail,
            remediation_hint=":rflag <root_flag_value>",
            is_critical=True,
        )
    )

    # Calculate overall metrics
    satisfied_count = sum(1 for c in checks if c.status == AuditStatus.SATISFIED)
    total_count = len(checks)
    completion_pct = round((satisfied_count / total_count) * 100.0, 1) if total_count > 0 else 0.0

    missing_critical = [
        f"[{c.stage}] {c.name}: {c.remediation_hint}"
        for c in checks
        if c.is_critical and c.status != AuditStatus.SATISFIED
    ]

    # Pre-reset warnings
    pre_reset_warnings: List[str] = []
    if not has_cmd:
        pre_reset_warnings.append("FOOTHOLD COMMAND NOT SAVED: You may not be able to re-exploit if the target is reverted!")
    if not has_user_flag and not has_root_flag:
        pre_reset_warnings.append("NO FLAGS OR PROOFS SAVED: Target has zero captured flags!")
    elif not has_root_proof and has_user_flag:
        pre_reset_warnings.append("ROOT PROOF MISSING: You popped user but haven't captured root proof (id/ip a)!")
    if not has_privesc and has_root_flag:
        pre_reset_warnings.append("PRIVESC VECTOR NOT DOCUMENTED: How root was obtained is not written down!")

    return TargetAudit(
        target_id=target.id,
        ip=target.ip,
        hostname=target.hostname,
        os=target.os,
        is_in_scope=target.is_in_scope,
        is_pivot=target.is_pivot,
        checks=checks,
        satisfied_count=satisfied_count,
        total_count=total_count,
        completion_percentage=completion_pct,
        is_complete=(satisfied_count == total_count),
        missing_critical_proofs=missing_critical,
        pre_reset_warnings=pre_reset_warnings,
    )


def audit_workspace(store: NotebookStore, workspace_id: Optional[int] = None) -> WorkspaceAudit:
    """Audit all targets within a workspace against proof invariants."""
    ws = store.get_workspace(workspace_id) if workspace_id else store.get_active_workspace()
    ws_id = ws.id if ws and ws.id else 1
    ws_name = ws.name if ws else "default"

    targets = store.list_targets(workspace_id=ws_id)
    target_audits: List[TargetAudit] = []

    for t in targets:
        if t.id is not None:
            ta = audit_target(store, t.id)
            if ta:
                target_audits.append(ta)

    total_targets = len(target_audits)
    complete_targets = sum(1 for ta in target_audits if ta.is_complete)
    total_checks = sum(ta.total_count for ta in target_audits)
    total_satisfied = sum(ta.satisfied_count for ta in target_audits)
    overall_pct = round((total_satisfied / total_checks) * 100.0, 1) if total_checks > 0 else 0.0

    return WorkspaceAudit(
        workspace_id=ws_id,
        workspace_name=ws_name,
        targets=target_audits,
        total_targets=total_targets,
        complete_targets=complete_targets,
        overall_readiness_pct=overall_pct,
    )
