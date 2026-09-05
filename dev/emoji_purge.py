"""Purge emoji from TUI row markup — screenshot audit finding F1.

Your terminal font renders emoji as tofu boxes. This script swaps every
emoji in the Python sources for the glyph set that provably renders in
your terminal shots: check/cross/arrows/blocks, [U]/[R] flag tags, etc.

Idempotent: running it twice changes nothing. It keeps CELL_CYCLE and
_format_state in sync, then reports any leftover non-ASCII glyphs so you
can review them by hand.

Usage:
    uv run python dev/emoji_purge.py --check   # report only, write nothing
    uv run python dev/emoji_purge.py           # apply in place

Note: verification states persisted in the DB from older builds (e.g.
"VALID" with the heavy check mark) will not match the new CELL_CYCLE;
affected cells reset to UNTESTED on next cycle — cosmetic only.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPLACEMENTS = [
    # --- ordered: longest / most specific first --------------------------
    ('("\U0001F3C1", self.target.user_flag), ("\U0001F451", self.target.root_flag)',
     '("[U]", self.target.user_flag), ("[R]", self.target.root_flag)'),
    ('"○ UNTESTED", "✔ VALID", "\U0001F451 PWN3D", "✗ INVALID"',
     '"○ UNTESTED", "✓ VALID", "★ PWN3D", "✗ INVALID"'),
    ('"VALID" in state or "✔" in state', '"VALID" in state or "✓" in state'),
    ('icon = "✔" if target.root_flag', 'icon = "✓" if target.root_flag'),
    ("⚠️ [VULN] ", "[VULN] "),
    ("⚠ [VULN] ", "[VULN] "),
    ("\U0001F4DD [NOTE] ", "[NOTE] "),
    ("\U0001F4F7 [EVID] ", "[EVID] "),
    ("⚡ [LEAD] ", "[LEAD] "),
    ("\U0001F573️ [DEAD-END] ", "[✗ DEAD-END] "),
    ("\U0001F573 [DEAD-END] ", "[✗ DEAD-END] "),
    ("\U0001F3C1 CAPTURED EXAM FLAGS", "CAPTURED EXAM FLAGS"),
    ("⚡ INITIAL FOOTHOLD", "INITIAL FOOTHOLD"),
    ("\U0001F451 PRIVILEGE ESCALATION", "PRIVILEGE ESCALATION"),
    ("\U0001F4DD EXAM QUESTION PROOFS", "EXAM QUESTION PROOFS"),
    ("\U0001F4DD RECORD EXAM QUESTION PROOF", "RECORD EXAM QUESTION PROOF"),
    ("\U0001F9E0 RABBIT HOLES", "RABBIT HOLES"),
    ("\U0001F4D6 eJPTv2 CHEAT SHEET", "eJPTv2 CHEAT SHEET"),
    ("\U0001F511 Breakthrough Clue", "» Breakthrough Clue"),
    ("\U0001F4CC Permanent Rule", "» Permanent Rule"),
    ("\U0001F4DD Free-form note", "Free-form note"),
    ("✔ COPIED ", "[✓] COPIED "),
    # --- bare leftovers ----------------------------------------------------
    ("\U0001F511 ", "◆ "),
    ("\U0001F573️ ", "✗ "),
    ("\U0001F573 ", "✗ "),
    ("⚡ ", "» "),
]

# Glyphs proven to render in the screenshot audit plus harmless typography.
SAFE = set("✓✗→○◐●◈▸█░◆★»·•…—–≥≤≈≠×÷←↑↓↳▼◇❯⏸⏳✖✔")


def main() -> int:
    check_only = "--check" in sys.argv
    root = Path(__file__).resolve().parent.parent
    rewritten = 0
    for path in sorted(root.glob("src/cyb0x_s/**/*.py")):
        text = path.read_text(encoding="utf-8")
        original = text
        hits = {}
        for old, new in REPLACEMENTS:
            n = text.count(old)
            if n:
                hits[old] = n
                text = text.replace(old, new)
        leftover = sorted({c for c in text if not c.isascii() and c not in SAFE})
        if hits or leftover:
            print(path.relative_to(root))
            for old, n in hits.items():
                print(f"    {n}x  {old[:40]!r}")
            if leftover:
                print(f"    review leftover glyphs: {' '.join(leftover)}")
        if text != original and not check_only:
            path.write_text(text, encoding="utf-8")
            rewritten += 1
    mode = "would rewrite" if check_only else "rewrote"
    print(f"\n{mode} {rewritten} file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
