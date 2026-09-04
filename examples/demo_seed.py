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

    # 1. Targets (with Subnets & Pivoting)
    target = store.add_target(
        ip="10.10.10.20",
        hostname="target.local",
        os_name="Linux",
        notes="Dual-homed gateway into internal 172.16.1.0/24 network",
        workspace_id=ws.id,
    )
    store.update_target_details(
        target.id,
        subnet="10.10.10.0/24",
        is_pivot=True,
        pivot_route="172.16.1.0/24",
        user_flag="eJPT{user_flag_7a9e2b104c81f}",
        root_flag="eJPT{root_flag_f04b8d195ae32}",
    )
    internal_target = store.add_target(
        ip="172.16.1.50",
        hostname="db01.corp.internal",
        os_name="Linux",
        notes="Internal MySQL database host reachable via 10.10.10.20 pivot",
        workspace_id=ws.id,
    )
    store.update_target_details(internal_target.id, subnet="172.16.1.0/24")

    # 2. Services
    s_ssh = store.add_service(
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
    s_smb = store.add_service(
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

    store.add_service(
        target_id=internal_target.id,
        port=3306,
        protocol="tcp",
        service="MySQL",
        version="MySQL 5.7.33",
        status=ServiceStatus.UNTESTED,
        notes="Reachable via SOCKS proxy / Chisel tunnel",
    )

    # 4. Credentials
    c1 = store.add_credential(
        username="admin",
        secret="Summer2024!Secure",
        source="backup.zip / config.php",
        target_id=target.id,
        service_scope="Web / SSH",
        status="valid",
        notes="Extracted from config file",
    )
    c2 = store.add_credential(
        username="root",
        secret="toor",
        source="shadow crack",
        target_id=target.id,
        service_scope="SSH",
        status="valid",
        notes="Cracked with rockyou",
    )
    store.set_cred_validation(c1.id, s_ssh.id, "VALID")
    store.set_cred_validation(c1.id, s_smb.id, "PWN3D")
    store.set_cred_validation(c2.id, s_ssh.id, "VALID")

    # 5. Checklist
    store.add_checklist_item(
        title="TCP enumeration",
        category="ENUMERATION",
        target_id=target.id,
        status=ChecklistStatus.CHECKED,
    )
    store.add_checklist_item(
        title="SMB enumeration",
        category="ENUMERATION",
        target_id=target.id,
        status=ChecklistStatus.CHECKED,
    )
    store.add_checklist_item(
        title="Pivoting & Route Discovery",
        category="PIVOTING",
        target_id=target.id,
        status=ChecklistStatus.CHECKED,
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

    # 8. Exam Question Proofs & Failure Logs
    store.add_exam_proof(
        question_num="Q7",
        answer_proof="dbpass: R0ck3t_L4unch!#2024",
        category="CRED",
        notes="Found in /var/www/html/wp-config.php",
        target_id=target.id,
    )
    store.add_exam_proof(
        question_num="Q14",
        answer_proof="root:$6$qZ8jL1...:19120:0:99999:7:::",
        category="HASH",
        notes="Cracked root shadow hash from target",
        target_id=target.id,
    )
    store.add_failure_log(
        target_id=target.id,
        where_stuck="wp-login.php hydra brute force",
        breakthrough_clue="Account lockouts triggered; switched to SMB backup archive inspection",
        rule_for_next_time="Inspect unauthenticated network shares before brute forcing web logins",
    )
    store.add_failure_log(
        target_id=internal_target.id,
        where_stuck="MySQL port 3306 direct connect",
        breakthrough_clue="Host filtered from external subnet; route through SOCKS proxy on 10.10.10.20",
        rule_for_next_time="Always check routing tables and active pivots before declaring port dead",
    )
    store.set_active_target(target.id)

    print(f"Successfully seeded demo workspace '{ws.name}' with subnets, pivots, and exam proofs!")


if __name__ == "__main__":
    db = sys.argv[1] if len(sys.argv) > 1 else None
    s = NotebookStore(db)
    seed_demo(s)
