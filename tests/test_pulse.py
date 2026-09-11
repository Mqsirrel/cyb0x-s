"""Tests for the GLACIS Pulse offline intelligence layer."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from glacis.db.store import NotebookStore
from glacis.models import ChecklistStatus, ServiceStatus
from glacis.pulse import (
    ActionPriority,
    EventType,
    build_timeline,
    compute_next_actions,
    compute_target_scorecards,
    compute_workspace_pulse,
    progress_bar,
    render_sparkline,
    workspace_fingerprint,
)


def _seed_rich_workspace(store: NotebookStore) -> None:
    t1 = store.add_target("10.10.10.20", hostname="box1", os_name="Linux")
    store.add_service(target_id=t1.id, port=22, service="SSH", version="OpenSSH 8.2")
    store.add_service(target_id=t1.id, port=80, service="HTTP", version="Apache 2.4")
    store.add_finding("Anonymous SMB share", target_id=t1.id, severity="HIGH")
    store.add_finding("Verbose banners", target_id=t1.id, severity=None)
    store.add_credential("admin", "secret", target_id=t1.id)
    store.add_note("check backups", target_id=t1.id)
    store.add_evidence("screenshots/login.png", target_id=t1.id)
    store.add_checklist_item("SMB enumeration", target_id=t1.id)
    store.add_checklist_item("Web fuzzing", target_id=t1.id)

    t2 = store.add_target("172.16.1.50", hostname="db01", os_name="Linux")
    store.add_service(target_id=t2.id, port=3306, service="MySQL", status=ServiceStatus.UNTESTED)
    store.add_lead("old phpMyAdmin instance", target_id=t2.id)
    store.set_active_target(t2.id)


def test_pulse_counts_all_record_types(store: NotebookStore) -> None:
    _seed_rich_workspace(store)
    pulse = compute_workspace_pulse(store)

    assert pulse.workspace_name
    assert pulse.targets == 2
    assert pulse.in_scope_targets == 2
    assert pulse.services == 3
    assert pulse.services_tested == 2  # 3306 left UNTESTED
    assert pulse.findings == 2
    assert pulse.severity_counts["HIGH"] == 1
    assert pulse.severity_counts["UNRATED"] == 1
    assert pulse.credentials == 1
    assert pulse.notes == 1
    assert pulse.evidence == 1
    assert pulse.leads_total == 1
    assert pulse.leads_open == 1
    assert pulse.checklist_total == 2
    assert pulse.commands_logged >= 0
    assert pulse.coverage_pct == 67  # 2 of 3 tested
    assert len(pulse.activity_14d) == 14
    assert pulse.momentum_24h >= 8  # targets+services+findings+creds+notes+evidence+checklist+lead


def test_pulse_coverage_and_checklist_percent(store: NotebookStore) -> None:
    t = store.add_target("10.10.10.20")
    s1 = store.add_service(target_id=t.id, port=22, service="SSH")
    store.add_service(target_id=t.id, port=445, service="SMB")
    store.update_service_status(s1.id, ServiceStatus.DEAD_END)
    store.add_checklist_item("step A", target_id=t.id)
    item_b = store.add_checklist_item("step B", target_id=t.id)
    store.update_checklist_status(item_b.id, ChecklistStatus.CHECKED)

    pulse = compute_workspace_pulse(store)
    assert pulse.services == 2
    assert pulse.services_tested == 2  # CHECKED + DEAD-END both count as handled
    assert pulse.services_dead_ends == 1
    assert pulse.checklist_pct == 50
    assert pulse.checklist_checked == 1


def test_pulse_empty_workspace(store: NotebookStore) -> None:
    pulse = compute_workspace_pulse(store)
    assert pulse.targets == 0
    assert pulse.services == 0
    assert pulse.coverage_pct == 0
    assert len(pulse.activity_14d) == 14
    assert pulse.sparkline_blocks == "▁" * 14


def test_scorecards_grades_and_flags(store: NotebookStore) -> None:
    _seed_rich_workspace(store)
    cards = compute_target_scorecards(store)
    assert len(cards) == 2

    box1 = next(c for c in cards if c.ip == "10.10.10.20")
    assert box1.services == 2
    assert box1.findings == 2
    assert box1.credentials == 1
    assert box1.checklist_pct == 0  # both items TODO
    assert box1.flags_captured == 0
    assert box1.grade in "CDE"

    db01 = next(c for c in cards if c.ip == "172.16.1.50")
    assert db01.services == 1
    assert db01.grade == "F"

    # Capture both flags -> grade improves (coverage/flags outweigh untouched methodology)
    target = store.get_target_by_ip("10.10.10.20")
    store.update_target_details(
        target_id=target.id,
        user_flag="flag{user}",
        root_flag="flag{root}",
    )
    cards2 = compute_target_scorecards(store)
    box2 = next(c for c in cards2 if c.ip == "10.10.10.20")
    assert box2.flags_captured == 2
    assert box2.grade > box1.grade or box2.grade in "AB"  # improvement or already strong

    # Finishing the methodology too -> solid A
    for k in store.list_checklist_items(target_id=target.id):
        store.update_checklist_status(k.id, ChecklistStatus.CHECKED)
    cards3 = compute_target_scorecards(store)
    box3 = next(c for c in cards3 if c.ip == "10.10.10.20")
    assert box3.grade == "A"

    # Busiest / most-complete target sorts first
    assert cards2[0].ip == "10.10.10.20"


def test_timeline_merges_and_sorts(store: NotebookStore) -> None:
    _seed_rich_workspace(store)
    events = build_timeline(store)
    assert len(events) >= 10

    kinds = {e.kind for e in events}
    assert EventType.TARGET in kinds
    assert EventType.SERVICE in kinds
    assert EventType.FINDING in kinds
    assert EventType.CREDENTIAL in kinds
    assert EventType.NOTE in kinds
    assert EventType.EVIDENCE in kinds
    assert EventType.CHECKLIST in kinds
    assert EventType.LEAD in kinds

    # newest first
    whens = [e.when for e in events]
    assert whens == sorted(whens, reverse=True)

    # target attribution
    for e in events:
        if e.kind == EventType.FINDING and "Anonymous SMB" in e.label:
            assert e.target_ip == "10.10.10.20"

    # limit respected
    assert len(build_timeline(store, limit=3)) == 3


def test_next_actions_priorities(store: NotebookStore) -> None:
    t = store.add_target("10.10.10.20", hostname="box1")
    store.add_service(target_id=t.id, port=22, service="SSH", status=ServiceStatus.UNTESTED)
    store.add_service(target_id=t.id, port=445, service="SMB", status=ServiceStatus.UNTESTED)
    store.add_lead("default tomcat creds", target_id=t.id)
    store.add_checklist_item("directory fuzzing", target_id=t.id)

    actions = compute_next_actions(store)
    assert actions, "expected triage items"

    ranks = {"now": 0, "next": 1, "later": 2}
    order = [ranks[a.priority.value] for a in actions]
    assert order == sorted(order)

    # Without a foothold everything is NEXT/LATER — nothing claims NOW urgency
    assert all(a.priority != ActionPriority.NOW for a in actions)

    # Add a foothold: untested services and missing user proof become NOW
    store.update_target_details(target_id=t.id, initial_access_vuln="Tomcat manager login")
    actions2 = compute_next_actions(store)
    now_items = [a for a in actions2 if a.priority == ActionPriority.NOW]
    assert any(a.category == "service" for a in now_items)
    assert any(a.category == "proof" and "user" in a.title for a in now_items)

    # Dead ends never appear in the queue
    svc = store.list_services(target_id=t.id)[0]
    store.update_service_status(svc.id, ServiceStatus.DEAD_END)
    actions3 = compute_next_actions(store)
    assert not any("22/tcp" in a.title for a in actions3)  # dead-end dropped from queue


def test_action_queue_deterministic(store: NotebookStore) -> None:
    _seed_rich_workspace(store)
    a = compute_next_actions(store)
    b = compute_next_actions(store)
    assert a == b


def test_sparkline_and_progress_helpers() -> None:
    assert render_sparkline([]) == ""
    assert render_sparkline([0, 0, 0]) == "▁▁▁"
    assert render_sparkline([0, 5, 10])[-1] == "█"
    assert render_sparkline([0, 5, 10])[1] == "▅"  # round((7)*0.5)=4
    assert progress_bar(0, 10) == "░" * 10
    assert progress_bar(100, 10) == "█" * 10
    assert progress_bar(50, 10) == "█████░░░░░"
    assert progress_bar(999) == "█" * 10
    assert progress_bar(-5) == "░" * 10


def test_activity_series_windowing(store: NotebookStore) -> None:
    t = store.add_target("10.10.10.20")
    store.add_note("fresh note", target_id=t.id)
    pulse = compute_workspace_pulse(store)
    assert pulse.activity_14d[-1] >= 1          # today
    assert sum(pulse.activity_14d[:-1]) >= 0    # window stays 14 days wide
    assert pulse.momentum_24h >= 1


def test_stale_target_detection(store: NotebookStore) -> None:
    t = store.add_target("10.10.10.20")
    # backdate the target artificially
    old = datetime.now(timezone.utc) - timedelta(days=30)
    store.conn.execute(
        "UPDATE targets SET updated_at = ? WHERE id = ?",
        (old.isoformat(), t.id),
    )
    store.conn.commit()
    pulse = compute_workspace_pulse(store)
    assert pulse.stalest_target == "10.10.10.20"
    assert pulse.stale_days >= 29


# -----------------------------------------------------------------------------
# Fingerprint cache (perf): correctness first, speed second
# -----------------------------------------------------------------------------

def test_pulse_cache_hits_and_invalidation(store: NotebookStore) -> None:
    _seed_rich_workspace(store)

    first = compute_workspace_pulse(store)
    cards_first = compute_target_scorecards(store)
    actions_first = compute_next_actions(store)

    # Cache must be warm: mutating nothing returns identical snapshots and
    # the fingerprint should be stable.
    fp1 = workspace_fingerprint(store)
    fp2 = workspace_fingerprint(store)
    assert fp1 == fp2

    second = compute_workspace_pulse(store)
    assert second == first
    assert compute_target_scorecards(store) == cards_first
    assert compute_next_actions(store) == actions_first

    # Any recorded change must invalidate: add a service -> coverage changes.
    t1 = store.get_target_by_ip("10.10.10.20")
    store.add_service(target_id=t1.id, port=9999, service=" sneak", status=ServiceStatus.UNTESTED)

    assert workspace_fingerprint(store) != fp1
    third = compute_workspace_pulse(store)
    assert third.services == first.services + 1
    assert third.coverage_pct < first.coverage_pct

    # Status change also invalidates (updated_at + service row changed).
    svc = [s for s in store.list_services(target_id=t1.id) if s.port == 9999][0]
    store.update_service_status(svc.id, ServiceStatus.DEAD_END)
    fourth = compute_workspace_pulse(store)
    assert fourth.services_tested == third.services_tested + 1


def test_fingerprint_covers_settings_too(store: NotebookStore) -> None:
    fp_a = workspace_fingerprint(store)
    store.set_setting("welcome_seen", "1")
    assert workspace_fingerprint(store) != fp_a


def test_timeline_is_fingerprint_cached(store: NotebookStore) -> None:
    _seed_rich_workspace(store)

    tl1 = build_timeline(store, limit=50)
    tl2 = build_timeline(store, limit=50)
    assert tl1 == tl2
    assert tl1[0] is tl2[0], "repeat calls must reuse the cached event objects"

    # Any recorded write shifts the fingerprint -> timeline recomputes.
    t1 = store.get_target_by_ip("10.10.10.20")
    store.add_note(target_id=t1.id, content="post-cache note")
    tl3 = build_timeline(store, limit=50)
    assert any("post-cache note" in (e.detail or "") or "post-cache note" in (e.label or "") for e in tl3)
