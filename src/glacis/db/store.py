"""Local SQLite repository for CYB0X-S.

High performance, zero network footprint, fully ACID-compliant.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from glacis.db.schema import SCHEMA_SQL
from glacis.models import (
    ChecklistItem,
    ChecklistStatus,
    CommandRecord,
    Credential,
    Evidence,
    ExamProof,
    FailureLog,
    Finding,
    Lead,
    Note,
    ScanImport,
    Service,
    ServiceStatus,
    Target,
    Workspace,
)

CURRENT_SCHEMA_VERSION = 3


def _iso_now() -> str:
    """Return current UTC timestamp in ISO 8601 string format."""
    return datetime.now(timezone.utc).isoformat()


def detect_local_vpn_ip() -> Optional[str]:
    """Detect local local VPN IP (prioritizing tun*, wg*, tap* interfaces)."""
    try:
        import subprocess

        res = subprocess.run(
            ["ip", "-4", "-o", "addr", "show"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if res.returncode == 0:
            lines = res.stdout.strip().splitlines()
            # 1. First priority: VPN / tunnel interfaces
            for line in lines:
                parts = line.split()
                if len(parts) >= 4:
                    iface = parts[1]
                    ip = parts[3].split("/")[0]
                    if any(iface.startswith(p) for p in ("tun", "wg", "tap")):
                        return ip
            # 2. Second priority: any non-loopback global interface
            for line in lines:
                parts = line.split()
                if len(parts) >= 4:
                    iface = parts[1]
                    ip = parts[3].split("/")[0]
                    if iface != "lo" and not ip.startswith("127."):
                        return ip
    except Exception:
        pass

    # Fallback: query local interface addresses only. `hostname -I` reads the
    # interface table without creating any socket or touching the network
    # stack — important for exam-proctored environments where even a
    # loopback-free socket syscall looks suspicious.
    try:
        res = subprocess.run(
            ["hostname", "-I"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if res.returncode == 0:
            for ip in res.stdout.split():
                if ip and not ip.startswith("127."):
                    return ip.strip()
    except Exception:
        pass

    return None


def get_default_db_path() -> Path:
    """Determine the database storage location."""
    env_path = os.environ.get("GLACIS_DB") or os.environ.get("CYB0X_S_DB") or os.environ.get("CYB0X_DB")
    if env_path:
        return Path(env_path)

    # If local workspace folder exists, use it (.glacis favored, .cyb0x-s fallback)
    local_glacis = Path(".glacis")
    if local_glacis.is_dir():
        return local_glacis / "notebook.db"
    local_cybox = Path(".cyb0x-s")
    if local_cybox.is_dir():
        return local_cybox / "notebook.db"

    # Default to user XDG data dir
    data_home = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    base_dir = data_home / "glacis"
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir / "notebook.db"


class NotebookStore:
    """Thread-safe, local SQLite storage engine for GLACIS."""

    def __init__(self, db_path: Optional[Union[str, Path]] = None):
        if db_path is None:
            self.db_path = get_default_db_path()
        elif str(db_path) == ":memory:":
            self.db_path = Path(":memory:")
        else:
            self.db_path = Path(db_path)
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA busy_timeout = 3000;")
        self.conn.execute("PRAGMA temp_store = MEMORY;")
        try:
            self.conn.execute("PRAGMA journal_mode = WAL;")
            self.conn.execute("PRAGMA synchronous = NORMAL;")
            # TUI smoothness on modest hardware: bounded WAL checkpoints
            # avoid write hitches during capture bursts; a warm page cache
            # keeps repeated roster queries hot.
            self.conn.execute("PRAGMA wal_autocheckpoint = 512;")
            self.conn.execute("PRAGMA cache_size = -8000;")  # ~8 MB
        except Exception:
            pass  # :memory: and some filesystems cannot do WAL
        self.init_schema()
        try:
            self._ensure_list_indexes()
        except Exception:
            pass  # indexes are an optimisation; never block startup

    # Index maintenance is deliberately outside SCHEMA_SQL so fresh and
    # legacy databases converge on the same optimised shape at startup.
    _LIST_INDEX_SQL = (
        # Roster fast paths: ORDER BY id ASC scans per target/workspace.
        "CREATE INDEX IF NOT EXISTS idx_services_target_id_id ON services(target_id, id)",
        "CREATE INDEX IF NOT EXISTS idx_findings_target_id_id ON findings(target_id, id)",
        "CREATE INDEX IF NOT EXISTS idx_credentials_target_id_id ON credentials(target_id, id)",
        "CREATE INDEX IF NOT EXISTS idx_leads_target_id_id ON leads(target_id, id)",
        "CREATE INDEX IF NOT EXISTS idx_evidence_target_id_id ON evidence(target_id, id)",
        "CREATE INDEX IF NOT EXISTS idx_notes_target_id_id ON notes(target_id, id)",
        "CREATE INDEX IF NOT EXISTS idx_checklist_target_id_id ON checklist(target_id, id)",
        "CREATE INDEX IF NOT EXISTS idx_failures_target_id_id ON failure_log(target_id, id)",
        "CREATE INDEX IF NOT EXISTS idx_proofs_target_id_id ON exam_proofs(target_id, id)",
        "CREATE INDEX IF NOT EXISTS idx_commands_target_id_id ON command_history(target_id, id)",
        "CREATE INDEX IF NOT EXISTS idx_cred_validations_target_id_id ON cred_validations(target_id, id)",
        "CREATE INDEX IF NOT EXISTS idx_scan_imports_target_id_id ON scan_imports(target_id, id)",
        # Pulse fingerprints & workspace filters.
        "CREATE INDEX IF NOT EXISTS idx_targets_workspace_id_id ON targets(workspace_id, id)",
    )

    def _ensure_list_indexes(self) -> None:
        """Create/refresh the per-list composite indexes (idempotent)."""
        cur = self.conn.cursor()
        for stmt in self._LIST_INDEX_SQL:
            cur.execute(stmt)
        self.conn.commit()

    def init_schema(self) -> None:
        """Run initial DDL script, migrations, and ensure a default workspace exists."""
        cur = self.conn.cursor()
        cur.execute("PRAGMA user_version")
        row = cur.fetchone()
        current_version = row[0] if row else 0

        # Determine lab root path if database is located in a .glacis or .cyb0x-s directory
        lab_root = ""
        if self.db_path != Path(":memory:") and self.db_path.parent.name in (".glacis", ".cyb0x-s"):
            lab_root = str(self.db_path.parent.parent.resolve())

        is_fresh_db = False
        with self.conn:
            self.conn.executescript(SCHEMA_SQL)
            cur = self.conn.cursor()
            cur.execute("SELECT id FROM workspaces WHERE name = 'default'")
            row = cur.fetchone()
            if not row:
                is_fresh_db = True
                now = _iso_now()
                cur.execute(
                    "INSERT INTO workspaces (name, description, root_path, created_at, updated_at) VALUES ('default', 'Default assessment workspace', ?, ?, ?)",
                    (lab_root, now, now),
                )
                ws_id = cur.lastrowid
            else:
                ws_id = row["id"]
                if lab_root:
                    cur.execute("SELECT root_path FROM workspaces WHERE id = ?", (ws_id,))
                    rp_row = cur.fetchone()
                    if not rp_row or not rp_row["root_path"] or rp_row["root_path"] != lab_root:
                        cur.execute("UPDATE workspaces SET root_path = ? WHERE id = ?", (lab_root, ws_id))

            cur.execute("SELECT value FROM settings WHERE key = 'active_workspace'")
            if not cur.fetchone():
                cur.execute(
                    "INSERT INTO settings (key, value) VALUES ('active_workspace', ?)",
                    (str(ws_id),),
                )

            # Auto-normalize existing evidence & scan imports paths to relative if inside lab_root
            if lab_root:
                prefix = lab_root.rstrip("/") + "/"
                cur.execute(
                    "UPDATE evidence SET path_or_ref = substr(path_or_ref, ?) WHERE path_or_ref LIKE ?",
                    (len(prefix) + 1, prefix + "%"),
                )
                cur.execute(
                    "UPDATE scan_imports SET file_path = substr(file_path, ?) WHERE file_path LIKE ?",
                    (len(prefix) + 1, prefix + "%"),
                )

        if is_fresh_db:
            # Newly initialized database already created with complete up-to-date schema
            with self.conn:
                self.conn.execute(f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION};")
        elif current_version < CURRENT_SCHEMA_VERSION:
            # Upgrade existing pre-versioned database
            migration_cols = [
                ("workspaces", "root_path", "TEXT DEFAULT ''"),
                ("targets", "initial_access_vuln", "TEXT DEFAULT ''"),
                ("targets", "foothold_cmd", "TEXT DEFAULT ''"),
                ("targets", "foothold_context", "TEXT DEFAULT ''"),
                ("targets", "privesc_vector", "TEXT DEFAULT ''"),
                ("targets", "root_proof", "TEXT DEFAULT ''"),
                ("targets", "user_flag", "TEXT DEFAULT ''"),
                ("targets", "root_flag", "TEXT DEFAULT ''"),
                ("targets", "subnet", "TEXT DEFAULT ''"),
                ("targets", "is_pivot", "INTEGER DEFAULT 0"),
                ("targets", "pivot_route", "TEXT DEFAULT ''"),
                ("targets", "is_in_scope", "INTEGER DEFAULT 1"),
                ("services", "access_potential", "TEXT DEFAULT ''"),
                ("services", "next_action", "TEXT DEFAULT ''"),
                ("command_history", "is_golden", "INTEGER DEFAULT 0"),
                ("command_history", "step", "TEXT DEFAULT ''"),
            ]
            for tbl, col, ctype in migration_cols:
                try:
                    with self.conn:
                        self.conn.execute(f"ALTER TABLE {tbl} ADD COLUMN {col} {ctype};")
                except Exception:
                    pass

            try:
                with self.conn:
                    self.conn.execute("""
                        CREATE TABLE IF NOT EXISTS scan_imports (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            workspace_id INTEGER NOT NULL,
                            target_id INTEGER,
                            file_path TEXT NOT NULL,
                            file_hash TEXT NOT NULL,
                            scan_type TEXT DEFAULT 'nmap',
                            imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY(workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
                            FOREIGN KEY(target_id) REFERENCES targets(id) ON DELETE SET NULL,
                            UNIQUE(workspace_id, file_hash)
                        );
                    """)
                    self.conn.execute("CREATE INDEX IF NOT EXISTS idx_scan_imports_ws ON scan_imports(workspace_id);")
                    self.conn.execute("CREATE INDEX IF NOT EXISTS idx_scan_imports_target ON scan_imports(target_id);")
            except Exception:
                pass

            with self.conn:
                self.conn.execute(f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION};")

        # Backfill FTS index if database had records but empty FTS index
        try:
            cur = self.conn.cursor()
            cur.execute("SELECT count(*) FROM notebook_fts")
            fts_count = cur.fetchone()[0]
            if fts_count == 0:
                cur.execute("SELECT (SELECT count(*) FROM targets) + (SELECT count(*) FROM notes)")
                count_row = cur.fetchone()
                if count_row and count_row[0] > 0:
                    self.rebuild_fts()
        except Exception:
            pass

    def rebuild_fts(self) -> None:
        """Repopulate the FTS5 full-text search index across all notebook tables."""
        with self.conn:
            self.conn.execute("DELETE FROM notebook_fts;")
            # Notes
            self.conn.execute("""
                INSERT INTO notebook_fts (entity_type, entity_id, target_id, title, content, tags)
                SELECT 'note', id, target_id, 'Field Note', content, '' FROM notes;
            """)
            # Targets
            self.conn.execute("""
                INSERT INTO notebook_fts (entity_type, entity_id, target_id, title, content, tags)
                SELECT 'target', id, id, 'Target: ' || ip || ' (' || coalesce(hostname, 'no host') || ')',
                       'OS: ' || coalesce(os, '') || ' | Notes: ' || coalesce(notes, '') || ' | Vuln: ' || coalesce(initial_access_vuln, '') || ' | Foothold: ' || coalesce(foothold_cmd, '') || ' | PrivEsc: ' || coalesce(privesc_vector, '') || ' | Root: ' || coalesce(root_proof, '') || ' | Flags: ' || coalesce(user_flag, '') || ' ' || coalesce(root_flag, ''),
                       coalesce(subnet, '')
                FROM targets;
            """)
            # Services
            self.conn.execute("""
                INSERT INTO notebook_fts (entity_type, entity_id, target_id, title, content, tags)
                SELECT 'service', id, target_id, 'Service: ' || port || '/' || protocol || ' ' || service,
                       'Version: ' || coalesce(version, '') || ' [' || status || '] ' || coalesce(notes, '') || ' ' || coalesce(next_action, ''),
                       coalesce(service, '')
                FROM services;
            """)
            # Findings
            self.conn.execute("""
                INSERT INTO notebook_fts (entity_type, entity_id, target_id, title, content, tags)
                SELECT 'finding', id, target_id, 'Finding' || case when target_id is null then ' (Global): ' else ': ' end || title,
                       'Sev: ' || coalesce(severity, 'manual') || ' | ' || coalesce(description, '') || ' | ' || coalesce(notes, ''),
                       coalesce(severity, 'manual')
                FROM findings;
            """)
            # Credentials
            self.conn.execute("""
                INSERT INTO notebook_fts (entity_type, entity_id, target_id, title, content, tags)
                SELECT 'credential', id, target_id, 'Credential: ' || username || ' : ********',
                       'Scope: ' || coalesce(service_scope, '') || ' | Source: ' || coalesce(source, '') || ' [' || status || '] ' || coalesce(notes, ''),
                       status
                FROM credentials;
            """)
            # Checklist
            self.conn.execute("""
                INSERT INTO notebook_fts (entity_type, entity_id, target_id, title, content, tags)
                SELECT 'checklist', id, target_id, 'Checklist [' || status || ']: ' || title,
                       'Category: ' || category || ' | ' || coalesce(notes, ''),
                       category
                FROM checklist;
            """)
            # Evidence
            self.conn.execute("""
                INSERT INTO notebook_fts (entity_type, entity_id, target_id, title, content, tags)
                SELECT 'evidence', id, target_id, 'Evidence (' || evidence_type || '): ' || path_or_ref,
                       coalesce(description, ''),
                       evidence_type
                FROM evidence;
            """)
            # Commands
            self.conn.execute("""
                INSERT INTO notebook_fts (entity_type, entity_id, target_id, title, content, tags)
                SELECT 'command', id, target_id, 'Command: ' || command,
                       'Step: ' || coalesce(step, '') || ' | ' || coalesce(notes, ''),
                       case when is_golden = 1 then 'golden' else 'cmd' end
                FROM command_history;
            """)
            # Leads
            self.conn.execute("""
                INSERT INTO notebook_fts (entity_type, entity_id, target_id, title, content, tags)
                SELECT 'lead', id, target_id, 'Lead: ' || title,
                       'Status: ' || status || ' | ' || coalesce(notes, ''),
                       status
                FROM leads;
            """)
            # Exam / Objective Proofs
            self.conn.execute("""
                INSERT INTO notebook_fts (entity_type, entity_id, target_id, title, content, tags)
                SELECT 'proof', id, target_id, 'Objective [' || question_num || ']: ' || category,
                       'Proof: ' || answer_proof || ' | ' || coalesce(notes, ''),
                       category
                FROM exam_proofs;
            """)

    def close(self) -> None:
        """Close SQLite database connection."""
        self.conn.close()

    # -------------------------------------------------------------------------
    # Workspaces & Settings
    # -------------------------------------------------------------------------

    def get_or_create_workspace(
        self, name: str = "default", description: str = "", root_path: str = ""
    ) -> Workspace:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM workspaces WHERE name = ?", (name,))
        row = cur.fetchone()
        if row:
            ws = Workspace(**dict(row))
            if root_path and ws.root_path != root_path:
                self.update_workspace(ws.id, root_path=root_path)
                return self.get_workspace(ws.id)  # type: ignore
            return ws
        now = _iso_now()
        with self.conn:
            cur.execute(
                "INSERT INTO workspaces (name, description, root_path, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (name, description, root_path, now, now),
            )
            ws_id = cur.lastrowid
        return self.get_workspace(ws_id)  # type: ignore

    def update_workspace(
        self,
        workspace_id: int,
        name: Optional[str] = None,
        description: Optional[str] = None,
        root_path: Optional[str] = None,
    ) -> Optional[Workspace]:
        ws = self.get_workspace(workspace_id)
        if not ws:
            return None
        new_name = name.strip() if name is not None else ws.name
        new_desc = description.strip() if description is not None else ws.description
        new_root = str(root_path).strip() if root_path is not None else ws.root_path
        now = _iso_now()
        with self.conn:
            self.conn.execute(
                "UPDATE workspaces SET name = ?, description = ?, root_path = ?, updated_at = ? WHERE id = ?",
                (new_name, new_desc, new_root, now, workspace_id),
            )
        return self.get_workspace(workspace_id)

    def get_workspace_root(self, workspace: Optional[Workspace] = None) -> Path:
        """Return the filesystem root for the workspace, favoring local .glacis/.cyb0x-s parent if active."""
        if self.db_path != Path(":memory:") and self.db_path.parent.name in (".glacis", ".cyb0x-s"):
            return self.db_path.parent.parent.resolve()

        ws = workspace or self.get_active_workspace()
        if ws and ws.root_path:
            p = Path(ws.root_path).expanduser().resolve()
            if p.exists() or p.is_dir():
                return p

        if (Path.cwd() / ".glacis").is_dir() or (Path.cwd() / ".cyb0x-s").is_dir():
            return Path.cwd().resolve()

        if ws and ws.root_path:
            return Path(ws.root_path).expanduser().resolve()

        return Path.cwd().resolve()

    def relativize_path(
        self,
        path_str: str,
        workspace: Optional[Workspace] = None,
    ) -> str:
        """Convert an absolute path to a workspace-relative path (e.g. scans/nmap.xml) if inside workspace root."""
        cleaned = str(path_str).strip()
        if not cleaned:
            return cleaned

        p = Path(cleaned)
        if not p.is_absolute():
            return cleaned

        ws_root = self.get_workspace_root(workspace)
        try:
            rel = p.resolve().relative_to(ws_root.resolve())
            return str(rel)
        except (ValueError, OSError, RuntimeError):
            return cleaned

    def init_workspace_directory(
        self,
        name: str,
        target_dir: Union[str, Path],
        description: str = "",
        create_local_db: bool = True,
    ) -> tuple[Workspace, Path]:
        """Initialize a dedicated assessment workspace directory with standard folder scaffolding."""
        base_path = Path(target_dir).expanduser().resolve()
        base_path.mkdir(parents=True, exist_ok=True)

        subdirs = ["scans", "enum", "screenshots", "notes", "loot"]
        for sub in subdirs:
            (base_path / sub).mkdir(parents=True, exist_ok=True)

        findings_file = base_path / "findings.md"
        if not findings_file.exists():
            date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            template_text = (
                f"# Assessment Findings Report: {name}\n\n"
                f"**Workspace**: {name}  \n"
                f"**Date**: {date_str}  \n"
                f"**Status**: In Progress  \n\n"
                f"## Executive Summary\n"
                f"Brief summary of engagement objectives, scope, and key risks identified.\n\n"
                f"## Scope & Target Overview\n"
                f"| Target IP | Hostname | OS | Foothold | User Flag | Root Flag |\n"
                f"|-----------|----------|----|----------|-----------|-----------|\n\n"
                f"## High-Risk Findings & Vulnerabilities\n"
                f"<!-- Document key findings, vulnerabilities, and exploitation paths below -->\n\n"
                f"## Proof & Evidence Index\n"
                f"- Scans: `scans/`\n"
                f"- Enumeration: `enum/`\n"
                f"- Screenshots: `screenshots/`\n"
                f"- Loot & Artifacts: `loot/`\n"
            )
            findings_file.write_text(template_text, encoding="utf-8")

        if create_local_db:
            local_glacis_dir = base_path / ".glacis"
            local_glacis_dir.mkdir(parents=True, exist_ok=True)
            local_db_file = local_glacis_dir / "notebook.db"
            if not local_db_file.exists():
                local_store = NotebookStore(local_db_file)
                ws_local = local_store.get_active_workspace()
                local_store.update_workspace(
                    ws_local.id,
                    name=name,
                    description=description,
                    root_path=str(base_path),
                )
                local_store.close()

        ws = self.get_or_create_workspace(name=name, description=description, root_path=str(base_path))
        self.set_active_workspace(ws.id)
        return ws, base_path

    def resolve_evidence_path(
        self,
        evidence: Union[Evidence, str],
        workspace: Optional[Workspace] = None,
    ) -> Path:
        """Resolve an evidence path relative to workspace root or current directory."""
        raw_path_str = evidence.path_or_ref if isinstance(evidence, Evidence) else str(evidence)
        raw_path = Path(raw_path_str)
        if raw_path.is_absolute():
            return raw_path

        ws_root = self.get_workspace_root(workspace)
        return ws_root / raw_path

    def record_scan_import(
        self,
        workspace_id: int,
        file_path: str,
        file_hash: str,
        target_id: Optional[int] = None,
        scan_type: str = "nmap",
    ) -> ScanImport:
        """Record an imported scan file to avoid duplicate re-processing."""
        now = _iso_now()
        cur = self.conn.cursor()
        with self.conn:
            cur.execute(
                """INSERT OR REPLACE INTO scan_imports (workspace_id, target_id, file_path, file_hash, scan_type, imported_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (workspace_id, target_id, file_path, file_hash, scan_type, now),
            )
            import_id = cur.lastrowid
        return ScanImport(
            id=import_id,
            workspace_id=workspace_id,
            target_id=target_id,
            file_path=file_path,
            file_hash=file_hash,
            scan_type=scan_type,
        )

    def get_scan_import(self, workspace_id: int, file_hash: str) -> Optional[ScanImport]:
        """Check if a scan file has already been imported into this workspace."""
        cur = self.conn.cursor()
        cur.execute(
            "SELECT * FROM scan_imports WHERE workspace_id = ? AND file_hash = ?",
            (workspace_id, file_hash),
        )
        row = cur.fetchone()
        return ScanImport(**dict(row)) if row else None

    def list_scan_imports(
        self, workspace_id: Optional[int] = None, target_id: Optional[int] = None
    ) -> List[ScanImport]:
        cur = self.conn.cursor()
        query = "SELECT * FROM scan_imports WHERE 1=1"
        params: list[Any] = []
        if workspace_id is not None:
            query += " AND workspace_id = ?"
            params.append(workspace_id)
        if target_id is not None:
            query += " AND target_id = ?"
            params.append(target_id)
        query += " ORDER BY id DESC"
        cur.execute(query, tuple(params))
        return [ScanImport(**dict(r)) for r in cur.fetchall()]

    def get_workspace(self, workspace_id: int) -> Optional[Workspace]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM workspaces WHERE id = ?", (workspace_id,))
        row = cur.fetchone()
        return Workspace(**dict(row)) if row else None

    def list_workspaces(self) -> List[Workspace]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM workspaces ORDER BY id ASC")
        return [Workspace(**dict(r)) for r in cur.fetchall()]

    def set_active_workspace(self, name_or_id: Union[str, int]) -> Workspace:
        cur = self.conn.cursor()
        if isinstance(name_or_id, int) or str(name_or_id).isdigit():
            cur.execute("SELECT * FROM workspaces WHERE id = ?", (int(name_or_id),))
        else:
            cur.execute("SELECT * FROM workspaces WHERE name = ?", (str(name_or_id),))
        row = cur.fetchone()
        if not row:
            return self.get_or_create_workspace(str(name_or_id))
        ws = Workspace(**dict(row))
        with self.conn:
            self.conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES ('active_workspace', ?)",
                (str(ws.id),),
            )
        return ws

    def get_active_workspace(self) -> Workspace:
        cur = self.conn.cursor()
        cur.execute("SELECT value FROM settings WHERE key = 'active_workspace'")
        row = cur.fetchone()
        if row:
            ws = self.get_workspace(int(row["value"]))
            if ws:
                return ws
        return self.get_or_create_workspace("default")

    def set_active_target(self, ip_or_id: Union[str, int]) -> Optional[Target]:
        target = self.resolve_target(ip_or_id)
        if target:
            with self.conn:
                self.conn.execute(
                    "INSERT OR REPLACE INTO settings (key, value) VALUES ('active_target', ?)",
                    (str(target.id),),
                )
        return target

    def get_active_target(self, workspace_id: Optional[int] = None) -> Optional[Target]:
        ws_id = workspace_id or self.get_active_workspace().id
        cur = self.conn.cursor()
        cur.execute("SELECT value FROM settings WHERE key = 'active_target'")
        row = cur.fetchone()
        if row and row["value"]:
            try:
                target_id = int(row["value"])
                target = self.get_target(target_id)
                if target and target.workspace_id == ws_id:
                    return target
            except (ValueError, TypeError):
                pass
        targets = self.list_targets(workspace_id=ws_id)
        return targets[0] if targets else None

    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Retrieve a key-value setting from the notebook database."""
        cur = self.conn.cursor()
        cur.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cur.fetchone()
        if row and row["value"] is not None:
            return str(row["value"])
        return default

    def set_setting(self, key: str, value: str) -> None:
        """Store or update a key-value setting in the notebook database."""
        with self.conn:
            self.conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                (key, str(value)),
            )

    def get_lhost(self) -> str:
        """Get local LHOST from settings, or empty string if unset."""
        return self.get_setting("lhost", "") or ""

    def set_lhost(self, ip: str) -> None:
        """Store local LHOST in settings."""
        self.set_setting("lhost", ip.strip())

    def get_lport(self) -> str:
        """Get local LPORT from settings, default '4444'."""
        return self.get_setting("lport", "4444") or "4444"

    def set_lport(self, port: Union[int, str]) -> None:
        """Store local LPORT in settings."""
        self.set_setting("lport", str(port).strip())

    # -------------------------------------------------------------------------
    # Targets
    # -------------------------------------------------------------------------

    def add_target(
        self,
        ip: str,
        hostname: str = "",
        os_name: str = "Unknown",
        notes: str = "",
        workspace_id: Optional[int] = None,
        set_active: bool = True,
    ) -> Target:
        ws_id = workspace_id or self.get_active_workspace().id
        ip_clean = ip.strip()
        cur = self.conn.cursor()
        cur.execute(
            "SELECT * FROM targets WHERE workspace_id = ? AND ip = ?",
            (ws_id, ip_clean),
        )
        row = cur.fetchone()
        now = _iso_now()
        notes_clean = notes if isinstance(notes, str) else str(notes)
        if row:
            target_id = row["id"]
            new_hostname = hostname if hostname else row["hostname"]
            new_os = os_name if os_name != "Unknown" else row["os"]
            new_notes = notes_clean if notes_clean else row["notes"]
            with self.conn:
                self.conn.execute(
                    """UPDATE targets
                       SET hostname = ?, os = ?, notes = ?, updated_at = ?
                       WHERE id = ?""",
                    (new_hostname, new_os, new_notes, now, target_id),
                )
            target = self.get_target(target_id)
        else:
            with self.conn:
                cur.execute(
                    """INSERT INTO targets (workspace_id, ip, hostname, os, notes, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (ws_id, ip_clean, hostname.strip(), os_name.strip(), notes_clean.strip(), now, now),
                )
                target_id = cur.lastrowid
            target = self.get_target(target_id)

        if target:
            if set_active:
                self.set_active_target(target.id)
        return target  # type: ignore

    def get_target(self, target_id: int) -> Optional[Target]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM targets WHERE id = ?", (target_id,))
        row = cur.fetchone()
        return Target(**dict(row)) if row else None

    def get_target_by_ip(self, ip: str, workspace_id: Optional[int] = None) -> Optional[Target]:
        ws_id = workspace_id or self.get_active_workspace().id
        cur = self.conn.cursor()
        cur.execute(
            "SELECT * FROM targets WHERE workspace_id = ? AND (ip = ? OR hostname = ?)",
            (ws_id, ip.strip(), ip.strip()),
        )
        row = cur.fetchone()
        return Target(**dict(row)) if row else None

    def resolve_target(
        self, ip_or_id: Optional[Union[str, int]], workspace_id: Optional[int] = None
    ) -> Optional[Target]:
        if ip_or_id is None:
            return self.get_active_target(workspace_id)
        if isinstance(ip_or_id, int) or (isinstance(ip_or_id, str) and ip_or_id.isdigit()):
            target = self.get_target(int(ip_or_id))
            if target:
                return target
        return self.get_target_by_ip(str(ip_or_id), workspace_id)

    def list_targets(self, workspace_id: Optional[int] = None) -> List[Target]:
        ws_id = workspace_id or self.get_active_workspace().id
        cur = self.conn.cursor()
        cur.execute(
            "SELECT * FROM targets WHERE workspace_id = ? ORDER BY id ASC", (ws_id,)
        )
        return [Target(**dict(r)) for r in cur.fetchall()]

    def delete_target(self, target_id: int) -> bool:
        with self.conn:
            res = self.conn.execute("DELETE FROM targets WHERE id = ?", (target_id,))
            deleted = res.rowcount > 0
            if deleted:
                cur = self.conn.cursor()
                cur.execute("SELECT value FROM settings WHERE key = 'active_target'")
                row = cur.fetchone()
                if row and row["value"] == str(target_id):
                    self.conn.execute("DELETE FROM settings WHERE key = 'active_target'")
            return deleted

    def get_target_counts(self, target_id: Optional[int] = None) -> dict[str, int]:
        """Fetch entity counts for a target in a single fast, index-backed SQL query."""
        if target_id is None:
            return {"ports": 0, "creds": 0, "vulns": 0, "notes": 0, "dead_ends": 0, "failures": 0}
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM services WHERE target_id = ?) AS ports,
                (SELECT COUNT(*) FROM credentials WHERE target_id = ?) AS creds,
                (SELECT COUNT(*) FROM findings WHERE target_id = ?) AS vulns,
                (SELECT COUNT(*) FROM notes WHERE target_id = ?) AS notes,
                (SELECT COUNT(*) FROM checklist WHERE target_id = ? AND status = 'DEAD-END') AS dead_ends,
                (SELECT COUNT(*) FROM failure_log WHERE target_id = ?) AS failures
            """,
            (target_id, target_id, target_id, target_id, target_id, target_id),
        )
        row = cur.fetchone()
        if row:
            return dict(row)
        return {"ports": 0, "creds": 0, "vulns": 0, "notes": 0, "dead_ends": 0, "failures": 0}

    def ingest_scan_results(
        self, parsed_targets: List[Dict[str, Any]], workspace_id: Optional[int] = None
    ) -> tuple[int, int]:
        """Ingest parsed targets and services into the active workspace.

        Returns:
            (targets_added, services_added)
        """
        ws_id = workspace_id or self.get_active_workspace().id
        targets_added = 0
        services_added = 0

        for pt in parsed_targets:
            ip = pt.get("ip", "").strip()
            if not ip:
                continue

            target = self.get_target_by_ip(ip, workspace_id=ws_id)
            if not target:
                target = self.add_target(
                    ip=ip,
                    hostname=pt.get("hostname", ""),
                    os_name=pt.get("os", "Unknown"),
                    workspace_id=ws_id,
                    set_active=False,
                )
                targets_added += 1
            else:
                # Update hostname/OS if previously unknown
                if pt.get("hostname") and not target.hostname:
                    self.update_target_details(target.id, hostname=pt["hostname"])
                if pt.get("os") and pt["os"] != "Unknown" and target.os_name == "Unknown":
                    self.update_target_details(target.id, os_name=pt["os"])

            existing_services = {
                (s.port, s.protocol.lower()): s for s in self.list_services(target.id)
            }

            for s in pt.get("services", []):
                port = int(s.get("port", 0))
                proto = s.get("protocol", "tcp").lower()
                if port <= 0:
                    continue

                if (port, proto) not in existing_services:
                    self.add_service(
                        target_id=target.id,
                        port=port,
                        protocol=proto,
                        service=s.get("name", "unknown"),
                        version=s.get("version", ""),
                        access_potential=s.get("access_potential", ""),
                        next_action=s.get("next_action", ""),
                        status=ServiceStatus.CHECKED,
                    )
                    services_added += 1

        return targets_added, services_added

    # -------------------------------------------------------------------------
    # Services
    # -------------------------------------------------------------------------

    def add_service(
        self,
        target_id: int,
        port: int,
        protocol: str = "tcp",
        service: str = "unknown",
        version: str = "",
        access_potential: str = "",
        next_action: str = "",
        status: Union[str, ServiceStatus] = ServiceStatus.CHECKED,
        notes: str = "",
        preserve_status: bool = False,
    ) -> Service:
        proto_clean = protocol.strip().lower()
        stat_clean = (
            status.value if isinstance(status, ServiceStatus) else ServiceStatus.from_str(status).value
        )
        now = _iso_now()
        cur = self.conn.cursor()
        cur.execute(
            "SELECT * FROM services WHERE target_id = ? AND port = ? AND protocol = ?",
            (target_id, port, proto_clean),
        )
        row = cur.fetchone()
        if row:
            svc_id = row["id"]
            new_service = service if service != "unknown" else row["service"]
            new_version = version if version else row["version"]
            # Blank means "not rated": keep any existing rating unless the caller
            # explicitly supplies a new (non-empty) one.
            new_pot = access_potential or (row["access_potential"] if "access_potential" in row.keys() else "")
            new_act = next_action if next_action else (row["next_action"] if "next_action" in row.keys() else "")
            new_notes = notes if notes else row["notes"]
            final_status = row["status"] if preserve_status else stat_clean
            with self.conn:
                self.conn.execute(
                    """UPDATE services
                       SET service = ?, version = ?, access_potential = ?, next_action = ?, status = ?, notes = ?, updated_at = ?
                       WHERE id = ?""",
                    (new_service, new_version, new_pot, new_act, final_status, new_notes, now, svc_id),
                )
        else:
            with self.conn:
                cur.execute(
                    """INSERT INTO services (target_id, port, protocol, service, version, access_potential, next_action, status, notes, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        target_id,
                        port,
                        proto_clean,
                        service.strip(),
                        version.strip(),
                        access_potential.strip().upper(),
                        next_action.strip(),
                        stat_clean,
                        notes.strip(),
                        now,
                        now,
                    ),
                )
                svc_id = cur.lastrowid
        return self.get_service(svc_id)  # type: ignore

    def get_service(self, service_id: int) -> Optional[Service]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM services WHERE id = ?", (service_id,))
        row = cur.fetchone()
        return Service(**dict(row)) if row else None

    def list_services(self, target_id: Optional[int] = None) -> List[Service]:
        cur = self.conn.cursor()
        if target_id is not None:
            cur.execute(
                "SELECT * FROM services WHERE target_id = ? ORDER BY port ASC, protocol ASC",
                (target_id,),
            )
        else:
            cur.execute("SELECT * FROM services ORDER BY target_id ASC, port ASC")
        return [Service(**dict(r)) for r in cur.fetchall()]

    def delete_service(self, service_id: int) -> bool:
        with self.conn:
            res = self.conn.execute("DELETE FROM services WHERE id = ?", (service_id,))
            return res.rowcount > 0

    def cycle_service_status(self, service_id: int) -> Optional[Service]:
        svc = self.get_service(service_id)
        if not svc:
            return None
        transitions = {
            ServiceStatus.UNTESTED: ServiceStatus.CHECKED,
            ServiceStatus.CHECKED: ServiceStatus.DEAD_END,
            ServiceStatus.DEAD_END: ServiceStatus.DEFERRED,
            ServiceStatus.DEFERRED: ServiceStatus.UNTESTED,
        }
        next_stat = transitions.get(svc.status, ServiceStatus.CHECKED)
        now = datetime.now(timezone.utc).isoformat()
        with self.conn:
            self.conn.execute(
                "UPDATE services SET status = ?, updated_at = ? WHERE id = ?",
                (next_stat.value, now, service_id),
            )
        return self.get_service(service_id)

    def update_service_status(
        self, service_id: int, status: Union[str, ServiceStatus]
    ) -> Optional[Service]:
        stat_clean = (
            status.value if isinstance(status, ServiceStatus) else ServiceStatus.from_str(status).value
        )
        now = _iso_now()
        with self.conn:
            self.conn.execute(
                "UPDATE services SET status = ?, updated_at = ? WHERE id = ?",
                (stat_clean, now, service_id),
            )
        return self.get_service(service_id)

    # -------------------------------------------------------------------------
    # Findings
    # -------------------------------------------------------------------------

    def add_finding(
        self,
        title: str,
        target_id: Optional[int] = None,
        description: str = "",
        notes: str = "",
        severity: Optional[str] = None,
    ) -> Finding:
        now = _iso_now()
        cur = self.conn.cursor()
        with self.conn:
            cur.execute(
                """INSERT INTO findings (target_id, title, description, notes, severity, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    target_id,
                    title.strip(),
                    description.strip(),
                    notes.strip(),
                    severity.strip().upper() if severity else None,
                    now,
                    now,
                ),
            )
            finding_id = cur.lastrowid
        return self.get_finding(finding_id)  # type: ignore

    def get_finding(self, finding_id: int) -> Optional[Finding]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM findings WHERE id = ?", (finding_id,))
        row = cur.fetchone()
        return Finding(**dict(row)) if row else None

    def list_findings(self, target_id: Optional[int] = None) -> List[Finding]:
        cur = self.conn.cursor()
        if target_id is not None:
            cur.execute(
                "SELECT * FROM findings WHERE target_id = ? ORDER BY id ASC",
                (target_id,),
            )
        else:
            cur.execute("SELECT * FROM findings ORDER BY id ASC")
        return [Finding(**dict(r)) for r in cur.fetchall()]

    def delete_finding(self, finding_id: int) -> bool:
        with self.conn:
            res = self.conn.execute("DELETE FROM findings WHERE id = ?", (finding_id,))
            return res.rowcount > 0

    # -------------------------------------------------------------------------
    # Credentials
    # -------------------------------------------------------------------------

    def add_credential(
        self,
        username: str,
        secret: str,
        source: str = "",
        target_id: Optional[int] = None,
        service_scope: str = "",
        status: str = "untested",
        notes: str = "",
    ) -> Credential:
        now = _iso_now()
        cur = self.conn.cursor()
        with self.conn:
            cur.execute(
                """INSERT INTO credentials (target_id, username, secret, source, service_scope, status, notes, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    target_id,
                    username.strip(),
                    secret.strip(),
                    source.strip(),
                    service_scope.strip(),
                    status.strip(),
                    notes.strip(),
                    now,
                    now,
                ),
            )
            cred_id = cur.lastrowid
        return self.get_credential(cred_id)  # type: ignore

    def get_credential(self, cred_id: int) -> Optional[Credential]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM credentials WHERE id = ?", (cred_id,))
        row = cur.fetchone()
        return Credential(**dict(row)) if row else None

    def list_credentials(self, target_id: Optional[int] = None) -> List[Credential]:
        cur = self.conn.cursor()
        if target_id is not None:
            cur.execute(
                "SELECT * FROM credentials WHERE target_id = ? ORDER BY id ASC",
                (target_id,),
            )
        else:
            cur.execute("SELECT * FROM credentials ORDER BY id ASC")
        return [Credential(**dict(r)) for r in cur.fetchall()]

    def delete_credential(self, cred_id: int) -> bool:
        with self.conn:
            res = self.conn.execute("DELETE FROM credentials WHERE id = ?", (cred_id,))
            return res.rowcount > 0

    def update_credential(
        self,
        cred_id: int,
        secret: Optional[str] = None,
        status: Optional[str] = None,
        notes: Optional[str] = None,
        username: Optional[str] = None,
    ) -> Optional[Credential]:
        """Update an existing credential record in-place (e.g. hash cracked to plaintext)."""
        existing = self.get_credential(cred_id)
        if not existing:
            return None
        now = _iso_now()
        new_secret = secret.strip() if secret is not None else existing.secret
        new_status = status.strip() if status is not None else existing.status
        new_notes = notes.strip() if notes is not None else existing.notes
        new_username = username.strip() if username is not None else existing.username

        with self.conn:
            self.conn.execute(
                """UPDATE credentials
                   SET username = ?, secret = ?, status = ?, notes = ?, updated_at = ?
                   WHERE id = ?""",
                (new_username, new_secret, new_status, new_notes, now, cred_id),
            )
        return self.get_credential(cred_id)

    def export_wordlists_to_loot(
        self, workspace_id: Optional[int] = None
    ) -> tuple[Path, Path]:
        """Export all unique discovered usernames and secrets to workspace loot files.

        Writes:
          <workspace_root>/loot/users.txt
          <workspace_root>/loot/passwords.txt
        """
        ws = self.get_workspace(workspace_id) if workspace_id else self.get_active_workspace()
        if not ws:
            ws = self.get_or_create_workspace("default")

        ws_root = self.get_workspace_root(ws)
        loot_dir = ws_root / "loot"
        loot_dir.mkdir(parents=True, exist_ok=True)

        users_file = loot_dir / "users.txt"
        passwords_file = loot_dir / "passwords.txt"

        creds = self.list_credentials()
        if ws.id:
            targets = {t.id for t in self.list_targets(workspace_id=ws.id)}
            creds = [c for c in creds if c.target_id is None or c.target_id in targets]

        users = sorted({c.username.strip() for c in creds if c.username.strip()})
        passwords = sorted({c.secret.strip() for c in creds if c.secret.strip()})

        users_file.write_text("\n".join(users) + ("\n" if users else ""), encoding="utf-8")
        passwords_file.write_text("\n".join(passwords) + ("\n" if passwords else ""), encoding="utf-8")

        return users_file, passwords_file

    # -------------------------------------------------------------------------
    # Leads
    # -------------------------------------------------------------------------

    def add_lead(
        self,
        title: str,
        target_id: Optional[int] = None,
        notes: str = "",
        status: str = "open",
    ) -> Lead:
        now = _iso_now()
        cur = self.conn.cursor()
        with self.conn:
            cur.execute(
                """INSERT INTO leads (target_id, title, notes, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (target_id, title.strip(), notes.strip(), status.strip(), now, now),
            )
            lead_id = cur.lastrowid
        return self.get_lead(lead_id)  # type: ignore

    def get_lead(self, lead_id: int) -> Optional[Lead]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM leads WHERE id = ?", (lead_id,))
        row = cur.fetchone()
        return Lead(**dict(row)) if row else None

    def list_leads(self, target_id: Optional[int] = None) -> List[Lead]:
        cur = self.conn.cursor()
        if target_id is not None:
            cur.execute(
                "SELECT * FROM leads WHERE target_id = ? ORDER BY id ASC",
                (target_id,),
            )
        else:
            cur.execute("SELECT * FROM leads ORDER BY id ASC")
        return [Lead(**dict(r)) for r in cur.fetchall()]

    def delete_lead(self, lead_id: int) -> bool:
        with self.conn:
            res = self.conn.execute("DELETE FROM leads WHERE id = ?", (lead_id,))
            return res.rowcount > 0

    # -------------------------------------------------------------------------
    # Evidence
    # -------------------------------------------------------------------------

    def add_evidence(
        self,
        path_or_ref: str,
        target_id: Optional[int] = None,
        evidence_type: str = "screenshot",
        description: str = "",
        workspace_id: Optional[int] = None,
    ) -> Evidence:
        now = _iso_now()
        ws = self.get_workspace(workspace_id) if workspace_id else None
        if not ws and target_id:
            tgt = self.get_target(target_id)
            if tgt:
                ws = self.get_workspace(tgt.workspace_id)
        rel_path = self.relativize_path(path_or_ref, workspace=ws)
        cur = self.conn.cursor()
        with self.conn:
            cur.execute(
                """INSERT INTO evidence (target_id, evidence_type, path_or_ref, description, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    target_id,
                    evidence_type.strip().lower(),
                    rel_path,
                    description.strip(),
                    now,
                    now,
                ),
            )
            evidence_id = cur.lastrowid
        return self.get_evidence(evidence_id)  # type: ignore

    def get_evidence(self, evidence_id: int) -> Optional[Evidence]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM evidence WHERE id = ?", (evidence_id,))
        row = cur.fetchone()
        return Evidence(**dict(row)) if row else None

    def list_evidence(self, target_id: Optional[int] = None) -> List[Evidence]:
        cur = self.conn.cursor()
        if target_id is not None:
            cur.execute(
                "SELECT * FROM evidence WHERE target_id = ? ORDER BY id ASC",
                (target_id,),
            )
        else:
            cur.execute("SELECT * FROM evidence ORDER BY id ASC")
        return [Evidence(**dict(r)) for r in cur.fetchall()]

    def delete_evidence(self, evidence_id: int) -> bool:
        with self.conn:
            res = self.conn.execute("DELETE FROM evidence WHERE id = ?", (evidence_id,))
            return res.rowcount > 0

    # -------------------------------------------------------------------------
    # Notes
    # -------------------------------------------------------------------------

    def add_note(self, content: str, target_id: Optional[int] = None) -> Note:
        now = _iso_now()
        cur = self.conn.cursor()
        with self.conn:
            cur.execute(
                """INSERT INTO notes (target_id, content, created_at, updated_at)
                   VALUES (?, ?, ?, ?)""",
                (target_id, content.strip(), now, now),
            )
            note_id = cur.lastrowid
        return self.get_note(note_id)  # type: ignore

    def get_note(self, note_id: int) -> Optional[Note]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM notes WHERE id = ?", (note_id,))
        row = cur.fetchone()
        return Note(**dict(row)) if row else None

    def list_notes(self, target_id: Optional[int] = None) -> List[Note]:
        cur = self.conn.cursor()
        if target_id is not None:
            cur.execute(
                "SELECT * FROM notes WHERE target_id = ? ORDER BY id ASC",
                (target_id,),
            )
        else:
            cur.execute("SELECT * FROM notes ORDER BY id ASC")
        return [Note(**dict(r)) for r in cur.fetchall()]

    def delete_note(self, note_id: int) -> bool:
        with self.conn:
            res = self.conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
            return res.rowcount > 0

    # -------------------------------------------------------------------------
    # Checklist
    # -------------------------------------------------------------------------

    def add_checklist_item(
        self,
        title: str,
        category: str = "ENUMERATION",
        target_id: Optional[int] = None,
        status: Union[str, ChecklistStatus] = ChecklistStatus.TODO,
        notes: str = "",
    ) -> ChecklistItem:
        stat_clean = (
            status.value if isinstance(status, ChecklistStatus) else ChecklistStatus.from_str(status).value
        )
        now = _iso_now()
        cur = self.conn.cursor()
        with self.conn:
            cur.execute(
                """INSERT INTO checklist (target_id, category, title, status, notes, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    target_id,
                    category.strip().upper(),
                    title.strip(),
                    stat_clean,
                    notes.strip(),
                    now,
                    now,
                ),
            )
            item_id = cur.lastrowid
        return self.get_checklist_item(item_id)  # type: ignore

    def get_checklist_item(self, item_id: int) -> Optional[ChecklistItem]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM checklist WHERE id = ?", (item_id,))
        row = cur.fetchone()
        return ChecklistItem(**dict(row)) if row else None

    def list_checklist_items(
        self, target_id: Optional[int] = None, category: Optional[str] = None
    ) -> List[ChecklistItem]:
        cur = self.conn.cursor()
        query = "SELECT * FROM checklist WHERE 1=1"
        params: List[Any] = []
        if target_id is not None:
            query += " AND target_id = ?"
            params.append(target_id)
        if category:
            query += " AND category = ?"
            params.append(category.strip().upper())
        query += " ORDER BY id ASC"
        cur.execute(query, params)
        return [ChecklistItem(**dict(r)) for r in cur.fetchall()]

    def update_checklist_status(
        self, item_id: int, status: Union[str, ChecklistStatus]
    ) -> Optional[ChecklistItem]:
        stat_clean = (
            status.value if isinstance(status, ChecklistStatus) else ChecklistStatus.from_str(status).value
        )
        now = _iso_now()
        with self.conn:
            self.conn.execute(
                "UPDATE checklist SET status = ?, updated_at = ? WHERE id = ?",
                (stat_clean, now, item_id),
            )
        return self.get_checklist_item(item_id)

    def cycle_checklist_status(self, item_id: int) -> Optional[ChecklistItem]:
        item = self.get_checklist_item(item_id)
        if not item:
            return None
        next_stat = item.status.next_state()
        return self.update_checklist_status(item_id, next_stat)

    def delete_checklist_item(self, item_id: int) -> bool:
        with self.conn:
            res = self.conn.execute("DELETE FROM checklist WHERE id = ?", (item_id,))
            return res.rowcount > 0

    def clear_checklist(self, target_id: Optional[int] = None) -> int:
        """Remove all checklist items for a target (or global items if target_id is None)."""
        with self.conn:
            if target_id is not None:
                res = self.conn.execute("DELETE FROM checklist WHERE target_id = ?", (target_id,))
            else:
                res = self.conn.execute("DELETE FROM checklist WHERE target_id IS NULL")
            return res.rowcount

    # -------------------------------------------------------------------------
    # Command History
    # -------------------------------------------------------------------------

    def add_command(
        self,
        command: str,
        target_id: Optional[int] = None,
        notes: str = "",
        is_golden: bool = False,
        step: str = "",
    ) -> CommandRecord:
        now = _iso_now()
        cur = self.conn.cursor()
        with self.conn:
            cur.execute(
                """INSERT INTO command_history (target_id, command, notes, is_golden, step, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (target_id, command.strip(), notes.strip(), int(is_golden), step.strip(), now),
            )
            cmd_id = cur.lastrowid
        cur.execute("SELECT * FROM command_history WHERE id = ?", (cmd_id,))
        row = cur.fetchone()
        return CommandRecord(**dict(row))

    def list_commands(
        self,
        target_id: Optional[int] = None,
        limit: int = 50,
        golden_only: bool = False,
    ) -> List[CommandRecord]:
        cur = self.conn.cursor()
        where_clauses = []
        params: List[Any] = []
        if target_id is not None:
            where_clauses.append("target_id = ?")
            params.append(target_id)
        if golden_only:
            where_clauses.append("is_golden = 1")

        query = "SELECT * FROM command_history"
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        cur.execute(query, tuple(params))
        rows = cur.fetchall()
        return [CommandRecord(**dict(r)) for r in reversed(rows)]

    # -------------------------------------------------------------------------
    # Target Scope, Foothold, PrivEsc & Flags Helpers
    # -------------------------------------------------------------------------

    def update_target_details(
        self,
        target_id: int,
        hostname: Optional[str] = None,
        os_name: Optional[str] = None,
        initial_access_vuln: Optional[str] = None,
        foothold_cmd: Optional[str] = None,
        foothold_context: Optional[str] = None,
        privesc_vector: Optional[str] = None,
        root_proof: Optional[str] = None,
        user_flag: Optional[str] = None,
        root_flag: Optional[str] = None,
        is_in_scope: Optional[bool] = None,
        subnet: Optional[str] = None,
        is_pivot: Optional[bool] = None,
        pivot_route: Optional[str] = None,
    ) -> Optional[Target]:
        target = self.get_target(target_id)
        if not target:
            return None

        new_hostname = hostname if hostname is not None else target.hostname
        new_os = os_name if os_name is not None else target.os
        new_vuln = initial_access_vuln if initial_access_vuln is not None else target.initial_access_vuln
        new_cmd = foothold_cmd if foothold_cmd is not None else target.foothold_cmd
        new_ctx = foothold_context if foothold_context is not None else target.foothold_context
        new_priv = privesc_vector if privesc_vector is not None else target.privesc_vector
        new_proof = root_proof if root_proof is not None else target.root_proof
        new_uflag = user_flag if user_flag is not None else target.user_flag
        new_rflag = root_flag if root_flag is not None else target.root_flag
        new_scope = int(is_in_scope) if is_in_scope is not None else int(target.is_in_scope)
        new_subnet = subnet if subnet is not None else target.subnet
        new_pivot = int(is_pivot) if is_pivot is not None else int(target.is_pivot)
        new_proute = pivot_route if pivot_route is not None else target.pivot_route
        now = _iso_now()

        with self.conn:
            self.conn.execute(
                """UPDATE targets
                   SET hostname = ?, os = ?, initial_access_vuln = ?, foothold_cmd = ?, foothold_context = ?,
                       privesc_vector = ?, root_proof = ?, user_flag = ?, root_flag = ?,
                       is_in_scope = ?, subnet = ?, is_pivot = ?, pivot_route = ?, updated_at = ?
                   WHERE id = ?""",
                (
                    new_hostname,
                    new_os,
                    new_vuln,
                    new_cmd,
                    new_ctx,
                    new_priv,
                    new_proof,
                    new_uflag,
                    new_rflag,
                    new_scope,
                    new_subnet,
                    new_pivot,
                    new_proute,
                    now,
                    target_id,
                ),
            )
        return self.get_target(target_id)

    # Alias for backwards compatibility
    update_target_methodology = update_target_details

    def audit_target(self, target_id: int) -> Dict[str, Any]:
        """Perform pre-reset integrity audit to ensure proof artifacts are recorded before VM reverts."""
        target = self.get_target(target_id)
        if not target:
            return {"error": f"Target with ID {target_id} not found", "ready_to_revert": False, "checks": []}

        services = self.list_services(target_id=target.id)
        evidence = self.list_evidence(target_id=target.id)
        creds = self.list_credentials(target_id=target.id)
        golden_cmds = self.list_commands(target_id=target.id, golden_only=True)

        checks = [
            {
                "name": "Scope Confirmation",
                "key": "scope",
                "passed": bool(target.is_in_scope),
                "critical": True,
                "detail": "Target is marked IN-SCOPE" if target.is_in_scope else "TARGET IS OUT-OF-SCOPE",
            },
            {
                "name": "Service Enumeration",
                "key": "services",
                "passed": len(services) > 0,
                "critical": False,
                "detail": f"{len(services)} service(s) recorded" if services else "No services recorded",
            },
            {
                "name": "Initial Foothold / Exploit",
                "key": "foothold",
                "passed": bool(target.foothold_cmd or target.initial_access_vuln),
                "critical": True,
                "detail": target.foothold_cmd or target.initial_access_vuln or "MISSING (foothold command or CVE)",
            },
            {
                "name": "User Flag",
                "key": "user_flag",
                "passed": bool(target.user_flag),
                "critical": True,
                "detail": target.user_flag or "MISSING (user flag not recorded)",
            },
            {
                "name": "PrivEsc & Root Proof",
                "key": "privesc",
                "passed": bool(target.privesc_vector or target.root_proof),
                "critical": True,
                "detail": target.root_proof or target.privesc_vector or "MISSING (root proof or privesc vector)",
            },
            {
                "name": "Root Flag",
                "key": "root_flag",
                "passed": bool(target.root_flag),
                "critical": True,
                "detail": target.root_flag or "MISSING (root flag not recorded)",
            },
            {
                "name": "Evidence / Screenshots",
                "key": "evidence",
                "passed": len(evidence) > 0,
                "critical": True,
                "detail": f"{len(evidence)} evidence item(s) attached" if evidence else "MISSING (no screenshots or loot attached)",
            },
        ]

        critical_failed = [c for c in checks if c["critical"] and not c["passed"]]
        ready_to_revert = len(critical_failed) == 0
        total_passed = sum(1 for c in checks if c["passed"])

        verdict = (
            "READY TO RESET: All required proof artifacts are recorded."
            if ready_to_revert
            else f"DO NOT REVERT: Missing {len(critical_failed)} critical proof artifact(s)!"
        )

        return {
            "target_id": target.id,
            "ip": target.ip,
            "hostname": target.hostname,
            "os": target.os,
            "ready_to_revert": ready_to_revert,
            "verdict": verdict,
            "checks": checks,
            "score": f"{total_passed}/{len(checks)}",
            "stats": {
                "services_count": len(services),
                "creds_count": len(creds),
                "evidence_count": len(evidence),
                "golden_cmds_count": len(golden_cmds),
            },
        }

    # -------------------------------------------------------------------------
    # Failure Log & Breakthrough Tracking (Notion Section 06)
    # -------------------------------------------------------------------------

    def add_failure_log(
        self,
        target_id: Optional[int] = None,
        where_stuck: str = "",
        breakthrough_clue: str = "",
        rule_for_next_time: str = "",
    ) -> FailureLog:
        now = _iso_now()
        cur = self.conn.cursor()
        with self.conn:
            cur.execute(
                """INSERT INTO failure_log (target_id, where_stuck, breakthrough_clue, rule_for_next_time, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (target_id, where_stuck.strip(), breakthrough_clue.strip(), rule_for_next_time.strip(), now, now),
            )
            log_id = cur.lastrowid
        cur.execute("SELECT * FROM failure_log WHERE id = ?", (log_id,))
        row = cur.fetchone()
        return FailureLog(**dict(row))

    def list_failure_logs(self, target_id: Optional[int] = None) -> List[FailureLog]:
        cur = self.conn.cursor()
        if target_id is not None:
            cur.execute("SELECT * FROM failure_log WHERE target_id = ? ORDER BY id ASC", (target_id,))
        else:
            cur.execute("SELECT * FROM failure_log ORDER BY id ASC")
        return [FailureLog(**dict(r)) for r in cur.fetchall()]

    def delete_failure_log(self, log_id: int) -> bool:
        with self.conn:
            res = self.conn.execute("DELETE FROM failure_log WHERE id = ?", (log_id,))
            return res.rowcount > 0

    # -------------------------------------------------------------------------
    # Credential Verification Matrix Persistence (Station 3)
    # -------------------------------------------------------------------------

    def get_cred_validations(self) -> Dict[tuple[int, int], str]:
        """Fetch all credential cell verification states: (cred_id, svc_id) -> status."""
        cur = self.conn.cursor()
        cur.execute("SELECT credential_id, service_id, status FROM cred_validations")
        return {(r["credential_id"], r["service_id"]): r["status"] for r in cur.fetchall()}

    def set_cred_validation(self, credential_id: int, service_id: int, status: str) -> None:
        """Store or update verification status of a credential against a service."""
        now = _iso_now()
        with self.conn:
            self.conn.execute(
                """INSERT INTO cred_validations (credential_id, service_id, status, updated_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(credential_id, service_id) DO UPDATE SET
                   status = excluded.status, updated_at = excluded.updated_at""",
                (credential_id, service_id, status, now),
            )

    # -------------------------------------------------------------------------
    # Exam Question Proofs Ledger (Station 4)
    # -------------------------------------------------------------------------

    def add_exam_proof(
        self,
        question_num: str,
        answer_proof: str,
        category: str = "FLAG",
        notes: str = "",
        target_id: Optional[int] = None,
    ) -> ExamProof:
        now = _iso_now()
        cur = self.conn.cursor()
        with self.conn:
            cur.execute(
                """INSERT INTO exam_proofs (target_id, question_num, category, answer_proof, notes, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (target_id, question_num.strip().upper(), category.strip().upper(), answer_proof.strip(), notes.strip(), now, now),
            )
            proof_id = cur.lastrowid
        cur.execute("SELECT * FROM exam_proofs WHERE id = ?", (proof_id,))
        return ExamProof(**dict(cur.fetchone()))

    def list_exam_proofs(self, target_id: Optional[int] = None) -> List[ExamProof]:
        cur = self.conn.cursor()
        if target_id is not None:
            cur.execute("SELECT * FROM exam_proofs WHERE target_id = ? ORDER BY id ASC", (target_id,))
        else:
            cur.execute("SELECT * FROM exam_proofs ORDER BY id ASC")
        return [ExamProof(**dict(r)) for r in cur.fetchall()]

    def delete_exam_proof(self, proof_id: int) -> bool:
        with self.conn:
            res = self.conn.execute("DELETE FROM exam_proofs WHERE id = ?", (proof_id,))
            return res.rowcount > 0

    def export_exam_evidence_markdown(self) -> str:
        """Export all recorded exam question proofs formatted for review before submission."""
        proofs = self.list_exam_proofs()
        lines = [
            "# Assessment Evidence & Submission Ledger",
            f"Generated: {_iso_now()} (GLACIS Field Notebook)",
            "",
            "| Question | Target | Category | Proof / Answer Value | Notes |",
            "|---|---|---|---|---|",
        ]
        if not proofs:
            lines.append("| - | - | - | *No question proofs recorded yet* | - |")
        else:
            def sort_key(p: ExamProof) -> tuple[int, str]:
                q = p.question_num.lstrip("Qq")
                return (int(q) if q.isdigit() else 9999, p.question_num)

            for p in sorted(proofs, key=sort_key):
                tgt = f"Host #{p.target_id}" if p.target_id else "Global"
                if p.target_id:
                    t = self.get_target(p.target_id)
                    if t:
                        tgt = t.ip
                lines.append(f"| **{p.question_num}** | `{tgt}` | `{p.category}` | `{p.answer_proof}` | {p.notes or '-'} |")
        lines.append("")
        return "\n".join(lines)

