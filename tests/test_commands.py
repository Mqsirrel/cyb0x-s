"""Unit tests for the TUI command normalization and parser."""

from __future__ import annotations

from cyb0x_s.tui.commands import normalize_command


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
