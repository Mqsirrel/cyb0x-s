"""Pytest fixtures for cyb0x-s."""

from __future__ import annotations

import gc
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any, Generator, Optional

import pytest
from click.testing import CliRunner

from cyb0x_s.db.store import NotebookStore
from cyb0x_s.tui.widgets import clear_badge_caches


def _get_physical_core_count() -> int:
    """Detect physical CPU cores without external dependencies."""
    try:
        core_ids = set()
        cpu_path = "/sys/devices/system/cpu"
        if os.path.exists(cpu_path):
            for entry in os.listdir(cpu_path):
                if re.match(r"^cpu[0-9]+$", entry):
                    topo_file = os.path.join(cpu_path, entry, "topology", "core_id")
                    if os.path.exists(topo_file):
                        with open(topo_file, "r") as f:
                            core_ids.add(f.read().strip())
            if core_ids:
                return len(core_ids)
    except Exception:
        pass
    logical = os.cpu_count() or 1
    return max(1, logical // 2)


def _get_available_ram_mb() -> int:
    """Read available memory from /proc/meminfo on Linux."""
    try:
        with open("/proc/meminfo", "r") as f:
            for line in f:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) // 1024
    except Exception:
        pass
    return 2048


def pytest_xdist_auto_num_workers(config: Any) -> Optional[int]:
    """
    Intelligently calculate worker count for -n auto.
    Leaves physical cores and RAM free for the OS and desktop so laptops don't throttle or freeze.
    """
    physical_cores = _get_physical_core_count()
    # Reserve at least 1 physical core for OS/UI, cap at 3 for 15W TDP thermal envelope
    cpu_cap = max(1, min(physical_cores - 1, 3))

    avail_ram_mb = _get_available_ram_mb()
    # Ensure ~650MB per worker without triggering Linux swap direct reclaim
    ram_cap = max(1, avail_ram_mb // 650)

    return min(cpu_cap, ram_cap)


@pytest.fixture
def temp_db_path() -> Generator[Path, None, None]:
    """Provide a temporary SQLite database file path in RAM (/dev/shm if available)."""
    shm = Path("/dev/shm")
    temp_dir = "/dev/shm" if shm.is_dir() and os.access(shm, os.W_OK) else None
    with tempfile.NamedTemporaryFile(suffix=".db", dir=temp_dir, delete=False) as f:
        path = Path(f.name)
    yield path
    for p in (path, path.with_name(path.name + "-wal"), path.with_name(path.name + "-shm")):
        if p.exists():
            p.unlink()


# Warp-Pilot: tune Textual pilot sleep granularity from 20ms to 1ms
try:
    import textual.pilot as _tp
    _tp.SLEEP_GRANULARITY = 0.001
    _tp.SLEEP_IDLE = 0.0005
except ImportError:
    pass


class DatabaseTemplateManager:
    """Pre-compiled B-Tree Template Cloning (PBTC) Manager.
    
    Operates at raw B-tree page layer using sqlite3_backup to clone pre-compiled
    schema in ~50 microseconds, bypassing SQL tokenizing, Lemon parsing, and VDBE code generation.
    """
    _empty_template: Optional[NotebookStore] = None
    _seeded_template: Optional[NotebookStore] = None

    @classmethod
    def get_empty_template(cls) -> NotebookStore:
        if cls._empty_template is None:
            cls._empty_template = NotebookStore(":memory:")
        return cls._empty_template

    @classmethod
    def create_cloned_store(cls) -> NotebookStore:
        import sqlite3
        template = cls.get_empty_template()
        worker = NotebookStore.__new__(NotebookStore)
        worker.db_path = Path(":memory:")
        conn = sqlite3.connect(":memory:", check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        template.conn.backup(conn, pages=-1)
        worker.conn = conn
        return worker

    @classmethod
    def get_seeded_template(cls) -> NotebookStore:
        if cls._seeded_template is None:
            s = cls.create_cloned_store()
            target = s.add_target("10.10.10.20", hostname="target.local", os_name="Linux")
            s.add_service(target_id=target.id, port=22, service="SSH", version="OpenSSH 8.2p1")
            s.add_service(target_id=target.id, port=445, service="SMB", version="Samba 4.3")
            s.add_credential(username="admin", secret="Summer2024!", target_id=target.id)
            s.add_checklist_item(title="SMB enumeration", target_id=target.id)
            s.add_note("backup share contains archive.zip", target_id=target.id)
            cls._seeded_template = s
        return cls._seeded_template

    @classmethod
    def create_seeded_cloned_store(cls) -> NotebookStore:
        import sqlite3
        template = cls.get_seeded_template()
        worker = NotebookStore.__new__(NotebookStore)
        worker.db_path = Path(":memory:")
        conn = sqlite3.connect(":memory:", check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        template.conn.backup(conn, pages=-1)
        worker.conn = conn
        return worker


@pytest.fixture
def seeded_store() -> Generator[NotebookStore, None, None]:
    """Provide a pre-seeded in-memory NotebookStore cloned via PBTC in <50µs."""
    s = DatabaseTemplateManager.create_seeded_cloned_store()
    yield s
    s.close()


@pytest.fixture
def store() -> Generator[NotebookStore, None, None]:
    """Provide a clean, isolated in-memory NotebookStore cloned via PBTC in <50µs."""
    s = DatabaseTemplateManager.create_cloned_store()
    yield s
    s.close()


@pytest.fixture
def mem_store() -> Generator[NotebookStore, None, None]:
    """Provide an in-memory NotebookStore instance cloned via PBTC in <50µs."""
    s = DatabaseTemplateManager.create_cloned_store()
    yield s
    s.close()


@pytest.fixture
def cli_runner() -> CliRunner:
    """Provide a Click test CLI runner."""
    return CliRunner()


@pytest.fixture(scope="session")
def session_config_dir(tmp_path_factory: pytest.TempPathFactory) -> Generator[Path, None, None]:
    """Single session-scoped sandbox directory in RAM tmpfs to avoid 150+ disk directory allocations."""
    shm = Path("/dev/shm")
    if shm.is_dir() and os.access(shm, os.W_OK):
        d = tempfile.mkdtemp(prefix="cybox_cfg_", dir="/dev/shm")
        p = Path(d)
        yield p
        shutil.rmtree(p, ignore_errors=True)
    else:
        yield tmp_path_factory.mktemp("cybox_cfg")


@pytest.fixture(autouse=True)
def isolate_test_environment(session_config_dir: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    """Ensure every test runs in an isolated sandbox with clean config directory and GC sweep."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(session_config_dir))
    monkeypatch.delenv("CYB0X_THEME", raising=False)
    monkeypatch.delenv("CYB0X_PALETTE", raising=False)
    monkeypatch.delenv("CYB0X_TRANSPARENT", raising=False)
    theme_file = session_config_dir / "cyb0x-s" / "theme"
    if theme_file.exists():
        theme_file.unlink()
    yield
    # Post-test memory sweep: instantly reclaim circular Textual DOM graphs
    clear_badge_caches()
    gc.collect()


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register custom CLI options."""
    parser.addoption(
        "--fast",
        action="store_true",
        default=False,
        help="Run only fast unit/backend tests (skips slow TUI async pilot tests).",
    )
    parser.addoption(
        "--smart",
        action="store_true",
        default=False,
        help="Run only tests impacted by recent git changes via AST reverse reachability graph.",
    )


def _find_git_impacted_tests(repo_root: Path) -> Optional[set[str]]:
    """Compute reverse reachability graph from git status modified files to tests."""
    import ast
    import subprocess
    from collections import defaultdict, deque

    try:
        res = subprocess.run(["git", "status", "--porcelain"], cwd=repo_root, capture_output=True, text=True, check=True)
    except Exception:
        return None

    modified: set[Path] = set()
    for line in res.stdout.splitlines():
        if not line.strip():
            continue
        path_str = line[3:].strip()
        if " -> " in path_str:
            path_str = path_str.split(" -> ")[1]
        p = (repo_root / path_str).resolve()
        if p.suffix == ".py" and p.exists():
            modified.add(p)

    if not modified:
        return set()

    # If global config or conftest was modified, run full suite
    global_triggers = {"conftest.py", "pyproject.toml"}
    for m in modified:
        if m.name in global_triggers:
            return None

    src_dir = repo_root / "src" / "cyb0x_s"
    tests_dir = repo_root / "tests"
    all_tests = set(tests_dir.rglob("test_*.py"))
    modified_tests = modified.intersection(all_tests)
    modified_src = modified.difference(all_tests)

    if not modified_src:
        return {p.name for p in modified_tests}

    # Build reverse dependency graph: file -> set of files that import it
    reverse_graph: dict[Path, set[Path]] = defaultdict(set)
    all_files = list(src_dir.rglob("*.py")) + list(all_tests)

    for f in all_files:
        try:
            tree = ast.parse(f.read_bytes(), filename=str(f))
        except Exception:
            continue
        for node in ast.walk(tree):
            mod_names = []
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("cyb0x_s"):
                        mod_names.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.startswith("cyb0x_s"):
                    mod_names.append(node.module)

            for mod in mod_names:
                rel = mod.replace("cyb0x_s", "").lstrip(".")
                parts = rel.split(".")
                cand = src_dir.joinpath(*parts).with_suffix(".py")
                if cand.is_file():
                    reverse_graph[cand].add(f)

    # BFS from modified source files to find reachable test files
    queue = deque(modified_src)
    visited = set(modified_src)
    impacted_test_files = set(modified_tests)

    while queue:
        curr = queue.popleft()
        for dep in reverse_graph.get(curr, ()):
            if dep in all_tests:
                impacted_test_files.add(dep)
            if dep not in visited and dep not in all_tests:
                visited.add(dep)
                queue.append(dep)

    return {p.name for p in impacted_test_files}


CACHE_KEY_DURATIONS = "cybox/test_durations_v1"
FALLBACK_TUI_DURATION = 3.5
FALLBACK_FAST_DURATION = 0.02
_RECORDED_DURATIONS: dict[str, float] = {}


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Tag tests, handle --fast and --smart filtering, and sort tests descending by duration (Graham's LPT)."""
    tui_marker = pytest.mark.tui
    fast_marker = pytest.mark.fast
    run_fast = config.getoption("--fast", default=False)
    run_smart = config.getoption("--smart", default=False)

    impacted_test_names = None
    if run_smart:
        impacted_test_names = _find_git_impacted_tests(Path(config.rootpath))

    fast_items = []
    deselected = []

    for item in items:
        fspath = str(item.fspath)
        fname = Path(fspath).name
        is_tui = ("test_tui" in fspath or "test_theme_picker" in fspath) and not (
            "contrast" in item.name or "resolve_palette" in item.name
        )

        if is_tui:
            item.add_marker(tui_marker)
        else:
            item.add_marker(fast_marker)

        # Smart filter: skip if not in impacted tests
        if impacted_test_names is not None and fname not in impacted_test_names:
            deselected.append(item)
            continue

        # Fast filter: skip TUI tests if --fast
        if run_fast and is_tui:
            deselected.append(item)
            continue

        fast_items.append(item)

    if deselected:
        config.hook.pytest_deselected(items=deselected)
        items[:] = fast_items

    # Graham's LPT (Longest Processing Time First) Multiprocessor Scheduling:
    # Sort tests descending by duration so heavy tests start at t=0, and fast unit tests
    # act as fine-grained filler, eliminating worker tail starvation.
    durations: dict[str, float] = {}
    if config.cache:
        durations = config.cache.get(CACHE_KEY_DURATIONS, {}) or {}

    def _get_estimated_duration(item: pytest.Item) -> float:
        if item.nodeid in durations:
            return float(durations[item.nodeid])
        fspath = str(item.fspath)
        if "test_tui" in fspath or "test_theme_picker" in fspath:
            return FALLBACK_TUI_DURATION
        return FALLBACK_FAST_DURATION

    items.sort(key=_get_estimated_duration, reverse=True)


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    """Collect test durations on controller process as workers finish tests."""
    if report.when == "call":
        _RECORDED_DURATIONS[report.nodeid] = report.duration


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Persist test durations to .pytest_cache upon session completion."""
    if _RECORDED_DURATIONS and session.config.cache:
        cached = session.config.cache.get(CACHE_KEY_DURATIONS, {}) or {}
        cached.update(_RECORDED_DURATIONS)
        session.config.cache.set(CACHE_KEY_DURATIONS, cached)


