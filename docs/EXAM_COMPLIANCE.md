# Exam Compliance Charter

CYB0X-S accompanies certification lab exams such as INE's eJPT. This file is
the engineering policy that keeps the tool within exam rules. Every
contribution — human or AI-generated — must respect it.

## Context

- The eJPT exam is open-book: prepared notes, command references, and personal
  cheat sheets are permitted.
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

## PR checklist

- [ ] No new network calls (grep the diff for `requests`, `httpx`, `urllib`,
      `socket`, `urlopen`)
- [ ] Any suggestive/guidance feature is opt-in and off by default
- [ ] Scope-safety tests pass untouched
- [ ] No exam-specific content added
