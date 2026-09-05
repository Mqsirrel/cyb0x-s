"""Integration and unit tests for audit, proof-cmd, cmd golden chain, clean ANSI, and lossless export."""

import json
from pathlib import Path
import pytest
from click.testing import CliRunner

from cyb0x_s.cli import ANSI_ESCAPE_RE, cli
from cyb0x_s.db.store import NotebookStore
from cyb0x_s.export import export_json, export_markdown, import_json
from cyb0x_s.models import ChecklistStatus, ServiceStatus


@pytest.mark.fast
def test_audit_target_store_logic(store: NotebookStore) -> None:
    """Test audit_target passes/fails based on critical proof items."""
    t = store.add_target("10.10.10.20", hostname="audit-box.local", os_name="Linux")

    # Initial state: no services, no foothold, no flags, no root proof, no evidence
    res1 = store.audit_target(t.id)
    assert res1["ready_to_revert"] is False
    assert "DO NOT REVERT" in res1["verdict"]

    checks_by_key = {c["key"]: c for c in res1["checks"]}
    assert checks_by_key["scope"]["passed"] is True
    assert checks_by_key["services"]["passed"] is False
    assert checks_by_key["foothold"]["passed"] is False
    assert checks_by_key["user_flag"]["passed"] is False
    assert checks_by_key["privesc"]["passed"] is False
    assert checks_by_key["root_flag"]["passed"] is False
    assert checks_by_key["evidence"]["passed"] is False

    # Add all required proof artifacts
    store.add_service(target_id=t.id, port=80, service="HTTP")
    store.update_target_details(
        target_id=t.id,
        initial_access_vuln="CVE-2021-41773",
        foothold_cmd="curl -s --path-as-is http://10.10.10.20/cgi-bin/.%%32%65/.%%32%65/bin/sh",
        privesc_vector="sudo /usr/bin/find",
        root_proof="id && whoami && cat /root/root.txt",
        user_flag="eJPT{user_flag_123}",
        root_flag="eJPT{root_flag_456}",
    )
    store.add_evidence("proof_screenshot.png", target_id=t.id, description="Root terminal")
    store.add_command(
        command="sudo find . -exec /bin/sh \\; -quit",
        target_id=t.id,
        is_golden=True,
        step="privesc",
    )

    res2 = store.audit_target(t.id)
    assert res2["ready_to_revert"] is True
    assert "SAFE TO REVERT" in res2["verdict"]
    assert res2["score"] == "7/7"
    assert res2["stats"]["golden_cmds_count"] == 1


@pytest.mark.fast
def test_cli_audit_command(cli_runner: CliRunner, temp_db_path: Path) -> None:
    """Test cyb0x-s audit CLI reporting."""
    cli_runner.invoke(cli, ["--db", str(temp_db_path), "target", "10.10.10.25", "--os", "Linux"])

    # First audit should warn not ready
    res_not_ready = cli_runner.invoke(cli, ["--db", str(temp_db_path), "audit", "10.10.10.25"])
    assert res_not_ready.exit_code == 0
    assert "Pre-Reset Integrity Audit" in res_not_ready.output
    assert "DO NOT REVERT" in res_not_ready.output

    # Record flags, foothold, privesc, evidence
    cli_runner.invoke(cli, ["--db", str(temp_db_path), "service", "10.10.10.25", "22/tcp", "SSH"])
    cli_runner.invoke(cli, ["--db", str(temp_db_path), "flag", "user", "user_flag_val", "-t", "10.10.10.25"])
    cli_runner.invoke(cli, ["--db", str(temp_db_path), "flag", "root", "root_flag_val", "-t", "10.10.10.25"])
    cli_runner.invoke(cli, ["--db", str(temp_db_path), "foothold", "ssh -i id_rsa user@10.10.10.25", "-t", "10.10.10.25"])
    cli_runner.invoke(cli, ["--db", str(temp_db_path), "privesc", "sudo su", "--proof", "id; whoami", "-t", "10.10.10.25"])
    cli_runner.invoke(cli, ["--db", str(temp_db_path), "evidence", "proof.png", "-t", "10.10.10.25"])

    # Second audit should pass
    res_ready = cli_runner.invoke(cli, ["--db", str(temp_db_path), "audit", "10.10.10.25"])
    assert res_ready.exit_code == 0
    assert "SAFE TO REVERT" in res_ready.output


@pytest.mark.fast
def test_cli_proof_cmd_generator(cli_runner: CliRunner, temp_db_path: Path) -> None:
    """Test composite proof one-liner generation for Linux and Windows."""
    # Linux explicit
    res_linux = cli_runner.invoke(cli, ["--db", str(temp_db_path), "proof-cmd", "--os", "linux"])
    assert res_linux.exit_code == 0
    assert "id && whoami && hostname && ip a" in res_linux.output
    assert "Linux Composite Proof" in res_linux.output

    # Windows explicit
    res_win = cli_runner.invoke(cli, ["--db", str(temp_db_path), "proof-cmd", "--os", "windows"])
    assert res_win.exit_code == 0
    assert "whoami /priv && whoami && hostname && ipconfig" in res_win.output
    assert "Windows Composite Proof" in res_win.output

    # Auto-detect from target OS
    cli_runner.invoke(cli, ["--db", str(temp_db_path), "target", "10.10.10.30", "--os", "Windows Server 2019"])
    res_auto = cli_runner.invoke(cli, ["--db", str(temp_db_path), "proof-cmd", "-t", "10.10.10.30"])
    assert res_auto.exit_code == 0
    assert "Windows Composite Proof" in res_auto.output


@pytest.mark.fast
def test_cli_cmd_golden_chain(cli_runner: CliRunner, temp_db_path: Path) -> None:
    """Test recording commands and filtering the Golden Replication Chain."""
    cli_runner.invoke(cli, ["--db", str(temp_db_path), "target", "10.10.10.40"])

    # Normal command
    res_norm = cli_runner.invoke(
        cli,
        ["--db", str(temp_db_path), "cmd", "gobuster dir -u http://10.10.10.40 -w /tmp/wordlist.txt", "-t", "10.10.10.40"],
    )
    assert res_norm.exit_code == 0
    assert "Recorded command" in res_norm.output

    # Golden breakthrough command
    res_gold = cli_runner.invoke(
        cli,
        [
            "--db",
            str(temp_db_path),
            "cmd",
            "sudo /usr/bin/find . -exec /bin/sh \\; -quit",
            "-t",
            "10.10.10.40",
            "--golden",
            "--step",
            "privesc",
            "--notes",
            "Escapes find sandbox to root",
        ],
    )
    assert res_gold.exit_code == 0
    assert "GOLDEN REPRODUCTION STEP" in res_gold.output

    # List all
    res_list_all = cli_runner.invoke(cli, ["--db", str(temp_db_path), "cmd", "--list", "-t", "10.10.10.40"])
    assert res_list_all.exit_code == 0
    assert "gobuster" in res_list_all.output
    assert "sudo /usr/bin/find" in res_list_all.output

    # List golden only
    res_list_gold = cli_runner.invoke(cli, ["--db", str(temp_db_path), "cmd", "--list", "--golden-only", "-t", "10.10.10.40"])
    assert res_list_gold.exit_code == 0
    assert "sudo /usr/bin/find" in res_list_gold.output
    assert "gobuster" not in res_list_gold.output


@pytest.mark.fast
def test_cli_clean_ansi_sanitizer(cli_runner: CliRunner) -> None:
    """Test ANSI terminal escape code sanitizer."""
    raw_terminal_log = "\x1b[31;1m[+] Admin Password Found:\x1b[0m \x1b[32mSecret123!\x1b[0m\r\n\x1b[2KDone.\r\n"
    res = cli_runner.invoke(cli, ["clean"], input=raw_terminal_log)
    assert res.exit_code == 0
    cleaned = res.output
    assert "[+] Admin Password Found: Secret123!" in cleaned
    assert "Done." in cleaned
    assert "\x1b" not in cleaned
    assert "\r" not in cleaned


@pytest.mark.fast
def test_lossless_markdown_and_json_export(store: NotebookStore) -> None:
    """Test complete preservation of methodology, golden steps, failure logs, and exam proofs."""
    t = store.add_target("10.10.10.77", hostname="corp.target", os_name="Linux")
    store.update_target_details(
        target_id=t.id,
        initial_access_vuln="Log4Shell",
        foothold_cmd="curl -H 'X-Api-Version: ${jndi:ldap://...}' http://10.10.10.77",
        privesc_vector="SUID pkexec",
        root_proof="id; whoami",
        user_flag="flag{user77}",
        root_flag="flag{root77}",
        subnet="192.168.100.0/24",
        is_pivot=True,
        pivot_route="via 10.10.10.77 port 1080",
    )
    store.add_command(
        command="curl http://10.10.10.77/exploit",
        target_id=t.id,
        is_golden=True,
        step="foothold",
        notes="Trigger reverse shell",
    )
    store.add_failure_log(
        target_id=t.id,
        where_stuck="Tried brute-forcing SSH for 45 minutes",
        breakthrough_clue="Found unauthenticated API header",
        rule_for_next_time="Always enumerate headers before brute-forcing",
    )
    store.add_exam_proof(
        question_num="Q14",
        category="FLAG",
        answer_proof="flag{root77}",
        notes="Root flag on internal pivot host",
        target_id=t.id,
    )

    # 1. Verify Markdown Export includes Golden Walkthrough & Exam Ledger
    md = export_markdown(store)
    assert "## 🏆 Golden Reproduction Walkthrough" in md
    assert "[FOOTHOLD]" in md
    assert "curl http://10.10.10.77/exploit" in md
    assert "# Exam Evidence & Answer Submission Ledger (Q1–Q35)" in md
    assert "**Q14**" in md
    assert "flag{root77}" in md

    # 2. Verify JSON Export is Lossless
    json_str = export_json(store)
    data = json.loads(json_str)

    # Check target methodology and commands in JSON
    t_export = data["targets"][0]
    assert t_export["foothold_cmd"] == "curl -H 'X-Api-Version: ${jndi:ldap://...}' http://10.10.10.77"
    assert t_export["user_flag"] == "flag{user77}"
    assert t_export["root_flag"] == "flag{root77}"
    assert t_export["is_pivot"] is True
    assert len(t_export["commands"]) == 1
    assert t_export["commands"][0]["is_golden"] is True
    assert len(t_export["failure_logs"]) == 1
    assert len(t_export["exam_proofs"]) == 1

    # 3. Import into completely fresh store and verify 100% round-trip fidelity
    fresh = NotebookStore(":memory:")
    ws_imported = import_json(fresh, json_str, workspace_name="Restored-Workspace")
    assert ws_imported.name == "Restored-Workspace"

    restored_targets = fresh.list_targets(workspace_id=ws_imported.id)
    assert len(restored_targets) == 1
    rt = restored_targets[0]
    assert rt.ip == "10.10.10.77"
    assert rt.foothold_cmd == "curl -H 'X-Api-Version: ${jndi:ldap://...}' http://10.10.10.77"
    assert rt.user_flag == "flag{user77}"
    assert rt.root_flag == "flag{root77}"
    assert rt.is_pivot is True
    assert rt.pivot_route == "via 10.10.10.77 port 1080"

    # Restored golden commands
    restored_golden = fresh.list_commands(target_id=rt.id, golden_only=True)
    assert len(restored_golden) == 1
    assert restored_golden[0].command == "curl http://10.10.10.77/exploit"
    assert restored_golden[0].step == "foothold"

    # Restored failure log
    restored_failures = fresh.list_failure_logs(target_id=rt.id)
    assert len(restored_failures) == 1
    assert "brute-forcing" in restored_failures[0].where_stuck

    # Restored exam proofs
    restored_proofs = fresh.list_exam_proofs(target_id=rt.id)
    assert len(restored_proofs) == 1
    assert restored_proofs[0].question_num == "Q14"
    assert restored_proofs[0].answer_proof == "flag{root77}"
