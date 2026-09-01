"""Tests for Markdown, JSON, and TXT exporters and JSON importer."""

import json
from cyb0x_s.db.store import NotebookStore
from cyb0x_s.export import export_json, export_markdown, export_txt, import_json
from cyb0x_s.models import ChecklistStatus, ServiceStatus


def test_export_markdown_format(store: NotebookStore) -> None:
    t = store.add_target("10.10.10.20", hostname="target.local", os_name="Linux")
    store.add_service(target_id=t.id, port=22, protocol="tcp", service="SSH")
    store.add_service(target_id=t.id, port=80, protocol="tcp", service="HTTP")
    store.add_service(target_id=t.id, port=445, protocol="tcp", service="SMB")

    store.add_finding(title="SMB backup share accessible", target_id=t.id)
    store.add_finding(title="HTTP redirects to /login", target_id=t.id)

    store.add_credential(username="admin", secret="Secret123", target_id=t.id)

    store.add_checklist_item(title="TCP enumeration", target_id=t.id, status=ChecklistStatus.CHECKED)
    store.add_checklist_item(title="HTTP enumeration", target_id=t.id, status=ChecklistStatus.CHECKED)
    store.add_checklist_item(title="SMB enumeration", target_id=t.id, status=ChecklistStatus.TODO)

    store.add_note("backup share contains archive.zip", target_id=t.id)

    md = export_markdown(store, reveal_creds=False)

    # Check key sections from specification
    assert "# Target: 10.10.10.20" in md
    assert "## Services" in md
    assert "22/tcp — SSH" in md
    assert "80/tcp — HTTP" in md
    assert "445/tcp — SMB" in md
    assert "## Findings" in md
    assert "SMB backup share accessible" in md
    assert "HTTP redirects to /login" in md
    assert "## Credentials" in md
    assert "admin : ********" in md
    assert "## Checklist" in md
    assert "[x] TCP enumeration" in md
    assert "[x] HTTP enumeration" in md
    assert "[ ] SMB enumeration" in md
    assert "## Notes" in md
    assert "backup share contains archive.zip" in md


def test_export_markdown_reveal_creds(store: NotebookStore) -> None:
    t = store.add_target("10.10.10.20")
    store.add_credential(username="admin", secret="SecretPassword!", target_id=t.id)

    md_masked = export_markdown(store, reveal_creds=False)
    assert "admin : ********" in md_masked
    assert "SecretPassword!" not in md_masked

    md_revealed = export_markdown(store, reveal_creds=True)
    assert "admin : SecretPassword!" in md_revealed


def test_export_txt(store: NotebookStore) -> None:
    t = store.add_target("10.10.10.20")
    store.add_service(target_id=t.id, port=80, service="HTTP")
    store.add_note("Test TXT note", target_id=t.id)

    txt = export_txt(store)
    assert "CYB0X-S SAFE FIELD NOTEBOOK" in txt
    assert "TARGET: 10.10.10.20" in txt
    assert "Test TXT note" in txt


def test_json_export_and_import_roundtrip(store: NotebookStore, temp_db_path) -> None:
    t = store.add_target("10.10.10.50", hostname="roundtrip.local", os_name="Windows")
    store.add_service(target_id=t.id, port=3389, service="RDP", status=ServiceStatus.CHECKED)
    store.add_finding(title="RDP NLA Disabled", target_id=t.id, severity="MEDIUM")
    store.add_credential(username="operator", secret="Password2024!", target_id=t.id)
    store.add_checklist_item(title="Audit RDP certificates", target_id=t.id)
    store.add_evidence("rdp_screenshot.png", target_id=t.id)
    store.add_note("RDP login banner shows corporate warning", target_id=t.id)

    # Export JSON
    json_str = export_json(store)
    data = json.loads(json_str)
    assert data["format"] == "cyb0x-s-backup"
    assert len(data["targets"]) == 1

    # Import into a new fresh store
    fresh_store = NotebookStore(":memory:")
    imported_ws = import_json(fresh_store, json_str, workspace_name="Imported-WS")
    assert imported_ws.name == "Imported-WS"

    # Verify entities imported correctly
    imported_targets = fresh_store.list_targets(workspace_id=imported_ws.id)
    assert len(imported_targets) == 1
    it = imported_targets[0]
    assert it.ip == "10.10.10.50"

    services = fresh_store.list_services(target_id=it.id)
    assert len(services) == 1
    assert services[0].service == "RDP"

    findings = fresh_store.list_findings(target_id=it.id)
    assert len(findings) == 1
    assert findings[0].title == "RDP NLA Disabled"
    assert findings[0].severity == "MEDIUM"

    creds = fresh_store.list_credentials(target_id=it.id)
    assert len(creds) == 1
    assert creds[0].username == "operator"
    assert creds[0].secret == "Password2024!"

    fresh_store.close()
