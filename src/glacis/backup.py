"""Local snapshot safety net for GLACIS workspaces.

Creates timestamped JSON snapshots of the active workspace (via the same
lossless ``export_json`` used by ``glacis export``) and rotates old ones so
your backups folder never grows unbounded.

* **Local only** — snapshots live under the workspace root ``backups/`` dir.
* **Lossless** — same round-trip format as the JSON export/import engine.
* **Deterministic** — rotation keeps the newest N (default 20) and never
  touches anything outside the GLACIS backups folder.

The TUI also takes one automatic snapshot per session on shutdown (see the
``auto_backup`` hook), so a crash never costs more than one session of notes.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from glacis.db.store import NotebookStore
from glacis.export import export_json, import_json

SNAPSHOT_PREFIX = "glacis-snapshot"
SNAPSHOT_SUFFIX = ".json"
SNAPSHOT_PATTERN = re.compile(
    rf"^{SNAPSHOT_PREFIX}-(\d{{8}})-(\d{{6}})(?:-[a-z0-9-]+)?{SNAPSHOT_SUFFIX}$"
)
DEFAULT_KEEP = 20


@dataclass(frozen=True)
class SnapshotInfo:
    """Metadata for one snapshot file on disk."""

    path: Path
    created_at: datetime
    size_bytes: int
    label: str = ""

    @property
    def name(self) -> str:
        return self.path.name


def backups_dir(store: NotebookStore) -> Path:
    """Snapshot folder: ``<workspace root>/backups`` (created on demand)."""
    d = store.get_workspace_root() / "backups"
    d.mkdir(parents=True, exist_ok=True)
    return d


def create_snapshot(
    store: NotebookStore,
    label: str = "",
    keep: int = DEFAULT_KEEP,
) -> SnapshotInfo:
    """Write one JSON snapshot of the active workspace, then rotate old ones.

    The filename embeds a UTC timestamp; a short slug derived from ``label``
    keeps manual snapshots recognisable. Returns the snapshot's metadata.
    """
    payload = export_json(store)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    suffix = ""
    if label:
        suffix = "-" + re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")[:24]
    directory = backups_dir(store)
    path = directory / f"{SNAPSHOT_PREFIX}-{stamp}{suffix}{SNAPSHOT_SUFFIX}"
    if path.exists():  # same-second collisions get a numeric bump
        n = 2
        while path.exists():
            path = directory / f"{SNAPSHOT_PREFIX}-{stamp}{suffix}-{n}{SNAPSHOT_SUFFIX}"
            n += 1
    path.write_text(payload, encoding="utf-8")
    rotate_snapshots(directory, keep=keep)
    return SnapshotInfo(
        path=path,
        created_at=datetime.now(timezone.utc),
        size_bytes=path.stat().st_size,
        label=label,
    )


def list_snapshots(store: NotebookStore) -> List[SnapshotInfo]:
    """All known snapshots, newest first."""
    directory = backups_dir(store)
    infos: List[SnapshotInfo] = []
    for p in sorted(directory.glob(f"{SNAPSHOT_PREFIX}-*{SNAPSHOT_SUFFIX}")):
        m = SNAPSHOT_PATTERN.match(p.name)
        created = None
        if m:
            try:
                created = datetime.strptime(
                    f"{m.group(1)}-{m.group(2)}", "%Y%m%d-%H%M%S"
                ).replace(tzinfo=timezone.utc)
            except ValueError:
                created = None
        if created is None:
            created = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
        infos.append(
            SnapshotInfo(
                path=p,
                created_at=created,
                size_bytes=p.stat().st_size,
            )
        )
    infos.sort(key=lambda i: i.created_at, reverse=True)
    return infos


def rotate_snapshots(directory: Path, keep: int = DEFAULT_KEEP) -> int:
    """Delete the oldest snapshots beyond ``keep``. Returns how many removed."""
    if keep <= 0:
        keep = DEFAULT_KEEP
    snaps: List[SnapshotInfo] = []
    for p in directory.glob(f"{SNAPSHOT_PREFIX}-*{SNAPSHOT_SUFFIX}"):
        if not SNAPSHOT_PATTERN.match(p.name):
            continue  # never rotate files we did not generate
        snaps.append(SnapshotInfo(p, datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc), p.stat().st_size))
    snaps.sort(key=lambda i: i.created_at, reverse=True)
    removed = 0
    for old in snaps[keep:]:
        try:
            old.path.unlink()
            removed += 1
        except OSError:
            continue
    return removed


def restore_snapshot(
    store: NotebookStore,
    snapshot_path: Path,
    workspace_name: Optional[str] = None,
) -> str:
    """Import a snapshot back into the local database as a new workspace.

    Restores never overwrite existing data: the snapshot becomes a fresh
    workspace (``<name>-restored`` by default) and is set active.
    """
    p = Path(snapshot_path).expanduser()
    if not p.is_file():
        raise FileNotFoundError(f"Snapshot not found: {p}")
    payload = json.loads(p.read_text(encoding="utf-8"))

    base_name = workspace_name
    if not base_name:
        ws = payload.get("workspace", {})
        base_name = f"{ws.get('name') or 'workspace'}-restored"
    existing = {w.name for w in store.list_workspaces()}
    final_name, n = base_name, 2
    while final_name in existing:
        final_name = f"{base_name}-{n}"
        n += 1

    restored = import_json(store, payload, workspace_name=final_name)
    store.set_active_workspace(restored.id)
    return final_name
