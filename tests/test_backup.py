"""Tests for the local snapshot safety net (backup / rotate / restore)."""

from __future__ import annotations

from pathlib import Path

import pytest

from glacis.backup import (
    SNAPSHOT_PATTERN,
    backups_dir,
    create_snapshot,
    list_snapshots,
    restore_snapshot,
)
from glacis.db.store import NotebookStore


def test_snapshot_pattern_matches() -> None:
    assert SNAPSHOT_PATTERN.match("glacis-snapshot-20260909-214900.json")
    assert SNAPSHOT_PATTERN.match("glacis-snapshot-20260909-214900-pre-enum.json")
    assert not SNAPSHOT_PATTERN.match("other-file.json")


def test_snapshot_create_and_list(store: NotebookStore, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    t = store.add_target("10.10.10.20", hostname="dc01")
    store.add_service(target_id=t.id, port=22, service="SSH")

    snap = create_snapshot(store, label="pre-enum")
    assert snap.path.exists()
    assert snap.size_bytes > 0
    assert "pre-enum" in snap.name
    assert snap.path.parent.name == "backups"

    snaps = list_snapshots(store)
    assert len(snaps) == 1
    assert snaps[0].name == snap.name

    payload = snap.path.read_text(encoding="utf-8")
    assert "10.10.10.20" in payload


def test_snapshot_rotation_keeps_newest(store: NotebookStore, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    store.add_target("10.10.10.20")

    for _ in range(7):
        create_snapshot(store, keep=3)
        import time
        time.sleep(0.02)  # ensure distinct timestamps

    snaps = list_snapshots(store)
    assert len(snaps) == 3
    # newest wins: the oldest four are gone
    names = [s.name for s in snaps]
    assert not any("20260101" in n for n in names)


def test_rotation_never_touches_foreign_files(store: NotebookStore, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    d = backups_dir(store)
    stranger = d / "glacis-snapshot-manual-keep.json"
    stranger.write_text("{}", encoding="utf-8")
    create_snapshot(store, keep=1)
    assert stranger.exists()  # non-timestamped snapshot name is untouched


def test_restore_creates_new_workspace(store: NotebookStore, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    t = store.add_target("10.10.10.20", hostname="dc01")
    store.add_service(target_id=t.id, port=22, service="SSH", version="OpenSSH 8.2")
    snap = create_snapshot(store)

    # Wipe all records (same DB, different workspace view)
    store.delete_target(t.id)
    assert store.list_targets() == []

    name = restore_snapshot(store, snap.path)
    assert "restored" in name
    targets = store.list_targets()
    assert len(targets) == 1
    assert targets[0].ip == "10.10.10.20"
    services = store.list_services(target_id=targets[0].id)
    assert services[0].version == "OpenSSH 8.2"

    # Restoring again never collides or overwrites
    name2 = restore_snapshot(store, snap.path)
    assert name2 != name
    ws2 = store.get_active_workspace()
    assert len(store.list_targets(workspace_id=ws2.id)) == 1
    assert len(store.list_workspaces()) >= 3


def test_restore_missing_file_raises(store: NotebookStore, tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        restore_snapshot(store, tmp_path / "nope.json")
