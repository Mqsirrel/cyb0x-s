# CYB0X-S — SAFE FIELD WORKSHEET

**Conservative, passive, human-controlled pentesting and lab field worksheet.**

```
┌─────────────────────────────────────────────────────────────┐
│ CYB0X-S WORKSHEET                    MODE: SAFE             │
│ Passive field worksheet              Human-controlled       │
└─────────────────────────────────────────────────────────────┘
```

CYB0X-S is the conservative, passive companion to CYB0X. Its purpose is to provide a fast, local terminal/TUI field worksheet for recording information that the human operator has personally discovered during cybersecurity labs, CTFs, and security assessments.

---

## 1. Core Design Principle

> **The human decides and performs the security-testing actions.**
> **CYB0X-S records and organizes them.**

This project is **NOT** an AI pentesting assistant, solver, attack planner, or autonomous security tool. It contains zero autonomous scripts, zero external AI API integrations, zero heuristic vulnerability scorers, and zero background scanners.

---

## 2. What It Is

A fast, lightweight, keyboard-driven digital field notebook designed to replace `notes.txt`, scratchpads, and complex note apps during active security assessments.

### What It Does
* **Organizes by Target**: Records target IPs, hostnames, OS info, and operator observations.
* **Records Services**: Stores ports, protocols, service banners, and software versions manually observed.
* **Records Findings**: Stores security findings discovered by the operator, with optional human-assigned severities.
* **Manages Credentials Safely**: Simple local vault with masked password display (`********`), explicit toggle reveal, and direct clipboard copying.
* **Tracks Methodology Checklist**: Manually toggled status (`TODO`, `CHECKED`, `DEFERRED`, `DEAD-END`) with optional static methodology templates.
* **Captures Evidence**: Logs references and paths to screenshots, flag hashes, and command outputs without automatic collection.
* **Fast CLI Capture**: Record discoveries in sub-second CLI commands (e.g. `cyb0x-s note "..."`, `cyb0x-s cred admin:pass`).
* **Standalone Export**: Export clean, human-readable Markdown notebooks, JSON backups, or plain text summaries.
* **Fast Search**: Instant keyword search across notes, findings, services, creds, and evidence (`Ctrl+F` or `cyb0x-s search`).
* **Clipboard Integration**: Instant copying of IPs, `IP:port`, credentials, or checklist items directly to your terminal clipboard (`y` key).

### What It Does NOT Do
* **NO AI or LLM Calls**: No OpenAI, Anthropic, Ollama, or AI SDK dependencies whatsoever.
* **NO Attack Recommendations**: Does not tell you what to run next or predict attack paths.
* **NO Automatic Scanning**: Does not execute nmap, masscan, gobuster, or any background network scans.
* **NO Automatic Vulnerability Classification**: Does not parse banners to infer CVEs or suggest exploits.
* **NO Automatic Credential Harvesting**: Does not scrape commands or outputs for passwords.
* **NO Command Generation**: Does not formulate exploit payloads or automated commands based on target ports.
* **NO Behavioral Monitoring / Hidden Logic**: Completely transparent, local-first code that does exactly what the operator types.

---

## 3. Exam & Certification Disclaimer

> [!IMPORTANT]
> **CYB0X-S is designed as a passive note-taking and organization tool. Whether it may be used during a particular certification or assessment depends entirely on that provider’s current rules. Users must verify the rules themselves before using it.**
>
> CYB0X-S makes no claim of endorsement or pre-approval by OffSec (OSCP), INE Security (eJPT), Hack The Box, or any other certification body. Always consult the specific assessment rules and guidelines provided by your exam proctor or examination authority before using any tool.

---

## 4. Example Workflow

```
Run your tools yourself (nmap, burp, terminal)
               ↓
     Discover something
               ↓
    Record it in CYB0X-S
               ↓
       Continue working
               ↓
     Update findings/evidence
               ↓
       Export your notes
```

---

## 5. Installation

```bash
# Clone the repository
git clone https://github.com/your-org/cyb0x-s.git
cd cyb0x-s

# Install locally with pip or uv
pip install -e .
# or
uv pip install -e .
```

---

## 6. Fast Capture CLI

The CLI is engineered for minimal friction. It records verbatim what you supply:

### Record a Target
```bash
cyb0x-s target 10.10.10.20 --hostname target.local --os Linux
# Shorthand alias:
cyb0x-s t 10.10.10.20
```

### Record a Service
```bash
cyb0x-s service 10.10.10.20 22/tcp SSH --version "OpenSSH 8.2p1"
cyb0x-s service 10.10.10.20 80/tcp HTTP --version "Apache 2.4.41"
cyb0x-s service 10.10.10.20 445/tcp SMB --version "Samba 4.3"
# Shorthand alias:
cyb0x-s s 445/tcp SMB
```

### Record a Field Note
```bash
cyb0x-s note "Port 80 redirects to /login"
# Shorthand alias:
cyb0x-s n "backup share contains archive.zip"
```

### Record a Manually Discovered Finding
```bash
cyb0x-s finding "SMB anonymous access enabled" --notes "read access to backup share" --severity HIGH
# Shorthand alias:
cyb0x-s f "HTTP default credentials on tomcat manager"
```

### Record a Credential
```bash
cyb0x-s cred admin:secret123 --source "backup.zip" --scope "SMB"
# Shorthand alias:
cyb0x-s c user:Summer2024!
```

### Manage Checklists & Ready Methodology Templates
CYB0X-S includes ready-to-use, community-curated methodology templates (eJPTv2, OSCP, r/eJPT, r/oscp standard). These are 100% static cognitive safety nets and are fully permitted during timed hands-on assessments.

| Template | Focus Area | Items | Description |
|---|---|---|---|
| `ejpt` | Master Workflow | 14 | Full eJPTv2 assessment flow (Scope → Discovery → Foothold → Pivoting → PrivEsc) |
| `discovery` | Network Discovery | 7 | Local subnets, ARP scans, ICMP sweeps, TTL OS guesses, dual-homed machine discovery |
| `pivoting` | Pivoting & Routing | 13 | Dual-homed detection, Metasploit autoroute, SOCKS5 proxy, SSH tunnels, Chisel, Proxychains |
| `web` | Web Applications | 14 | Headers, robots.txt, directory fuzzing, SQLi, LFI, XSS, Command Injection, uploads |
| `smb` | SMB & Shares | 9 | Null sessions, share permissions, backups/configs, enum4linux, RID cycling |
| `ftp` | FTP Services | 8 | Anonymous login, banner CVEs, binary mode, writable folders, web shell uploads |
| `ssh` | SSH Services | 7 | OpenSSH banner CVEs, key permissions, root login, discovered credential spraying |
| `snmp` | SNMP (UDP 161) | 9 | Community strings, MIB walk, running processes, installed software, interfaces |
| `databases` | Databases (MySQL/MSSQL)| 9 | Blank root logins, table dumping, MySQL `LOAD_FILE`, MSSQL `xp_cmdshell` |
| `linux` | Linux PrivEsc | 14 | SUID/SGID, `sudo -l`, cron jobs, capabilities, writable passwd, shadow leaks |
| `windows` | Windows PrivEsc | 14 | `whoami /priv` (SeImpersonate), unquoted paths, AlwaysInstallElevated, scheduled tasks |
| `cracking` | Password Cracking | 9 | Hash identification, John the Ripper, Hashcat modes, Hydra online brute-forcing |

```bash
# Apply eJPT master methodology to active target:
cyb0x-s checklist template ejpt

# Apply pivoting checklist for an internal host:
cyb0x-s checklist template pivoting

# Check off an item:
cyb0x-s checklist check "Directory and file fuzzing"

# List current checklist items:
cyb0x-s checklist list
```

*(In the TUI, press **`m`** to open the interactive template picker)*

### Search Across Everything
```bash
cyb0x-s search "backup"
```

### Export Notes
```bash
# Clean standalone Markdown notebook:
cyb0x-s export --format md -o notes.md

# Full lossless JSON backup:
cyb0x-s export --format json -o workspace_backup.json

# Plain text:
cyb0x-s export --format txt
```

---

## 7. Terminal User Interface (TUI)

Launch the interactive field notebook by running:

```bash
cyb0x-s
# or
cyb0x-s tui
```

### TUI Keyboard Shortcuts

| Key | Action |
|---|---|
| `Tab` / `Shift+Tab` | Cycle focus between panels |
| `j` / `k` or `↑` / `↓` | Navigate items in list |
| `y` | Copy selected item (IP, port, secret, note text) to clipboard |
| `Space` | Cycle checklist status (`TODO` → `CHECKED` → `DEFERRED` → `DEAD-END`) or toggle password reveal |
| `/` or `Ctrl+F` | Open global search modal |
| `t` | Add target |
| `s` | Add service to active target |
| `f` | Record finding |
| `c` | Record credential |
| `n` | Add field note |
| `k` | Add checklist item |
| `m` | Apply static checklist template (`linux`, `windows`, `web`, `smb`, `privesc`, `pivoting`) |
| `d` | Delete highlighted item |
| `?` | View help and shortcut reference |
| `q` | Exit CYB0X-S |

### Quick Command Bar (Bottom of TUI)
You can also type single-line commands into the bottom input field:
* `:n <text>` — Record a note
* `:f <text>` — Record a finding
* `:c <user:pass>` — Record a credential
* `:s <port/proto> <service>` — Record a service
* `:t <ip>` — Record a new target
* `:q` — Quit

---

## 8. License

MIT License. Designed and built for ethical security professionals, lab students, and penetration testers who value speed, simplicity, and strict methodology control.
