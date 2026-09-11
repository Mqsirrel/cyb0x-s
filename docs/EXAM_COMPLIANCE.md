# Exam Compliance Charter

GLACIS accompanies certification lab exams such as INE's eJPT. This file is
the engineering policy that keeps the tool within exam rules. Every
contribution — human or AI-generated — must respect it.

## Context

- The eJPT exam is open-book: prepared notes and command references are
  permitted.
- The exam lab has no internet access; only the tools pre-installed in the
  exam environment may run against targets.
- INE community guidance treats tools that *suggest next actions* from entered
  data as a gray area.
- Credentialing best practice prohibits content derived from confidential exam
  material (flags, answers, lab specifics).

## Hard rules

1. **Fully offline.** No network requests, ever: no telemetry, analytics,
   update checks, cloud sync, or API integrations. If a feature needs the
   network, it does not ship.
2. **Passive by design.** The app records, organizes, references, and exports.
   It does not scan, exploit, brute-force, or execute payloads. Command text
   is copied by the user and run by the user, in their own terminal, under
   their own judgment.
3. **Derived guidance stays opt-in.** Any feature that infers next actions
   from entered data ships disabled by default and clearly labeled. The
   default posture is a notebook, not an advisor.
4. **Scope safety is non-negotiable.** Out-of-scope safeguards and
   `tests/test_scope_safety.py` stay in place and green. A PR that weakens
   scope checks is rejected outright.
5. **No confidential exam content.** Never commit real exam flags, answer
   banks, lab topologies, or question-specific solutions. Templates and
   reference material must be generic, original, or properly licensed with
   attribution.
6. **The candidate is responsible.** Rules change. Verify the current INE
   candidate agreement before exam day. This file is project policy, not
   legal advice.

## AI-proctored exams (eJPT v2 and similar)

Newer INE practical exams may be monitored by an AI proctoring system that
watches the candidate's screen and running applications for rule-breaking
behaviour (unauthorized assistance, communication tools, AI assistants,
cloud services). GLACIS is built to be unambiguous under that scrutiny:

| Proctor-visible signal | GLACIS behaviour |
|---|---|
| "Is an AI/LLM assisting?" | **No.** GLACIS ships no AI features and calls no models. Every suggestion in `Playbooks`/`Reference` is a static, bundled text lookup. |
| "Is anything sent over the network?" | **No.** Zero network code paths — verify with `glacis exam-check`. |
| "Is it talking to another person/machine?" | **No.** No chat, sync, telemetry, update checks, or APIs. One local SQLite file. |
| "Is it doing the exam for you?" | **No.** GLACIS cannot execute anything. Commands are copied; the candidate types/runs them and makes every decision. |
| "Is it exam content?" | **No.** Templates/reference are generic public methodology. No exam answers, flags, or vendor material. |

### Recommended exam posture

1. Launch with **Exam Mode**: press **`E`** (or `:exam on`) — the header shows
   a persistent `[ EXAM MODE · OFFLINE NOTES ]` badge so a reviewer can see at
   a glance that the window is a personal-notes worksheet.
2. Keep the default posture: derived guidance stays off, no mods.
3. Treat it exactly like the permitted personal notes it replaces: it holds
   only what *you* typed and generic references.
4. If a proctor or rules text is ever stricter than this file, follow the
   rules — close the tool or ask the vendor. The candidate is always
   responsible for compliance (Rule 6).

## PR checklist

- [ ] No new network calls (grep the diff for `requests`, `httpx`, `urllib`,
      `socket`, `urlopen`)
- [ ] Any suggestive/guidance feature is opt-in and off by default
- [ ] Scope-safety tests pass untouched
- [ ] No exam-specific content added
