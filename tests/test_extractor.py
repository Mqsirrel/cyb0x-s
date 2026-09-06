"""Tests for Constrained Candidate Log Extractor (P4).

Verifies staging and operator confirmation workflows.
Guarantees zero auto-population without explicit confirmation.
"""

from pathlib import Path
from click.testing import CliRunner

from cyb0x_s.cli import cli
from cyb0x_s.db.store import NotebookStore
from cyb0x_s.extractor import (
    CandidateType,
    extract_candidates,
    stage_and_commit_candidate,
)


SAMPLE_TERMINAL_LOG = """
Starting Nmap 7.94 ( https://nmap.org ) at 2026-09-06 10:00 UTC
Nmap scan report for 10.10.10.123 (target.corp.local)
Host is up (0.0021s latency).
PORT     STATE SERVICE VERSION
22/tcp   open  ssh     OpenSSH 8.4p1 Debian 5+deb11u1
80/tcp   open  http    Apache httpd 2.4.56 ((Debian))
445/tcp  open  smb     Samba smbd 4.9.5

[+] 10.10.10.123:445 - CORP\\svc_backup:Summer2023! (Pwn3d!)
[*] Cracked shadow entry: user_bob:$6$salt123$abc1234567890abcdef1234567890abc
[*] Found secret flag in /home/user/flag.txt: FLAG{local_user_flag_captured_9988}
"""


def test_extract_candidates_staging_isolation(store: NotebookStore) -> None:
    # 1. Extraction stages candidates in-memory only
    candidates = extract_candidates(SAMPLE_TERMINAL_LOG)
    assert len(candidates) >= 5

    types = {c.candidate_type for c in candidates}
    assert CandidateType.TARGET in types
    assert CandidateType.SERVICE in types
    assert CandidateType.CREDENTIAL in types
    assert CandidateType.HASH in types
    assert CandidateType.FLAG in types

    # 2. Verify notebook database is untouched (Zero Auto-Population)
    assert len(store.list_targets()) == 0
    assert len(store.list_services()) == 0
    assert len(store.list_credentials()) == 0


def test_stage_and_commit_candidate_workflow(store: NotebookStore) -> None:
    candidates = extract_candidates(SAMPLE_TERMINAL_LOG)

    # Operator explicitly confirms Target candidate
    target_cand = next(c for c in candidates if c.candidate_type == CandidateType.TARGET)
    success, msg = stage_and_commit_candidate(target_cand, store)
    assert success is True
    assert "10.10.10.123" in msg

    t = store.get_target_by_ip("10.10.10.123")
    assert t is not None

    # Operator explicitly confirms Service candidate
    svc_cand = next(c for c in candidates if c.candidate_type == CandidateType.SERVICE and c.port == 22)
    success, msg = stage_and_commit_candidate(svc_cand, store, target_id=t.id)
    assert success is True
    services = store.list_services(target_id=t.id)
    assert len(services) == 1
    assert services[0].port == 22

    # Operator explicitly confirms Flag candidate
    flag_cand = next(c for c in candidates if c.candidate_type == CandidateType.FLAG)
    success, msg = stage_and_commit_candidate(flag_cand, store, target_id=t.id)
    assert success is True

    # Check that flag is safely attached to target
    updated_t = store.get_target(t.id)
    assert updated_t is not None
    assert "FLAG{local_user_flag_captured_9988}" in updated_t.user_flag


def test_cli_extract_command_preview_and_apply(cli_runner: CliRunner, temp_db_path: Path, tmp_path: Path) -> None:
    log_file = tmp_path / "terminal.log"
    log_file.write_text(SAMPLE_TERMINAL_LOG, encoding="utf-8")

    # Mode 1: Preview without apply (Database remains empty)
    res_preview = cli_runner.invoke(cli, ["--db", str(temp_db_path), "extract", str(log_file)])
    assert res_preview.exit_code == 0
    assert "Staged Artifact Candidates" in res_preview.output
    assert "Candidates are staged in memory. No changes written to database" in res_preview.output

    # Verify no targets in db
    store = NotebookStore(temp_db_path)
    assert len(store.list_targets()) == 0

    # Mode 2: Apply with confirmation
    res_apply = cli_runner.invoke(cli, ["--db", str(temp_db_path), "extract", str(log_file), "--apply"])
    assert res_apply.exit_code == 0
    assert "Committing all candidates into workspace database" in res_apply.output
    assert "Done!" in res_apply.output

    # Verify targets and creds now exist
    store_updated = NotebookStore(temp_db_path)
    assert len(store_updated.list_targets()) >= 1
    assert len(store_updated.list_credentials()) >= 1
