"""Tests for SQLite database store operations."""

from cyb0x_s.db.store import NotebookStore
from cyb0x_s.models import ChecklistStatus, ServiceStatus


def test_workspace_crud(store: NotebookStore) -> None:
    ws = store.get_or_create_workspace("Lab-A", description="Lab machine A")
    assert ws.id is not None
    assert ws.name == "Lab-A"

    workspaces = store.list_workspaces()
    assert len(workspaces) >= 2  # default + Lab-A

    store.set_active_workspace(ws.id)
    active = store.get_active_workspace()
    assert active.id == ws.id
    assert active.name == "Lab-A"


def test_target_crud(store: NotebookStore) -> None:
    t = store.add_target(ip="10.10.10.20", hostname="target.local", os_name="Linux", notes="Primary DC")
    assert t.id is not None
    assert t.ip == "10.10.10.20"
    assert t.hostname == "target.local"
    assert t.os == "Linux"

    # Fetch
    fetched = store.get_target(t.id)
    assert fetched is not None
    assert fetched.ip == "10.10.10.20"

    # Fetch by IP
    by_ip = store.get_target_by_ip("10.10.10.20")
    assert by_ip is not None
    assert by_ip.id == t.id

    # Active target
    active = store.get_active_target()
    assert active is not None
    assert active.id == t.id

    # Updating target
    updated = store.add_target(ip="10.10.10.20", hostname="dc01.local")
    assert updated.hostname == "dc01.local"
    assert updated.id == t.id


def test_service_crud(store: NotebookStore) -> None:
    t = store.add_target("10.10.10.20")
    s = store.add_service(
        target_id=t.id,
        port=445,
        protocol="tcp",
        service="SMB",
        version="Samba 4.3",
        status=ServiceStatus.CHECKED,
        notes="Anonymous enabled",
    )
    assert s.id is not None
    assert s.port == 445
    assert s.service == "SMB"

    services = store.list_services(target_id=t.id)
    assert len(services) == 1
    assert services[0].version == "Samba 4.3"

    # Delete service
    deleted = store.delete_service(s.id)
    assert deleted is True
    assert len(store.list_services(target_id=t.id)) == 0


def test_finding_crud(store: NotebookStore) -> None:
    t = store.add_target("10.10.10.20")
    f = store.add_finding(
        title="Anonymous SMB Share",
        target_id=t.id,
        description="Share 'backup' is readable",
        notes="Contains zip file",
        severity="HIGH",
    )
    assert f.id is not None
    assert f.severity == "HIGH"

    findings = store.list_findings(target_id=t.id)
    assert len(findings) == 1
    assert findings[0].title == "Anonymous SMB Share"

    store.delete_finding(f.id)
    assert len(store.list_findings(target_id=t.id)) == 0


def test_credential_crud(store: NotebookStore) -> None:
    t = store.add_target("10.10.10.20")
    c = store.add_credential(
        username="admin",
        secret="Summer2024!Secure",
        source="backup.zip",
        target_id=t.id,
        service_scope="SMB",
        status="valid",
    )
    assert c.id is not None
    assert c.username == "admin"
    assert c.secret == "Summer2024!Secure"
    assert c.masked_secret == "********"

    creds = store.list_credentials(target_id=t.id)
    assert len(creds) == 1
    assert creds[0].username == "admin"


def test_checklist_crud_and_cycle(store: NotebookStore) -> None:
    t = store.add_target("10.10.10.20")
    item = store.add_checklist_item(
        title="Check SMB null session",
        category="SMB",
        target_id=t.id,
        status=ChecklistStatus.TODO,
    )
    assert item.status == ChecklistStatus.TODO

    # Cycle status: TODO -> CHECKED
    c1 = store.cycle_checklist_status(item.id)
    assert c1 is not None
    assert c1.status == ChecklistStatus.CHECKED

    # Cycle status: CHECKED -> DEFERRED
    c2 = store.cycle_checklist_status(item.id)
    assert c2 is not None
    assert c2.status == ChecklistStatus.DEFERRED

    # Cycle status: DEFERRED -> DEAD-END
    c3 = store.cycle_checklist_status(item.id)
    assert c3 is not None
    assert c3.status == ChecklistStatus.DEAD_END

    # Cycle status: DEAD-END -> TODO
    c4 = store.cycle_checklist_status(item.id)
    assert c4 is not None
    assert c4.status == ChecklistStatus.TODO


def test_notes_evidence_leads_commands(store: NotebookStore) -> None:
    t = store.add_target("10.10.10.20")

    # Note
    n = store.add_note("Test note", target_id=t.id)
    assert n.content == "Test note"
    assert len(store.list_notes(target_id=t.id)) == 1

    # Evidence
    ev = store.add_evidence("screenshot-01.png", target_id=t.id, description="Login page")
    assert ev.path_or_ref == "screenshot-01.png"
    assert len(store.list_evidence(target_id=t.id)) == 1

    # Lead
    ld = store.add_lead("Inspect Jenkins console", target_id=t.id, notes="Port 8080")
    assert ld.title == "Inspect Jenkins console"
    assert len(store.list_leads(target_id=t.id)) == 1

    # Command
    cmd = store.add_command("smbclient -L //10.10.10.20/", target_id=t.id)
    assert "smbclient" in cmd.command
    assert len(store.list_commands(target_id=t.id)) == 1


def test_cascade_delete_target(store: NotebookStore) -> None:
    t = store.add_target("10.10.10.30")
    store.add_service(target_id=t.id, port=80, service="HTTP")
    store.add_finding(title="XSS", target_id=t.id)
    store.add_credential(username="user", secret="pass", target_id=t.id)
    store.add_checklist_item(title="Item 1", target_id=t.id)
    store.add_note("Note 1", target_id=t.id)

    # Delete target
    deleted = store.delete_target(t.id)
    assert deleted is True

    # Check child records removed by CASCADE
    assert len(store.list_services(target_id=t.id)) == 0
    assert len(store.list_findings(target_id=t.id)) == 0
    assert len(store.list_credentials(target_id=t.id)) == 0
    assert len(store.list_checklist_items(target_id=t.id)) == 0
    assert len(store.list_notes(target_id=t.id)) == 0


def test_get_target_counts(store: NotebookStore) -> None:
    """Test fast single-query target counts aggregation."""
    # None returns zeros
    assert store.get_target_counts(None) == {
        "ports": 0, "creds": 0, "vulns": 0, "notes": 0, "dead_ends": 0, "failures": 0
    }

    t = store.add_target("10.10.10.40")
    store.add_service(target_id=t.id, port=22, service="ssh")
    store.add_service(target_id=t.id, port=80, service="http")
    store.add_credential(username="admin", secret="pass", target_id=t.id)
    store.add_finding(title="RCE", target_id=t.id)
    store.add_note("Discovered vhost", target_id=t.id)
    from cyb0x_s.models import ChecklistStatus
    store.add_checklist_item(title="Task 1", target_id=t.id, status=ChecklistStatus.DEAD_END)
    store.add_failure_log(target_id=t.id, where_stuck="Port 80")

    counts = store.get_target_counts(t.id)
    assert counts["ports"] == 2
    assert counts["creds"] == 1
    assert counts["vulns"] == 1
    assert counts["notes"] == 1
    assert counts["dead_ends"] == 1
    assert counts["failures"] == 1

