"""Unit tests for the TUI command normalization and parser."""

from __future__ import annotations

from pathlib import Path

from glacis.tui.commands import normalize_command


def test_normalize_empty_and_whitespace() -> None:
    assert normalize_command("") == ""
    assert normalize_command("   ") == ""


def test_normalize_natural_language_targets() -> None:
    assert normalize_command("add target 10.10.10.50") == ":t 10.10.10.50"
    assert normalize_command("target 192.168.1.1") == ":t 192.168.1.1"


def test_normalize_natural_language_services() -> None:
    assert normalize_command("add service 80/tcp http") == ":s 80/tcp http"
    assert normalize_command("service 445/tcp smb") == ":s 445/tcp smb"


def test_normalize_natural_language_creds() -> None:
    assert normalize_command("add cred admin:Password123") == ":c admin:Password123"
    assert normalize_command("cred root:toor") == ":c root:toor"


def test_normalize_natural_language_notes_and_findings() -> None:
    assert normalize_command("add note Found backup file") == ":n Found backup file"
    assert normalize_command("note In scope box") == ":n In scope box"
    assert normalize_command("add finding SMB Anonymous Share") == ":f SMB Anonymous Share"
    assert normalize_command("finding SQL Injection on /login") == ":f SQL Injection on /login"


def test_normalize_theme_aliases() -> None:
    assert normalize_command("theme warm") == ":theme warm"
    assert normalize_command("palette matrix") == ":theme matrix"
    assert normalize_command("theme") == ":theme"
    assert normalize_command("palette") == ":theme"


def test_canonical_commands_preserved() -> None:
    assert normalize_command(":t 10.10.11.1") == ":t 10.10.11.1"
    assert normalize_command(":s 22/tcp ssh") == ":s 22/tcp ssh"
    assert normalize_command(":m web") == ":m web"
    assert normalize_command(":uflag deadbeef") == ":uflag deadbeef"
    assert normalize_command(":1") == ":1"
    assert normalize_command("/login") == "/login"


def test_normalize_wordlist_aliases() -> None:
    assert normalize_command("wordlist rockyou") == ":w rockyou"
    assert normalize_command("wordlist common") == ":w common"
    assert normalize_command(":w medium") == ":w medium"
    assert normalize_command("wordlist") == ":w"
    assert normalize_command(":w") == ":w"


def test_wordlist_aliases_dictionary() -> None:
    from glacis.tui.commands import WORDLIST_ALIASES

    assert "rockyou" in WORDLIST_ALIASES
    assert "common" in WORDLIST_ALIASES
    assert "medium" in WORDLIST_ALIASES
    assert "raft-d" in WORDLIST_ALIASES
    assert "users" in WORDLIST_ALIASES
    assert WORDLIST_ALIASES["rockyou"].endswith("rockyou.txt")


def test_pivot_subnet_proof_aliases() -> None:
    assert normalize_command("pivot on") == ":pivot on"
    assert normalize_command("pivot 192.168.1.0/24 via :1080") == ":pivot 192.168.1.0/24 via :1080"
    assert normalize_command("subnet 10.10.10.0/24") == ":subnet 10.10.10.0/24"
    assert normalize_command("proof Q1 flag{123}") == ":q Q1 flag{123}"
    assert normalize_command("question 14 secret") == ":q 14 secret"


def test_normalize_import_and_workspace() -> None:
    assert normalize_command("import scans/nmap.xml") == ":import scans/nmap.xml"
    assert normalize_command(":import /tmp/scan.txt") == ":import /tmp/scan.txt"
    assert normalize_command("import") == ":import"
    assert normalize_command("workspace lab01") == ":ws lab01"
    assert normalize_command("ws switch lab02") == ":ws switch lab02"
    assert normalize_command("workspace") == ":ws"
    assert normalize_command("ws") == ":ws"


def test_normalize_lhost_lport_aliases() -> None:
    assert normalize_command("set lhost 10.10.14.47") == ":lhost 10.10.14.47"
    assert normalize_command("lhost 10.10.14.47") == ":lhost 10.10.14.47"
    assert normalize_command("lhost auto") == ":lhost auto"
    assert normalize_command("lhost") == ":lhost"
    assert normalize_command(":lhost") == ":lhost"

    assert normalize_command("set lport 9001") == ":lport 9001"
    assert normalize_command("lport 9001") == ":lport 9001"
    assert normalize_command("lport") == ":lport"
    assert normalize_command(":lport") == ":lport"


def test_normalize_export_crack_and_evidence() -> None:
    assert normalize_command("export wordlists") == ":export wordlists"
    assert normalize_command("export creds") == ":export wordlists"
    assert normalize_command(":export wordlists") == ":export wordlists"

    assert normalize_command("crack 3 Password123") == ":c crack 3 Password123"
    assert normalize_command(":crack 3 Password123") == ":c crack 3 Password123"

    assert normalize_command("paste-ev Proof of root") == ":paste-ev Proof of root"
    assert normalize_command(":paste-evidence Flag proof") == ":paste-ev Flag proof"

    assert normalize_command("ev latest Final proof") == ":ev latest Final proof"
    assert normalize_command("evidence latest Final proof") == ":ev latest Final proof"
    assert normalize_command("evidence screenshots/test.png") == ":ev screenshots/test.png"


def test_execute_lhost_lport_and_crack() -> None:
    from unittest.mock import MagicMock

    from glacis.db.store import NotebookStore
    from glacis.tui.commands import execute_command

    store = NotebookStore(":memory:")
    t = store.add_target("10.10.10.60")
    c = store.add_credential(username="admin", secret="$NTLM$hash123", target_id=t.id, status="captured")

    app = MagicMock()
    app.store = store
    app.refresh_all = MagicMock()
    app.notify = MagicMock()

    # 1. Execute LHOST
    execute_command(app, ":lhost 10.10.14.55")
    assert store.get_lhost() == "10.10.14.55"
    app.notify.assert_called_with("LHOST set to: 10.10.14.55")

    # 2. Execute LPORT
    execute_command(app, ":lport 443")
    assert store.get_lport() == "443"
    app.notify.assert_called_with("LPORT set to: 443")

    # 3. Execute :c crack
    execute_command(app, f":c crack {c.id} password123")
    updated_c = store.get_credential(c.id)
    assert updated_c.secret == "password123"
    assert updated_c.status == "cracked"


def test_normalize_init_command() -> None:
    assert normalize_command("init") == ":init"
    assert normalize_command(":init") == ":init"
    assert normalize_command("init lab_box") == ":init lab_box"
    assert normalize_command(":init lab_box 10.10.10.20") == ":init lab_box 10.10.10.20"


def test_execute_init_command(tmp_path: Path, monkeypatch) -> None:
    from unittest.mock import MagicMock

    from glacis.db.store import NotebookStore
    from glacis.tui.commands import execute_command

    monkeypatch.chdir(tmp_path)
    store = NotebookStore(":memory:")
    app = MagicMock()
    app.store = store
    app.refresh_all = MagicMock()
    app.notify = MagicMock()

    execute_command(app, ":init target_omega 10.10.10.77")
    app.refresh_all.assert_called()
    assert (tmp_path / "target_omega" / ".glacis" / "notebook.db").is_file()
    assert (tmp_path / "target_omega" / "target.env").is_file()
    assert 'export TARGET="10.10.10.77"' in (tmp_path / "target_omega" / "target.env").read_text(encoding="utf-8")

