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

### Offline eJPTv2 Cheat Sheet & Command Reference
Instant, offline playbook lookup with dynamic target IP substitution:

```bash
# Lookup WinRM commands for active target:
cyb0x-s ref winrm

# Lookup SMB commands and copy top syntax to clipboard:
cyb0x-s ref smb --copy

# Lookup PrivEsc, Pivoting, or Database commands:
cyb0x-s ref privesc
cyb0x-s ref mssql
cyb0x-s ref mimikatz
```

*(In the TUI, press **`r`** or type `:ref <keyword>` to open the interactive Cheat Sheet modal)*

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

Launch the interactive field worksheet by running:

```bash
cyb0x-s
# or
cyb0x-s tui
```

### The cockpit (station 1)

```
┌─ CYB0X-S  worksheet · Lab-01 ───────────────────────────────────── targets 1 ─┐
│ ◆ 10.10.10.20  target.local  Linux   [IN-SCOPE]  🏁 —  👑 —   3 ports 1 cred   │
│ NEXT ▸ SMB null session check   ██████░░░░  50% (2/4)              no blockers │
│  1 ⌂ Cockpit    2 ▸ Playbooks    3 ▸ Credentials    4 ▸ Loot & Flags          │
├──────────────────┬────────────────────────────────────────────────────────────┤
│ ATTACK SURFACE   │ SERVICES & PORTS                                  3 ports  │
│ ▾ 10.10.10.20    │  22/tcp   ssh     OpenSSH 8.2p1   ▸ hydra -l …             │
│   22 ssh         │  80/tcp   http    Apache 2.4.41   ▸ feroxbuster …          │
│   445 smb        │  445/tcp  smb     Samba 4.3       ▸ smbmap -H …            │
│                  ├────────────────────────────┬───────────────────────────────┤
│ CREDENTIALS      │ METHODOLOGY    ████░░ 50%  │ NOTES & FINDINGS     6 entries│
│ 🔑 admin : ••••  │ ✓ TCP enumeration          │ ⚠ SMB anonymous access [HIGH]│
├──────────────────┴────────────────────────────┴───────────────────────────────┤
│ ❯ smbmap -H 10.10.10.20 -u guest -p ''                        [Enter]=copy    │
│   Null session lists shares without auth — check every share for backups.     │
│ ▸ :s 445/tcp smb   :c admin:pw   :n note   :uflag <hash>   :ref winrm   ? help │
└───────────────────────────────────────────────────────────────────────────────┘
```

Station 1 answers the four questions you keep asking under time pressure:

| Zone | Question |
|---|---|
| Status strip | Which box am I on, and what have I captured? |
| `NEXT ▸` row | What should I try next? How far through the methodology am I? |
| Services panel | What is exposed, and what is the command for it? |
| Bottom console | What can I copy right now — and where do I type new findings? |

The remaining stations are deep dives: **2** offline playbooks, **3** the full
credential vault, **4** flags / foothold / rabbit-hole log.

### Themes

Two palettes ship with the app and can be swapped live:

| Name | Look | Command |
|---|---|---|
| `slate` | graphite chrome, cyan/mint data, amber warnings — **default** | `:theme slate` |
| `warm` | the original charcoal / terracotta / kraft identity | `:theme warm` |

Press **`T`** to cycle, or use `:theme <name>` in the command bar.
Below 110 columns the workbench stacks into a single column so rows stay readable.

### TUI Keyboard Shortcuts

| Key | Action |
|---|---|
| `1` | **Cockpit** — attack surface, services, methodology, notes |
| `2` | **Playbooks** — full-screen interactive playbook browser |
| `3` | **Credentials** — full-screen credential vault & spray matrix |
| `4` | **Loot & Flags** — user/root flags, foothold proof, rabbit-hole log |
| `Tab` / `Shift+Tab` | Cycle focus between panels |
| `j` / `k` (or `↑` / `↓`) | Move down / up inside the focused list or tree |
| `Enter` | **Copy the command** shown in the console for the highlighted row |
| `y` | Copy the value (IP, `IP:port`, secret, note text) |
| `Space` | Cycle checklist status (`TODO` → `CHECKED` → `DEFERRED` → `DEAD-END`) or reveal a credential |
| `z` | Zoom the focused panel to the whole cockpit (press again to restore) |
| `g` | Record captured flags (`user.txt`, `root.txt`) |
| `r` | Quick cheat-sheet modal |
| `o` | Toggle the active target in-scope / out-of-scope |
| `/` or `Ctrl+F` | Global search (type, `Enter` copies the top hit) |
| `t` / `s` / `f` / `c` / `n` | Add target / service / finding / credential / note |
| `K` (`Shift+k`) | Add custom checklist item (`k` is list navigation) |
| `m` | Methodology template picker |
| `d` | Delete highlighted item (asks for confirmation) |
| `T` | Cycle theme |
| `?` | Help and shortcut reference |
| `q` | Exit CYB0X-S |

The footer only shows the five keys you need to get going (`q ? / y Space`);
press `?` for the complete reference.

### Quick Command Bar (Bottom of TUI)

* `:1` … `:4` — instant station switching
* `:t <ip>` — add a target
* `:s <port/proto> <service>` — quick service entry (e.g. `:s 445/tcp smb`)
* `:c <user:pass>` — quick credential entry
* `:n <text>` — quick field note
* `:f <text>` — quick finding
* `:uflag <hash>` / `:rflag <hash>` — save captured exam flags
* `:foothold <vuln>` — record initial access vulnerability
* `:privesc <vector>` — record privilege escalation vector
* `:stuck <why>` — log a rabbit hole dead end
* `:clue <breakthrough>` — log the breakthrough clue that unlocked progress
* `:ev <path>` — log evidence
* `:ref <term>` — pop up the offline cheat sheet (e.g. `:ref winrm`)
* `:theme <name>` — switch palette (`slate`, `warm`); `:theme` alone cycles
* `:q` — quit

Anything else you type is recorded as a field note, so the bar never blocks you.

---

## 8. License

MIT License. Designed and built for ethical security professionals, lab students, and penetration testers who value speed, simplicity, and strict methodology control.
