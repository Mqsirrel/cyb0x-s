"""Tests for the static offline-by-construction compliance audit."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

import glacis
from glacis.cli import cli
from glacis.offline_audit import scan_source, scan_tree

SRC_ROOT = Path(glacis.__file__).parent


def test_ship_tree_has_zero_network_imports() -> None:
    """The shipped package itself must pass exam-check cleanly."""
    report = scan_tree(SRC_ROOT)
    offenders = [f"{v.path}:{v.lineno} {v.offender}" for v in report.violations]
    assert report.clean, "network imports found:\n" + "\n".join(offenders)
    assert report.files_scanned >= 20


def test_detects_socket_import() -> None:
    src = "import socket\ns = socket.socket()\n"
    violations = scan_source(src, "evil.py")
    assert any(v.offender == "socket" and v.kind == "forbidden-import" for v in violations)
    assert any(v.kind == "forbidden-call" and "socket" in v.offender for v in violations)


def test_detects_http_clients() -> None:
    src = (
        "import requests\n"
        "import httpx\n"
        "from urllib.request import urlopen\n"
        "requests.get('http://x')\n"
    )
    violations = scan_source(src, "evil.py")
    offenders = {v.offender for v in violations}
    assert "requests" in offenders
    assert "httpx" in offenders
    assert any("urllib" in o for o in offenders)


def test_detects_telemetry() -> None:
    src = "import sentry_sdk\nimport websockets\n"
    violations = scan_source(src, "evil.py")
    roots = {v.offender.split(".")[0] for v in violations}
    assert "sentry_sdk" in roots
    assert "websockets" in roots


def test_benign_stdlib_passes() -> None:
    src = (
        "import sqlite3\nimport json\nfrom pathlib import Path\nfrom textual.app import App\n"
        "x = Path.cwd()\n"
    )
    assert scan_source(src, "good.py") == []


def test_syntax_errors_are_skipped_not_fatal(tmp_path: Path) -> None:
    broken = tmp_path / "broken.py"
    broken.write_text("def oops(:\n", encoding="utf-8")
    report = scan_tree(tmp_path)
    assert report.files_scanned == 1
    assert report.clean


def test_exam_check_cli_passes() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["exam-check"])
    assert result.exit_code == 0, result.output
    assert "PASS" in result.output


def test_exam_check_cli_fails_on_planted_violation(tmp_path: Path) -> None:
    # Point the scanner at a tree containing a violation directly.
    pkg = tmp_path / "evilpkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("import requests\n", encoding="utf-8")
    report = scan_tree(pkg)
    assert not report.clean
    assert report.violations[0].offender == "requests"
