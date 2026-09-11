"""Tests for the deterministic, explainable triage engine."""

from __future__ import annotations

from glacis.db.store import NotebookStore
from glacis.models import ChecklistStatus, ServiceStatus
from glacis.settings import set_derive_guidance
from glacis.triage import (
    AdvisoryKind,
    AdvisorySeverity,
    HostPhase,
    TriageAdvisory,
    evaluate_workspace,
    phase_counts,
)


def _rule_ids(report) -> list[str]:
    return [a.rule_id for a in report.advisories]


def test_empty_workspace_is_calm(store: NotebookStore) -> None:
    report = evaluate_workspace(store)
    assert report.hosts == []
    assert report.advisories == []
    assert report.overall_pct == 0.0
    assert report.totals == {
        "targets": 0, "in_scope": 0, "services": 0, "credentials": 0,
        "findings": 0, "evidence": 0, "proofs": 0, "dead_ends": 0,
        "untouched": 0, "complete": 0,
    }


def test_untouched_host_phase_and_advisory(store: NotebookStore) -> None:
    store.add_target("10.1.1.1")
    report = evaluate_workspace(store)
    assert len(report.hosts) == 1
    host = report.hosts[0]
    assert host.phase == HostPhase.UNTOUCHED
    assert host.completion_pct == 0
    assert host.progress_bar.count("░") == 8
    assert "S1-untouched-host" in _rule_ids(report)
    s1 = next(a for a in report.advisories if a.rule_id == "S1-untouched-host")
    assert s1.severity == AdvisorySeverity.WARN
    assert s1.kind == AdvisoryKind.STATE
    assert s1.station == "tab-worksheet"
    assert s1.host_ip == "10.1.1.1"


def test_phase_progression_is_pure_arithmetic(store: NotebookStore) -> None:
    t = store.add_target("10.1.1.2")
    store.add_service(t.id, port=22, service="ssh", status=ServiceStatus.UNTESTED)
    report = evaluate_workspace(store)
    assert report.hosts[0].phase == HostPhase.RECON
    assert report.hosts[0].services_untested == 1
    assert "S2-untested-services" in _rule_ids(report)

    store.add_checklist_item("nmap sweep", target_id=t.id, status=ChecklistStatus.CHECKED)
    store.update_target_details(t.id, initial_access_vuln="weak creds on ssh")
    report = evaluate_workspace(store)
    assert report.hosts[0].phase == HostPhase.FOOTHOLD

    store.update_target_details(t.id, user_flag="user{abc}")
    report = evaluate_workspace(store)
    assert report.hosts[0].phase == HostPhase.USER

    store.update_target_details(t.id, privesc_vector="sudo NOPASSWD find", root_flag="root{xyz}")
    report = evaluate_workspace(store)
    # root flag but no evidence yet -> ROOT, not COMPLETE
    assert report.hosts[0].phase == HostPhase.ROOT

    store.add_evidence("screenshots/root.png", target_id=t.id)
    report = evaluate_workspace(store)
    assert report.hosts[0].phase == HostPhase.COMPLETE
    assert report.hosts[0].completion_pct == 100.0


def test_evidence_gap_rules(store: NotebookStore) -> None:
    t = store.add_target("10.1.1.3")
    store.update_target_details(t.id, user_flag="u{1}")
    report = evaluate_workspace(store)
    assert "S4-flag-without-evidence" in _rule_ids(report)

    t2 = store.add_target("10.1.1.4")
    store.update_target_details(t2.id, root_flag="r{1}")
    report = evaluate_workspace(store)
    assert "S5-root-without-vector" in _rule_ids(report)


def test_golden_command_gap_rule(store: NotebookStore) -> None:
    t = store.add_target("10.1.1.5")
    store.update_target_details(t.id, initial_access_vuln="CVE-X")
    report = evaluate_workspace(store)
    assert "S6-foothold-no-golden" in _rule_ids(report)
    store.add_command("python3 exploit.py", target_id=t.id, is_golden=True)
    report = evaluate_workspace(store)
    assert "S6-foothold-no-golden" not in _rule_ids(report)


def test_out_of_scope_is_crit_state_rule(store: NotebookStore) -> None:
    t = store.add_target("10.1.1.6")
    store.update_target_details(t.id, is_in_scope=False)
    report = evaluate_workspace(store)
    s7 = next(a for a in report.advisories if a.rule_id == "S7-out-of-scope")
    assert s7.severity == AdvisorySeverity.CRIT


def test_proof_ledger_empty_after_flag_rule(store: NotebookStore) -> None:
    t = store.add_target("10.1.1.7")
    store.update_target_details(t.id, user_flag="u{2}")
    report = evaluate_workspace(store)
    assert "S8-proof-ledger-empty" in _rule_ids(report)
    store.add_exam_proof("Q1", "answer", target_id=t.id)
    report = evaluate_workspace(store)
    assert "S8-proof-ledger-empty" not in _rule_ids(report)


def test_checklist_next_rule_points_to_first_todo(store: NotebookStore) -> None:
    t = store.add_target("10.1.1.8")
    store.add_checklist_item("first step", target_id=t.id, status=ChecklistStatus.CHECKED)
    store.add_checklist_item("second step", target_id=t.id, status=ChecklistStatus.TODO)
    report = evaluate_workspace(store)
    s3 = next(a for a in report.advisories if a.rule_id == "S3-checklist-next")
    assert "second step" in s3.title


def test_direction_rules_opt_in_only(store: NotebookStore) -> None:
    set_derive_guidance(False)
    t = store.add_target("10.1.1.9")
    store.add_service(t.id, port=22, service="ssh")
    store.add_credential("admin", "pw1", target_id=t.id, service_scope="global")
    report = evaluate_workspace(store)
    assert all(a.kind == AdvisoryKind.STATE for a in report.advisories)
    assert not any(a.rule_id.startswith("D") for a in report.advisories)
    assert report.direction_enabled is False

    report = evaluate_workspace(store, include_direction=True)
    d1 = [a for a in report.advisories if a.rule_id == "D1-cred-reuse"]
    assert d1, "credential vs untested SSH surface should surface"
    assert d1[0].station == "tab-creds"
    assert d1[0].kind == AdvisoryKind.DIRECTION


def test_direction_respects_credential_scope(store: NotebookStore) -> None:
    t = store.add_target("10.1.1.10")
    store.add_service(t.id, port=445, service="smb")
    store.add_credential("webuser", "pw", target_id=t.id, service_scope="http")
    report = evaluate_workspace(store, include_direction=True)
    assert not [a for a in report.advisories if a.rule_id == "D1-cred-reuse"]


def test_d2_lateral_reuse_across_hosts(store: NotebookStore) -> None:
    t1 = store.add_target("10.1.1.11")
    s1 = store.add_service(t1.id, port=22, service="ssh")
    c = store.add_credential("admin", "pw", target_id=t1.id, service_scope="global")
    store.set_cred_validation(c.id, s1.id, "✔ VALID")
    t2 = store.add_target("10.1.1.12")
    store.add_service(t2.id, port=22, service="ssh")
    report = evaluate_workspace(store, include_direction=True)
    d2 = [a for a in report.advisories if a.rule_id == "D2-lateral-reuse"]
    assert d2 and d2[0].host_ip == "10.1.1.12"
    assert d2[0].severity == AdvisorySeverity.WARN


def test_d3_rabbit_hole_switch(store: NotebookStore) -> None:
    stuck = store.add_target("10.1.1.13")
    store.add_service(stuck.id, port=8080, service="http", status=ServiceStatus.DEAD_END)
    store.add_service(stuck.id, port=9090, service="http", status=ServiceStatus.DEAD_END)
    store.add_failure_log(target_id=stuck.id, where_stuck="brute forced login 90m")
    fresh = store.add_target("10.1.1.14")
    store.add_service(fresh.id, port=445, service="smb", access_potential="HIGH")
    report = evaluate_workspace(store, include_direction=True)
    d3 = [a for a in report.advisories if a.rule_id == "D3-rabbit-hole-switch"]
    assert d3 and d3[0].host_ip == "10.1.1.14"
    assert d3[0].target_id == fresh.id


def test_d4_pivot_undocumented(store: NotebookStore) -> None:
    store.add_target("10.1.1.15")
    store.add_target("192.168.1.15")
    report = evaluate_workspace(store, include_direction=True)
    assert any(a.rule_id == "D4-pivot-undocumented" for a in report.advisories)
    # Once a pivot is documented the advisory clears.
    store.update_target_details(store.list_targets()[0].id, is_pivot=True,
                                pivot_route="192.168.1.0/24 via socks5:1080")
    report = evaluate_workspace(store, include_direction=True)
    assert not any(a.rule_id == "D4-pivot-undocumented" for a in report.advisories)


def test_report_is_deterministic_and_sorted(store: NotebookStore) -> None:
    for i in range(3):
        t = store.add_target(f"10.2.0.{i + 10}")
        store.add_service(t.id, port=22, service="ssh", status=ServiceStatus.UNTESTED)
    store.add_target("192.168.9.9")
    r1 = evaluate_workspace(store, include_direction=True)
    r2 = evaluate_workspace(store, include_direction=True)
    keys1 = [(a.rule_id, a.target_id, a.title) for a in r1.advisories]
    keys2 = [(a.rule_id, a.target_id, a.title) for a in r2.advisories]
    assert keys1 == keys2
    # Severity never increases down the feed.
    rank = {AdvisorySeverity.CRIT: 3, AdvisorySeverity.WARN: 2,
            AdvisorySeverity.HINT: 1, AdvisorySeverity.INFO: 0}
    seq = [rank[a.severity] for a in r1.advisories]
    assert seq == sorted(seq, reverse=True)
    # Untouched hosts sort ahead of mapped hosts.
    assert r1.hosts[0].phase == HostPhase.UNTOUCHED
    counts = phase_counts(r1)
    assert counts["UNTOUCHED"] >= 1 and counts["RECON"] == 3


def test_advisory_key_is_stable() -> None:
    a = TriageAdvisory(
        rule_id="S1-untouched-host", severity=AdvisorySeverity.WARN,
        kind=AdvisoryKind.STATE, title="x", target_id=4,
    )
    assert a.key() == ("S1-untouched-host", 4, "x")
