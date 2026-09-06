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


def test_target_subnet_and_pivot(store: NotebookStore) -> None:
    """Test subnet assignment and pivot routing fields."""
    t = store.add_target("10.10.10.20")
    assert t.subnet == ""
    assert not t.is_pivot
    assert t.pivot_route == ""

    updated = store.update_target_details(
        t.id,
        subnet="10.10.10.0/24",
        is_pivot=True,
        pivot_route="192.168.1.0/24 via socks5:1080",
    )
    assert updated is not None
    assert updated.subnet == "10.10.10.0/24"
    assert updated.is_pivot
    assert updated.pivot_route == "192.168.1.0/24 via socks5:1080"


def test_cred_validations_persistence(store: NotebookStore) -> None:
    """Test saving and retrieving credential cell states."""
    t = store.add_target("10.10.10.30")
    s = store.add_service(target_id=t.id, port=22, service="ssh")
    c = store.add_credential(username="root", secret="toor", target_id=t.id)

    store.set_cred_validation(c.id, s.id, "✔ VALID")
    vals = store.get_cred_validations()
    assert vals.get((c.id, s.id)) == "✔ VALID"

    # Update state
    store.set_cred_validation(c.id, s.id, "👑 PWN3D")
    vals = store.get_cred_validations()
    assert vals.get((c.id, s.id)) == "👑 PWN3D"


def test_exam_proofs_crud_and_export(store: NotebookStore) -> None:
    """Test exam question proof recording, listing, and markdown export."""
    t = store.add_target("10.10.10.50")
    p1 = store.add_exam_proof(
        question_num="Q1",
        answer_proof="ProFTPD 1.3.5",
        category="VERSION",
        notes="Vulnerable to mod_copy",
        target_id=t.id,
    )
    assert p1.id is not None
    assert p1.question_num == "Q1"
    assert p1.answer_proof == "ProFTPD 1.3.5"

    p2 = store.add_exam_proof(
        question_num="Q14",
        answer_proof="aad3b435b51404eeaad3b435b51404ee:31d6cfe0d16ae931b73c59d7e0c089c0",
        category="HASH",
        notes="Administrator NTLM",
        target_id=t.id,
    )
    assert p2.id is not None

    proofs = store.list_exam_proofs()
    assert len(proofs) == 2

    export_md = store.export_exam_evidence_markdown()
    assert "Q1" in export_md
    assert "ProFTPD 1.3.5" in export_md
    assert "Q14" in export_md
    assert "Administrator NTLM" in export_md

    assert store.delete_exam_proof(p1.id)
    assert len(store.list_exam_proofs()) == 1


def test_pragma_user_version_migration(temp_db_path) -> None:
    """Verify that user_version is stamped to CURRENT_SCHEMA_VERSION and legacy DB is migrated."""
    import sqlite3

    from cyb0x_s.db.store import CURRENT_SCHEMA_VERSION

    # 1. New store should have PRAGMA user_version = CURRENT_SCHEMA_VERSION
    store = NotebookStore(db_path=temp_db_path)
    cur = store.conn.cursor()
    cur.execute("PRAGMA user_version")
    assert cur.fetchone()[0] == CURRENT_SCHEMA_VERSION
    store.close()

    # 2. Simulate opening a legacy database with user_version = 0
    raw_conn = sqlite3.connect(str(temp_db_path))
    raw_conn.execute("PRAGMA user_version = 0")
    raw_conn.commit()
    raw_conn.close()

    # Reopening store should run migration and stamp version back to CURRENT_SCHEMA_VERSION
    store2 = NotebookStore(db_path=temp_db_path)
    cur2 = store2.conn.cursor()
    cur2.execute("PRAGMA user_version")
    assert cur2.fetchone()[0] == CURRENT_SCHEMA_VERSION
    store2.close()


def test_lhost_lport_settings(store: NotebookStore) -> None:
    # Defaults
    assert store.get_lhost() == ""
    assert store.get_lport() == "4444"

    # Set custom
    store.set_lhost("10.10.14.47")
    store.set_lport(9001)

    assert store.get_lhost() == "10.10.14.47"
    assert store.get_lport() == "9001"


def test_detect_local_vpn_ip() -> None:
    from unittest.mock import MagicMock, patch

    from cyb0x_s.db.store import detect_local_vpn_ip

    # 1. Test VPN interface priority (tun0)
    mock_ip_out = (
        "1: lo    inet 127.0.0.1/8 scope host lo\\ valid_lft forever\n"
        "2: wlan0    inet 192.168.1.50/24 brd 192.168.1.255 scope global dynamic wlan0\n"
        "3: tun0    inet 10.10.14.47/23 scope global tun0\n"
    )
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=mock_ip_out)
        assert detect_local_vpn_ip() == "10.10.14.47"

    # 2. Test non-loopback fallback if no VPN interface
    mock_no_vpn = (
        "1: lo    inet 127.0.0.1/8 scope host lo\n"
        "2: eth0    inet 192.168.0.105/24 brd 192.168.0.255 scope global eth0\n"
    )
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=mock_no_vpn)
        assert detect_local_vpn_ip() == "192.168.0.105"


def test_update_credential_crack(store: NotebookStore) -> None:
    t = store.add_target("10.10.10.30")
    c = store.add_credential(
        username="admin",
        secret="aad3b435b51404eeaad3b435b51404ee:31d6cfe0d16ae931b73c59d7e0c089c0",
        target_id=t.id,
        status="captured",
    )
    assert c.id is not None
    assert c.status == "captured"

    # Operator cracks the hash
    updated = store.update_credential(c.id, secret="Password123", status="cracked", notes="Hashcat NTLM rockyou")
    assert updated is not None
    assert updated.id == c.id
    assert updated.secret == "Password123"
    assert updated.status == "cracked"
    assert updated.notes == "Hashcat NTLM rockyou"


def test_export_wordlists_to_loot(tmp_path) -> None:
    store = NotebookStore(":memory:")
    lab_dir = tmp_path / "lab_export"
    ws, _ = store.init_workspace_directory("lab_export", target_dir=lab_dir)
    t = store.add_target("10.10.10.40", workspace_id=ws.id)

    store.add_credential(username="admin", secret="Summer2023!", target_id=t.id)
    store.add_credential(username="root", secret="toor", target_id=t.id)
    store.add_credential(username="admin", secret="Summer2023!", target_id=t.id)  # duplicate to test dedup
    store.add_credential(username="svc_backup", secret="Backup2022", target_id=t.id)

    u_file, p_file = store.export_wordlists_to_loot(workspace_id=ws.id)
    assert u_file.is_file()
    assert p_file.is_file()
    assert u_file == lab_dir / "loot" / "users.txt"
    assert p_file == lab_dir / "loot" / "passwords.txt"

    users = u_file.read_text(encoding="utf-8").strip().splitlines()
    passwords = p_file.read_text(encoding="utf-8").strip().splitlines()

    assert users == ["admin", "root", "svc_backup"]
    assert sorted(passwords) == ["Backup2022", "Summer2023!", "toor"]


def test_workspace_scaffolding_and_root_path(tmp_path) -> None:
    store = NotebookStore(":memory:")
    lab_dir = tmp_path / "lab01"
    ws, base = store.init_workspace_directory("lab01", target_dir=lab_dir, description="Test Lab")

    assert ws.name == "lab01"
    assert ws.root_path == str(lab_dir.resolve())
    assert (lab_dir / ".cyb0x-s" / "notebook.db").is_file()
    assert (lab_dir / "scans").is_dir()
    assert (lab_dir / "enum").is_dir()
    assert (lab_dir / "screenshots").is_dir()
    assert (lab_dir / "notes").is_dir()
    assert (lab_dir / "loot").is_dir()
    assert (lab_dir / "findings.md").is_file()


def test_evidence_stores_strictly_relative_paths(tmp_path) -> None:
    lab_dir = tmp_path / "lab02"
    local_db = lab_dir / ".cyb0x-s" / "notebook.db"
    store = NotebookStore(local_db)
    ws = store.get_active_workspace()
    assert ws.root_path == str(lab_dir.resolve())

    # Create dummy scan and screenshot inside the lab
    scan_file = lab_dir / "scans" / "nmap-full.xml"
    scan_file.parent.mkdir(parents=True, exist_ok=True)
    scan_file.write_text("<nmaprun></nmaprun>", encoding="utf-8")

    # Add evidence using absolute path
    ev_scan = store.add_evidence(
        path_or_ref=str(scan_file.resolve()),
        evidence_type="scan",
        description="Full TCP Scan",
    )

    # Must be stored as relative path in database!
    assert ev_scan.path_or_ref == "scans/nmap-full.xml"

    # Resolving evidence path yields full absolute path in current workspace
    resolved = store.resolve_evidence_path(ev_scan)
    assert resolved == scan_file.resolve()


def test_portable_lab_directory_relocation(tmp_path) -> None:
    # 1. Initialize lab in dir A
    dir_a = tmp_path / "original_lab"
    local_db_a = dir_a / ".cyb0x-s" / "notebook.db"
    store_a = NotebookStore(local_db_a)

    proof_file = dir_a / "screenshots" / "proof.png"
    proof_file.parent.mkdir(parents=True, exist_ok=True)
    proof_file.write_bytes(b"\x89PNG\r\n\x1a\n")

    ev = store_a.add_evidence(str(proof_file.resolve()), evidence_type="screenshot")
    assert ev.path_or_ref == "screenshots/proof.png"
    store_a.close()

    # 2. Move lab directory to dir B (simulating USB / machine transfer)
    import shutil
    dir_b = tmp_path / "moved_lab"
    shutil.move(dir_a, dir_b)

    # 3. Open database in new location
    local_db_b = dir_b / ".cyb0x-s" / "notebook.db"
    store_b = NotebookStore(local_db_b)
    ws_b = store_b.get_active_workspace()

    # Workspace root path dynamically detected and updated
    assert ws_b.root_path == str(dir_b.resolve())

    # Evidence path still stored as relative
    ev_b = store_b.get_evidence(ev.id)
    assert ev_b is not None
    assert ev_b.path_or_ref == "screenshots/proof.png"

    # Resolves to the new location without any broken path!
    resolved_b = store_b.resolve_evidence_path(ev_b)
    assert resolved_b == (dir_b / "screenshots" / "proof.png").resolve()
    assert resolved_b.is_file()
    store_b.close()



