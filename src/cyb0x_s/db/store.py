"""Local SQLite repository for CYB0X-S.

High performance, zero network footprint, fully ACID-compliant.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from cyb0x_s.db.schema import SCHEMA_SQL
from cyb0x_s.models import (
    ChecklistItem,
    ChecklistStatus,
    CommandRecord,
    Credential,
    Evidence,
    FailureLog,
    Finding,
    Lead,
    Note,
    Service,
    ServiceStatus,
    Target,
    Workspace,
)


def _iso_now() -> str:
    """Return current UTC timestamp in ISO 8601 string format."""
    return datetime.now(timezone.utc).isoformat()


def get_default_db_path() -> Path:
    """Determine the database storage location."""
    env_path = os.environ.get("CYB0X_S_DB")
    if env_path:
        return Path(env_path)

    # If local workspace folder exists, use it
    local_dir = Path(".cyb0x-s")
    if local_dir.is_dir():
        return local_dir / "notebook.db"

    # Default to user XDG data dir
    data_home = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    base_dir = data_home / "cyb0x-s"
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir / "notebook.db"


class NotebookStore:
    """Thread-safe, local SQLite storage engine for CYB0X-S."""

    def __init__(self, db_path: Optional[Union[str, Path]] = None):
        if db_path is None:
            self.db_path = get_default_db_path()
        elif str(db_path) == ":memory:":
            self.db_path = Path(":memory:")
        else:
            self.db_path = Path(db_path)
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self.conn = sqlite3.connect(
            str(self.db_path),
            check_same_thread=False,
        )
        self.conn.row_factory = sqlite3.Row
        self.init_schema()

    def init_schema(self) -> None:
        """Run initial DDL script and ensure a default workspace exists."""
        with self.conn:
            self.conn.executescript(SCHEMA_SQL)
            cur = self.conn.cursor()
            cur.execute("SELECT id FROM workspaces WHERE name = 'default'")
            row = cur.fetchone()
            if not row:
                now = _iso_now()
                cur.execute(
                    "INSERT INTO workspaces (name, description, created_at, updated_at) VALUES ('default', 'Default assessment workspace', ?, ?)",
                    (now, now),
                )
                ws_id = cur.lastrowid
            else:
                ws_id = row["id"]

            cur.execute("SELECT value FROM settings WHERE key = 'active_workspace'")
            if not cur.fetchone():
                cur.execute(
                    "INSERT INTO settings (key, value) VALUES ('active_workspace', ?)",
                    (str(ws_id),),
                )

        # Non-destructive migrations for existing databases
        migration_cols = [
            ("targets", "initial_access_vuln", "TEXT DEFAULT ''"),
            ("targets", "foothold_cmd", "TEXT DEFAULT ''"),
            ("targets", "foothold_context", "TEXT DEFAULT ''"),
            ("targets", "privesc_vector", "TEXT DEFAULT ''"),
            ("targets", "root_proof", "TEXT DEFAULT ''"),
            ("targets", "user_flag", "TEXT DEFAULT ''"),
            ("targets", "root_flag", "TEXT DEFAULT ''"),
            ("targets", "is_in_scope", "INTEGER DEFAULT 1"),
            ("services", "access_potential", "TEXT DEFAULT 'MED'"),
            ("services", "next_action", "TEXT DEFAULT ''"),
        ]
        for tbl, col, ctype in migration_cols:
            try:
                with self.conn:
                    self.conn.execute(f"ALTER TABLE {tbl} ADD COLUMN {col} {ctype};")
            except Exception:
                pass

    def close(self) -> None:
        """Close SQLite database connection."""
        self.conn.close()

    # -------------------------------------------------------------------------
    # Workspaces & Settings
    # -------------------------------------------------------------------------

    def get_or_create_workspace(self, name: str = "default", description: str = "") -> Workspace:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM workspaces WHERE name = ?", (name,))
        row = cur.fetchone()
        if row:
            return Workspace(**dict(row))
        now = _iso_now()
        with self.conn:
            cur.execute(
                "INSERT INTO workspaces (name, description, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (name, description, now, now),
            )
            ws_id = cur.lastrowid
        return self.get_workspace(ws_id)  # type: ignore

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
                        access_potential=s.get("access_potential", "MED"),
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
        access_potential: str = "MED",
        next_action: str = "",
        status: Union[str, ServiceStatus] = ServiceStatus.CHECKED,
        notes: str = "",
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
            new_pot = access_potential if access_potential != "MED" or not row.get("access_potential") else row["access_potential"]
            new_act = next_action if next_action else (row["next_action"] if "next_action" in row.keys() else "")
            new_notes = notes if notes else row["notes"]
            with self.conn:
                self.conn.execute(
                    """UPDATE services
                       SET service = ?, version = ?, access_potential = ?, next_action = ?, status = ?, notes = ?, updated_at = ?
                       WHERE id = ?""",
                    (new_service, new_version, new_pot, new_act, stat_clean, new_notes, now, svc_id),
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
    ) -> Evidence:
        now = _iso_now()
        cur = self.conn.cursor()
        with self.conn:
            cur.execute(
                """INSERT INTO evidence (target_id, evidence_type, path_or_ref, description, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    target_id,
                    evidence_type.strip().lower(),
                    path_or_ref.strip(),
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

    # -------------------------------------------------------------------------
    # Command History
    # -------------------------------------------------------------------------

    def add_command(
        self,
        command: str,
        target_id: Optional[int] = None,
        notes: str = "",
    ) -> CommandRecord:
        now = _iso_now()
        cur = self.conn.cursor()
        with self.conn:
            cur.execute(
                """INSERT INTO command_history (target_id, command, notes, created_at)
                   VALUES (?, ?, ?, ?)""",
                (target_id, command.strip(), notes.strip(), now),
            )
            cmd_id = cur.lastrowid
        cur.execute("SELECT * FROM command_history WHERE id = ?", (cmd_id,))
        row = cur.fetchone()
        return CommandRecord(**dict(row))

    def list_commands(
        self, target_id: Optional[int] = None, limit: int = 50
    ) -> List[CommandRecord]:
        cur = self.conn.cursor()
        if target_id is not None:
            cur.execute(
                "SELECT * FROM command_history WHERE target_id = ? ORDER BY id DESC LIMIT ?",
                (target_id, limit),
            )
        else:
            cur.execute("SELECT * FROM command_history ORDER BY id DESC LIMIT ?", (limit,))
        rows = cur.fetchall()
        return [CommandRecord(**dict(r)) for r in reversed(rows)]

    # -------------------------------------------------------------------------
    # Target Scope, Foothold, PrivEsc & Flags Helpers
    # -------------------------------------------------------------------------

    def update_target_details(
        self,
        target_id: int,
        initial_access_vuln: Optional[str] = None,
        foothold_cmd: Optional[str] = None,
        foothold_context: Optional[str] = None,
        privesc_vector: Optional[str] = None,
        root_proof: Optional[str] = None,
        user_flag: Optional[str] = None,
        root_flag: Optional[str] = None,
        is_in_scope: Optional[bool] = None,
    ) -> Optional[Target]:
        target = self.get_target(target_id)
        if not target:
            return None

        new_vuln = initial_access_vuln if initial_access_vuln is not None else target.initial_access_vuln
        new_cmd = foothold_cmd if foothold_cmd is not None else target.foothold_cmd
        new_ctx = foothold_context if foothold_context is not None else target.foothold_context
        new_priv = privesc_vector if privesc_vector is not None else target.privesc_vector
        new_proof = root_proof if root_proof is not None else target.root_proof
        new_uflag = user_flag if user_flag is not None else target.user_flag
        new_rflag = root_flag if root_flag is not None else target.root_flag
        new_scope = int(is_in_scope) if is_in_scope is not None else int(target.is_in_scope)
        now = _iso_now()

        with self.conn:
            self.conn.execute(
                """UPDATE targets
                   SET initial_access_vuln = ?, foothold_cmd = ?, foothold_context = ?,
                       privesc_vector = ?, root_proof = ?, user_flag = ?, root_flag = ?,
                       is_in_scope = ?, updated_at = ?
                   WHERE id = ?""",
                (new_vuln, new_cmd, new_ctx, new_priv, new_proof, new_uflag, new_rflag, new_scope, now, target_id),
            )
        return self.get_target(target_id)

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

