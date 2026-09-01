"""Static methodology templates for CYB0X-S checklists.

These templates represent standard manual penetration testing methodologies commonly
utilized in eJPTv2, OSCP, and lab assessments (curated from community best practices).

Strictly passive: these are human memory-aids and methodology tracking checklists.
They contain zero dynamic code, zero adaptive algorithms, and zero autonomous scanning.
"""

from __future__ import annotations

from typing import Dict, List, Optional
from cyb0x_s.models import ChecklistItem, ChecklistStatus

STATIC_TEMPLATES: Dict[str, Dict[str, any]] = {
    "ejpt": {
        "category": "EJPTv2 MASTER METHODOLOGY",
        "description": "Complete eJPTv2 multi-phase assessment workflow (Recon → Foothold → Pivoting → PrivEsc)",
        "items": [
            "1. [Scope & Recon] Verify subnet scope, assigned IP address, and default gateway",
            "2. [Host Discovery] Scan live hosts using arp-scan / fping / ping sweep",
            "3. [Port Discovery] TCP full SYN port scan against live targets (`nmap -p- -sS -T4`)",
            "4. [Service & Version Detection] Run service detection and default scripts (`nmap -sC -sV -O`)",
            "5. [Low-Hanging Fruit] Test anonymous FTP, null SMB sessions, default web logins, SNMP public string",
            "6. [Web Enumeration] Identify tech stack, fuzz directories/files, inspect source comments, review robots.txt",
            "7. [Vulnerability Analysis] Match software versions against known CVEs manually (SearchSploit, Exploit-DB)",
            "8. [Foothold] Execute verified manual exploit or valid credentials to obtain initial shell",
            "9. [Host Recon] Run local enumeration (`id`, `whoami /priv`, network interfaces, routing table)",
            "10. [Pivoting Check] Check for secondary NICs / internal subnets (`ip a`, `ifconfig`, `arp -a`, `netstat`)",
            "11. [Routing & Tunneling] Set up route / socks proxy (Metasploit autoroute, SSH -D, Chisel) if secondary subnet found",
            "12. [Internal Host Discovery] Scan internal targets through pivot tunnel (`proxychains nmap -sT -Pn`)",
            "13. [Privilege Escalation] Elevate to root or NT AUTHORITY\\SYSTEM using local misconfigurations",
            "14. [Flag & Proof Capture] Document proof commands (`whoami`, `ip a`/`ipconfig`, flags) and take screenshots",
        ],
    },
    "discovery": {
        "category": "NETWORK & HOST DISCOVERY",
        "description": "Standard host discovery and network mapping methodology",
        "items": [
            "Identify local network interface and routing table (`ip a`, `ip route`, `route -n`)",
            "Perform ARP sweep on the local subnet (`arp-scan --localnet` or `netdiscover -r <subnet>`)",
            "Perform ICMP ping sweep across target range (`fping -a -g <subnet> 2>/dev/null`)",
            "Inspect TTL values to guess OS (TTL ~64 = Linux/Unix, TTL ~128 = Windows)",
            "Run fast TCP port discovery on discovered live hosts (`nmap -sn` / `nmap -F`)",
            "Identify dual-homed machines, routers, and default gateways",
            "Record all discovered live IP addresses as targets in worksheet",
        ],
    },
    "web": {
        "category": "WEB APPLICATION TESTING",
        "description": "Standard web application manual testing methodology (OWASP & eJPTv2 focus)",
        "items": [
            "Inspect HTTP response headers, cookies, and server banners (`curl -I`, WhatWeb, Wappalyzer)",
            "Review robots.txt, sitemap.xml, crossdomain.xml, and security.txt",
            "Review HTML source code and client-side JavaScript for comments, hidden inputs, and paths",
            "Run directory and file fuzzing (Gobuster / Feroxbuster / Dirsearch with common.txt or raft wordlists)",
            "Test virtual hosts and subdomain routing (Gobuster vhost fuzzing / `Host:` header manipulation)",
            "Test administrative endpoints for default credentials (e.g. `admin:admin`, `admin:password`)",
            "Inspect authentication, session management, and cookies (HttpOnly, Secure, SameSite flags)",
            "Test input parameters for SQL Injection (manual quotes `'`, `--`, OR 1=1, then sqlmap if confirmed)",
            "Test parameters for Path Traversal / Local File Inclusion (`../../../../etc/passwd`, `win.ini`)",
            "Test input reflection for Cross-Site Scripting (Reflected / Stored XSS `<script>alert(1)</script>`)",
            "Test input fields for OS Command Injection (`; id`, `| whoami`, `$(whoami)`)",
            "Test file upload forms (extension bypass `.php5`, `.phtml`, double extensions, MIME-type tampering)",
            "Scan CMS installations if applicable (WPScan for WordPress, Droopescan for Drupal, Joomscan)",
            "Inspect API endpoints, REST routes, and Swagger / OpenAPI documentation",
        ],
    },
    "smb": {
        "category": "SMB ENUMERATION",
        "description": "SMB & Windows file sharing enumeration methodology",
        "items": [
            "Check SMB protocol dialect support and SMB signing requirement (`crackmapexec smb <IP>` / `nxc smb`)",
            "Test anonymous / guest null session authentication (`smbclient -N -L //<IP>/`)",
            "List accessible shares and verify read / write permissions on each share",
            "Recursively inspect accessible shares for backups, scripts, `.config`, `.xml`, or `.zip` files",
            "Run comprehensive SMB enumeration (`enum4linux-ng -A <IP>` or `enum4linux -a <IP>`)",
            "Enumerate domain and local user accounts via RPC / SAMR (`rpcclient -U '' <IP>` with `enumdomusers`)",
            "Perform RID cycling to discover valid usernames (`crackmapexec smb <IP> -u '' -p '' --rid-brute`)",
            "Inspect domain password policy (lockout threshold, minimum password length)",
            "Check for named pipes accessibility (e.g. `samr`, `lsarpc`, `spoolss`)",
        ],
    },
    "ftp": {
        "category": "FTP ENUMERATION",
        "description": "File Transfer Protocol enumeration and inspection checklist",
        "items": [
            "Check banner and exact FTP server version (check for vsftpd 2.3.4 backdoor or known CVEs)",
            "Test anonymous login (`ftp <IP>` with username `anonymous` and blank/email password)",
            "List all files including hidden files (`ls -la` in FTP prompt)",
            "Check if binary mode is required for binary/executable transfers (`binary`)",
            "Download all discovered configuration files, source code, or credential archives",
            "Test write permissions in FTP root and subdirectories (`put test.txt`)",
            "If writable and web server serves the FTP directory, test uploading web shell (`shell.php`)",
            "Test brute-forcing user credentials using Hydra (`hydra -L users.txt -P rockyou.txt ftp://<IP>`)",
        ],
    },
    "ssh": {
        "category": "SSH ENUMERATION",
        "description": "Secure Shell configuration and credential testing checklist",
        "items": [
            "Inspect OpenSSH banner and version (check for user enumeration CVEs like OpenSSH < 7.7)",
            "Verify allowed authentication methods (Password, Publickey, Keyboard-interactive)",
            "Test root login permission (`ssh root@<IP>`)",
            "Test any discovered credentials or default accounts (`admin`, `user`, `test`, `guest`)",
            "Inspect harvested private keys (`id_rsa`), verify permissions (`chmod 600 id_rsa`), and test login",
            "If private key is passphrase-protected, convert and crack with John (`ssh2john.py id_rsa > hash`)",
            "Test password spraying or targeted brute-force with Hydra if account names are known",
        ],
    },
    "snmp": {
        "category": "SNMP ENUMERATION",
        "description": "SNMP (UDP 161) community string and MIB enumeration checklist",
        "items": [
            "Verify UDP port 161 is open using nmap (`nmap -sU -p 161 -sV <IP>`)",
            "Brute-force community strings using wordlist (`onesixtyone -c /usr/share/seclists/... <IP>`)",
            "Test default community strings: `public`, `private`, `manager`, `community`",
            "Query system MIB table (`snmpwalk -v2c -c public <IP> 1.3.6.1.2.1.1` or `snmp-check <IP>`)",
            "Enumerate running host processes (`snmpwalk -v2c -c public <IP> 1.3.6.1.2.1.25.4.2.1.2`)",
            "Enumerate installed software (`snmpwalk -v2c -c public <IP> 1.3.6.1.2.1.25.6.3.1.2`)",
            "Enumerate system network interfaces and IP addresses (`snmpwalk -v2c -c public <IP> ipAddrTable`)",
            "Enumerate listening network ports and services (`snmpwalk -v2c -c public <IP> tcpConnTable`)",
            "Enumerate local user accounts (`snmpwalk -v2c -c public <IP> 1.3.6.1.4.1.77.1.2.25`)",
        ],
    },
    "databases": {
        "category": "DATABASE SERVICES",
        "description": "Database enumeration checklist (MySQL 3306, MSSQL 1433, PostgreSQL 5432)",
        "items": [
            "Check database service banner and authentication requirements",
            "Test default administrative accounts (MySQL: `root` with blank password, MSSQL: `sa`)",
            "Test discovered system/web credentials against database ports",
            "List accessible databases, tables, and columns (`SHOW DATABASES;`, `SELECT name FROM master..sysdatabases;`)",
            "Dump user password hashes and credentials from database tables",
            "Check MySQL file read capability (`SELECT LOAD_FILE('/etc/passwd');`)",
            "Check MySQL file write / web shell capability (`SELECT '<?php system($_GET[\"c\"]); ?>' INTO OUTFILE '...';`)",
            "Check MSSQL command execution capability (`EXEC sp_configure 'show advanced options', 1; RECONFIGURE; EXEC sp_configure 'xp_cmdshell', 1; RECONFIGURE;`)",
            "Check for database User Defined Functions (UDF) privilege escalation avenues",
        ],
    },
    "pivoting": {
        "category": "PIVOTING & ROUTING (eJPTv2)",
        "description": "Dual-homed host discovery, routing table setup, and pivot tunneling methodology",
        "items": [
            "Inspect compromised host network interfaces (`ip a`, `ifconfig`, `ipconfig /all`)",
            "Identify secondary internal subnets (e.g. `192.168.x.x`, `10.x.x.x`) not reachable directly",
            "Inspect routing table and default gateway (`ip route`, `route -n`, `route print`)",
            "Inspect local ARP cache for neighbors on internal subnets (`ip neigh`, `arp -a`)",
            "Perform internal host discovery from compromised host (ping sweep bash loop or ping.exe)",
            "Metasploit route method: add route in msfconsole (`route add <internal_subnet> <netmask> <session_id>`)",
            "Metasploit SOCKS proxy: launch `auxiliary/server/socks_proxy` (port 1080, SOCKS5)",
            "SSH dynamic tunnel: set up SOCKS proxy via SSH (`ssh -D 1080 -N -f user@<foothold_IP>`)",
            "Chisel tunnel: run chisel server on attacker (`chisel server -p 8000 --reverse`) and client on victim",
            "Configure `/etc/proxychains4.conf` to point to `socks5 127.0.0.1 1080` (ensure `quiet_mode` is enabled)",
            "Scan internal target through tunnel (`proxychains -q nmap -sT -Pn -n -p 21,22,80,445,3389 <internal_IP>`)",
            "Access internal web applications through browser (configure Firefox proxy to `127.0.0.1:1080`)",
            "Exploit internal target through proxy tunnel (`proxychains smbclient`, `proxychains crackmapexec`)",
        ],
    },
    "linux": {
        "category": "LINUX ENUMERATION",
        "description": "Standard manual Linux host enumeration and privilege escalation checklist",
        "items": [
            "OS release and kernel version (`uname -a`, `cat /etc/os-release`, `cat /etc/issue`)",
            "Current user context and group memberships (`id`, `groups`, `whoami`)",
            "Sudo privileges and rules (`sudo -l`)",
            "SUID / SGID executables (`find / -perm -u=s -type f 2>/dev/null`)",
            "Capabilities on local binaries (`getcap -r / 2>/dev/null`)",
            "Listening network services and ports (`ss -tulpn` or `netstat -antup`)",
            "Active processes and background tasks (`ps aux | grep root`, pspy)",
            "System cron jobs and timers (`cat /etc/crontab`, `/etc/cron.*`, `crontab -l`, `systemctl list-timers`)",
            "World-writable files and directories (`find / -writable -type d 2>/dev/null`)",
            "Unmounted file systems and fstab (`cat /etc/fstab`, `lsblk`)",
            "SSH keys, history files, and config leaks (`~/.ssh`, `~/.bash_history`)",
            "Readable `/etc/shadow` or writable `/etc/passwd`",
            "Plaintext credentials in web files (`/var/www/html/`, `wp-config.php`)",
            "NFS exports with `no_root_squash` (`cat /etc/exports`)",
        ],
    },
    "windows": {
        "category": "WINDOWS ENUMERATION",
        "description": "Standard manual Windows host enumeration and privilege escalation checklist",
        "items": [
            "OS name, build, and architecture (`systeminfo`)",
            "Current user, SID, and assigned privileges (`whoami /all`, `whoami /priv`)",
            "Check for Impersonate privileges (`SeImpersonatePrivilege` -> PrintSpoofer/GodPotato)",
            "Local and domain user accounts (`net user`, `net localgroup administrators`)",
            "Installed software and patches (`wmic qfe`, PowerShell `Get-HotFix`)",
            "Running processes and loaded modules (`tasklist /v`)",
            "Active network connections and routes (`netstat -ano`, `route print`)",
            "Service permissions and unquoted service paths (`accesschk.exe`, `wmic service`)",
            "Scheduled tasks and autoruns (`schtasks /query /fo LIST /v`)",
            "AlwaysInstallElevated registry settings inspection",
            "Saved credentials and DPAPI blobs (`cmdkey /list`, Vault)",
            "Stored plaintext passwords in unattend files (`Unattend.xml`, `sysprep.inf`)",
        ],
    },
    "privesc": {
        "category": "PRIVILEGE ESCALATION",
        "description": "Cross-platform privilege escalation checklist (Linux & Windows low-hanging fruit)",
        "items": [
            "[Linux] Sudo rights (`sudo -l`) and GTFOBins check",
            "[Linux] SUID binaries (`find / -perm -u=s -type f 2>/dev/null`)",
            "[Linux] Writable cron jobs or systemd services",
            "[Linux] Stored credentials in bash history or web configs",
            "[Windows] `whoami /priv` for SeImpersonate / SeBackupPrivilege",
            "[Windows] Unquoted service paths and weak service permissions",
            "[Windows] AlwaysInstallElevated registry settings",
            "[Windows] Saved credentials in `cmdkey /list`",
        ],
    },
    "cracking": {
        "category": "PASSWORD & HASH CRACKING",
        "description": "Hash identification, password cracking, and online brute-forcing methodology",
        "items": [
            "Identify hash type (`hashid -m <hash>` or `hash-identifier` or name-that-hash)",
            "Identify hash format: MD5 (0), SHA256 (1400), NTLM (1000), NetNTLMv2 (5600), Unix crypt (1800)",
            "Prepare target hash file (clean up whitespace, ensure correct format)",
            "Run John the Ripper (`john --wordlist=/usr/share/wordlists/rockyou.txt --format=<format> hashes.txt`)",
            "Run Hashcat if GPU available (`hashcat -m <mode> -a 0 hashes.txt /usr/share/wordlists/rockyou.txt`)",
            "Online brute-force for SSH with Hydra (`hydra -l <user> -P /usr/share/wordlists/rockyou.txt ssh://<IP> -t 4`)",
            "Online brute-force for FTP with Hydra (`hydra -L users.txt -P passwords.txt ftp://<IP> -vV`)",
            "Online brute-force for HTTP POST login (`hydra <IP> http-post-form \"/login.php:user=^USER^&pass=^PASS^:F=invalid\" -L users.txt -P rockyou.txt`)",
            "Test cracked passwords against all discovered targets and services (credential reuse)",
        ],
    },
}

# Aliases for convenience
TEMPLATE_ALIASES: Dict[str, str] = {
    "linux-privesc": "linux",
    "windows-privesc": "windows",
    "net": "discovery",
    "scan": "discovery",
    "routing": "pivoting",
    "tunnel": "pivoting",
    "db": "databases",
    "sql": "databases",
    "crack": "cracking",
    "hashes": "cracking",
}


def get_available_templates() -> List[str]:
    """Return list of canonical template names."""
    return list(STATIC_TEMPLATES.keys())


def load_template(template_name: str) -> Optional[Dict[str, any]]:
    """Retrieve template definition by name, supporting common aliases."""
    name_clean = template_name.strip().lower()
    canonical = TEMPLATE_ALIASES.get(name_clean, name_clean)
    return STATIC_TEMPLATES.get(canonical)


def apply_template_to_store(
    store: any,
    template_name: str,
    target_id: Optional[int] = None,
) -> List[ChecklistItem]:
    """Load a static template and instantiate checklist items into the store."""
    tmpl = load_template(template_name)
    if not tmpl:
        valid_options = ", ".join(get_available_templates())
        raise ValueError(f"Unknown template: '{template_name}'. Available templates: {valid_options}")

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
