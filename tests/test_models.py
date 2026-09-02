"""Unit tests for CYB0X-S data models."""

from datetime import datetime

from cyb0x_s.models import (
    ChecklistStatus,
    CommandRecord,
    Credential,
    Evidence,
    Finding,
    Lead,
    Note,
    Service,
    ServiceStatus,
    Target,
    Workspace,
)


def test_workspace_model() -> None:
    ws = Workspace(name="Test Assessment", description="Assessment for client")
    assert ws.name == "Test Assessment"
    assert ws.description == "Assessment for client"
    assert isinstance(ws.created_at, datetime)


def test_target_model() -> None:
    target = Target(ip="10.10.10.20", hostname="target.local", os="Linux", notes="Web server")
    assert target.ip == "10.10.10.20"
    assert target.hostname == "target.local"
    assert target.os == "Linux"


def test_service_model() -> None:
    svc = Service(target_id=1, port=445, protocol="tcp", service="SMB", version="Samba 4.3")
    assert svc.port == 445
    assert svc.protocol == "tcp"
    assert svc.service == "SMB"
    assert svc.status == ServiceStatus.CHECKED


def test_credential_masking() -> None:
    cred = Credential(username="admin", secret="SecretPassword123!")
    assert cred.username == "admin"
    assert cred.secret == "SecretPassword123!"
    assert cred.masked_secret == "********"


def test_checklist_status_transitions() -> None:
    assert ChecklistStatus.from_str("checked") == ChecklistStatus.CHECKED
    assert ChecklistStatus.from_str("done") == ChecklistStatus.CHECKED
    assert ChecklistStatus.from_str("deferred") == ChecklistStatus.DEFERRED
    assert ChecklistStatus.from_str("dead-end") == ChecklistStatus.DEAD_END
    assert ChecklistStatus.from_str("todo") == ChecklistStatus.TODO

    # Cycle test
    st = ChecklistStatus.TODO
    st = st.next_state()
    assert st == ChecklistStatus.CHECKED
    st = st.next_state()
    assert st == ChecklistStatus.DEFERRED
    st = st.next_state()
    assert st == ChecklistStatus.DEAD_END
    st = st.next_state()
    assert st == ChecklistStatus.TODO


def test_finding_model() -> None:
    f = Finding(title="SMB anonymous access", notes="Backup share readable", severity="HIGH")
    assert f.title == "SMB anonymous access"
    assert f.severity == "HIGH"


def test_evidence_and_leads() -> None:
    ev = Evidence(path_or_ref="screen1.png", description="SMB listing")
    assert ev.path_or_ref == "screen1.png"
    assert ev.evidence_type == "screenshot"

    ld = Lead(title="Check port 8080")
    assert ld.status == "open"


def test_note_and_command() -> None:
    n = Note(content="Test note")
    assert n.content == "Test note"

    cmd = CommandRecord(command="smbclient -N -L //10.10.10.20/")
    assert "smbclient" in cmd.command
