"""Demo seed script for CYB0X-S.

Quickly populates a notebook workspace with sample lab data matching the scenario.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add src to path if running directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from cyb0x_s.db.store import NotebookStore
from cyb0x_s.models import ChecklistStatus, ServiceStatus


def seed_demo(store: NotebookStore) -> None:
    ws = store.get_or_create_workspace("Lab-Assessment-01", description="Field notes for 10.10.10.20 lab assessment")
    store.set_active_workspace(ws.id)

    # 1. Target
    target = store.add_target(
        ip="10.10.10.20",
        hostname="target.local",
        os_name="Linux",
        notes="Lab host running web application and file share services",
        workspace_id=ws.id,
    )

    # 2. Services
    store.add_service(
        target_id=target.id,
        port=22,
        protocol="tcp",
        service="SSH",
        version="OpenSSH 8.2p1",
        status=ServiceStatus.CHECKED,
        notes="Password auth allowed",
    )
    store.add_service(
        target_id=target.id,
        port=80,
        protocol="tcp",
        service="HTTP",
        version="Apache 2.4.41",
        status=ServiceStatus.CHECKED,
        notes="Redirects to /login",
    )
    store.add_service(
        target_id=target.id,
        port=445,
        protocol="tcp",
        service="SMB",
        version="Samba 4.3",
        status=ServiceStatus.CHECKED,
        notes="Anonymous read access",
    )

    # 3. Findings
    store.add_finding(
        title="SMB anonymous access enabled",
        target_id=target.id,
        description="Read access confirmed to backup share",
        notes="Contains archive.zip",
        severity="HIGH",
    )
    store.add_finding(
        title="HTTP redirects to /login",
        target_id=target.id,
        description="Landing page presents login form",
        severity="INFO",
    )

    # 4. Credentials
    store.add_credential(
        username="admin",
        secret="Summer2024!Secure",
        source="backup.zip / config.php",
        target_id=target.id,
        service_scope="Web Administration",
        status="untested",
        notes="Extracted from config file",
    )

    # 5. Checklist
    store.add_checklist_item(
        title="TCP enumeration",
        category="ENUMERATION",
        target_id=target.id,
        status=ChecklistStatus.CHECKED,
    )
    store.add_checklist_item(
        title="HTTP enumeration",
        category="ENUMERATION",
        target_id=target.id,
        status=ChecklistStatus.CHECKED,
    )
    store.add_checklist_item(
        title="SMB enumeration",
        category="ENUMERATION",
        target_id=target.id,
        status=ChecklistStatus.TODO,
    )
    store.add_checklist_item(
        title="UDP service sweep",
        category="ENUMERATION",
        target_id=target.id,
        status=ChecklistStatus.DEFERRED,
    )

    # 6. Notes
    store.add_note(
        content="backup share contains archive.zip",
        target_id=target.id,
    )
    store.add_note(
        content="archive.zip contains old site configs and admin credentials",
        target_id=target.id,
    )

    # 7. Evidence
    store.add_evidence(
        path_or_ref="evidence/proof_screenshot_01.png",
        target_id=target.id,
        evidence_type="screenshot",
        description="Anonymous SMB access listing backup share",
    )

    # 8. Leads
    store.add_lead(
        title="Test admin credentials against SMB and SSH",
        target_id=target.id,
        notes="Try SSH first, then smbclient with -U admin",
    )

    print(f"Successfully seeded demo workspace '{ws.name}' for target {target.ip}!")


if __name__ == "__main__":
    db = sys.argv[1] if len(sys.argv) > 1 else None
    s = NotebookStore(db)
    seed_demo(s)
