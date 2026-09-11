"""Local snapshot safety net for the GLACIS notebook database.

A snapshot is a byte-consistent, online copy of the SQLite notebook made with
the sqlite backup API (safe even while WAL mode is active), stored beside the
database in a ``snapshots/`` directory. Creation rotates the directory,
keeping the newest *N* snapshots; restore is a lossless file swap.

    snapshots/glacis-20260911-101530.db
    snapshots/index.json

Everything is local file IO: no network, no background jobs, no telemetry.
In-memory databases (``:memory:``) cannot be snapshotted to themselves, so
callers pass an explicit output path for them.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Union

from glacis.db.store import NotebookStore

INDEX_NAME = "index.json"
DEFAULT_KEEP = 5
SNAPSHOT_PREFIX = "glacis-"
SNAPSHOT_SUFFIX = ".db"


@dataclass
class SnapshotInfo:
    """Metadata describing one rotated snapshot."""

    file_name: str
    note: str
    created_at: str
    size_bytes: int
    workspace: str = ""

    @property
    def label(self) -> str:
        stamp = self.file_name[len(SNAPSHOT_PREFIX): -len(SNAPSHOT_SUFFIX)]
        return f"{stamp}  {self.size_bytes // 1024} KB  {self.note}"


def snapshots_dir_for(store_or_path: Union[NotebookStore, Path, str, None]) -> Path:
    """Return the snapshot directory next to a database file."""
    if isinstance(store_or_path, NotebookStore):
        db_path = Path(store_or_path.db_path)
    elif store_or_path is None:
        db_path = Path(NotebookStore().db_path)  # default discovery
    else:
        db_path = Path(store_or_path)
    return db_path.parent / "snapshots"


def _read_index(directory: Path) -> List[SnapshotInfo]:
    index_file = directory / INDEX_NAME
    if not index_file.is_file():
        return []
    try:
        raw = json.loads(index_file.read_text(encoding="utf-8"))
        return [SnapshotInfo(**item) for item in raw.get("snapshots", [])]
    except Exception:
        return []


def _write_index(directory: Path, entries: List[SnapshotInfo]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    payload = {"snapshots": [asdict(e) for e in entries]}
    (directory / INDEX_NAME).write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )


def list_snapshots(
    store_or_path: Union[NotebookStore, Path, str, None] = None,
    *,
    directory: Optional[Union[str, Path]] = None,
) -> List[SnapshotInfo]:
    """List snapshots newest-first for a database location."""
    directory = Path(directory) if directory is not None else snapshots_dir_for(store_or_path)
    entries = _read_index(directory)
    known = {e.file_name for e in entries}

    # Also discover orphaned snapshot files not present in the index.
    if directory.is_dir():
        for db_file in sorted(directory.glob(f"{SNAPSHOT_PREFIX}*{SNAPSHOT_SUFFIX}"), reverse=True):
            if db_file.name not in known:
                entries.append(
                    SnapshotInfo(
                        file_name=db_file.name,
                        note="",
                        created_at=datetime.fromtimestamp(
                            db_file.stat().st_mtime, tz=timezone.utc
                        ).isoformat(),
                        size_bytes=db_file.stat().st_size,
                    )
                )
    entries.sort(key=lambda e: e.file_name, reverse=True)
    return entries


def create_snapshot(
    store: NotebookStore,
    note: str = "",
    *,
    keep: int = DEFAULT_KEEP,
    output_path: Optional[Union[str, Path]] = None,
) -> SnapshotInfo:
    """Create a consistent backup of ``store`` and rotate older snapshots.

    ``keep`` retains at most that many snapshots (oldest deleted). For an
    on-disk database the snapshot lands in the adjacent ``snapshots/`` folder;
    pass ``output_path`` for an in-memory source.
    """
    if keep < 1:
        raise ValueError("keep must be >= 1")

    source_path = Path(store.db_path)
    if output_path is not None:
        target = Path(output_path)
        directory = target.parent
    else:
        if str(source_path) == ":memory:":
            raise ValueError(
                "in-memory databases require an explicit output_path for snapshots"
            )
        directory = source_path.parent / "snapshots"
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        target = directory / f"{SNAPSHOT_PREFIX}{stamp}{SNAPSHOT_SUFFIX}"

    # Disambiguate within the same second.
    counter = 1
    while target.exists():
        target = target.with_name(
            f"{target.stem}-{counter}{target.suffix}"
        )
        counter += 1

    directory.mkdir(parents=True, exist_ok=True)

    # Online backup API: consistent copy even while transactions are in flight.
    try:
        with sqlite3.connect(str(target)) as dest_conn:
            store.conn.backup(dest_conn)
            dest_conn.execute("PRAGMA wal_checkpoint(FULL);")
    except Exception:
        target.unlink(missing_ok=True)
        raise

    ws_name = ""
    try:
        ws_name = store.get_active_workspace().name
    except Exception:
        ws_name = ""

    info = SnapshotInfo(
        file_name=target.name,
        note=(note or "").strip()[:200],
        created_at=datetime.now(timezone.utc).isoformat(),
        size_bytes=target.stat().st_size,
        workspace=ws_name,
    )

    existing = (
        list_snapshots(directory=directory)
        if output_path is not None
        else list_snapshots(source_path)
    )
    entries = [e for e in existing if e.file_name != info.file_name]
    entries.insert(0, info)

    # Rotation: keep newest N files; prune index + disk together.
    kept = entries[:keep]
    for stale in entries[keep:]:
        (directory / stale.file_name).unlink(missing_ok=True)
    _write_index(directory, kept)

    return info


def resolve_snapshot(
    reference: Union[str, int],
    store_or_path: Union[NotebookStore, Path, str, None] = None,
) -> Path:
    """Resolve a snapshot by 1-based newest-first index, name or path."""
    entries = list_snapshots(store_or_path)
    if isinstance(reference, int) or (isinstance(reference, str) and reference.isdigit()):
        idx = int(reference) - 1
        if idx < 0 or idx >= len(entries):
            raise IndexError(
                f"snapshot #{int(reference)} does not exist (have {len(entries)})"
            )
        return snapshots_dir_for(store_or_path) / entries[idx].file_name
    candidate = Path(str(reference))
    if candidate.is_file():
        return candidate
    directory = snapshots_dir_for(store_or_path)
    candidate = directory / str(reference)
    if candidate.is_file():
        return candidate
    raise FileNotFoundError(f"snapshot not found: {reference!r}")


def restore_snapshot(
    snapshot: Union[str, Path],
    db_path: Union[str, Path],
) -> Path:
    """Restore a snapshot file over ``db_path`` (closed connection recommended).

    WAL/SHM sidecars from the live database are removed first so SQLite cannot
    replay newer journal pages on top of the older snapshot. Returns the
    restored path.
    """
    source = Path(snapshot)
    if not source.is_file():
        raise FileNotFoundError(f"snapshot file missing: {source}")
    target = Path(db_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    for suffix in ("-wal", "-shm"):
        target.with_name(target.name + suffix).unlink(missing_ok=True)
    shutil.copy2(source, target)
    return target


def prune_snapshots(
    store_or_path: Union[NotebookStore, Path, str, None] = None,
    *,
    keep: int = DEFAULT_KEEP,
) -> int:
    """Explicitly rotate the snapshot directory; returns how many were removed."""
    directory = snapshots_dir_for(store_or_path)
    if not directory.is_dir():
        return 0
    entries = list_snapshots(store_or_path)
    removed = 0
    for stale in entries[keep:]:
        (directory / stale.file_name).unlink(missing_ok=True)
        removed += 1
    _write_index(directory, entries[:keep])
    return removed
