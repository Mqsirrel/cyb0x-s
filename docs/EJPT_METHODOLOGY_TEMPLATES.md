# Penetration Testing & Assessment Methodology Templates Guide

This document describes the ready-to-use methodology checklists based on standard manual penetration testing guidelines (PTES, OWASP WSTG, NIST SP 800-115) built directly into **CYB0X-S**.

---

## 1. Why These Checklists are Assessment-Safe & Allowed

> **Methodology Note:**
> Hands-on practical assessments require the operator to manually discover, enumerate, exploit, pivot, and document vulnerabilities.
>
> In an assessment:
> * **Manual note-taking and static methodology checklists are 100% permitted.**
> * **Automated attack planners and autonomous exploit engines are strictly prohibited.**
>
> CYB0X-S templates are **completely static human checklists**. They do not run tools on your behalf, do not execute commands, and do not make autonomous decisions. They serve purely as your cognitive safety net under time pressure.

---

## 2. Available Ready Templates

You can apply any template in the TUI by pressing **`m`** and picking from the interactive list, or from the CLI using `cyb0x-s checklist template <name>`.

| Template Name | Focus Area | Items | Description |
|---|---|---|---|
| **`ejpt`** | Master Workflow | 14 | Complete eJPTv2 assessment flow (Scope → Discovery → Foothold → Pivoting → PrivEsc → Proofs) |
| **`discovery`** | Host & Network | 7 | Local subnets, ARP scans, ICMP sweeps, TTL OS guesses, dual-homed machine discovery |
| **`web`** | Web Applications | 14 | Headers, robots.txt, directory fuzzing, SQLi, LFI, XSS, Command Injection, file upload bypass |
| **`smb`** | SMB & Shares | 9 | Null sessions, share permissions, backups/configs, enum4linux, RID cycling, user enumeration |
| **`ftp`** | FTP Services | 8 | Anonymous login, banner CVEs, binary transfers, writable folders, web shell uploads |
| **`ssh`** | SSH Services | 7 | OpenSSH banner CVEs, key permissions, root login, discovered credential spraying |
| **`snmp`** | SNMP (UDP 161) | 9 | Community strings, MIB walk, running processes, installed software, network interfaces |
| **`databases`** | MySQL & MSSQL | 9 | Blank root logins, table dumping, MySQL `LOAD_FILE`, MSSQL `xp_cmdshell`, UDF privesc |
| **`pivoting`** | Pivoting & Routing | 13 | Dual-homed detection, Metasploit autoroute, SOCKS5 proxy, SSH tunnels, Chisel, Proxychains |
| **`linux`** | Linux PrivEsc | 14 | SUID/SGID, `sudo -l`, cron jobs, capabilities, writable passwd, shadow leaks, web configs |
| **`windows`** | Windows PrivEsc | 14 | `whoami /priv` (SeImpersonate), unquoted paths, AlwaysInstallElevated, scheduled tasks, saved creds |
| **`cracking`** | Password Cracking | 9 | Hash identification, John the Ripper, Hashcat modes, Hydra online brute-forcing |

---

## 3. Template Details & Checklist Items

### `ejpt` — Master Assessment Workflow
Recommended to apply first on your engagement or active target:
1. `[Scope & Recon]` Verify subnet scope, assigned IP address, and default gateway
2. `[Host Discovery]` Scan live hosts using arp-scan / fping / ping sweep
3. `[Port Discovery]` TCP full SYN port scan against live targets (`nmap -p- -sS -T4`)
4. `[Service & Version Detection]` Run service detection and default scripts (`nmap -sC -sV -O`)
5. `[Low-Hanging Fruit]` Test anonymous FTP, null SMB sessions, default web logins, SNMP public string
6. `[Web Enumeration]` Identify tech stack, fuzz directories/files, inspect source comments, review robots.txt
7. `[Vulnerability Analysis]` Match software versions against known CVEs manually (SearchSploit, Exploit-DB)
8. `[Foothold]` Execute verified manual exploit or valid credentials to obtain initial shell
9. `[Host Recon]` Run local enumeration (`id`, `whoami /priv`, network interfaces, routing table)
10. `[Pivoting Check]` Check for secondary NICs / internal subnets (`ip a`, `ifconfig`, `arp -a`, `netstat`)
11. `[Routing & Tunneling]` Set up route / socks proxy (Metasploit autoroute, SSH -D, Chisel) if secondary subnet found
12. `[Internal Host Discovery]` Scan internal targets through pivot tunnel (`proxychains nmap -sT -Pn`)
13. `[Privilege Escalation]` Elevate to root or NT AUTHORITY\SYSTEM using local misconfigurations
14. `[Flag & Proof Capture]` Document proof commands (`whoami`, `ip a`/`ipconfig`, flags) and take screenshots

---

### `pivoting` — Pivoting & Routing (The #1 eJPTv2 Exam Challenge)
Essential when you compromise a dual-homed host:
* Inspect network interfaces (`ip a`, `ifconfig`, `ipconfig /all`)
* Identify secondary internal subnets (e.g. `192.168.x.x` or `10.x.x.x`)
* Inspect local routing table and ARP cache (`ip route`, `arp -a`)
* Perform internal host discovery from compromised host (bash ping sweep)
* Add route in Metasploit (`route add <subnet> <netmask> <session_id>`)
* Launch Metasploit SOCKS proxy (`auxiliary/server/socks_proxy`) on port 1080
* Or set up SSH dynamic tunnel (`ssh -D 1080 -N -f user@<foothold_IP>`)
* Configure `/etc/proxychains4.conf` (`socks5 127.0.0.1 1080`)
* Scan internal target through tunnel (`proxychains -q nmap -sT -Pn -p 21,22,80,445 <IP>`)
* Configure Firefox proxy for internal web applications (`127.0.0.1:1080`)
* Exploit internal targets through proxy tunnel (`proxychains smbclient`, `proxychains crackmapexec`)

---

### `web` — Web Application Assessment
* Review headers, server banners, and cookies (WhatWeb, Wappalyzer)
* Review robots.txt, sitemap.xml, and client-side HTML comments
* Run directory/file fuzzing (Gobuster / Feroxbuster / Dirsearch)
* Test virtual hosts and subdomain routing
* Test admin endpoints for default credentials
* Test input parameters for SQL Injection (manual quotes `'`, `--`, OR 1=1, then sqlmap)
* Test for Path Traversal / LFI (`../../../../etc/passwd`, `win.ini`)
* Test input reflection for XSS (`<script>alert(1)</script>`)
* Test input fields for OS Command Injection (`; id`, `| whoami`)
* Test file upload bypass (`.php5`, `.phtml`, double extensions, MIME tampering)
* Scan CMS installations (WPScan, Droopescan)

---

### `smb` — SMB & NetBIOS Enumeration
* Check SMB dialect negotiation and signing requirement
* Test anonymous / guest null session (`smbclient -N -L //<IP>/`)
* List accessible shares and check read/write permissions
* Recursively inspect shares for backups, scripts, `.config`, `.xml`, `.zip`
* Run comprehensive SMB enumeration (`enum4linux-ng -A <IP>`)
* Enumerate local/domain user accounts via RPC (`rpcclient -U '' <IP>` with `enumdomusers`)
* Perform RID cycling to discover valid usernames
* Inspect domain password policy

---

### `snmp` — SNMP Enumeration (UDP 161)
* Verify UDP port 161 is open (`nmap -sU -p 161 -sV <IP>`)
* Brute-force community strings (`onesixtyone -c /usr/share/seclists/... <IP>`)
* Test default community strings: `public`, `private`, `manager`
* Query system MIB table (`snmpwalk -v2c -c public <IP> 1.3.6.1.2.1.1`)
* Enumerate running host processes (`snmpwalk -v2c -c public <IP> 1.3.6.1.2.1.25.4.2.1.2`)
* Enumerate installed software (`snmpwalk -v2c -c public <IP> 1.3.6.1.2.1.25.6.3.1.2`)
* Enumerate network interfaces (`snmpwalk -v2c -c public <IP> ipAddrTable`)
* Enumerate listening network ports (`snmpwalk -v2c -c public <IP> tcpConnTable`)
* Enumerate local user accounts (`snmpwalk -v2c -c public <IP> 1.3.6.1.4.1.77.1.2.25`)

---

## 4. How to Use in CYB0X-S

### Inside the TUI:
1. Press **`m`** on any active target.
2. Use the **`↑` / `↓`** arrow keys to highlight the desired methodology (e.g. `ejpt`, `web`, `pivoting`).
3. Press **`Enter`**. The complete checklist is instantly added to your active worksheet target!
4. Focus the checklist panel with **`Tab`**, navigate items with **`j` / `k`**, and press **`Space`** to cycle item states:
   * `[ ]` **TODO** → `[✓]` **CHECKED** → `[~]` **DEFERRED** → `[✗]` **DEAD-END**

### From the Command Line:
```bash
# Apply eJPT master methodology
cyb0x-s checklist template ejpt

# Apply pivoting checklist for an internal dual-homed machine
cyb0x-s checklist template pivoting -t 10.10.10.20

# Apply web application testing checklist
cyb0x-s checklist template web -t 10.10.10.20

# Check off an item
cyb0x-s checklist check "Directory and file fuzzing" -t 10.10.10.20
```
