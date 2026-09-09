#!/usr/bin/env python3
"""Build the illustrated GLACIS Field Guide / Operator Guide PDFs.

Design goals (v2 rewrite):
  * Clear first: readable 9pt+ typography, real quick-start, one repeating
    "core loop" the reader can memorise in a minute.
  * Easy to scan: grouped keyboard/console reference tables, colour-coded
    callouts (TIP / GOLDEN RULE / SUCCESS), aspect-correct screenshots.
  * Better workflows: five battle-tested workflows (first contact, exam
    battle plan, credential spray loop, pivoting, prove & submit) written as
    terminal-action + GLACIS-action pairs, plus the v0.2.0 Pulse rhythm.

Outputs (both from the same content, matching the committed filenames):
    docs/CYB0X-S_Field_Guide.pdf
    docs/CYB0X-S_Operator_Guide.pdf

Rebuild with:  python scripts/build_pdf_guide.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.platypus import (
    HRFlowable,
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# ---------------------------------------------------------------------------
# Design tokens
# ---------------------------------------------------------------------------

INK = colors.HexColor("#0F172A")
ACCENT = colors.HexColor("#1D63B8")
LINE = colors.HexColor("#C9D4E0")
MUTED = colors.HexColor("#475569")
ZEBRA = colors.HexColor("#F5F8FB")
HEADER_FILL = colors.HexColor("#13294B")

TIP_BG, TIP_BAR = colors.HexColor("#F0F7FF"), ACCENT
GOLD_BG, GOLD_BAR = colors.HexColor("#FFF8E7"), colors.HexColor("#D97706")
OK_BG, OK_BAR = colors.HexColor("#F0FDF4"), colors.HexColor("#059669")
PULSE_BG, PULSE_BAR = colors.HexColor("#F5F3FF"), colors.HexColor("#7C3AED")

PAGE_W, PAGE_H = letter
M_LEFT = M_RIGHT = 40
CONTENT_W = PAGE_W - M_LEFT - M_RIGHT  # 532pt


def _register_styles() -> dict:
    s = {}
    s["title"] = ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=30, leading=34, textColor=INK)
    s["subtitle"] = ParagraphStyle("subtitle", fontName="Helvetica", fontSize=12.5, leading=17, textColor=MUTED)
    s["version"] = ParagraphStyle("version", fontName="Helvetica-Bold", fontSize=10.5, leading=14, textColor=ACCENT)
    s["h1"] = ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=14, leading=17, textColor=INK, spaceBefore=10, spaceAfter=2)
    s["h2"] = ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=10.5, leading=13.5, textColor=ACCENT, spaceBefore=8, spaceAfter=2)
    s["body"] = ParagraphStyle("body", fontName="Helvetica", fontSize=9.2, leading=13, textColor=INK, spaceAfter=4)
    s["small"] = ParagraphStyle("small", fontName="Helvetica", fontSize=8, leading=11, textColor=MUTED, spaceAfter=3)
    s["cell"] = ParagraphStyle("cell", fontName="Helvetica", fontSize=8.2, leading=11, textColor=INK)
    s["cellb"] = ParagraphStyle("cellb", fontName="Helvetica-Bold", fontSize=8.2, leading=11, textColor=INK)
    s["cellmuted"] = ParagraphStyle("cellmuted", fontName="Helvetica", fontSize=8.2, leading=11, textColor=MUTED)
    s["th"] = ParagraphStyle("th", fontName="Helvetica-Bold", fontSize=8.4, leading=11, textColor=colors.white)
    s["code"] = ParagraphStyle("code", fontName="Courier", fontSize=8.2, leading=11, textColor=INK)
    s["codeb"] = ParagraphStyle("codeb", fontName="Courier-Bold", fontSize=8.2, leading=11, textColor=ACCENT)
    s["key"] = ParagraphStyle("key", fontName="Courier-Bold", fontSize=8.4, leading=11, textColor=ACCENT)
    s["callout"] = ParagraphStyle("callout", fontName="Helvetica", fontSize=8.8, leading=12.4, textColor=INK)
    s["callouttitle"] = ParagraphStyle("callouttitle", fontName="Helvetica-Bold", fontSize=9.2, leading=12.5, textColor=INK)
    s["caption"] = ParagraphStyle("caption", fontName="Helvetica-Oblique", fontSize=7.8, leading=10, textColor=MUTED, alignment=1)
    s["chip"] = ParagraphStyle("chip", fontName="Helvetica-Bold", fontSize=9, leading=12, textColor=colors.white, alignment=1)
    s["toc"] = ParagraphStyle("toc", fontName="Helvetica", fontSize=9.2, leading=13.6, textColor=INK)
    s["tocb"] = ParagraphStyle("tocb", fontName="Helvetica-Bold", fontSize=9.2, leading=13.6, textColor=INK)
    return s


S = _register_styles()


def P(text: str, style: str = "body") -> Paragraph:
    return Paragraph(text, S[style])


# ---------------------------------------------------------------------------
# Components
# ---------------------------------------------------------------------------

def section(num: str, title: str) -> Table:
    """Numbered section banner: accent chip + title + rule."""
    chip = Table([[Paragraph(f"<b>{num}</b>", S["chip"])]], colWidths=[26], rowHeights=[17])
    chip.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), ACCENT),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("ROUNDEDCORNERS", [3, 3, 3, 3]),
    ]))
    row = Table([[chip, Paragraph(title, S["h1"])]], colWidths=[34, CONTENT_W - 34])
    row.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return Table([[row], [HRFlowable(width="100%", thickness=1.1, color=ACCENT, spaceBefore=1, spaceAfter=6)]])


def subsection(title: str) -> Paragraph:
    return Paragraph(title, S["h2"])


def callout(kind: str, title: str, body_html: str) -> Table:
    bg, bar = {"tip": (TIP_BG, TIP_BAR), "gold": (GOLD_BG, GOLD_BAR),
               "ok": (OK_BG, OK_BAR), "pulse": (PULSE_BG, PULSE_BAR)}[kind]
    icon = {"tip": "&#9656;", "gold": "&#9873;", "ok": "&#10003;", "pulse": "&#9673;"}[kind]
    inner = [
        [Paragraph(f"{icon}&nbsp; {title}", S["callouttitle"])],
        [Paragraph(body_html, S["callout"])],
    ]
    t = Table(inner, colWidths=[CONTENT_W - 0])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("LINEBEFORE", (0, 0), (0, -1), 3, bar),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (0, 0), 6),
        ("BOTTOMPADDING", (0, -1), (0, -1), 6),
        ("TOPPADDING", (0, 1), (0, 1), 1),
        ("BOTTOMPADDING", (0, 0), (0, 0), 1),
    ]))
    return t


def data_table(headers: list[str], rows: list[list], widths: list[float], zebra: bool = True) -> Table:
    head = [Paragraph(h, S["th"]) for h in headers]

    def _cell(c):
        if isinstance(c, (Paragraph, Table, Spacer)):
            return c
        if isinstance(c, (list, tuple)):  # a list of flowables stays as-is
            return list(c)
        return Paragraph(str(c), S["cell"])

    body = [[_cell(c) for c in r] for r in rows]
    t = Table([head] + body, colWidths=widths, repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_FILL),
        ("GRID", (0, 0), (-1, -1), 0.5, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    if zebra:
        style.append(("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ZEBRA]))
    t.setStyle(TableStyle(style))
    return t


def K(short: str) -> Paragraph:
    """Keycap cell."""
    return Paragraph(f"<b>{short}</b>", S["key"])


def C(text: str) -> Paragraph:
    """Code cell."""
    return Paragraph(text, S["code"])


def CB(text: str) -> Paragraph:
    return Paragraph(text, S["codeb"])


def figure(path: Path, caption: str, max_w: float = CONTENT_W, max_h: float = 235) -> Table:
    """Aspect-correct screenshot card with caption."""
    with PILImage.open(path) as im:
        w, h = im.size
    scale = min(max_w / w, max_h / h)
    fw, fh = w * scale, h * scale
    img = Image(str(path), width=fw, height=fh)
    t = Table([[img], [Paragraph(caption, S["caption"])]], colWidths=[fw + 10])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("BOX", (0, 0), (-1, -1), 0.75, LINE),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, 0), 5),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 2),
        ("TOPPADDING", (0, 1), (-1, 1), 2),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 5),
    ]))
    return t


def chip_row(chips: list[str], color: str = "#1D63B8") -> Table:
    """A row of label chips separated by chevrons, e.g. SCAN > RECORD > ..."""
    arrow_style = ParagraphStyle("arr", fontName="Helvetica-Bold", fontSize=12, leading=14, textColor=MUTED, alignment=1)
    row, widths = [], []
    chip_w = (CONTENT_W - 18 * (len(chips) - 1)) / len(chips)
    for i, c in enumerate(chips):
        row.append(Paragraph(f"<b>{c}</b>", S["chip"]))
        widths.append(chip_w)
        if i < len(chips) - 1:
            row.append(Paragraph("<b>&#8250;</b>", arrow_style))
            widths.append(18)
    t = Table([row], colWidths=widths)
    style = [("VALIGN", (0, 0), (-1, -1), "MIDDLE")]
    for i in range(0, len(row), 2):
        style += [
            ("BACKGROUND", (i, 0), (i, 0), colors.HexColor(color)),
            ("TOPPADDING", (i, 0), (i, 0), 4),
            ("BOTTOMPADDING", (i, 0), (i, 0), 4),
            ("ROUNDEDCORNERS", [3, 3, 3, 3]),
        ]
    t.setStyle(TableStyle(style))
    return t


# ---------------------------------------------------------------------------
# Page furniture
# ---------------------------------------------------------------------------

class NumberedCanvas(pdfcanvas.Canvas):
    """Running header (pages 2+) and footer with total page count."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._decorate(total)
            super().showPage()
        super().save()

    def _decorate(self, total: int):
        self.saveState()
        if self._pageNumber > 1:
            self.setFont("Helvetica-Bold", 7.6)
            self.setFillColor(MUTED)
            self.drawString(M_LEFT, PAGE_H - 26, "GLACIS FIELD GUIDE")
            self.setFont("Helvetica", 7.6)
            self.drawRightString(PAGE_W - M_RIGHT, PAGE_H - 26, "v0.2.0 \u201cPulse\u201d \u00b7 offline worksheet & exam companion")
            self.setStrokeColor(LINE)
            self.setLineWidth(0.6)
            self.line(M_LEFT, PAGE_H - 31, PAGE_W - M_RIGHT, PAGE_H - 31)
        self.setStrokeColor(LINE)
        self.setLineWidth(0.6)
        self.line(M_LEFT, 34, PAGE_W - M_RIGHT, 34)
        self.setFont("Helvetica", 7.6)
        self.setFillColor(MUTED)
        self.drawString(M_LEFT, 22, "100% offline \u00b7 local SQLite \u00b7 zero telemetry \u00b7 human-controlled")
        self.drawRightString(PAGE_W - M_RIGHT, 22, f"Page {self._pageNumber} of {total}")
        self.restoreState()


# ---------------------------------------------------------------------------
# The guide
# ---------------------------------------------------------------------------

def build_story(screens: Path) -> list:
    story: list = []

    # =====================================================================
    # COVER
    # =====================================================================
    story.append(Spacer(1, 10))
    story.append(Paragraph("GLACIS FIELD GUIDE", S["title"]))
    story.append(Spacer(1, 4))
    story.append(Paragraph("The offline penetration-testing worksheet &amp; practical-exam companion", S["subtitle"]))
    story.append(Paragraph("Version 0.2.0 \u201cPulse\u201d \u00b7 eJPTv2 / eCPPT friendly \u00b7 works the same in labs, CTFs and client work", S["version"]))
    story.append(HRFlowable(width="100%", thickness=2, color=ACCENT, spaceBefore=6, spaceAfter=9))

    story.append(P(
        "GLACIS is a keyboard-driven terminal worksheet that sits next to your tools and remembers "
        "everything for you: targets, ports, services, credentials, flags, proofs, dead ends and the "
        "commands you ran. It <b>never attacks anything itself</b> \u2014 it shows you the right command, "
        "copies it to your clipboard, and you run it in your own terminal. Everything lives in a local "
        "SQLite file. No network, no cloud, no AI in the loop."))
    story.append(Spacer(1, 5))

    story.append(subsection("The whole method in one line"))
    story.append(chip_row(["SCAN", "RECORD", "COPY", "RUN", "MARK", "EXPORT"]))
    story.append(Spacer(1, 7))

    cards = Table(
        [[
            Paragraph("<b>Why it wins in practical exams</b>", S["cellb"]),
            Paragraph("<b>Exam-integrity compliance</b>", S["cellb"]),
        ],
        [
            Paragraph(
                "\u2022 One screen answers: which host, what\u2019s open, what\u2019s next, what did I prove?<br/>"
                "\u2022 Ready-made commands per service \u2014 press <font face='Courier-Bold' color='#1D63B8'>Enter</font> to copy, zero typos.<br/>"
                "\u2022 Credential matrix stops password-reuse amnesia across machines.<br/>"
                "\u2022 Pulse dashboard shows exactly which machine is being neglected.",
                S["cell"]),
            Paragraph(
                "\u2022 <b>100% offline</b> \u2014 local SQLite, zero network calls, zero telemetry.<br/>"
                "\u2022 <b>Zero autonomous action</b> \u2014 GLACIS copies commands; you execute them.<br/>"
                "\u2022 <b>No AI / cloud assistance</b> \u2014 nothing that violates exam rules.<br/>"
                "\u2022 Equivalent to permitted personal notes (Obsidian / CherryTree), just faster.",
                S["cell"]),
        ]],
        colWidths=[CONTENT_W / 2 - 4, CONTENT_W / 2 - 4],
    )
    cards.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), ZEBRA),
        ("BACKGROUND", (1, 0), (1, 0), OK_BG),
        ("BOX", (0, 0), (0, -1), 0.6, LINE),
        ("BOX", (1, 0), (1, -1), 0.6, OK_BAR),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(cards)
    story.append(Spacer(1, 10))

    story.append(subsection("What\u2019s in this guide"))
    toc_rows = [
        ("1", "Start in 10 minutes \u2014 install, launch, first target, first export", "2"),
        ("2", "The five stations \u2014 what each screen is for (+ what\u2019s new in v0.2.0)", "3"),
        ("3", "The core loop \u2014 the six beats you repeat on every machine", "4"),
        ("4", "Keyboard map \u2014 grouped by task, survival keys first", "5"),
        ("5", "Console command reference \u2014 every : command, verified", "6"),
        ("6", "Workflow I & II \u2014 first contact with a machine \u00b7 the exam battle plan", "7"),
        ("7", "Workflow III & IV \u2014 credential spray loop \u00b7 pivoting to the internal net", "8"),
        ("8", "Workflow V \u2014 prove it and submit (proofs, flags, reports, backups)", "9"),
        ("9", "Pulse \u2014 the see-everything dashboard and when to look at it", "10"),
        ("10", "Methodology templates & CLI pocket reference \u00b7 exam-day checklist", "11"),
    ]
    toc = Table(
        [[Paragraph(f"<b>{n}</b>", S["tocb"]), Paragraph(t, S["toc"]), Paragraph(f"<b>{p}</b>", S["tocb"])] for n, t, p in toc_rows],
        colWidths=[24, CONTENT_W - 54, 30],
    )
    toc_style_leading = 13.6
    toc.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, colors.HexColor("#E3EAF2")),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
    ]))
    story.append(toc)
    story.append(Spacer(1, 12))
    story.append(P("This guide was refreshed for v0.2.0 with documentation assistance from <b>GPT-6 Astra (medium)</b>; "
                   "every command shown was verified against the v0.2.0 source.", "small"))

    story.append(PageBreak())

    # =====================================================================
    # 1 — START IN 10 MINUTES  +  2 — FIVE STATIONS
    # =====================================================================
    story.append(section("1", "Start in 10 minutes"))
    story.append(P("Do this once per lab. Every step is optional except 1\u20133 \u2014 GLACIS never forces ceremony."))

    steps = [
        (CB("1"), P("<b>Install &amp; launch</b>", "cell"), [C("pip install -e .   # inside the repo"), C("glacis                 # opens the TUI")]),
        (CB("2"), P("<b>Make it yours</b>", "cell"), [C("T          # theme picker, d = save default"), C(":theme midnight  # or direct switch")]),
        (CB("3"), P("<b>Create the lab workspace</b>", "cell"), [C("W               # workspace manager"), C(":ws init lab01   # scaffolds scans/ enum/"), C("                 # screenshots/ notes/ loot/")]),
        (CB("4"), P("<b>Get targets in fast</b>", "cell"), [C("I                      # import nmap XML/txt/gnmap"), C(":t 10.10.10.20         # or add one by hand"), C(":subnet 10.10.10.20 10.10.10.0/24")]),
        (CB("5"), P("<b>Load a methodology</b>", "cell"), [C("m           # template picker"), C(":m ejpt     # master exam checklist")]),
        (CB("6"), P("<b>Work the loop</b> (\u00a73)", "cell"), [C("j/k, Enter, Space   # copy cmd, run it,"), C("                    # mark result, repeat")]),
        (CB("7"), P("<b>Export &amp; protect</b>", "cell"), [C(":export exam            # markdown dossier"), C("glacis export --format html -o report.html"), C("glacis backup --label checkpoint")]),
    ]
    story.append(data_table(
        ["#", "Step", "Do exactly this"],
        [[a, b, [x for x in c]] for a, b, c in steps],
        [22, 130, CONTENT_W - 152],
    ))
    story.append(Spacer(1, 4))
    story.append(P("Prefer plain shell? Every TUI action has a CLI twin \u2014 see the pocket reference in \u00a710.", "small"))
    story.append(Spacer(1, 8))
    story.append(callout(
        "gold", "Mind-set",
        "GLACIS is the co-pilot, not the pilot. It remembers, suggests syntax and tracks progress; "
        "<b>you</b> scan, exploit and decide. Write down everything the moment you learn it \u2014 future-you "
        "at hour six is a stranger."))

    story.append(PageBreak())

    story.append(section("2", "The five stations"))
    story.append(P("GLACIS splits the work across five screens. Switch with the number keys \u2014 anything you record is shared by all of them."))
    story.append(data_table(
        ["Key", "Station", "What it gives you", "Go here when\u2026"],
        [
            [K("0"), P("<b>Pulse</b> \u2014 engagement dashboard", "cell"), P("Stat cards, 14-day momentum sparkline, per-target scorecards (A\u2013F), next-action queue, live timeline of everything recorded.", "cell"), P("You finish a box, feel lost, or wonder what to touch next.", "cell")],
            [K("1"), P("<b>Cockpit</b> \u2014 the workbench", "cell"), P("Target tree, services &amp; ports with triage states, methodology checklist, notes and the command console.", "cell"), P("Actually working a machine \u2014 this is home.", "cell")],
            [K("2"), P("<b>Playbooks</b>", "cell"), P("Offline command encyclopedia: per-service attack recipes you can copy with Enter.", "cell"), P("You know the service, not the syntax.", "cell")],
            [K("3"), P("<b>Credentials</b>", "cell"), P("2D matrix: accounts \u00d7 services. Compiles spray commands; tracks valid / pwned / invalid.", "cell"), P("You hold creds and need to know where they work.", "cell")],
            [K("4"), P("<b>Loot &amp; Flags</b>", "cell"), P("User/root flags, foothold &amp; privesc proofs, question evidence, disk-loot browser, rabbit-hole log.", "cell"), P("You captured something \u2014 or you\u2019re stuck.", "cell")],
        ],
        [30, 105, 225, CONTENT_W - 360],
    ))
    story.append(Spacer(1, 8))
    story.append(callout(
        "pulse", "New in v0.2.0 \u2014 Pulse, HTML reports and snapshots",
        "Press <font face='Courier-Bold' color='#1D63B8'>0</font> anytime for the new <b>Pulse</b> dashboard: momentum sparkline, per-target scorecards "
        "and a next-action queue built from your own open items. Export a self-contained <b>HTML report</b> with "
        "<font face='Courier-Bold' color='#1D63B8'>glacis export --format html</font>, and protect long sessions with <font face='Courier-Bold' color='#1D63B8'>glacis backup</font>. "
        "All still 100% offline \u2014 see \u00a79."))

    story.append(PageBreak())

    # =====================================================================
    # 3 — THE CORE LOOP
    # =====================================================================
    story.append(section("3", "The core loop \u2014 six beats, every machine"))
    story.append(P(
        "Everything in GLACIS serves this loop. It takes seconds per beat and leaves a perfect trail: "
        "<b>what you tried, what worked, what to prove.</b>"))
    story.append(data_table(
        ["Beat", "Key / command", "What happens"],
        [
            [P("<b>1 \u00b7 RECORD</b>", "cellb"), C(":t 10.10.10.20  \u00b7  :s 445/tcp smb"), P("Target and services land in the cockpit; checklists and playbooks key off them.", "cell")],
            [P("<b>2 \u00b7 COPY</b>", "cellb"), [K("j / k"), Spacer(1, 1), K("Enter")], P("Highlight a service \u2014 the console shows a ready command with the IP substituted. Enter copies it.", "cell")],
            [P("<b>3 \u00b7 RUN</b>", "cellb"), C("(your terminal / tmux pane)"), P("Paste and execute. GLACIS never runs anything.", "cell")],
            [P("<b>4 \u00b7 MARK</b>", "cellb"), K("Space"), P("Cycle the service status: UNTESTED \u2192 CHECKED \u2192 DEAD-END \u2192 DEFERRED. The checklist % and Pulse coverage update.", "cell")],
            [P("<b>5 \u00b7 CAPTURE</b>", "cellb"), C(":c user:pass  \u00b7  :uflag \u2026  \u00b7  :q 7 \u2026"), P("Creds, flags and question proofs go straight into the ledger while you have them.", "cell")],
            [P("<b>6 \u00b7 PIVOT</b>", "cellb"), K("]"), P("Next target. Check station 0 if you\u2019re unsure what \u201cnext\u201d is.", "cell")],
        ],
        [72, 175, CONTENT_W - 247],
    ))
    story.append(Spacer(1, 6))
    story.append(KeepTogether([
        figure(screens / "01-worksheet.png",
               "Station 1 Cockpit \u2014 attack-surface tree (left), services with triage states (top right), methodology & notes (bottom), command console underneath.",
               max_h=185),
        Spacer(1, 6),
        callout(
            "tip", "PRO-TIP \u2014 the zero-mouse flow",
            "Highlight a port with <font face='Courier-Bold' color='#1D63B8'>j / k</font> \u2192 read the console \u2192 press "
            "<font face='Courier-Bold' color='#1D63B8'>.</font> to swap tool recipes (whatweb \u2192 feroxbuster \u2192 gobuster \u2192 nikto \u2192 curl) \u2192 "
            "<font face='Courier-Bold' color='#1D63B8'>Enter</font> copies \u2192 run it in tmux \u2192 <font face='Courier-Bold' color='#1D63B8'>Space</font> to mark the result. "
            "Your hands never leave the keyboard."),
    ]))

    story.append(PageBreak())

    # =====================================================================
    # 4 — KEYBOARD MAP
    # =====================================================================
    story.append(section("4", "Keyboard map \u2014 grouped by job"))
    story.append(P("Single letters fire instantly unless a modal or the console input is focused. "
                   "On day one you only need the eight keys in the blue box \u2014 the rest come naturally."))

    story.append(subsection("A \u00b7 Survival \u2014 learn these first"))
    story.append(data_table(
        ["Key", "Does"],
        [
            [K("0 1 2 3 4"), P("Jump to Pulse / Cockpit / Playbooks / Credentials / Loot &amp; Flags.", "cell")],
            [K("j / k"), P("Move down / up in the focused list or tree (arrows work too).", "cell")],
            [K("Enter"), P("Copy the highlighted command / value (matrix: compiled spray command).", "cell")],
            [K("Space"), P("Cycle triage status; in station 3 cycle UNTESTED \u2192 VALID \u2192 PWN3D \u2192 INVALID; in station 4 preview loot.", "cell")],
            [K("y"), P("Quick-copy the row\u2019s core value (IP, IP:port, secret, note text).", "cell")],
            [K("/ or Ctrl+F"), P("Global search across everything; Enter copies the top hit.", "cell")],
            [K("?"), P("Full help &amp; shortcut reference.", "cell")],
            [K("q"), P("Quit (your data is already saved).", "cell")],
        ],
        [80, CONTENT_W - 80],
    ))
    story.append(Spacer(1, 5))

    story.append(subsection("B \u00b7 Capture \u2014 get findings in fast"))
    story.append(data_table(
        ["Key", "Does"],
        [
            [K("t / s / c / n"), P("Add target / service / credential / note via modal (or just type :t, :s, :c, :n in the console).", "cell")],
            [K("f"), P("Record a finding with optional severity.", "cell")],
            [K("K"), P("Add a custom checklist item (capital K \u2014 lowercase k moves).", "cell")],
            [K("m"), P("Methodology template picker.", "cell")],
            [K("I"), P("Import a scan: Nmap XML/text/gnmap, FFUF, feroxbuster, gobuster \u2014 staged for review before anything is committed.", "cell")],
            [K("g"), P("Record captured user/root flags.", "cell")],
            [K("a"), P("Link a question number to proof evidence (station 4).", "cell")],
            [K("v"), P("Paste clipboard screenshot into screenshots/ and attach as evidence.", "cell")],
        ],
        [80, CONTENT_W - 80],
    ))
    story.append(Spacer(1, 5))

    story.append(subsection("C \u00b7 Move fast"))
    story.append(data_table(
        ["Key", "Does"],
        [
            [K("[ / ]"), P("Previous / next target \u2014 rotate machines in one keystroke.", "cell")],
            [K(", / ."), P("Cycle the tool recipe for the highlighted service in the console.", "cell")],
            [K("w \u00b7 h / l"), P("Cycle panel focus; jump to left / right column.", "cell")],
            [K("b \u00b7 z"), P("Collapse sidebar \u00b7 zoom focused panel full-screen.", "cell")],
            [K("o \u00b7 r \u00b7 T"), P("Toggle scope \u00b7 offline reference modal \u00b7 theme picker (d saves; G toggles derived guidance, off by default).", "cell")],
        ],
        [80, CONTENT_W - 80],
    ))
    story.append(Spacer(1, 6))
    story.append(callout(
        "tip", "Day-one eight",
        "<font face='Courier-Bold' color='#1D63B8'>0-4</font> stations \u00b7 <font face='Courier-Bold' color='#1D63B8'>j / k</font> move \u00b7 "
        "<font face='Courier-Bold' color='#1D63B8'>Enter</font> copy \u00b7 <font face='Courier-Bold' color='#1D63B8'>Space</font> mark \u00b7 "
        "<font face='Courier-Bold' color='#1D63B8'>:</font> console \u00b7 <font face='Courier-Bold' color='#1D63B8'>y</font> copy value \u00b7 "
        "<font face='Courier-Bold' color='#1D63B8'>/</font> search \u00b7 <font face='Courier-Bold' color='#1D63B8'>?</font> help. "
        "Everything else can wait until you feel the rhythm \u2014 and <font face='Courier-Bold' color='#1D63B8'>r</font> opens the offline syntax cheatsheet."))

    story.append(PageBreak())

    # =====================================================================
    # 5 — CONSOLE COMMANDS
    # =====================================================================
    story.append(section("5", "Console command reference"))
    story.append(P("Press <font face='Courier-Bold' color='#1D63B8'>:</font> and type. Tab completes; Esc returns to the workbench."))

    story.append(subsection("Capture"))
    story.append(data_table(
        ["Command", "Effect"],
        [
            [C(":t 10.10.10.20 [hostname] [os] [subnet] [pivot]"), P("Add target (also: <font face='Courier' size='7.6'>add target \u2026</font> in plain words).", "cell")],
            [C(":s 445/tcp smb [-- notes]"), P("Record an open service on the active target.", "cell")],
            [C(":c admin:Secret123! [scope]"), P("Record a credential; scope tags the service.", "cell")],
            [C(":c crack 3 Password123!"), P("Upgrade a captured hash (row 3) to plaintext in place.", "cell")],
            [C(":n any free text"), P("Timestamped note attached to the active target.", "cell")],
            [C(":f Suspicious ACL on /admin"), P("Finding with optional severity prompt.", "cell")],
        ],
        [215, CONTENT_W - 215],
    ))
    story.append(Spacer(1, 5))

    story.append(subsection("Knowledge & navigation"))
    story.append(data_table(
        ["Command", "Effect"],
        [
            [C(":ref winrm  \u00b7  :ref smb"), P("Offline command reference for a service/tool.", "cell")],
            [C(":m ejpt  \u00b7  :m web append"), P("Load methodology template (replace or append).", "cell")],
            [C(":theme midnight"), P("Live theme switch (persist with T \u2192 d).", "cell")],
        ],
        [215, CONTENT_W - 215],
    ))
    story.append(Spacer(1, 5))

    story.append(subsection("Host state, proofs & evidence"))
    story.append(data_table(
        ["Command", "Effect"],
        [
            [C(":uflag 7a9e\u2026  \u00b7  :rflag f04b\u2026"), P("Record user / root flag for the active target.", "cell")],
            [C(":foothold smb null session  \u00b7  :privesc SUID \u2026"), P("Record how you got in and how you went up.", "cell")],
            [C(":q 7 /etc/shadow root hash"), P("Pin exam-question 7 to its proof string.", "cell")],
            [C(":stuck wp-login brute = rabbit hole"), P("Log a rabbit hole (also :dead).", "cell")],
            [C(":clue backup.zip in downloads share"), P("Log the breakthrough clue.", "cell")],
            [C(":ev latest [desc]  \u00b7  :paste-ev [desc]"), P("Attach newest OS screenshot / paste clipboard image as evidence.", "cell")],
            [C(":subnet 10.10.10.20 10.10.10.0/24"), P("Tag which subnet a target lives in.", "cell")],
            [C(":pivot 10.10.10.20 172.16.1.0/24"), P("Mark a dual-homed pivot host + its hidden subnet.", "cell")],
        ],
        [215, CONTENT_W - 215],
    ))
    story.append(Spacer(1, 5))

    story.append(subsection("Workspace & output"))
    story.append(data_table(
        ["Command", "Effect"],
        [
            [C(":ws lab02  \u00b7  :ws init lab02"), P("Switch workspace / scaffold a new lab folder tree.", "cell")],
            [C(":lhost auto  \u00b7  :lport 4444"), P("Attacker VPN IP (auto-detects tun0/wg0) &amp; listener port \u2014 substituted into playbooks.", "cell")],
            [C(":w rockyou  \u00b7  :w common  \u00b7  :w medium"), P("Copy standard wordlist paths to clipboard (see aliases below).", "cell")],
            [C(":export wordlists"), P("Write deduplicated loot/users.txt + loot/passwords.txt.", "cell")],
            [C(":export exam"), P("Markdown dossier: targets, question proofs, flags, creds, audit trail.", "cell")],
            [C(":w &lt;alias&gt;"), P("Copy a wordlist path: <font face='Courier' size='7.6'>rockyou \u00b7 common \u00b7 medium \u00b7 big / small \u00b7 raft-d / raft-f \u00b7 users / passwords \u00b7 fasttrack</font>.", "cell")],
        ],
        [215, CONTENT_W - 215],
    ))

    story.append(PageBreak())

    # =====================================================================
    # 6 — WORKFLOWS I & II
    # =====================================================================
    story.append(section("6", "Workflow I \u2014 first contact with a machine"))
    story.append(P("The repeatable 10-minute pattern for any new box. Left: what you run in your terminal. "
                   "Right: what you tell GLACIS."))
    story.append(data_table(
        ["#", "In your terminal", "In GLACIS"],
        [
            [CB("1"), C("nmap -sn 10.10.10.0/24"), P("Spot the alive hosts.", "cell")],
            [CB("2"), P("\u2014", "cell"), C(":t 10.10.10.20 hostname os  \u00b7  :subnet \u2026")],
            [CB("3"), C("nmap -sS -p- --min-rate 1000 10.10.10.20"), P("\u2014 (or import whole XML next step)", "cell")],
            [CB("4"), C("nmap -sV -sC -p 22,80,445 10.10.10.20 -oX out.xml"), C("I  \u2192 review staged hosts/services \u2192 commit")],
            [CB("5"), P("\u2014", "cell"), C(":m ejpt   # methodology on this target")],
            [CB("6"), P("run the copied recipe", "cell"), [K("j/k"), P("highlight service,", "cellmuted"), K("."), P("pick tool,", "cellmuted"), K("Enter"), P("copy", "cellmuted")]],
            [CB("7"), C("(paste & execute)"), K("Space"),],
            [CB("8"), P("find creds / flag / foothold", "cell"), C(":c \u2026  \u00b7  :uflag \u2026  \u00b7  :foothold \u2026  \u00b7  :q \u2026")],
            [CB("9"), P("stuck? move on", "cell"), C(":stuck \u2026 then ]  # rotate to next target")],
        ],
        [20, (CONTENT_W - 20) * 0.44, (CONTENT_W - 20) * 0.56],
    ))
    story.append(Spacer(1, 6))

    story.append(section("II", "Workflow II \u2014 the exam battle plan (5 phases)"))
    phases = [
        ("PHASE 1 \u00b7 Scope & discovery", "Find every machine and put it on the record.", C("nmap -sn / arp-scan \u2192 :t + :subnet per host \u00b7 :pivot for dual-homed boxes")),
        ("PHASE 2 \u00b7 Enumerate everything", "Full TCP sweep, then versions; import instead of typing.", C("nmap -p- \u2192 -sV -sC -oX \u2192 I import \u00b7 Space-mark each service as you clear it")),
        ("PHASE 3 \u00b7 Low-hanging fruit", "Anonymous & default access first, then web fuzzing.", C("ftp/smb/snmp quick wins \u2192 :w common + feroxbuster \u2192 :f findings with severity")),
        ("PHASE 4 \u00b7 Sprawl with creds", "Every cred into the matrix; spray SMB/SSH/WinRM everywhere (\u00a77).", C(":c harvest \u2192 station 3 \u2192 Enter = spray cmd \u2192 Space = VALID/PWN3D")),
        ("PHASE 5 \u00b7 Prove & submit", "Flags, question proofs, clean dossier \u2014 before you forget.", C(":uflag/:rflag \u00b7 :q n proof \u00b7 :export exam \u00b7 glacis backup --label submitted")),
    ]
    story.append(data_table(
        ["Phase", "Goal", "GLACIS verbs"],
        [[P(f"<b>{a}</b>", "cell"), P(b, "cell"), c] for a, b, c in phases],
        [110, 165, CONTENT_W - 275],
    ))
    story.append(Spacer(1, 8))
    story.append(KeepTogether([
        callout(
            "gold", "THE 20-MINUTE RULE \u2014 the single highest-value habit",
            "Stuck on one service for 20 minutes with no new lead? <b>Stop.</b> "
            "<font face='Courier-Bold' color='#1D63B8'>Space</font> it to <font face='Courier'>DEFERRED</font>, type "
            "<font face='Courier-Bold' color='#1D63B8'>:stuck what-you-tried</font>, press <font face='Courier-Bold' color='#1D63B8'>]</font> and rotate. "
            "The Pulse queue and your DEAD-END trail will bring you back with fresh eyes. Most failed practicals are one 3-hour rabbit hole deep."),
    ]))

    story.append(PageBreak())

    # =====================================================================
    # 7 — WORKFLOWS III & IV
    # =====================================================================
    story.append(section("III", "Workflow III \u2014 the credential spray loop"))
    story.append(P(
        "Multi-machine exams are won on password reuse. Station 3 lays every credential against every service, "
        "so \u201cdid I try this password on this box?\u201d always has a visible answer."))
    story.append(data_table(
        ["Step", "Action"],
        [
            [CB("1 \u00b7 HARVEST"), P("Pull creds from web configs, DB dumps, SAM hive, shell history.", "cell")],
            [CB("2 \u00b7 RECORD"), [K("c"), Spacer(1, 1), C(":c dbuser:S3cret! mysql")]],
            [CB("3 \u00b7 SPRAY"), [P("Station ", "cellmuted"), K("3"), P(" \u2192 highlight a cred \u00d7 service cell \u2192 ", "cellmuted"), K("Enter"), P(" copies the compiled spray command.", "cellmuted")]],
            [CB("4 \u00b7 RUN & MARK"), [P("Run it; ", "cellmuted"), K("Space"), P(" the cell: UNTESTED \u2192 VALID \u2192 PWN3D \u2192 INVALID (persisted).", "cellmuted")]],
            [CB("5 \u00b7 EXPLOIT THE WIN"), P("PWN3D cell = your foothold on that box: back to station 1, capture flags, repeat.", "cell")],
        ],
        [95, CONTENT_W - 95],
    ))
    story.append(Spacer(1, 6))
    story.append(KeepTogether([
        figure(screens / "03-creds.png",
               "Station 3 \u2014 the credential \u00d7 service matrix. Badges persist in SQLite; restarting the TUI loses nothing.",
               max_h=118),
    ]))
    story.append(Spacer(1, 4))
    story.append(callout(
        "tip", "Cracked a hash mid-session?",
        "Don\u2019t duplicate the row \u2014 upgrade it: <font face='Courier-Bold' color='#1D63B8'>:c crack &lt;row&gt; &lt;plaintext&gt;</font>. "
        "Then <font face='Courier-Bold' color='#1D63B8'>:export wordlists</font> writes deduplicated "
        "<font face='Courier'>loot/users.txt</font> + <font face='Courier'>loot/passwords.txt</font> for hydra / netexec runs."))

    story.append(section("IV", "Workflow IV \u2014 pivot into the internal network"))
    story.append(data_table(
        ["Step", "Action"],
        [
            [CB("1 \u00b7 SPOT & ROUTE"), [C("ip a"), P(" on a pwned box \u2192 second NIC = hidden subnet. Record: ", "cellmuted"), C(":pivot 10.10.10.20 172.16.1.0/24"), P(" \u2014 the console switches to tunnel guidance.", "cellmuted")]],
            [CB("2 \u00b7 TUNNEL"), C("chisel server on pwned box \u2192 client on Kali \u2192 proxychains nmap -sT 172.16.1.0/24")],
            [CB("3 \u00b7 RECORD THE REST"), [C(":t 172.16.1.50 --notes via-pivot"), P(" \u2014 same core loop; the target tree shows both segments.", "cellmuted")]],
            [CB("WHY IT PAYS"), P("Exam questions ask about <b>hidden subnets and routes</b>, not just flags \u2014 and the dossier spells your routes out.", "cell")],
        ],
        [95, CONTENT_W - 95],
    ))

    story.append(PageBreak())

    # =====================================================================
    # 8 — WORKFLOW V  +  9 — PULSE
    # =====================================================================
    story.append(section("V", "Workflow V \u2014 prove it and submit"))
    story.append(P("Evidence you didn\u2019t write down is evidence you don\u2019t have. Station 4 is where proofs live."))
    story.append(data_table(
        ["You captured\u2026", "Do this"],
        [
            [P("A user/root flag", "cell"), C(":uflag &lt;hash&gt;   \u00b7   :rflag &lt;hash&gt;")],
            [P("An exam answer", "cell"), C(":q &lt;question#&gt; &lt;exact proof string&gt;   # or key a in station 4")],
            [P("A screenshot", "cell"), [K("v"), P(" pastes the clipboard image into screenshots/ and links it as evidence \u00b7 ", "cellmuted"), C(":ev latest desc")]],
            [P("Loot on disk", "cell"), P("The loot browser indexes scans/, enum/, loot/, screenshots/ \u2014 Space previews, Enter copies the path.", "cell")],
            [P("A dead end", "cell"), C(":stuck \u2026  /  :clue \u2026   # future-you says thanks")],
        ],
        [110, CONTENT_W - 110],
    ))
    story.append(Spacer(1, 6))
    story.append(KeepTogether([
        figure(screens / "04-loot.png",
               "Station 4 \u2014 flags, foothold &amp; privesc proofs, question evidence, disk loot, rabbit-hole log.",
               max_h=165),
    ]))
    story.append(Spacer(1, 4))
    story.append(callout(
        "ok", "The submission moment",
        "Before touching the exam portal: <font face='Courier-Bold' color='#1D63B8'>:export exam</font> \u2192 a self-contained Markdown dossier "
        "(target inventory, question proofs, flags, credential states, audit trail). Keep it open beside the portal and answer from it. "
        "Want something prettier to attach to a client report? <font face='Courier-Bold' color='#1D63B8'>glacis export --format html -o report.html</font> "
        "renders a styled, self-contained HTML report (masked credentials, printable)."))

    story.append(PageBreak())

    story.append(section("9", "Pulse \u2014 see everything, choose smarter"))
    story.append(P(
        "Press <font face='Courier-Bold' color='#1D63B8'>0</font>. Pulse is a read-only dashboard computed from what you already recorded: "
        "coverage (% services tested), methodology %, 14-day momentum sparkline, per-target scorecards with a transparent A\u2013F grade, "
        "a <b>next-action queue</b> (your own untested services, missing proofs, open leads \u2014 ranked NOW / NEXT / LATER) "
        "and the newest timeline events."))
    story.append(data_table(
        ["Moment", "What to look at"],
        [
            [P("Just finished a box", "cell"), P("Scorecards \u2192 the neglected machine (lowest coverage, no flags) is usually your next target.", "cell")],
            [P("Don\u2019t know what\u2019s next", "cell"), P("The NOW/NEXT queue \u2014 it\u2019s your own TODOs, ordered. Work top down.", "cell")],
            [P("Feels like slow progress", "cell"), P("Momentum sparkline \u2014 flat two days = rotate sooner, log rabbit holes.", "cell")],
            [P("CLI equivalent", "cell"), C("glacis stats  \u00b7  glacis timeline -n 40")],
        ],
        [130, CONTENT_W - 130],
    ))
    story.append(Spacer(1, 6))
    story.append(KeepTogether([
        figure(screens / "00-pulse.png",
               "Station 0 Pulse \u2014 stat cards, momentum, scorecards, next actions and timeline. Zero inference: it only counts what you recorded.",
               max_h=210),
    ]))

    story.append(PageBreak())

    # =====================================================================
    # 10 — TEMPLATES, CLI POCKET REFERENCE, EXAM DAY
    # =====================================================================
    story.append(section("10", "Templates, CLI pocket reference & exam day"))

    story.append(subsection("Methodology templates (:m &lt;name&gt;)"))
    story.append(data_table(
        ["Template", "Focus", "Covers"],
        [
            [C(":m ejpt"), P("Master flow", "cell"), P("Scope \u2192 discovery \u2192 enumeration \u2192 foothold \u2192 pivoting \u2192 privesc \u2014 the exam spine.", "cell")],
            [C(":m discovery"), P("Network", "cell"), P("Local subnets, ARP/ICMP sweeps, TTL guesses, dual-homed discovery.", "cell")],
            [C(":m web"), P("Web app", "cell"), P("Headers, robots, dir fuzzing, SQLi, LFI, XSS, command injection, uploads.", "cell")],
            [C(":m smb"), P("SMB", "cell"), P("Null sessions, share perms, backups in shares, enum4linux, RID cycling.", "cell")],
            [C(":m pivoting"), P("Routing", "cell"), P("Dual-homed detection, autoroute, SOCKS5, SSH tunnels, chisel, proxychains.", "cell")],
            [C(":m linux  \u00b7  :m windows"), P("PrivEsc", "cell"), P("SUID/SGID, sudo -l, cron, capabilities / SeImpersonate, unquoted paths, AIE.", "cell")],
            [C(":m ftp  \u00b7  :m ssh  \u00b7  :m snmp"), P("Services", "cell"), P("Anonymous login, banner CVEs, key perms / communities, MIB walk.", "cell")],
            [C(":m databases  \u00b7  :m cracking"), P("Data &amp; hashes", "cell"), P("Blank root logins, LOAD_FILE, xp_cmdshell / hash ID, John, Hashcat modes, hydra.", "cell")],
        ],
        [120, 70, CONTENT_W - 190],
    ))
    story.append(Spacer(1, 6))

    story.append(subsection("CLI pocket reference \u2014 when you\u2019d rather stay in the shell"))
    story.append(data_table(
        ["Command", "Records / does"],
        [
            [C("glacis t 10.10.10.20 -h dc01 --os Linux"), P("Add a target.", "cell")],
            [C("glacis s 10.10.10.20 445/tcp SMB -v 'Samba 4.3'"), P("Add a service.", "cell")],
            [C("glacis c admin:secret --source backup.zip"), P("Add a credential.", "cell")],
            [C("glacis n 'checked share, nothing'  \u00b7  glacis f 'anon SMB' -s HIGH"), P("Note / finding.", "cell")],
            [C("glacis import scan.xml"), P("Staged scan import (same review as key I).", "cell")],
            [C("glacis search 'backup'"), P("Search everything.", "cell")],
            [C("glacis stats  \u00b7  glacis timeline"), P("Pulse from the shell.", "cell")],
            [C("glacis backup --label pre-enum  \u00b7  glacis backups"), P("Snapshot / list snapshots.", "cell")],
            [C("glacis restore &lt;snapshot.json&gt;"), P("Restores as a NEW workspace \u2014 never overwrites.", "cell")],
            [C("glacis export --format md|json|txt|html [-o file]"), P("Export (html = styled report).", "cell")],
        ],
        [250, CONTENT_W - 250],
    ))
    story.append(Spacer(1, 6))

    story.append(subsection("Exam-day checklist"))
    two = Table([
        [
            Paragraph("<b>First 15 minutes</b>", S["cellb"]),
            Paragraph("<b>Last 30 minutes</b>", S["cellb"]),
        ],
        [
            Paragraph(
                "1. Launch <font face='Courier-Bold' color='#1D63B8'>glacis</font>, pick theme (T, d).<br/>"
                "2. <font face='Courier-Bold' color='#1D63B8'>:ws init exam</font> \u2014 clean workspace.<br/>"
                "3. Import the scope/first scan (I).<br/>"
                "4. <font face='Courier-Bold' color='#1D63B8'>:lhost auto</font> \u00b7 <font face='Courier-Bold' color='#1D63B8'>:lport 4444</font>.<br/>"
                "5. <font face='Courier-Bold' color='#1D63B8'>:m ejpt</font> on the first target.<br/>"
                "6. <font face='Courier-Bold' color='#1D63B8'>glacis backup --label start</font>.",
                S["cell"]),
            Paragraph(
                "1. Station 0: any target without flags? NOW queue empty?<br/>"
                "2. Walk every DEFERRED service once more.<br/>"
                "3. Every question has a <font face='Courier' size='7.8'>:q</font> proof? Check count.<br/>"
                "4. <font face='Courier-Bold' color='#1D63B8'>:export exam</font> \u2192 answer from the dossier.<br/>"
                "5. <font face='Courier-Bold' color='#1D63B8'>glacis export --format html -o exam.html</font>.<br/>"
                "6. <font face='Courier-Bold' color='#1D63B8'>glacis backup --label submitted</font>.",
                S["cell"]),
        ]],
        colWidths=[CONTENT_W / 2 - 4, CONTENT_W / 2 - 4],
    )
    two.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), ZEBRA),
        ("BACKGROUND", (1, 0), (1, 0), OK_BG),
        ("BOX", (0, 0), (-1, -1), 0.6, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(two)
    story.append(Spacer(1, 8))
    story.append(callout(
        "ok", "Where your data lives",
        "One SQLite file (default <font face='Courier'>~/.local/share/glacis/notebook.db</font>, or <font face='Courier'>.glacis/</font> beside an initialised workspace) "
        "plus plain folders for scans and loot. Copy them to a USB stick and you have a full backup \u2014 or let "
        "<font face='Courier-Bold' color='#1D63B8'>glacis backup</font> rotate snapshots for you. No network, ever: safe for exam NDAs by design. "
        "Always defer to your certifying body\u2019s current rules."))

    return story


def build_pdf(dest_path: Path, screens: Path) -> None:
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(dest_path),
        pagesize=letter,
        leftMargin=M_LEFT,
        rightMargin=M_RIGHT,
        topMargin=46,
        bottomMargin=48,
        title="GLACIS Field Guide \u2014 v0.2.0 Pulse",
        author="GLACIS Contributors",
        subject="Offline pentest worksheet & practical-exam companion",
    )
    doc.build(build_story(screens), canvasmaker=NumberedCanvas)
    print(f"wrote {dest_path}")


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    screens = repo_root / "docs" / "screenshots"
    # Build once, ship twice: both guide filenames carry identical content
    # (byte-for-byte), so they can never drift apart.
    primary = repo_root / "docs" / "CYB0X-S_Field_Guide.pdf"
    build_pdf(primary, screens)
    import shutil

    twin = repo_root / "docs" / "CYB0X-S_Operator_Guide.pdf"
    twin.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(primary, twin)
    print(f"wrote {twin} (copy of {primary.name})")


if __name__ == "__main__":
    main()
