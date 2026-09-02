"""Pytest fixtures for cyb0x-s."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Generator
import pytest
from click.testing import CliRunner

from cyb0x_s.db.store import NotebookStore


@pytest.fixture
def temp_db_path() -> Generator[Path, None, None]:
    """Provide a temporary SQLite database file path."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = Path(f.name)
    yield path
    if path.exists():
        path.unlink()


@pytest.fixture
def store(temp_db_path: Path) -> Generator[NotebookStore, None, None]:
    """Provide a clean, isolated NotebookStore instance."""
    s = NotebookStore(db_path=temp_db_path)
    yield s
    s.close()


@pytest.fixture
def mem_store() -> Generator[NotebookStore, None, None]:
    """Provide an in-memory NotebookStore instance."""
    s = NotebookStore(db_path=":memory:")
    yield s
    s.close()


@pytest.fixture
def cli_runner() -> CliRunner:
    """Provide a Click test CLI runner."""
    return CliRunner()


@pytest.fixture(autouse=True)
def isolate_test_environment(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure every test runs in an isolated sandbox with clean config directory."""
    tmp_config = tmp_path_factory.mktemp("cybox_cfg")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_config))
    monkeypatch.delenv("CYB0X_THEME", raising=False)
    monkeypatch.delenv("CYB0X_PALETTE", raising=False)


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Automatically tag tests with 'tui' or 'fast' markers based on module path."""
    tui_marker = pytest.mark.tui
    fast_marker = pytest.mark.fast

    for item in items:
        # Check if the test is inside a TUI-related test module
        fspath = str(item.fspath)
        if "test_tui" in fspath or "test_theme_picker" in fspath:
            # If it's pure contrast math calculation without pilot, mark fast as well
            if "contrast" in item.name or "resolve_palette" in item.name:
                item.add_marker(fast_marker)
            else:
                item.add_marker(tui_marker)
        else:
            item.add_marker(fast_marker)

