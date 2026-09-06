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
    import shlex

    from cyb0x_s.tui.widgets import compile_spray_command

    # Credential with single quote and shell metacharacters
    cmd = compile_spray_command("admin", "p@ss'word$123", "ssh", "10.10.10.20", 22)
    # Shell splitting must succeed without SyntaxError / unclosed quotes
    tokens = shlex.split(cmd)
    assert "sshpass" in tokens
    assert "p@ss'word$123" in tokens
    assert "admin@10.10.10.20" in tokens


def test_substitute_command_placeholders_lhost_lport() -> None:
    from cyb0x_s.tui.widgets import substitute_command_placeholders

    raw_cmd = "nc -lvnp <LPORT> # listen on <LHOST> (<ATTACKER_IP>) against <TARGET_IP> (<TARGET_SUBNET>) with <WORDLIST>"
    subbed = substitute_command_placeholders(
        raw_cmd,
        target_ip="10.10.10.50",
        lhost="10.10.14.47",
        lport="9001",
    )
    assert "nc -lvnp 9001" in subbed
    assert "listen on 10.10.14.47 (10.10.14.47)" in subbed
    assert "against 10.10.10.50 (10.10.10.0/24)" in subbed
    assert "/usr/share/wordlists/dirb/common.txt" in subbed


def test_find_latest_screenshot(tmp_path) -> None:
    import time

    from cyb0x_s.clipboard import find_latest_screenshot

    sc_dir = tmp_path / "Screenshots"
    sc_dir.mkdir(parents=True)

    img1 = sc_dir / "old_shot.png"
    img1.write_bytes(b"PNG fake data 1")

    time.sleep(0.05)
    img2 = sc_dir / "new_shot.png"
    img2.write_bytes(b"PNG fake data 2")

    latest = find_latest_screenshot([sc_dir])
    assert latest is not None
    assert latest.name == "new_shot.png"

    # Test file older than max_age is ignored
    time.sleep(0.02)
    assert find_latest_screenshot([sc_dir], max_age_seconds=0.01) is None


def test_save_clipboard_image_fallback(tmp_path) -> None:
    from cyb0x_s.clipboard import save_clipboard_image

    dest = tmp_path / "clipboard_test.png"
    # When no clipboard tools or no image in clipboard, gracefully returns False
    res = save_clipboard_image(dest)
    assert isinstance(res, bool)


