# Using GLACIS in the INE eJPT v2 Exam

> **First**: read the current INE candidate rules yourself. This guide is
> community documentation, not legal advice, and rules can change.

The eJPT v2 is an open-book, hands-on practical exam. INE permits candidates
to keep **personal notes and command references** available during the exam.
GLACIS is exactly that — a local, offline notes file with a fast keyboard
interface — and nothing more.

## Why GLACIS is safe under AI proctoring

Modern INE exams may be monitored by an automated proctor that watches for
unauthorized assistance: AI assistants, communication tools, cloud services,
or anything reaching outside the exam environment.

GLACIS under that lens:

- **No AI, no models, no "smart" features.** Playbooks and `:ref` are static
  text bundled with the app — a `man` page, not an advisor. The optional
  derived-guidance helper ships **off by default**; leave it off for exams.
- **No network. Zero.** No telemetry, updates, sync, APIs, or sockets. There
  is literally no code path to the internet. An AI proctor inspecting
  processes or traffic sees a local SQLite file editor.
- **No automation of the exam.** GLACIS cannot scan, exploit, or execute
  anything. It shows you a command, you copy it, you run it in your own
  terminal with your own judgment — identical to reading it out of your own
  cheat sheet.
- **Visible transparency:** press **`E`** for Exam Mode. A persistent
  `[ EXAM MODE · OFFLINE NOTES ]` badge in the header makes the window's
  purpose obvious to anyone reviewing your screen.

## Setting up in the first 15 minutes

```text
glacis                      # launch
E                           # Exam Mode badge on
:ws init ejpt               # clean workspace: scans/ enum/ screenshots/ loot/
I                           # import the scope/nmap scan you run
:lhost auto && :lport 4444  # your VPN IP for the playbooks
:m ejpt                     # the exam methodology checklist
```

## The exam workflow (memorise this loop)

Per machine: `:t <ip>` → run your nmap → `I` import (or `:s 80 http`) →
highlight each service, `Enter` to copy the ready command → run it →
`Space` to mark CHECKED / DEAD-END → record everything you learn
(`:c` creds, `:uflag`/`:rflag` flags, `:q <n>` question proofs, `:f` findings)
→ `]` next machine.

Rules of the road:

- **The 20-minute rule:** stuck 20 minutes with no new lead → `Space` to
  DEFERRED, `:stuck why`, `]` rotate. Use station **0** (Pulse) to decide
  what's next — it ranks your own open items.
- **Proof as you go:** every exam question gets a `:q <n> <proof>` the moment
  you answer it. Before submitting: `:export exam` and answer from the
  dossier; `glacis export --format html -o exam.html` for a styled copy.
- **Don't touch `G`** (derived guidance) during the exam — the default,
  guidance-free posture is the exam-safe posture.

## What to do if a proctor challenges the tool

Close GLACIS and cooperate — your data is one local SQLite file plus plain
folders, nothing else. Politely point at the facts above (offline personal
notes, no network capability, no AI). And regardless of outcome, the vendor's
current rules always win: verify them before exam day.
