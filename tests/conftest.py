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
