"""Tests for clipboard copying value extraction and escape formatting."""

from cyb0x_s.clipboard import copy_osc52, extract_copy_value
from cyb0x_s.models import (
    ChecklistItem,
    Credential,
    Evidence,
    Finding,
    Lead,
    Note,
    Service,
    Target,
)


def test_extract_copy_value_target() -> None:
    t = Target(ip="10.10.10.20")
    assert extract_copy_value(t) == "10.10.10.20"


def test_extract_copy_value_service() -> None:
    s = Service(target_id=1, port=445, service="SMB")
    # With target IP
    assert extract_copy_value(s, target_ip="10.10.10.20") == "10.10.10.20:445"
    # Without target IP
    assert extract_copy_value(s) == "445"


def test_extract_copy_value_credential() -> None:
    c = Credential(username="admin", secret="SecretPassword123!")
    # Extracts the unmasked secret so user can paste it into shell/tool
    assert extract_copy_value(c) == "SecretPassword123!"


def test_extract_copy_value_checklist() -> None:
    ci = ChecklistItem(title="SMB enumeration")
    # Strictly the text of the checklist item, no commands
    assert extract_copy_value(ci) == "SMB enumeration"


def test_extract_copy_value_finding_and_note() -> None:
    f = Finding(title="SMB Anonymous Access")
    assert extract_copy_value(f) == "SMB Anonymous Access"

    n = Note(content="archive.zip has configs")
    assert extract_copy_value(n) == "archive.zip has configs"

    ld = Lead(title="Inspect 8080")
    assert extract_copy_value(ld) == "Inspect 8080"

    ev = Evidence(path_or_ref="screenshot-04.png")
    assert extract_copy_value(ev) == "screenshot-04.png"


def test_osc52_generation() -> None:
    # Verify osc52 executes without throwing exceptions
    res = copy_osc52("test_copy_payload")
    assert isinstance(res, bool)


def test_compile_spray_command_shell_quoting() -> None:
    from cyb0x_s.tui.widgets import compile_spray_command
    import shlex

    # Credential with single quote and shell metacharacters
    cmd = compile_spray_command("admin", "p@ss'word$123", "ssh", "10.10.10.20", 22)
    # Shell splitting must succeed without SyntaxError / unclosed quotes
    tokens = shlex.split(cmd)
    assert "sshpass" in tokens
    assert "p@ss'word$123" in tokens
    assert "admin@10.10.10.20" in tokens

