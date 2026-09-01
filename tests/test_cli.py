"""Integration tests for CYB0X-S CLI fast-capture commands."""

from pathlib import Path
from click.testing import CliRunner

from cyb0x_s.cli import cli
from cyb0x_s.db.store import NotebookStore


def test_cli_target_capture(cli_runner: CliRunner, temp_db_path: Path) -> None:
    res = cli_runner.invoke(cli, ["--db", str(temp_db_path), "target", "10.10.10.20", "--hostname", "target.local", "--os", "Linux"])
    assert res.exit_code == 0
    assert "Target recorded: 10.10.10.20" in res.output

    # Verify in DB
    s = NotebookStore(temp_db_path)
    t = s.get_target_by_ip("10.10.10.20")
    assert t is not None
    assert t.hostname == "target.local"
    s.close()


def test_cli_service_capture(cli_runner: CliRunner, temp_db_path: Path) -> None:
    # Setup target first
    cli_runner.invoke(cli, ["--db", str(temp_db_path), "target", "10.10.10.20"])

    # Record service with full syntax: cyb0x-s service 10.10.10.20 445/tcp SMB --version "Samba 4.3"
    res = cli_runner.invoke(
        cli,
        ["--db", str(temp_db_path), "service", "10.10.10.20", "445/tcp", "SMB", "--version", "Samba 4.3"],
    )
    assert res.exit_code == 0
    assert "Service recorded: 10.10.10.20:445/tcp SMB" in res.output

    s = NotebookStore(temp_db_path)
    t = s.get_target_by_ip("10.10.10.20")
    services = s.list_services(target_id=t.id)
    assert len(services) == 1
    assert services[0].port == 445
    assert services[0].version == "Samba 4.3"
    s.close()


def test_cli_note_capture(cli_runner: CliRunner, temp_db_path: Path) -> None:
    cli_runner.invoke(cli, ["--db", str(temp_db_path), "target", "10.10.10.20"])

    res = cli_runner.invoke(
        cli,
        ["--db", str(temp_db_path), "note", "8080 appears to be Jenkins"],
    )
    assert res.exit_code == 0
    assert "Note recorded" in res.output

    s = NotebookStore(temp_db_path)
    notes = s.list_notes()
    assert len(notes) == 1
    assert notes[0].content == "8080 appears to be Jenkins"
    s.close()


def test_cli_finding_capture(cli_runner: CliRunner, temp_db_path: Path) -> None:
    cli_runner.invoke(cli, ["--db", str(temp_db_path), "target", "10.10.10.20"])

    res = cli_runner.invoke(
        cli,
        ["--db", str(temp_db_path), "finding", "SMB backup share accessible", "--severity", "HIGH"],
    )
    assert res.exit_code == 0
    assert "Finding recorded" in res.output

    s = NotebookStore(temp_db_path)
    findings = s.list_findings()
    assert len(findings) == 1
    assert findings[0].title == "SMB backup share accessible"
    assert findings[0].severity == "HIGH"
    s.close()


def test_cli_cred_capture(cli_runner: CliRunner, temp_db_path: Path) -> None:
    cli_runner.invoke(cli, ["--db", str(temp_db_path), "target", "10.10.10.20"])

    res = cli_runner.invoke(
        cli,
        ["--db", str(temp_db_path), "cred", "admin:password123", "--source", "backup.zip"],
    )
    assert res.exit_code == 0
    assert "Credential saved" in res.output
    assert "********" in res.output
    # Secret must be masked in output
    assert "password123" not in res.output

    s = NotebookStore(temp_db_path)
    creds = s.list_credentials()
    assert len(creds) == 1
    assert creds[0].username == "admin"
    assert creds[0].secret == "password123"
    s.close()


def test_cli_checklist_commands(cli_runner: CliRunner, temp_db_path: Path) -> None:
    cli_runner.invoke(cli, ["--db", str(temp_db_path), "target", "10.10.10.20"])

    # Template
    res_tmpl = cli_runner.invoke(cli, ["--db", str(temp_db_path), "checklist", "template", "smb"])
    assert res_tmpl.exit_code == 0
    assert "Applied static template 'smb'" in res_tmpl.output

    # Check off
    res_check = cli_runner.invoke(cli, ["--db", str(temp_db_path), "checklist", "check", "null session"])
    assert res_check.exit_code == 0
    assert "Checked:" in res_check.output

    # List
    res_list = cli_runner.invoke(cli, ["--db", str(temp_db_path), "checklist", "list"])
    assert res_list.exit_code == 0
    assert "CHECKED" in res_list.output


def test_cli_search_and_export(cli_runner: CliRunner, temp_db_path: Path) -> None:
    cli_runner.invoke(cli, ["--db", str(temp_db_path), "target", "10.10.10.20"])
    cli_runner.invoke(cli, ["--db", str(temp_db_path), "note", "archive.zip in backup share"])

    # Search
    res_search = cli_runner.invoke(cli, ["--db", str(temp_db_path), "search", "archive"])
    assert res_search.exit_code == 0
    assert "archive.zip" in res_search.output

    # Export markdown
    res_export = cli_runner.invoke(cli, ["--db", str(temp_db_path), "export", "--format", "md"])
    assert res_export.exit_code == 0
    assert "# Target: 10.10.10.20" in res_export.output
    assert "archive.zip in backup share" in res_export.output
