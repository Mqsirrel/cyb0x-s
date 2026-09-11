# GLACIS Assessment Field Workflow Guide

This guide walks through using **GLACIS** during a real cybersecurity lab, CTF, or penetration test.

```
┌─────────────────────────────────────────────────────────────┐
│ GLACIS WORKSHEET                                           │
│ Field notes & methodology tracker    Human-controlled       │
└─────────────────────────────────────────────────────────────┘
```

---

## 1. Why GLACIS vs `notes.txt` or Obsidian?

During a timed lab or fast-paced assessment, context switching is expensive. Opening a heavy note-taking tool or manually formatting bullet points in `notes.txt` introduces friction:

| Friction Point | `notes.txt` / Markdown file | GLACIS |
|---|---|---|
| **Adding a port & service** | Open editor, find section, type `- 445/tcp SMB Samba 4.3` | `glacis s 10.10.10.20 445/tcp SMB -v "Samba 4.3"` (< 1s) |
| **Masking credentials** | Plaintext in file, risk of shoulder surfing / stream leak | Masked by default (`********`), space/toggle to reveal |
| **Copying Target IP:Port** | Highlight with mouse, copy | Press `y` on service item |
| **Tracking methodology** | Manual checkboxes, messy status changes | Press `Space` to cycle `TODO` → `CHECKED` → `DEFERRED` → `DEAD-END` |
| **Exam preparation** | Complex formatting cleanup required at the end | Instant standalone Markdown export with `glacis export -f md` |

---

## 2. Realistic Step-by-Step Scenario

Imagine you are testing a lab machine at **`10.10.10.20`**.

### Step 1: Target Registration
Run your ping or quick check in your terminal:
```bash
$ ping -c 1 10.10.10.20
PING 10.10.10.20 (10.10.10.20) 56(84) bytes of data.
64 bytes from 10.10.10.20: icmp_seq=1 ttl=63 time=21.4 ms
```
Record the target in GLACIS:
```bash
$ glacis target 10.10.10.20 --hostname target.local --os Linux
✓ Target recorded: 10.10.10.20 (ID: 1)
```

### Step 2: Record Discovered Open Ports
You run your own port scanner (e.g. `nmap -p- --min-rate 1000 10.10.10.20`):
```bash
$ nmap -sC -sV -p 22,80,445 10.10.10.20
PORT    STATE SERVICE     VERSION
22/tcp  open  ssh         OpenSSH 8.2p1 Ubuntu 4ubuntu0.5
80/tcp  open  http        Apache httpd 2.4.41 ((Ubuntu))
445/tcp open  netbios-ssn Samba smbd 4.6.2
```
Instantly record each service:
```bash
$ glacis s 10.10.10.20 22/tcp SSH --version "OpenSSH 8.2p1"
$ glacis s 10.10.10.20 80/tcp HTTP --version "Apache 2.4.41"
$ glacis s 10.10.10.20 445/tcp SMB --version "Samba 4.6.2"
```

### Step 3: Apply Static Methodology Checklist
Load a standard methodology checklist to track what you check:
```bash
$ glacis checklist template smb
✓ Applied static template 'smb' (7 items) for 10.10.10.20
```

### Step 4: Investigating & Recording Findings
You manually run `smbclient -N -L //10.10.10.20/` and discover a readable `backup` share:
```bash
$ smbclient -N -L //10.10.10.20/
Anonymous login successful
        Sharename       Type      Comment
        ---------       ----      -------
        backup          Disk      System backups
        IPC$            IPC       IPC Service
```
Check off the methodology item and record the finding:
```bash
$ glacis checklist check "null session"
$ glacis finding "SMB anonymous access enabled" --notes "Read access to 'backup' share" --severity HIGH
$ glacis note "backup share contains company_backup.zip"
```

### Step 5: Recording Stored Credentials
You download `company_backup.zip`, unzip it, and inspect `config.php`:
```bash
$ unzip company_backup.zip
$ cat config.php | grep -i pass
$db_user = 'admin';
$db_pass = 'Summer2024!Secure';
```
Store the credential into GLACIS:
```bash
$ glacis cred admin:Summer2024!Secure --source "company_backup.zip / config.php" --scope "Web/Database"
✓ Credential saved (10.10.10.20): admin : ********
```
Notice that the password is automatically masked on screen.

### Step 6: Logging Screenshots & Evidence
You capture a screenshot of your initial shell or user flag:
```bash
$ glacis evidence "screenshots/proof_user_flag.png" --desc "User flag retrieved via web shell"
```

### Step 7: Live TUI Monitoring & Fast Toggling
Keep `glacis` open in a tmux pane or split terminal:
```bash
$ glacis
```
* Use `j`/`k` to navigate between findings and services.
* Press `y` on the service to copy `10.10.10.20:445` or target IP directly to your clipboard.
* Press `Space` on checklist items to advance their state (`TODO` → `CHECKED` → `DEFERRED` → `DEAD-END`).
* Press `Space` on the credential to briefly inspect the unmasked password.
* Press `Ctrl+F` to search for `"backup"` across all your notes.
* Press **`0`** for **Pulse**: a host-by-host kill-chain board plus
  explainable state-gap signals (e.g. `S6-foothold-no-golden`,
  `S4-flag-without-evidence`). Pressing **`G`** additionally reveals the
  opt-in focus-shift hints (`D1`–`D4`); the default `STATE ONLY` mode never
  suggests where to go next.
* Press **`5`** for **Network**: once you document a dual-homed host
  (`:pivot 192.168.50.0/24 via socks5:1080` or `glacis pivot …`), Station 5
  renders the subnet map and copies ProxyChains / Chisel / SSH-ProxyJump
  syntax for you to run yourself.
* Before ingesting a scan file, `:snap "pre-import"` rotates a local DB
  snapshot (the TUI also auto-snapshots before scan imports). `glacis
  snapshot restore 1` rolls back if an import mangles your notes.

### Step 8: Generating Standalone Deliverable / Report
When you finish your assessment or lab session, export everything to a standalone Markdown notebook:
```bash
$ glacis export --format md -o assessment_notes.md
✓ Exported workspace to: /path/to/assessment_notes.md
```

Your Markdown export is completely readable and structured:
```markdown
# Target: 10.10.10.20
> Hostname: `target.local` | OS: Linux

## Services
- 22/tcp — SSH — OpenSSH 8.2p1
- 80/tcp — HTTP — Apache 2.4.41
- 445/tcp — SMB — Samba 4.6.2

## Findings
- [HIGH] SMB anonymous access enabled
  Note: Read access to 'backup' share

## Credentials
- admin : ******** (Source: company_backup.zip / config.php, Scope: Web/Database)

## Checklist
- [x] Anonymous / guest null session authentication check
- [ ] List accessible shares and permissions (Read / Write)
- [ ] Inspect share contents for backups, scripts, or configuration files

## Notes
- backup share contains company_backup.zip

## Evidence
- [screenshot] `screenshots/proof_user_flag.png` — User flag retrieved via web shell
```

For a polished, printable handover use the self-contained HTML report
(embedded CSS, no external URLs, scripts or fonts):
```bash
$ glacis export --format html -o report.html
# inside the TUI: :export html report.html
```

Before exam day, verify the tool's offline posture yourself:
```bash
$ glacis exam-check
✓ PASS — zero network/telemetry imports; the tool is fully offline by construction.
```

---

## 3. Passive Safety Rules in Practice

1. **You make the decisions**: GLACIS will never recommend that you test SMB before HTTP.
2. **Exact verbatim storage**: `glacis note "admin:pass"` stays a note. Only `glacis cred admin:pass` stores a credential.
3. **No background tasks**: When `glacis` isn't responding to a keystroke or command, it does nothing.
4. **Offline and self-contained**: Everything is stored in a single local SQLite database.
