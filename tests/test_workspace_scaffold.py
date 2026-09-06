"""Tests for CYB0X-S per-lab workspace scaffolding and path portability."""

from pathlib import Path

from click.testing import CliRunner

from cyb0x_s.cli import cli
from cyb0x_s.db.store import NotebookStore
from cyb0x_s.models import Evidence


def test_init_workspace_directory_scaffolding(tmp_path: Path) -> None:
    store = NotebookStore(":memory:")
    lab_dir = tmp_path / "lab_victim"
    ws, resolved = store.init_workspace_directory(
        name="victim-lab",
        target_dir=lab_dir,
        description="Active Directory lab 01",
    )

    assert ws.name == "victim-lab"
    assert ws.description == "Active Directory lab 01"
    assert ws.root_path == str(resolved)
    assert resolved.is_dir()

    # Check required subdirectories
    for subdir in ["scans", "enum", "screenshots", "notes", "loot"]:
        expected = resolved / subdir
        assert expected.is_dir(), f"Expected directory '{subdir}' was not created"

    # Check findings.md report scaffold
    findings_file = resolved / "findings.md"
    assert findings_file.is_file(), "findings.md was not created"
    content = findings_file.read_text(encoding="utf-8")
    assert "# Assessment Findings Report: victim-lab" in content
    assert "Executive Summary" in content
    assert "Scope & Target Overview" in content
    assert "scans/" in content
    assert "screenshots/" in content


def test_resolve_evidence_path(tmp_path: Path) -> None:
    store = NotebookStore(":memory:")
    lab_dir = tmp_path / "lab_box"
    ws, _ = store.init_workspace_directory(name="box", target_dir=lab_dir)

    # Relative path inside workspace
    ev1 = Evidence(path_or_ref="screenshots/proof.png", evidence_type="screenshot")
    resolved_ev1 = store.resolve_evidence_path(ev1)
    assert resolved_ev1 == lab_dir.resolve() / "screenshots" / "proof.png"

    # Absolute path remains unchanged
    abs_path = tmp_path / "external" / "scan.xml"
    ev2 = Evidence(path_or_ref=str(abs_path), evidence_type="scan")
    assert store.resolve_evidence_path(ev2) == abs_path.resolve()


def test_cli_init_command(tmp_path: Path) -> None:
    runner = CliRunner()
    db_file = tmp_path / "test_notebook.db"
    lab_dir = tmp_path / "my_assessment"

    res = runner.invoke(
        cli,
        ["--db", str(db_file), "init", str(lab_dir), "--name", "Assessment-Alfa", "--desc", "Test lab"],
    )
    assert res.exit_code == 0
    assert "Workspace initialized & selected: Assessment-Alfa" in res.output
    assert (lab_dir / "scans").is_dir()
    assert (lab_dir / "findings.md").is_file()

    # Verify workspace list reflects root path
    res_list = runner.invoke(cli, ["--db", str(db_file), "workspace", "list"])
    assert res_list.exit_code == 0
    assert "Assessment-Alfa" in res_list.output
    ws_record = NotebookStore(db_file).get_active_workspace()
    assert ws_record.name == "Assessment-Alfa"
    assert ws_record.root_path == str(lab_dir.resolve())


def test_cli_workspace_init_subcommand(tmp_path: Path) -> None:
    runner = CliRunner()
    db_file = tmp_path / "test_notebook.db"
    lab_dir = tmp_path / "workspaces" / "target2"

    res = runner.invoke(
        cli,
        ["--db", str(db_file), "workspace", "init", "target2", "--path", str(lab_dir)],
    )
    assert res.exit_code == 0
    assert "Initialized workspace: target2" in res.output
    assert (lab_dir / "loot").is_dir()
    assert (lab_dir / "findings.md").is_file()
