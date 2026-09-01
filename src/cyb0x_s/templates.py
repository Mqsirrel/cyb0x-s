"""Static methodology templates for CYB0X-S checklists.

These templates are 100% static checklists representing standard human methodologies.
They do NOT dynamically adapt or recommend actions based on scan outputs or findings.
"""

from __future__ import annotations

from typing import Dict, List, Optional
from cyb0x_s.models import ChecklistItem, ChecklistStatus

STATIC_TEMPLATES: Dict[str, Dict[str, any]] = {
    "linux": {
        "category": "LINUX ENUMERATION",
        "description": "Standard manual Linux host enumeration checklist",
        "items": [
            "OS release and kernel version (`uname -a`, `/etc/os-release`)",
            "Current user context and group memberships (`id`, `groups`)",
            "Sudo privileges and rules (`sudo -l`)",
            "SUID / SGID executables (`find / -perm -4000 2>/dev/null`)",
            "Capabilities on local binaries (`getcap -r / 2>/dev/null`)",
            "Listening network services and ports (`ss -tulpn` or `netstat -antup`)",
            "Active processes and background tasks (`ps aux`, `ps -ef`)",
            "System cron jobs and timers (`/etc/cron*`, `crontab -l`, `systemctl list-timers`)",
            "World-writable files and directories (`find / -writable -type d 2>/dev/null`)",
            "Unmounted file systems and fstab (`cat /etc/fstab`, `lsblk`)",
            "SSH keys, history files, and config leaks (`~/.ssh`, `~/.bash_history`)",
            "Internal log files and spool directories (`/var/log`, `/var/mail`)",
        ],
    },
    "windows": {
        "category": "WINDOWS ENUMERATION",
        "description": "Standard manual Windows host enumeration checklist",
        "items": [
            "OS name, build, and architecture (`systeminfo`)",
            "Current user, SID, and assigned privileges (`whoami /all`, `whoami /priv`)",
            "Local and domain user accounts (`net user`, `net localgroup administrators`)",
            "Installed software and patches (`wmic qfe`, PowerShell `Get-HotFix`)",
            "Running processes and loaded modules (`tasklist /v`)",
            "Active network connections and routes (`netstat -ano`, `route print`)",
            "Service permissions and unquoted service paths (`accesschk.exe`, `wmic service`)",
            "Scheduled tasks and autoruns (`schtasks /query /fo LIST /v`)",
            "AlwaysInstallElevated registry settings inspection",
            "Saved credentials and DPAPI blobs (`cmdkey /list`, Vault)",
            "Active Directory domain join and trust relationships (`nltest /domain_trusts`)",
            "LAPS or credential manager configurations",
        ],
    },
    "web": {
        "category": "WEB ENUMERATION",
        "description": "Standard manual web application testing checklist",
        "items": [
            "Server headers, TLS certificates, and technologies (WhatWeb, Wappalyzer)",
            "Review robots.txt, sitemap.xml, and security.txt",
            "Directory and file enumeration (Gobuster / Feroxbuster / Dirsearch)",
            "Virtual host and subdomain enumeration",
            "Authentication mechanisms, default credentials, and password resets",
            "Session management and cookie attributes (HttpOnly, Secure, SameSite)",
            "Input parameter fuzzing and reflection checks",
            "File upload functionality and extension filtering",
            "API endpoints and OpenAPI / Swagger documentation",
            "Authorization boundaries and IDOR testing across roles",
        ],
    },
    "smb": {
        "category": "SMB ENUMERATION",
        "description": "Standard manual SMB service enumeration checklist",
        "items": [
            "SMB dialect negotiation and signing requirement",
            "Anonymous / guest null session authentication check",
            "List accessible shares and permissions (Read / Write)",
            "Inspect share contents for backups, scripts, or configuration files",
            "Enumerate domain / local user accounts via RPC / SAMR",
            "Enumerate groups and domain password policies",
            "Inspect IPC$ pipe accessibility",
        ],
    },
    "privesc": {
        "category": "PRIVILEGE ESCALATION",
        "description": "Standard manual privilege escalation checklist",
        "items": [
            "Verify current privileges, tokens, and groups",
            "Check for stored plaintext credentials in configuration / history files",
            "Audit writable system services, path variables, and binaries",
            "Audit scheduled tasks and automated cron jobs",
            "Check for outdated kernel or driver versions with known exploits",
            "Inspect internal loopback services bound to 127.0.0.1",
            "Check clipboard, credential managers, and memory dumps",
        ],
    },
    "pivoting": {
        "category": "PIVOTING & TUNNELING",
        "description": "Standard manual pivoting and network tunneling checklist",
        "items": [
            "Inspect local network interfaces and secondary NICs (`ip a`, `ifconfig`, `ipconfig`)",
            "Review ARP tables and neighbor caches (`ip neigh`, `arp -a`)",
            "Review system routing tables and default gateways (`route -n`, `netstat -r`)",
            "Scan internal subnets from compromise host (ping sweeps, port checks)",
            "Establish proxy / tunnel (SSH dynamic SOCKS -D, Chisel, Ligolo-ng)",
            "Configure Proxychains or SOCKS client routing",
            "Test access to secondary internal targets through tunnel",
        ],
    },
}


def get_available_templates() -> List[str]:
    """Return list of available static template keys."""
    return list(STATIC_TEMPLATES.keys())


def load_template(template_name: str) -> Optional[Dict[str, any]]:
    """Retrieve template definition by name."""
    name_clean = template_name.strip().lower()
    return STATIC_TEMPLATES.get(name_clean)


def apply_template_to_store(
    store: any,
    template_name: str,
    target_id: Optional[int] = None,
) -> List[ChecklistItem]:
    """Load a static template and instantiate checklist items into the store."""
    tmpl = load_template(template_name)
    if not tmpl:
        raise ValueError(f"Unknown template: {template_name}. Available: {', '.join(get_available_templates())}")

    category = tmpl["category"]
    created_items: List[ChecklistItem] = []
    for item_title in tmpl["items"]:
        item = store.add_checklist_item(
            title=item_title,
            category=category,
            target_id=target_id,
            status=ChecklistStatus.TODO,
        )
        created_items.append(item)
    return created_items
