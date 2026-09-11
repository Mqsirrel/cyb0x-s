"""Tests for the snapshot safety net (create, rotate, list, restore)."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from glacis import snapshot as snap
from glacis.db.store import NotebookStore


@pytest.fixture
def file_store(tmp_path: Path):
    db = tmp_path / "lab" / ".glacis" / "notebook.db"
    store = NotebookStore(db)
    yield store
    store.close()


def test_create_snapshot_writes_consistent_copy(file_store: NotebookStore) -> None:
    t = file_store.add_target("10.5.5.5")
    file_store.add_note("important proof note", target_id=t.id)

    info = snap.create_snapshot(file_store, note="before changes")
    snap_dir = snap.snapshots_dir_for(file_store)
    assert (snap_dir / info.file_name).is_file()
    assert info.note == "before changes"
    assert info.size_bytes > 0

    entries = snap.list_snapshots(file_store)
    assert any(e.file_name == info.file_name and e.note == "before changes" for e in entries)
    # JSON index exists and is valid.
    assert (snap_dir / "index.json").is_file()


def test_rotation_keeps_newest_n(file_store: NotebookStore, tmp_path: Path) -> None:
    for i in range(5):
        snap.create_snapshot(file_store, note=f"s{i}", keep=3)
        time.sleep(1.02)  # filename resolution is per-second
    entries = snap.list_snapshots(file_store)
    assert len(entries) == 3
    assert entries[0].note == "s4"
    assert entries[-1].note == "s2"
    snap_dir = snap.snapshots_dir_for(file_store)
    db_files = list(snap_dir.glob("*.db"))
    assert len(db_files) == 3


def test_restore_is_lossless(file_store: NotebookStore, tmp_path: Path) -> None:
    t = file_store.add_target("10.5.5.6")
    file_store.add_credential("alice", "orig", target_id=t.id)
    info = snap.create_snapshot(file_store, note="baseline")
    original_note = (tmp_path / "lab" / ".glacis" / "snapshots" / info.file_name).read_bytes()[:50]
    assert original_note  # non-empty

    # Mutate post-snapshot state, then close and restore.
    file_store.add_target("10.5.5.99")
    file_store.add_credential("bob", "later", target_id=t.id)
    db_path = Path(file_store.db_path)
    file_store.close()

    target = snap.resolve_snapshot(1, db_path)
    snap.restore_snapshot(target, db_path)

    restored = NotebookStore(db_path)
    ips = [x.ip for x in restored.list_targets()]
    assert ips == ["10.5.5.6"]
    creds = restored.list_credentials()
    assert len(creds) == 1 and creds[0].username == "alice"
    restored.close()


def test_resolve_by_path_and_name(file_store: NotebookStore) -> None:
    info = snap.create_snapshot(file_store)
    by_index = snap.resolve_snapshot(1, file_store)
    by_name = snap.resolve_snapshot(info.file_name, file_store)
    assert by_index == by_name
    with pytest.raises(IndexError):
        snap.resolve_snapshot(99, file_store)
    with pytest.raises(FileNotFoundError):
        snap.resolve_snapshot("does-not-exist.db", file_store)


def test_in_memory_requires_output_path() -> None:
    mem = NotebookStore(":memory:")
    with pytest.raises(ValueError):
        snap.create_snapshot(mem)
    assert snap.list_snapshots(mem) == []


def test_explicit_output_path_for_in_memory(tmp_path: Path) -> None:
    mem = NotebookStore(":memory:")
    t = mem.add_target("10.9.9.9")
    mem.add_note("mem note", target_id=t.id)
    out = tmp_path / "subdir" / "manual.db"
    info = snap.create_snapshot(mem, output_path=out)
    assert out.is_file()
    assert info.file_name == out.name

    reopened = NotebookStore(out)
    assert reopened.get_target_by_ip("10.9.9.9") is not None
    reopened.close()


def test_keep_must_be_positive(file_store: NotebookStore) -> None:
    with pytest.raises(ValueError):
        snap.create_snapshot(file_store, keep=0)


def test_prune_removes_old_snapshots(file_store: NotebookStore) -> None:
    for i in range(4):
        snap.create_snapshot(file_store, note=f"p{i}")
        time.sleep(1.02)
    removed = snap.prune_snapshots(file_store, keep=2)
    assert removed >= 2
    assert len(snap.list_snapshots(file_store)) == 2
