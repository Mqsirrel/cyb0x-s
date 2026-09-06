"""Tests for CYB0X-S offline scan ingestion, evidence preservation, and deduplication."""

from pathlib import Path

from click.testing import CliRunner

from cyb0x_s.cli import cli
from cyb0x_s.db.store import NotebookStore
from cyb0x_s.models import ServiceStatus
from cyb0x_s.scan_import import (
    check_scan_already_imported,
    commit_scan_results,
    commit_web_enum_results,
    inspect_scan_file,
)

SAMPLE_NMAP_XML = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE nmaprun>
<nmaprun scanner="nmap" args="nmap -sV -oX out.xml 10.10.10.15">
<host starttime="1600000000" endtime="1600000010">
    <status state="up" reason="user-set"/>
    <address addr="10.10.10.15" addrtype="ipv4"/>
    <hostnames>
        <hostname name="target.local" type="user"/>
    </hostnames>
    <ports>
        <port protocol="tcp" portid="22">
            <state state="open" reason="syn-ack"/>
            <service name="ssh" product="OpenSSH" version="8.2p1 Ubuntu 4ubuntu0.5"/>
        </port>
        <port protocol="tcp" portid="80">
            <state state="open" reason="syn-ack"/>
            <service name="http" product="Apache httpd" version="2.4.41"/>
        </port>
        <port protocol="tcp" portid="445">
            <state state="filtered" reason="no-response"/>
        </port>
    </ports>
    <os>
        <osmatch name="Linux 5.4" accuracy="95"/>
    </os>
</host>
</nmaprun>
"""

SAMPLE_TRUNCATED_XML = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE nmaprun>
<nmaprun scanner="nmap" args="nmap -sV -oX out.xml 10.10.10.25">
<host starttime="1600000000">
    <status state="up"/>
    <address addr="10.10.10.25" addrtype="ipv4"/>
    <hostnames><hostname name="dev.corp"/></hostnames>
    <ports>
        <port protocol="tcp" portid="3306">
            <state state="open"/>
            <service name="mysql" product="MySQL" version="8.0.28"/>
        </port>
    <!-- Interrupted by Ctrl+C here: closing tags missing -->
"""

SAMPLE_NMAP_TEXT = """# Nmap 7.92 scan initiated Sun Sep 06 10:00:00 2026 as: nmap -sV -oN scan.nmap 10.10.10.35
Nmap scan report for web.local (10.10.10.35)
Host is up (0.025s latency).
PORT    STATE SERVICE VERSION
21/tcp  open  ftp     vsftpd 3.0.3
8080/tcp open  http    Apache Tomcat 9.0.30
Service Info: OS: Linux; CPE: cpe:/o:linux:linux_kernel
"""


def test_inspect_scan_file_xml(tmp_path: Path) -> None:
    xml_file = tmp_path / "scan.xml"
    xml_file.write_text(SAMPLE_NMAP_XML, encoding="utf-8")

    results = inspect_scan_file(xml_file)
    assert len(results) == 1
    target = results[0]
    assert target["ip"] == "10.10.10.15"
    assert target["hostname"] == "target.local"
    assert target["os"] == "Linux 5.4"
    assert len(target["services"]) == 2

    s22 = next(s for s in target["services"] if s["port"] == 22)
    assert s22["service"] == "ssh"
    assert "OpenSSH" in s22["version"]

    s80 = next(s for s in target["services"] if s["port"] == 80)
    assert s80["service"] == "http"
    assert "Apache" in s80["version"]


def test_inspect_scan_file_text(tmp_path: Path) -> None:
    txt_file = tmp_path / "scan.nmap"
    txt_file.write_text(SAMPLE_NMAP_TEXT, encoding="utf-8")

    results = inspect_scan_file(txt_file)
    assert len(results) == 1
    target = results[0]
    assert target["ip"] == "10.10.10.35"
    assert target["hostname"] == "web.local"
    assert len(target["services"]) == 2
    assert any(s["port"] == 21 and s["service"] == "ftp" for s in target["services"])
    assert any(s["port"] == 8080 and s["service"] == "http" for s in target["services"])


def test_inspect_salvages_truncated_xml(tmp_path: Path) -> None:
    trunc_file = tmp_path / "interrupted.xml"
    trunc_file.write_text(SAMPLE_TRUNCATED_XML, encoding="utf-8")

    results = inspect_scan_file(trunc_file)
    assert len(results) == 1
    target = results[0]
    assert target["ip"] == "10.10.10.25"
    assert target["hostname"] == "dev.corp"
    assert len(target["services"]) == 1
    assert target["services"][0]["port"] == 3306
    assert "MySQL" in target["services"][0]["version"]


def test_commit_scan_results_workflow(tmp_path: Path) -> None:
    store = NotebookStore(":memory:")
    lab_dir = tmp_path / "lab01"
    ws, _ = store.init_workspace_directory("lab01", target_dir=lab_dir)

    scan_file = tmp_path / "external_scans" / "initial_tcp.xml"
    scan_file.parent.mkdir(parents=True, exist_ok=True)
    scan_file.write_text(SAMPLE_NMAP_XML, encoding="utf-8")

    # Inspect
    targets_data = inspect_scan_file(scan_file)

    # Commit
    summary = commit_scan_results(
        store=store,
        file_path=scan_file,
        targets_data=targets_data,
        workspace_id=ws.id,
        copy_to_scans=True,
    )

    assert summary["targets_count"] == 1
    assert summary["services_count"] == 2
    assert summary["evidence_path"] == "scans/initial_tcp.xml"

    # Verify file was copied to workspace scans/ directory
    archived_file = lab_dir / "scans" / "initial_tcp.xml"
    assert archived_file.is_file()
    assert archived_file.read_text(encoding="utf-8") == SAMPLE_NMAP_XML

    # Verify target and services in database
    target = store.get_target_by_ip("10.10.10.15", workspace_id=ws.id)
    assert target is not None
    assert target.hostname == "target.local"
    assert target.os == "Linux 5.4"

    services = store.list_services(target_id=target.id)
    assert len(services) == 2
    ports = {s.port for s in services}
    assert ports == {22, 80}

    # Verify evidence was recorded
    evidences = store.list_evidence(target_id=target.id)
    assert len(evidences) == 1
    assert evidences[0].evidence_type == "scan"
    assert evidences[0].path_or_ref == "scans/initial_tcp.xml"

    # Verify deduplication record exists
    existing = check_scan_already_imported(store, scan_file, workspace_id=ws.id)
    assert existing is not None
    assert existing.file_hash == summary["file_hash"]


def test_service_status_preserved_on_rescan(tmp_path: Path) -> None:
    store = NotebookStore(":memory:")
    lab_dir = tmp_path / "lab_preserve"
    ws, _ = store.init_workspace_directory("test_preserve", target_dir=lab_dir)

    # Initial scan
    scan1 = tmp_path / "scan1.xml"
    scan1.write_text(SAMPLE_NMAP_XML, encoding="utf-8")
    commit_scan_results(store, scan1, inspect_scan_file(scan1), workspace_id=ws.id)

    target = store.get_target_by_ip("10.10.10.15", workspace_id=ws.id)
    assert target is not None

    # Operator marks port 80 as DEFERRED
    s80 = next(s for s in store.list_services(target_id=target.id) if s.port == 80)
    store.update_service_status(s80.id, ServiceStatus.DEFERRED)

    # Second scan (e.g. all-ports or deeper scan)
    commit_scan_results(
        store,
        scan1,
        inspect_scan_file(scan1),
        workspace_id=ws.id,
        preserve_status=True,
    )

    # Check port 80 status is still DEFERRED
    updated_s80 = store.get_service(s80.id)
    assert updated_s80.status == ServiceStatus.DEFERRED


def test_cli_import_apply(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    db_file = tmp_path / "test.db"
    scan_file = tmp_path / "quick.nmap"
    scan_file.write_text(SAMPLE_NMAP_TEXT, encoding="utf-8")

    res = runner.invoke(cli, ["--db", str(db_file), "import", str(scan_file), "--apply"])
    assert res.exit_code == 0
    assert "Scan imported successfully" in res.output
    assert "Targets committed: 1" in res.output
    assert "Services committed: 2" in res.output


def test_cli_import_interactive_abort(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    db_file = tmp_path / "test.db"
    scan_file = tmp_path / "quick.nmap"
    scan_file.write_text(SAMPLE_NMAP_TEXT, encoding="utf-8")

    # Decline confirmation
    res = runner.invoke(cli, ["--db", str(db_file), "import", str(scan_file)], input="n\n")
    assert res.exit_code == 0
    assert "Scan Review:" in res.output
    assert "Import aborted by operator." in res.output


def test_commit_web_enum_results_workflow(tmp_path: Path) -> None:
    store = NotebookStore(":memory:")
    lab_dir = tmp_path / "lab02"
    ws, _ = store.init_workspace_directory("lab02", target_dir=lab_dir)
    target = store.add_target("10.10.10.20", hostname="web.lab", workspace_id=ws.id)

    enum_file = tmp_path / "external" / "ffuf_output.json"
    enum_file.parent.mkdir(parents=True, exist_ok=True)
    enum_file.write_text('{"results": [{"input": {"FUZZ": "admin"}, "status": 200, "length": 512}]}', encoding="utf-8")

    endpoints = [
        {"path": "/admin", "status": 200, "size": 512, "tool": "ffuf", "redirect": ""},
        {"path": "/login", "status": 302, "size": 0, "tool": "ffuf", "redirect": "/dashboard"},
    ]

    res = commit_web_enum_results(
        store=store,
        file_path=enum_file,
        endpoints=endpoints,
        target_id=target.id,
        workspace_id=ws.id,
        copy_to_enum=True,
    )

    assert res["workspace_id"] == ws.id
    assert res["target_id"] == target.id
    assert res["endpoints_count"] == 2
    assert res["evidence_path"] == "enum/ffuf_output.json"

    # Verify archived file in workspace enum/
    archived = lab_dir / "enum" / "ffuf_output.json"
    assert archived.is_file()

    # Verify leads created in store
    leads = store.list_leads(target_id=target.id)
    assert len(leads) == 2
    lead_titles = {ld.title for ld in leads}
    assert "200 /admin" in lead_titles
    assert "302 /login" in lead_titles

    # Verify evidence created
    evidences = store.list_evidence(target_id=target.id)
    assert len(evidences) == 1
    assert evidences[0].evidence_type == "enum"
    assert evidences[0].path_or_ref == "enum/ffuf_output.json"

    # Verify deduplication record exists
    imports = store.list_scan_imports(workspace_id=ws.id, target_id=target.id)
    assert len(imports) == 1
    assert imports[0].scan_type == "web_enum"

