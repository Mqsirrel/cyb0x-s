"""Integration tests for GLACIS CLI fast-capture commands."""

from pathlib import Path

from click.testing import CliRunner

from glacis.cli import cli
from glacis.db.store import NotebookStore


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

    # Record service with full syntax: glacis service 10.10.10.20 445/tcp SMB --version "Samba 4.3"
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


def test_cli_flags_foothold_privesc_stuck(cli_runner: CliRunner, temp_db_path: Path) -> None:
    cli_runner.invoke(cli, ["--db", str(temp_db_path), "target", "10.10.10.30"])

    # User flag
    res_u = cli_runner.invoke(cli, ["--db", str(temp_db_path), "flag", "user", "eJPT{user_flag_123}"])
    assert res_u.exit_code == 0
    assert "Recorded user flag on 10.10.10.30" in res_u.output

    # Root flag
    res_r = cli_runner.invoke(cli, ["--db", str(temp_db_path), "flag", "root", "eJPT{root_flag_456}"])
    assert res_r.exit_code == 0
    assert "Recorded root flag on 10.10.10.30" in res_r.output

    # Foothold
    res_fh = cli_runner.invoke(
        cli,
        ["--db", str(temp_db_path), "foothold", "--vuln", "Tomcat Manager", "--cmd", "python3 exploit.py", "--context", "tomcat @ /opt/tomcat"],
    )
    assert res_fh.exit_code == 0
    assert "Recorded initial foothold on 10.10.10.30" in res_fh.output

    # PrivEsc
    res_pe = cli_runner.invoke(
        cli,
        ["--db", str(temp_db_path), "privesc", "--vector", "sudo find", "--proof", "whoami && id && ip a"],
    )
    assert res_pe.exit_code == 0
    assert "Recorded privilege escalation on 10.10.10.30" in res_pe.output

    # Stuck / Failure log
    res_st = cli_runner.invoke(
        cli,
        ["--db", str(temp_db_path), "stuck", "--stuck", "Spent 45 mins fuzzing /api", "--clue", "Found credentials in port 445 SMB share", "--rule", "Check SMB shares first"],
    )
    assert res_st.exit_code == 0
    assert "Recorded breakthrough & rabbit hole analysis entry" in res_st.output

    # Verify export includes all Notion-aligned sections
    res_export = cli_runner.invoke(cli, ["--db", str(temp_db_path), "export", "--format", "md"])
    assert res_export.exit_code == 0
    assert "## 03 — Exploitation & Initial Foothold" in res_export.output
    assert "Tomcat Manager" in res_export.output
    assert "## 04 — Privilege Escalation" in res_export.output
    assert "sudo find" in res_export.output
    assert "## 05 — Captured Flags & Evidence" in res_export.output
    assert "eJPT{user_flag_123}" in res_export.output
    assert "eJPT{root_flag_456}" in res_export.output
    assert "## 🧠 06 — Rabbit Hole & Breakthrough Analysis (Failure Log)" in res_export.output
    assert "Spent 45 mins fuzzing /api" in res_export.output
    assert "Found credentials in port 445 SMB share" in res_export.output
    assert "Check SMB shares first" in res_export.output


def test_cli_ref_command(cli_runner: CliRunner, temp_db_path: Path) -> None:
    # Test searching reference for winrm with target IP
    cli_runner.invoke(cli, ["--db", str(temp_db_path), "target", "10.10.10.40"])

    res = cli_runner.invoke(cli, ["--db", str(temp_db_path), "ref", "winrm"])
    assert res.exit_code == 0
    assert "evil-winrm" in res.output
    assert "10.10.10.40" in res.output

def test_cli_theme_option(cli_runner: CliRunner) -> None:
    res = cli_runner.invoke(cli, ["--help"])
    assert res.exit_code == 0
    assert "--theme" in res.output or "-t" in res.output

    res_tui = cli_runner.invoke(cli, ["tui", "--help"])
    assert res_tui.exit_code == 0
    assert "--theme" in res_tui.output





# -----------------------------------------------------------------------------
# Pulse & safety-net commands (v0.2.0)
# -----------------------------------------------------------------------------

def test_cli_stats_command(cli_runner: CliRunner, temp_db_path: Path) -> None:
    cli_runner.invoke(cli, ["--db", str(temp_db_path), "target", "10.10.10.20", "--hostname", "dc01"])
    cli_runner.invoke(cli, ["--db", str(temp_db_path), "service", "10.10.10.20", "445/tcp", "SMB"])
    cli_runner.invoke(cli, ["--db", str(temp_db_path), "finding", "anon smb", "--severity", "HIGH", "--target", "10.10.10.20"])

    res = cli_runner.invoke(cli, ["--db", str(temp_db_path), "stats"], env={"COLUMNS": "220", "LINES": "60"})
    assert res.exit_code == 0
    assert "PULSE" in res.output
    assert "Target Scorecards" in res.output
    assert "HIGH" in res.output


def test_cli_timeline_command(cli_runner: CliRunner, temp_db_path: Path) -> None:
    cli_runner.invoke(cli, ["--db", str(temp_db_path), "target", "10.10.10.20"])
    cli_runner.invoke(cli, ["--db", str(temp_db_path), "note", "first contact", "--target", "10.10.10.20"])

    res = cli_runner.invoke(cli, ["--db", str(temp_db_path), "timeline"], env={"COLUMNS": "220", "LINES": "60"})
    assert res.exit_code == 0
    assert "Timeline" in res.output
    assert "Note" in res.output
    assert "10.10.10.20" in res.output


def test_cli_backup_and_backups_commands(cli_runner: CliRunner, temp_db_path: Path, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    cli_runner.invoke(cli, ["--db", str(temp_db_path), "target", "10.10.10.20"])

    res = cli_runner.invoke(cli, ["--db", str(temp_db_path), "backup", "--label", "test"])
    assert res.exit_code == 0
    assert "Snapshot saved" in res.output

    res = cli_runner.invoke(cli, ["--db", str(temp_db_path), "backups"])
    assert res.exit_code == 0
    assert "glacis-snapshot-" in res.output

    # Restore from the snapshot file listed
    snapshot = next(iter(tmp_path.rglob("glacis-snapshot-*test*.json")))
    res = cli_runner.invoke(cli, ["--db", str(temp_db_path), "restore", str(snapshot)])
    assert res.exit_code == 0
    assert "imported workspace" in res.output


def test_cli_export_html(cli_runner: CliRunner, temp_db_path: Path, tmp_path: Path) -> None:
    cli_runner.invoke(cli, ["--db", str(temp_db_path), "target", "10.10.10.20", "--hostname", "dc01"])
    cli_runner.invoke(cli, ["--db", str(temp_db_path), "cred", "admin:secret123", "--target", "10.10.10.20"])

    out = tmp_path / "report.html"
    res = cli_runner.invoke(cli, ["--db", str(temp_db_path), "export", "--format", "html", "-o", str(out)])
    assert res.exit_code == 0
    html = out.read_text(encoding="utf-8")
    assert html.startswith("<!doctype html>")
    assert "secret123" not in html          # masked by default
    assert "https://" not in html           # fully offline asset-free


def test_cli_exam_check(cli_runner: CliRunner, temp_db_path: Path) -> None:
    res = cli_runner.invoke(cli, ["--db", str(temp_db_path), "exam-check"])
    assert res.exit_code == 0
    assert "EXAM-SAFETY AUDIT" in res.output
    assert "PASS" in res.output
    assert "FAIL" not in res.output, "glacis's own code must have zero network imports"
    assert "zero network imports" in res.output


def test_audit_network_isolation_function() -> None:
    from glacis.audit import audit_network_isolation

    ok, detail = audit_network_isolation()
    assert ok, detail
    assert "zero network imports" in detail
