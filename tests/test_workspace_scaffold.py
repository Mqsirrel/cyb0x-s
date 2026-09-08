"""Tests for GLACIS per-lab workspace scaffolding and path portability."""

from pathlib import Path

from click.testing import CliRunner

from glacis.cli import cli
from glacis.db.store import NotebookStore
from glacis.models import Evidence


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
    assert (lab_dir / "target.env").is_file()
    assert (lab_dir / "notes" / "scratchpad.md").is_file()
    assert (lab_dir / ".gitignore").is_file()

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
        ["--db", str(db_file), "workspace", "init", "target2", "--path", str(lab_dir), "-i", "10.10.10.99"],
    )
    assert res.exit_code == 0
    assert "Initialized workspace: target2" in res.output
    assert (lab_dir / "loot").is_dir()
    assert (lab_dir / "findings.md").is_file()
    assert (lab_dir / "target.env").is_file()
    assert 'export TARGET="10.10.10.99"' in (lab_dir / "target.env").read_text(encoding="utf-8")


def test_init_workspace_with_ip_and_template(tmp_path: Path) -> None:
    store = NotebookStore(":memory:")
    lab_dir = tmp_path / "lab_victim_seeded"
    ws, resolved = store.init_workspace_directory(
        name="victim_seeded",
        target_dir=lab_dir,
        initial_ip="10.10.10.45",
        template_name="ejpt",
    )

    # Check target.env
    env_file = resolved / "target.env"
    assert env_file.is_file()
    env_text = env_file.read_text(encoding="utf-8")
    assert 'export WORKSPACE="victim_seeded"' in env_text
    assert 'export TARGET="10.10.10.45"' in env_text

    # Check scratchpad
    sp_file = resolved / "notes" / "scratchpad.md"
    assert sp_file.is_file()
    sp_text = sp_file.read_text(encoding="utf-8")
    assert "10.10.10.45" in sp_text

    # Check findings.md
    findings_file = resolved / "findings.md"
    assert findings_file.is_file()
    findings_text = findings_file.read_text(encoding="utf-8")
    assert "10.10.10.45" in findings_text

    # Check local SQLite db contents
    local_db_file = resolved / ".glacis" / "notebook.db"
    assert local_db_file.is_file()
    local_store = NotebookStore(local_db_file)
    targets = local_store.list_targets()
    assert len(targets) == 1
    assert targets[0].ip == "10.10.10.45"
    assert targets[0].is_in_scope is True

    # Check checklist items populated from template
    items = local_store.list_checklist_items()
    assert len(items) > 0
    local_store.close()


def test_cli_init_smart_args_single_ip(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    res = runner.invoke(cli, ["init", "10.10.10.55"])
    assert res.exit_code == 0
    assert "Workspace initialized & selected:" in res.output
    assert "10.10.10.55" in res.output

    target_dir = tmp_path / "10.10.10.55"
    assert target_dir.is_dir()
    assert (target_dir / ".glacis" / "notebook.db").is_file()
    assert 'export TARGET="10.10.10.55"' in (target_dir / "target.env").read_text(encoding="utf-8")


def test_cli_init_smart_args_name_and_ip(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    res = runner.invoke(cli, ["init", "box_alfa", "10.10.10.60", "-m", "ejpt"])
    assert res.exit_code == 0
    assert "Workspace initialized & selected:" in res.output
    assert "box_alfa" in res.output
    assert "10.10.10.60" in res.output

    target_dir = tmp_path / "box_alfa"
    assert target_dir.is_dir()
    assert (target_dir / ".glacis" / "notebook.db").is_file()
    assert 'export TARGET="10.10.10.60"' in (target_dir / "target.env").read_text(encoding="utf-8")


def test_upward_db_discovery(tmp_path: Path, monkeypatch) -> None:
    from glacis.db.store import get_default_db_path

    lab_dir = tmp_path / "htb_lab"
    store = NotebookStore(":memory:")
    store.init_workspace_directory("htb_lab", lab_dir)

    expected_db = lab_dir / ".glacis" / "notebook.db"
    assert expected_db.is_file()

    # Subdirectory deep inside the lab
    nested_dir = lab_dir / "scans" / "nmap" / "scripts"
    nested_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.delenv("GLACIS_DB", raising=False)
    monkeypatch.delenv("CYB0X_S_DB", raising=False)
    monkeypatch.delenv("CYB0X_DB", raising=False)

    monkeypatch.chdir(nested_dir)
    discovered = get_default_db_path()
    assert discovered.resolve() == expected_db.resolve()

