#!/usr/bin/env python3
"""Build a comprehensive, beautifully styled illustrated PDF Field Guide for GLACIS.

Targeted for practical penetration testing exams (eJPTv2, eCPPTv3, OSCP) and lab assessments.
Features high-resolution UI screenshots from docs/screenshots/.
Outputs to:
  1. ~/Desktop/GLACIS_Field_Guide.pdf (if ~/Desktop exists)
  2. ~/Desktop/Documents_and_Media/GLACIS_Security_Docs/GLACIS_Field_Guide.pdf
  3. <repo_root>/docs/GLACIS_Field_Guide.pdf
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    HRFlowable,
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


class NumberedCanvas(canvas.Canvas):
    """Canvas that computes total pages dynamically for a running footer."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, total_pages: int):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))

        # Running Top Header (Pages 2+)
        if self._pageNumber > 1:
            self.drawString(
                36,
                792 - 24,
                "GLACIS · Field Guide & Practical Assessment Workflow Reference (eJPTv2 / eCPPT / OSCP)",
            )
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.5)
            self.line(36, 792 - 27, 612 - 36, 792 - 27)

        # Running Bottom Footer (All Pages)
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(36, 28, 612 - 36, 28)

        footer_left = "100% Offline & Passive · Local SQLite Engine · Exam Proctoring Compliant"
        footer_right = f"Page {self._pageNumber} of {total_pages}"
        self.drawString(36, 17, footer_left)
        self.drawRightString(612 - 36, 17, footer_right)

        self.restoreState()


def make_screenshot_card(
    img_path: Path | str,
    caption: str,
    width: float,
    height: float,
    caption_style: ParagraphStyle,
) -> Table:
    """Wrap a high-res screenshot with a neat border and italic caption."""
    img = Image(str(img_path), width=width, height=height)
    p_cap = Paragraph(caption, caption_style)
    table = Table([[img], [p_cap]], colWidths=[width + 8])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#CBD5E1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, 0), 3),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 2),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 1), (-1, 1), 2),
                ("BOTTOMPADDING", (0, 1), (-1, 1), 3),
            ]
        )
    )
    return table


def build_pdf(dest_path: Path, screenshots_dir: Path) -> None:
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(dest_path),
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=32,
        bottomMargin=30,
    )

    styles = getSampleStyleSheet()

    # Base typography palette (cohesive sapphire & slate)
    C_PRIMARY = colors.HexColor("#0F172A")    # slate-900
    C_ACCENT = colors.HexColor("#1D63B8")     # royal sapphire blue
    C_LINE = colors.HexColor("#CBD5E1")       # slate-300
    C_MUTED = colors.HexColor("#475569")      # slate-600

    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=15.5,
        leading=18,
        textColor=C_PRIMARY,
        spaceAfter=1,
    )
    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=10.5,
        textColor=C_ACCENT,
        spaceAfter=4,
    )
    h1_style = ParagraphStyle(
        "SectionH1",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10.5,
        leading=13,
        textColor=C_PRIMARY,
        spaceBefore=3,
        spaceAfter=2,
    )
    body_style = ParagraphStyle(
        "BodyDark",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.4,
        leading=9.8,
        textColor=C_PRIMARY,
        spaceAfter=2,
    )
    table_body_style = ParagraphStyle(
        "TableBody",
        parent=body_style,
        fontSize=7.0,
        leading=8.8,
        spaceAfter=0,
    )
    body_bold = ParagraphStyle(
        "BodyBold",
        parent=body_style,
        fontName="Helvetica-Bold",
    )
    th_style = ParagraphStyle(
        "TableHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.3,
        leading=9.0,
        textColor=colors.white,
    )
    code_style = ParagraphStyle(
        "CodeText",
        parent=styles["Normal"],
        fontName="Courier",
        fontSize=6.8,
        leading=8.5,
        textColor=colors.HexColor("#0F172A"),
    )
    code_bold = ParagraphStyle(
        "CodeBold",
        parent=code_style,
        fontName="Courier-Bold",
        textColor=C_ACCENT,
    )
    badge_style = ParagraphStyle(
        "KeyBadge",
        parent=styles["Normal"],
        fontName="Courier-Bold",
        fontSize=7.0,
        leading=8.8,
        textColor=C_ACCENT,
    )
    callout_text = ParagraphStyle(
        "CalloutText",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.1,
        leading=9.4,
        textColor=colors.HexColor("#1E293B"),
    )
    caption_style = ParagraphStyle(
        "FigureCaption",
        parent=styles["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=6.8,
        leading=8.2,
        textColor=C_MUTED,
        alignment=1,
    )

    story = []

    # =========================================================================
    # PAGE 1: TITLE, COMPLIANCE, 6 STATIONS & STATION 0 PULSE
    # =========================================================================
    story.append(Paragraph("GLACIS: FIELD GUIDE & PRACTICAL WORKFLOW REFERENCE", title_style))
    story.append(Paragraph("High-Speed Offline Security Assessment Worksheet · eJPTv2 / eCPPT / OSCP Practical Companion", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=C_ACCENT, spaceBefore=0, spaceAfter=4))

    # Intro & Exam Compliance Card
    intro_table_data = [
        [
            Paragraph(
                "<b>What is GLACIS?</b><br/>"
                "GLACIS is a fast, keyboard-driven terminal worksheet and operational cockpit designed to eliminate cognitive overload during timed practical security assessments. "
                "It provides an offline state machine for host discovery, port tracking, credential reuse, syntax playbooks, network pivots, and question proofs. "
                "<b>It does not run autonomous exploits or rely on AI.</b> You retain 100% human control while GLACIS manages your operational memory.",
                callout_text,
            ),
            Paragraph(
                "<b>INE & OffSec Exam Compliance</b><br/>"
                "• <b>100% Passive & Offline:</b> Verified by AST self-audit (<code>glacis exam-check</code>) — zero network/socket imports.<br/>"
                "• <b>Zero Autonomous Action:</b> Commands are copied to your clipboard; YOU execute them in your terminal.<br/>"
                "• <b>Zero Cloud / AI Dependencies:</b> No external API calls, background telemetry, or prohibited LLM endpoints.<br/>"
                "• <b>Permitted Personal Notes:</b> Functions strictly as an electronic field journal and methodology reference.",
                callout_text,
            ),
        ]
    ]
    t_intro = Table(intro_table_data, colWidths=[270, 270])
    t_intro.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#F8FAFC")),
                ("BACKGROUND", (1, 0), (1, 0), colors.HexColor("#F0FDF4")),
                ("BOX", (0, 0), (0, 0), 0.5, C_LINE),
                ("BOX", (1, 0), (1, 0), 0.5, colors.HexColor("#86EFAC")),
                ("PADDING", (0, 0), (-1, -1), 3.5),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(t_intro)
    story.append(Spacer(1, 3))

    # Section 1: The 6 Stations
    story.append(Paragraph("1. The Six Operational Stations (Switch with Keys 0, 1, 2, 3, 4, 5)", h1_style))
    stations_data = [
        [
            Paragraph("Station", th_style),
            Paragraph("Name & Purpose", th_style),
            Paragraph("What You See & Do Here", th_style),
            Paragraph("Hotkey", th_style),
        ],
        [
            Paragraph("<b>Station 0</b>", body_bold),
            Paragraph("<b>Pulse (Triage Board)</b>", body_style),
            Paragraph("Kill-chain host progression (UNTOUCHED → RECON → FOOTHOLD → USER → ROOT → COMPLETE), progress arithmetic, and explainable next-focus advisories.", body_style),
            Paragraph("<b>[0]</b>", badge_style),
        ],
        [
            Paragraph("<b>Station 1</b>", body_bold),
            Paragraph("<b>Cockpit (Workbench)</b>", body_style),
            Paragraph("Targets tree, open ports, service triage status, methodology roadmap, field notes, and interactive command console.", body_style),
            Paragraph("<b>[1]</b>", badge_style),
        ],
        [
            Paragraph("<b>Station 2</b>", body_bold),
            Paragraph("<b>Playbook Browser</b>", body_style),
            Paragraph("Browse full tactical playbooks (eJPT workflow, Web App OWASP, Active Directory, Pivoting, Linux & Windows PrivEsc) with instant copy.", body_style),
            Paragraph("<b>[2]</b>", badge_style),
        ],
        [
            Paragraph("<b>Station 3</b>", body_bold),
            Paragraph("<b>Credential Matrix</b>", body_style),
            Paragraph("2D grid of discovered credentials (rows) × target services (cols). Press <b>[Enter]</b> to compile spray commands; <b>[Space]</b> to cycle verification state.", body_style),
            Paragraph("<b>[3]</b>", badge_style),
        ],
        [
            Paragraph("<b>Station 4</b>", body_bold),
            Paragraph("<b>Proofs, Loot & Evidence</b>", body_style),
            Paragraph("Track assessment question answers (<code>:q</code>), user/root flags, disk-backed loot browser (<code>[Space]</code>), screenshot proofing (<code>[v]</code>), and Failure Logs.", body_style),
            Paragraph("<b>[4]</b>", badge_style),
        ],
        [
            Paragraph("<b>Station 5</b>", body_bold),
            Paragraph("<b>Network & Pivots</b>", body_style),
            Paragraph("ASCII network topology map of documented subnets, dual-homed pivot gateways, and copy-ready ProxyChains, Chisel, and SSH ProxyJump tunnel actions.", body_style),
            Paragraph("<b>[5]</b>", badge_style),
        ],
    ]
    t_stations = Table(stations_data, colWidths=[52, 125, 330, 33])
    t_stations.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), C_PRIMARY),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                ("GRID", (0, 0), (-1, -1), 0.5, C_LINE),
                ("PADDING", (0, 0), (-1, -1), 2.0),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    story.append(t_stations)
    story.append(Spacer(1, 3))

    # Section 2: Station 0 Pulse Visual Architecture
    story.append(Paragraph("2. Station 0 Pulse: Situation Awareness & Kill-Chain Triage", h1_style))
    fig0 = make_screenshot_card(
        screenshots_dir / "00-pulse.png",
        "Figure 1: Station 0 Pulse — Kill-chain progression cards (left), explainable S1-S8 state rules & D1-D4 focus-shift advisories (right), and KPI status band.",
        width=480,
        height=185,
        caption_style=caption_style,
    )
    story.append(fig0)

    story.append(PageBreak())

    # =========================================================================
    # PAGE 2: STATION 1 COCKPIT & KEYBOARD MUSCLE MEMORY MAP
    # =========================================================================
    story.append(Paragraph("3. Station 1 Cockpit Architecture & Real-Time Workspace", h1_style))
    fig1 = make_screenshot_card(
        screenshots_dir / "01-cockpit.png",
        "Figure 2: Station 1 Cockpit — Attack Surface Tree (left), Services & Port Triage (top), Methodology Roadmap (mid), and Bottom Command Console.",
        width=480,
        height=185,
        caption_style=caption_style,
    )
    story.append(fig1)
    story.append(Spacer(1, 2))

    story.append(Paragraph("4. Keyboard Navigation Matrix (\"Muscle Memory Map\")", h1_style))
    story.append(Paragraph(
        "GLACIS is 100% operational from the keyboard. Single-letter keys trigger immediate actions unless a text input is focused:",
        body_style,
    ))

    keys_data = [
        [Paragraph("Key", th_style), Paragraph("Category", th_style), Paragraph("Action & Operational Behavior", th_style)],
        [Paragraph("<b>0 – 5</b>", badge_style), Paragraph("Station", body_style), Paragraph("Switch stations: <b>[0]</b> Pulse, <b>[1]</b> Cockpit, <b>[2]</b> Playbooks, <b>[3]</b> Creds Matrix, <b>[4]</b> Loot, <b>[5]</b> Network.", table_body_style)],
        [Paragraph("<b>I</b> (Shift+i)", badge_style), Paragraph("Ingestion", body_style), Paragraph("<b>Import Scan & Enum:</b> Interactive review modal for Nmap (-oX, -oN, -oG) and Web Enum (FFUF, Ferox, Gobuster). Saves evidence to <code>scans/</code> or <code>enum/</code>.", table_body_style)],
        [Paragraph("<b>W</b> (Shift+w)", badge_style), Paragraph("Workspace", body_style), Paragraph("<b>Workspace Manager:</b> Switch between assessment workspaces or scaffold a new per-lab directory (<code>scans/</code>, <code>enum/</code>, <code>screenshots/</code>, <code>loot/</code>).", table_body_style)],
        [Paragraph("<b>Tab / Shift+Tab</b>", badge_style), Paragraph("Navigation", body_style), Paragraph("<b>Cycle Focus:</b> Move keyboard focus between panels in Cockpit (double-border indicates focused panel).", table_body_style)],
        [Paragraph("<b>j / k</b> (or ↑ / ↓)", badge_style), Paragraph("Navigation", body_style), Paragraph("<b>List Navigation:</b> Move highlight down (j) or up (k) in the active list or tree.", table_body_style)],
        [Paragraph("<b>[ / ]</b>", badge_style), Paragraph("Targeting", body_style), Paragraph("<b>Target Switcher:</b> Switch immediately to previous [ or next ] target machine.", table_body_style)],
        [Paragraph("<b>:</b> (colon)", badge_style), Paragraph("Console", body_style), Paragraph("<b>Focus Command Bar:</b> Instantly activates the bottom console input ready to type commands.", table_body_style)],
        [Paragraph("<b>Esc</b>", badge_style), Paragraph("Console", body_style), Paragraph("<b>Dismiss / Blur:</b> Clears command input and returns focus directly to the active workbench.", table_body_style)],
        [Paragraph("<b>Space</b>", badge_style), Paragraph("Triage / State", body_style), Paragraph("• <b>On Service:</b> Cycle status: <code>UNTESTED</code> → <code>[CHECKED]</code> → <code>[DEAD-END]</code> → <code>[DEFERRED]</code>.<br/>• <b>In Station 3 Matrix:</b> Cycle test state: <code>[UNTESTED]</code> → <code>[VALID]</code> → <code>[PWN3D]</code> → <code>[INVALID]</code>.<br/>• <b>In Station 4 Loot:</b> Open <b>Loot Preview Modal</b> to inspect hashes, configs, or keys.", table_body_style)],
        [Paragraph("<b>, / .</b>", badge_style), Paragraph("Tool Carousel", body_style), Paragraph("<b>Recipe Carousel:</b> When a service is highlighted, press <b>.</b> (next) or <b>,</b> (prev) to cycle alternative tool recipes in the console.", table_body_style)],
        [Paragraph("<b>Enter</b>", badge_style), Paragraph("Execute / Copy", body_style), Paragraph("• <b>On Service / Recipe:</b> Copies the previewed tool command to clipboard.<br/>• <b>In Station 3 Matrix:</b> Compiles & copies ready-to-run spray command for credential & port.<br/>• <b>In Station 5 Network:</b> Copies selected pivot/tunnel syntax to clipboard.<br/>• <b>In Station 0 Pulse:</b> Jumps directly to the station that owns the highlighted advisory.", table_body_style)],
        [Paragraph("<b>v</b>", badge_style), Paragraph("Evidence", body_style), Paragraph("<b>Paste Screenshot:</b> In Station 4, saves clipboard image directly to <code>screenshots/</code> and links as Evidence.", table_body_style)],
        [Paragraph("<b>y</b>", badge_style), Paragraph("Quick Copy", body_style), Paragraph("Copies selected entity's primary value (IP address, port, password, or checklist command).", table_body_style)],
        [Paragraph("<b>z</b>", badge_style), Paragraph("Layout", body_style), Paragraph("<b>Zoom:</b> Maximize the focused panel to full-screen; press <b>z</b> again to restore normal layout.", table_body_style)],
        [Paragraph("<b>T</b> (Shift+t)", badge_style), Paragraph("Theme", body_style), Paragraph("<b>Theme Picker:</b> Open theme modal with 8 WCAG AAA palettes (1-8 keys, <b>d</b> sets default).", table_body_style)],
        [Paragraph("<b>G</b> (Shift+g)", badge_style), Paragraph("Guidance", body_style), Paragraph("<b>Toggle Guidance:</b> Enables or disables opt-in focus-shift advisories (D-rules) on Station 0.", table_body_style)],
        [Paragraph("<b>/</b> or <b>Ctrl+F</b>", badge_style), Paragraph("Search", body_style), Paragraph("<b>Global Fuzzy Search:</b> Search across targets, services, credentials, checklists, and notes.", table_body_style)],
        [Paragraph("<b>r</b>", badge_style), Paragraph("Reference", body_style), Paragraph("<b>Quick Reference Modal:</b> Open offline practical reference for instant syntax lookup.", table_body_style)],
        [Paragraph("<b>t / s / c / n</b>", badge_style), Paragraph("Fast Capture", body_style), Paragraph("Modal dialogs to quickly add Target (t), Service (s), Credential (c), or Note (n).", table_body_style)],
        [Paragraph("<b>a</b>", badge_style), Paragraph("Question Proof", body_style), Paragraph("In Station 4: Open <b>Add Proof</b> modal to link question/item number to proof evidence.", table_body_style)],
    ]
    t_keys = Table(keys_data, colWidths=[65, 75, 400])
    t_keys.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), C_PRIMARY),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                ("GRID", (0, 0), (-1, -1), 0.5, C_LINE),
                ("PADDING", (0, 0), (-1, -1), 1.1),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(t_keys)

    story.append(PageBreak())

    # =========================================================================
    # PAGE 3: DUAL-TERMINAL WORKFLOW & UNIVERSAL CLI INGESTION
    # =========================================================================
    story.append(Paragraph("5. Dual-Terminal Operating Model & Universal CLI Ingestion", h1_style))
    story.append(Paragraph(
        "The standard professional workflow runs GLACIS TUI in one terminal pane while executing active scans and exploits in an adjacent shell. "
        "Because GLACIS uses a shared SQLite store with WAL mode, changes committed in your attack terminal update the TUI live.",
        body_style,
    ))

    cli_ingest_data = [
        [Paragraph("Workflow & Goal", th_style), Paragraph("Command Line Execution (In Attack Terminal)", th_style), Paragraph("Operational Result in GLACIS", th_style)],
        [
            Paragraph("<b>Automated Scan Ingest</b>", body_bold),
            Paragraph("<code>nmap -sC -sV $IP -oX scans/box.xml &amp;&amp;<br/>glacis import --apply scans/box.xml</code>", code_style),
            Paragraph("Parses all hosts, ports, services, and banners into SQLite. Raw XML archived into <code>scans/</code> as immutable evidence.", table_body_style),
        ],
        [
            Paragraph("<b>1-Liner Shell Wrapper</b>", body_bold),
            Paragraph("<code>gnmap() { nmap -sC -sV \"$@\" -oX scans/s.xml &amp;&amp;<br/>glacis import --apply scans/s.xml; }</code>", code_style),
            Paragraph("Type <code>gnmap 10.10.10.20</code>: scans and populates GLACIS with zero manual typing.", table_body_style),
        ],
        [
            Paragraph("<b>Direct Terminal Pipe</b>", body_bold),
            Paragraph("<code>nikto -h $IP | glacis extract - --apply</code><br/><code>cat enum.log | glacis extract - --apply</code>", code_style),
            Paragraph("Parses raw terminal text on the fly, extracting targets, ports, hashes, and CTF flags.", table_body_style),
        ],
        [
            Paragraph("<b>Target & Service Add</b>", body_bold),
            Paragraph("<code>glacis target 10.10.10.20 --os Linux</code><br/><code>glacis service 10.10.10.20 80/tcp http</code>", code_style),
            Paragraph("Direct CLI insertion from background scripts or terminal loops without opening the TUI.", table_body_style),
        ],
        [
            Paragraph("<b>Discovered Credential</b>", body_bold),
            Paragraph("<code>glacis cred admin:Password123! -t 10.10.10.20</code>", code_style),
            Paragraph("Immediately adds credentials into the Station 3 Credential Matrix.", table_body_style),
        ],
        [
            Paragraph("<b>Flag & Proof Capture</b>", body_bold),
            Paragraph("<code>glacis proof -t 10.10.10.20 --flag user \"eJPT{...}\"</code><br/><code>glacis proof --q-num Q7 --proof \"admin:P@ss\"</code>", code_style),
            Paragraph("Records objective flags and exam question proofs directly into the Station 4 ledger.", table_body_style),
        ],
        [
            Paragraph("<b>Snapshot Safety Net</b>", body_bold),
            Paragraph("<code>glacis snapshot create -m \"pre-privesc\"</code><br/><code>glacis snapshot list</code> / <code>glacis snapshot restore &lt;file&gt;</code>", code_style),
            Paragraph("Creates byte-consistent online SQLite backup. Rotates automatically (keeps newest 5 snapshots).", table_body_style),
        ],
        [
            Paragraph("<b>Offline Compliance Audit</b>", body_bold),
            Paragraph("<code>glacis exam-check</code>", code_style),
            Paragraph("AST static scan proving zero network/socket imports across all 38 codebase modules.", table_body_style),
        ],
    ]
    t_ingest = Table(cli_ingest_data, colWidths=[115, 195, 230])
    t_ingest.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), C_PRIMARY),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                ("GRID", (0, 0), (-1, -1), 0.5, C_LINE),
                ("PADDING", (0, 0), (-1, -1), 1.8),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(t_ingest)
    story.append(Spacer(1, 3))

    # Section 6: Console Syntax Table
    story.append(Paragraph("6. Quick Command Console Syntax (Press [:] Anywhere in TUI)", h1_style))
    console_data = [
        [Paragraph("Console Command", th_style), Paragraph("Description & Execution", th_style), Paragraph("Syntax Example", th_style)],
        [Paragraph("<b>:0 – :5</b>", code_bold), Paragraph("Switch stations: <code>:0</code> Pulse, <code>:1</code> Cockpit, <code>:2</code> Playbooks, <code>:3</code> Creds, <code>:4</code> Loot, <code>:5</code> Network.", table_body_style), Paragraph("<code>:0</code> &nbsp; <code>:pulse</code> &nbsp; <code>:network</code>", code_style)],
        [Paragraph("<b>:t &lt;ip&gt;</b>", code_bold), Paragraph("Quickly add new target host into active workspace.", table_body_style), Paragraph("<code>:t 10.10.10.20</code>", code_style)],
        [Paragraph("<b>:s &lt;port&gt; &lt;svc&gt;</b>", code_bold), Paragraph("Add open port/service under currently selected target.", table_body_style), Paragraph("<code>:s 445/tcp smb</code> &nbsp; <code>:s 8080 http</code>", code_style)],
        [Paragraph("<b>:c &lt;user:pass&gt;</b>", code_bold), Paragraph("Add credential pair into Vault and auto-mount to Spray Matrix.", table_body_style), Paragraph("<code>:c admin:Summer2024!</code>", code_style)],
        [Paragraph("<b>:n / :f</b>", code_bold), Paragraph("Record field note (<code>:n</code>) or security finding (<code>:f</code>).", table_body_style), Paragraph("<code>:n backup dir found</code><br/><code>:f anonymous smb</code>", code_style)],
        [Paragraph("<b>:uflag / :rflag</b>", code_bold), Paragraph("Record captured user flag or root flag hash.", table_body_style), Paragraph("<code>:uflag eJPT{user_hash}</code>", code_style)],
        [Paragraph("<b>:pivot &lt;route&gt;</b>", code_bold), Paragraph("Mark active target as dual-homed gateway; updates Station 5 topology.", table_body_style), Paragraph("<code>:pivot 172.16.1.0/24 via socks5:1080</code>", code_style)],
        [Paragraph("<b>:snap [note]</b>", code_bold), Paragraph("Take an online byte-consistent database snapshot safety net.", table_body_style), Paragraph("<code>:snap before-bruteforce</code>", code_style)],
        [Paragraph("<b>:stuck / :clue</b>", code_bold), Paragraph("Log rabbit-hole stuck point or breakthrough clue in Failure Log.", table_body_style), Paragraph("<code>:stuck hydra lockout</code><br/><code>:clue check backup.zip</code>", code_style)],
        [Paragraph("<b>:q &lt;num&gt; &lt;proof&gt;</b>", code_bold), Paragraph("Pin exam question answer proof (e.g. hash, flag, config path).", table_body_style), Paragraph("<code>:q 14 root:$6$hash...</code>", code_style)],
        [Paragraph("<b>:export html</b>", code_bold), Paragraph("Generate standalone, printable HTML handover report (zero JS/CDN).", table_body_style), Paragraph("<code>:export html exam_final.html</code>", code_style)],
        [Paragraph("<b>:export exam</b>", code_bold), Paragraph("Export exam evidence bundle to <code>exam_evidence.md</code>.", table_body_style), Paragraph("<code>:export exam</code>", code_style)],
        [Paragraph("<b>:export wordlists</b>", code_bold), Paragraph("Harvest all discovered credentials into <code>loot/users.txt</code> and <code>loot/passwords.txt</code>.", table_body_style), Paragraph("<code>:export wordlists</code>", code_style)],
        [Paragraph("<b>:theme &lt;name&gt;</b>", code_bold), Paragraph("Switch visual palette (slate, midnight, ember, cyber, sugary, candy, caramel, catppuccin).", table_body_style), Paragraph("<code>:theme midnight</code> &nbsp; <code>:theme cyber</code>", code_style)],
    ]
    t_console = Table(console_data, colWidths=[90, 240, 210])
    t_console.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), C_PRIMARY),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                ("GRID", (0, 0), (-1, -1), 0.5, C_LINE),
                ("PADDING", (0, 0), (-1, -1), 1.2),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(t_console)

    story.append(PageBreak())

    # =========================================================================
    # PAGE 4: PRACTICAL ASSESSMENT WORKFLOW ("THE BATTLE PLAN")
    # =========================================================================
    story.append(Paragraph("7. Step-by-Step Practical Assessment Workflow (\"The Battle Plan\")", h1_style))
    story.append(Paragraph(
        "Follow this battle-tested loop for each target in practical exams (eJPTv2, eCPPT, OSCP) to maintain 100% rigor and never lose progress:",
        body_style,
    ))

    workflow_stages = [
        ("Phase 1: Workspace Init & Scoping",
         "1. Create dedicated lab directory: <code>glacis init lab_name --ip 10.10.10.20</code>.<br/>"
         "2. Set attacker VPN IP: <code>:lhost auto</code> (or <code>:lhost 192.168.0.50</code>) and <code>:lport 4444</code>.<br/>"
         "3. Apply exam methodology checklist: <code>:m ejpt</code> in Cockpit."),
        ("Phase 2: Discovery & Ingestion",
         "1. Run port scan in attack terminal: <code>nmap -sC -sV $IP -oX scans/init.xml</code>.<br/>"
         "2. Ingest automatically: <code>glacis import --apply scans/init.xml</code> (or press <b>[I]</b> in TUI).<br/>"
         "3. Verify Station 0 Pulse reflects attack surface: host moves from <b>UNTOUCHED</b> to <b>RECON</b>."),
        ("Phase 3: Port Triage & Tool Recipes",
         "1. Highlight open port in Cockpit with <code>j</code> / <code>k</code>.<br/>"
         "2. Cycle alternative tool recipes in console with <code>.</code> (e.g. feroxbuster → nikto → curl).<br/>"
         "3. Press <b>[Enter]</b> to copy recipe to clipboard; run in terminal.<br/>"
         "4. Press <b>[Space]</b> on service to mark <code>[CHECKED]</code> or <code>[DEAD-END]</code>."),
        ("Phase 4: Credential Harvest & Spray Validation",
         "1. Record found credentials: <code>:c admin:Summer2024!</code>.<br/>"
         "2. Switch to Station 3 (press <b>[3]</b>) to inspect the 2D Credential Spray Matrix.<br/>"
         "3. Press <b>[Enter]</b> on any matrix cell to copy ready-to-run spray command.<br/>"
         "4. Press <b>[Space]</b> on cell to record outcome: <code>[VALID]</code> or <code>[PWN3D]</code>.<br/>"
         "5. Harvest discovered accounts: <code>:export wordlists</code> writes <code>loot/users.txt</code>."),
        ("Phase 5: Foothold, Flags & Anti-Rabbit Hole",
         "1. Record initial shell foothold: <code>:foothold php-reverse-shell</code>.<br/>"
         "2. Capture user flag: <code>:uflag eJPT{...}</code>.<br/>"
         "3. If stuck for >20 mins, avoid rabbit hole: log dead-end with <code>:stuck &lt;why&gt;</code> and check Station 0 Pulse for next un-checked surface.<br/>"
         "4. When progress is made, log breakthrough: <code>:clue &lt;what_worked&gt;</code>."),
        ("Phase 6: Internal Pivoting & Subnet Expansion",
         "1. Discovered internal route? Mark target dual-homed: <code>:pivot 172.16.1.0/24 via socks5:1080</code>.<br/>"
         "2. Switch to Station 5 (press <b>[5]</b>) to inspect ASCII network graph.<br/>"
         "3. Press <b>[Enter]</b> on actions to copy ProxyChains config, Chisel server/client, or SSH ProxyJump syntax.<br/>"
         "4. Add pivot target: <code>:t 172.16.1.50</code> and begin Phase 2 scan through proxy."),
        ("Phase 7: PrivEsc & Final Submission Handover",
         "1. Switch to Station 2 (press <b>[2]</b>) and search Linux / Windows PrivEsc playbooks.<br/>"
         "2. Record root flag: <code>:rflag eJPT{...}</code> and document privesc: <code>:privesc SUID-pkexec</code>.<br/>"
         "3. Log question proofs: <code>:q 14 /etc/shadow-hash</code> (press <b>[a]</b> in Station 4).<br/>"
         "4. Export standalone printable HTML handover: <code>:export html final_handover.html</code>.<br/>"
         "5. Export evidence markdown bundle: <code>:export exam</code> writes <code>exam_evidence.md</code>."),
    ]

    wf_table_data = [
        [Paragraph("Assessment Stage", th_style), Paragraph("Step-by-Step Operator Action & Commands", th_style)],
    ]
    for stage_title, stage_desc in workflow_stages:
        wf_table_data.append([
            Paragraph(f"<b>{stage_title}</b>", body_bold),
            Paragraph(stage_desc, table_body_style),
        ])

    t_wf = Table(wf_table_data, colWidths=[150, 390])
    t_wf.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), C_PRIMARY),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                ("GRID", (0, 0), (-1, -1), 0.5, C_LINE),
                ("PADDING", (0, 0), (-1, -1), 1.8),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(t_wf)
    story.append(Spacer(1, 3))

    # Safety Net Pro-Tip
    snap_box = [
        [
            Paragraph(
                "<b>SAFETY NET: AUTOMATIC & ON-DEMAND SNAPSHOTS (<code>:snap</code>)</b><br/>"
                "Lab VMs reset frequently, and databases can corrupt during power drops. "
                "GLACIS automatically creates a snapshot before scan imports. Take on-demand snapshots with <code>:snap before-pivot</code> "
                "or <code>glacis snapshot create</code>. Restore losslessly at any time with <code>glacis snapshot restore &lt;file&gt;</code>. "
                "Snapshots use SQLite's native backup API and keep the newest 5 copies automatically rotated.",
                callout_text,
            )
        ]
    ]
    t_snap = Table(snap_box, colWidths=[540])
    t_snap.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FEF3C7")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#F59E0B")),
                ("PADDING", (0, 0), (-1, -1), 3.0),
            ]
        )
    )
    story.append(t_snap)

    story.append(PageBreak())

    # =========================================================================
    # PAGE 5: STATION 3 CREDENTIAL MATRIX & STATION 4 LOOT LEDGER
    # =========================================================================
    story.append(Paragraph("8. Station 3 Deep Dive: 2D Credential Spray Matrix", h1_style))
    story.append(Paragraph(
        "Station 3 eliminates credential amnesia by organizing all discovered credentials (rows) against all target authentication services (columns) in a live 2D grid:",
        body_style,
    ))

    fig3 = make_screenshot_card(
        screenshots_dir / "03-creds.png",
        "Figure 3: Station 3 Credential Matrix — 2D grid of discovered accounts against authenticating services. Enter copies spray command; Space cycles verification state.",
        width=480,
        height=195,
        caption_style=caption_style,
    )
    story.append(fig3)
    story.append(Spacer(1, 3))

    creds_features = [
        [Paragraph("Matrix Element", th_style), Paragraph("Hotkey & Action", th_style), Paragraph("Operational Impact", th_style)],
        [
            Paragraph("<b>Cell Status Toggle</b>", body_bold),
            Paragraph("Press <b>[Space]</b>", code_style),
            Paragraph("Cycles cell through <code>[UNTESTED]</code> → <code>[VALID]</code> (green) → <code>[PWN3D]</code> (magenta) → <code>[INVALID]</code> (red).", table_body_style),
        ],
        [
            Paragraph("<b>Auto-Compile Spray Syntax</b>", body_bold),
            Paragraph("Press <b>[Enter]</b> on cell", code_style),
            Paragraph("Compiles ready-to-run NetExec, Hydra, SSH, or Evil-WinRM command for that specific user, password, target IP, and port.", table_body_style),
        ],
        [
            Paragraph("<b>Credential Vault Table</b>", body_bold),
            Paragraph("Left Panel (navigate with <b>h / l</b>)", body_style),
            Paragraph("Inventory of all discovered accounts, source tracking (e.g. shadow crack, wp-config, SAM dump), and validation flags.", table_body_style),
        ],
        [
            Paragraph("<b>Harvest Wordlists</b>", body_bold),
            Paragraph("<code>:export wordlists</code>", code_style),
            Paragraph("Exports all captured usernames to <code>loot/users.txt</code> and passwords to <code>loot/passwords.txt</code> for instant feeding to wordlist attacks.", table_body_style),
        ],
    ]
    t_creds = Table(creds_features, colWidths=[120, 140, 280])
    t_creds.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), C_PRIMARY),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                ("GRID", (0, 0), (-1, -1), 0.5, C_LINE),
                ("PADDING", (0, 0), (-1, -1), 1.8),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(t_creds)
    story.append(Spacer(1, 3))

    story.append(Paragraph("9. Station 4 Deep Dive: Question Proofs & Loot Ledger", h1_style))
    fig4 = make_screenshot_card(
        screenshots_dir / "04-loot.png",
        "Figure 4: Station 4 Proofs & Loot Ledger — Question Proofs, User/Root Flags, Disk Loot Browser, and Anti-Rabbit Hole Failure Log.",
        width=480,
        height=190,
        caption_style=caption_style,
    )
    story.append(fig4)

    story.append(PageBreak())

    # =========================================================================
    # PAGE 6: STATION 5 NETWORK TOPOLOGY & STATION 2 PLAYBOOKS
    # =========================================================================
    story.append(Paragraph("10. Station 5 Deep Dive: Network Topology, Dual-Homed Pivots & Tunnels", h1_style))
    story.append(Paragraph(
        "Station 5 visualizes internal network architecture and dual-homed pivot gateways directly from your documented target IPs and <code>:pivot</code> notes:",
        body_style,
    ))

    fig5 = make_screenshot_card(
        screenshots_dir / "05-network.png",
        "Figure 5: Station 5 Network — Documented ASCII Subnet Topology (left) and Copy-Ready Tunnel & Routing Actions (right). Enter copies syntax to clipboard.",
        width=480,
        height=195,
        caption_style=caption_style,
    )
    story.append(fig5)
    story.append(Spacer(1, 3))

    net_features = [
        [Paragraph("Feature / Capability", th_style), Paragraph("Command & Hotkey", th_style), Paragraph("Operational Purpose", th_style)],
        [
            Paragraph("<b>Mark Dual-Homed Pivot</b>", body_bold),
            Paragraph("<code>:pivot &lt;route&gt;</code><br/>(e.g. <code>:pivot 172.16.1.0/24 via socks5:1080</code>)", code_style),
            Paragraph("Registers host as pivot gateway between subnets. The ASCII topology graph draws the cross-subnet connection automatically.", table_body_style),
        ],
        [
            Paragraph("<b>ProxyChains Config</b>", body_bold),
            Paragraph("Highlight action & press <b>[Enter]</b>", body_style),
            Paragraph("Copies complete <code>proxychains4.conf</code> snippet configured for your active SOCKS proxy port.", table_body_style),
        ],
        [
            Paragraph("<b>Chisel Tunnel Recipes</b>", body_bold),
            Paragraph("Highlight action & press <b>[Enter]</b>", body_style),
            Paragraph("Copies ready-to-run Chisel server command (attacker) and Chisel client reverse tunnel command (victim).", table_body_style),
        ],
        [
            Paragraph("<b>SSH Dynamic Forwarding</b>", body_bold),
            Paragraph("Highlight action & press <b>[Enter]</b>", body_style),
            Paragraph("Copies <code>ssh -D 1080 -N -f user@pivot_ip</code> or SSH ProxyJump commands with target IP and credentials populated.", table_body_style),
        ],
    ]
    t_net = Table(net_features, colWidths=[120, 160, 260])
    t_net.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), C_PRIMARY),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                ("GRID", (0, 0), (-1, -1), 0.5, C_LINE),
                ("PADDING", (0, 0), (-1, -1), 1.8),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(t_net)
    story.append(Spacer(1, 3))

    story.append(Paragraph("11. Station 2 Deep Dive: Playbook Browser & Methodology Roadmaps", h1_style))
    fig2 = make_screenshot_card(
        screenshots_dir / "02-playbooks.png",
        "Figure 6: Station 2 Playbooks — Categorized command encyclopedia and multi-tool recipe carousel. Enter copies recipe to clipboard.",
        width=480,
        height=190,
        caption_style=caption_style,
    )
    story.append(fig2)

    story.append(PageBreak())

    # =========================================================================
    # PAGE 7: REPORTING, THEMES & EXAM DAY PROCEDURES
    # =========================================================================
    story.append(Paragraph("12. Standalone HTML Handover Reports & Evidence Bundles", h1_style))
    story.append(Paragraph(
        "At the end of an assessment, or before finalizing answers in the exam portal, export self-contained submission dossiers:",
        body_style,
    ))

    export_table_data = [
        [Paragraph("Export Format", th_style), Paragraph("Command Line & Console", th_style), Paragraph("Deliverable & Features", th_style)],
        [
            Paragraph("<b>Standalone HTML Report</b>", body_bold),
            Paragraph("<code>glacis export -f html -o report.html</code><br/>Console: <code>:export html</code>", code_style),
            Paragraph("Single self-contained HTML file. <b>Zero JavaScript, zero external CDN/fonts.</b> Includes engagement overview, target dossiers, masked creds, network topology, and <code>@media print</code> stylesheet for clean PDF printout.", table_body_style),
        ],
        [
            Paragraph("<b>Unmasked HTML Report</b>", body_bold),
            Paragraph("<code>glacis export -f html -o report.html --reveal-creds</code>", code_style),
            Paragraph("Reveals all plaintext passwords for internal auditor review or personal grading.", table_body_style),
        ],
        [
            Paragraph("<b>Markdown Evidence Bundle</b>", body_bold),
            Paragraph("<code>glacis export -f md -o exam.md</code><br/>Console: <code>:export exam</code>", code_style),
            Paragraph("Generates <code>exam_evidence.md</code> with all recorded question proofs (Q1-Q35), hashes, flags, and golden reproduction commands.", table_body_style),
        ],
        [
            Paragraph("<b>Lossless JSON Backup</b>", body_bold),
            Paragraph("<code>glacis export -f json -o backup.json</code>", code_style),
            Paragraph("Complete structured export of all database tables for archival or migration.", table_body_style),
        ],
    ]
    t_export = Table(export_table_data, colWidths=[120, 160, 260])
    t_export.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), C_PRIMARY),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                ("GRID", (0, 0), (-1, -1), 0.5, C_LINE),
                ("PADDING", (0, 0), (-1, -1), 1.8),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(t_export)
    story.append(Spacer(1, 3))

    # Built-In Methodology Templates Table
    story.append(Paragraph("13. Built-In Methodology Templates (Press [m] in Cockpit)", h1_style))
    tmpl_data = [
        [Paragraph("Template Alias", th_style), Paragraph("Category", th_style), Paragraph("Key Checklist Steps & Focus", th_style)],
        [Paragraph("<b>:m ejpt</b>", code_bold), Paragraph("eJPT Practical", body_style), Paragraph("Scope recon → Host discovery → Full TCP scan → Service triage → Low-hanging fruit → Web fuzzing → Cred spray → Pivoting → PrivEsc.", body_style)],
        [Paragraph("<b>:m web</b>", code_bold), Paragraph("OWASP Web App", body_style), Paragraph("Technology profiling (whatweb) → Directory fuzzing (feroxbuster) → Parameter fuzzing → SQLi → Auth bypass → LFI/RFI → File upload.", body_style)],
        [Paragraph("<b>:m smb</b>", code_bold), Paragraph("SMB & Windows", body_style), Paragraph("Null session shares (smbclient/smbmap) → User enum (rpcclient) → Password policy → Anonymous signing audit → Vulnerability scan (MS17-010).", body_style)],
        [Paragraph("<b>:m pivoting</b>", code_bold), Paragraph("Network Pivoting", body_style), Paragraph("Dual-homed adapter discovery (ip a) → Internal route inspect → Proxychains & Chisel server setup → Port forward (socat) → Subnet sweep.", body_style)],
        [Paragraph("<b>:m privesc_linux</b>", code_bold), Paragraph("Linux PrivEsc", body_style), Paragraph("sudo -l commands → SUID/SGID binaries (GTFOBins) → Capabilities (getcap) → World-writable scripts & crontabs → Internal listening ports.", body_style)],
        [Paragraph("<b>:m privesc_windows</b>", code_bold), Paragraph("Windows PrivEsc", body_style), Paragraph("whoami /priv (SeImpersonate) → Unquoted service paths → Modifiable service binaries → Stored credentials (cmdkey) → Registry backup.", body_style)],
    ]
    t_tmpl = Table(tmpl_data, colWidths=[85, 110, 345])
    t_tmpl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), C_PRIMARY),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                ("GRID", (0, 0), (-1, -1), 0.5, C_LINE),
                ("PADDING", (0, 0), (-1, -1), 1.8),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(t_tmpl)
    story.append(Spacer(1, 3))

    # The 8 Palettes Reference
    story.append(Paragraph("14. The Eight WCAG AAA Palettes (Press [T] to Switch)", h1_style))
    palettes_desc = [
        [
            Paragraph(
                "• <b>Slate</b> (Default): Glacial cyan accent on deep arctic granite. Clean, professional, high-contrast.<br/>"
                "• <b>Midnight:</b> Indigo and periwinkle on deep nocturne navy. Easy on the eyes during late-night assessments.<br/>"
                "• <b>Ember:</b> Amber CRT glow on warm dark charcoal. Classic retro phosphor terminal aesthetic.<br/>"
                "• <b>Cyber:</b> Electric cyan and hot pink on pitch black. High energy modern Tokyo nightscape.<br/>"
                "• <b>Sugary:</b> Soft espresso ink on unbleached vanilla cream. Soothing warm daylight mode.<br/>"
                "• <b>Candy:</b> Deep violet on soft cotton lilac. Playful pastel with verified 7:1 contrast.<br/>"
                "• <b>Caramel:</b> Teal instrument accent on toffee parchment. High-legibility technical document tone.<br/>"
                "• <b>Catppuccin:</b> Sapphire and lavender on warm mocha. The beloved community dark palette.",
                callout_text,
            )
        ]
    ]
    t_pal = Table(palettes_desc, colWidths=[540])
    t_pal.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                ("BOX", (0, 0), (-1, -1), 0.5, C_LINE),
                ("PADDING", (0, 0), (-1, -1), 3.0),
            ]
        )
    )
    story.append(t_pal)
    story.append(Spacer(1, 3))

    # Exam-Day Readiness & Quick Start Box
    exam_ready_box = [
        [
            Paragraph(
                "<b>EXAM / ASSESSMENT DAY QUICK START:</b><br/>"
                "1. <b>Verify Offline Compliance:</b> Run <code>glacis exam-check</code> in terminal (proves zero network imports for AI proctor).<br/>"
                "2. <b>Launch GLACIS:</b> Open terminal and launch <code>glacis</code> (or short alias <code>gls</code>).<br/>"
                "3. <b>Scaffold Dedicated Workspace:</b> Run <code>:init target_lab &lt;ip&gt;</code> to create a fresh directory with <code>scans/</code>, <code>enum/</code>, <code>screenshots/</code>, and <code>loot/</code>.<br/>"
                "4. <b>Set VPN & Methodology:</b> Run <code>:lhost auto</code> and apply template with <code>:m ejpt</code>.<br/>"
                "5. <b>Live Triage:</b> Use Station 0 (<b>[0]</b>) to track kill-chain progress; use Station 5 (<b>[5]</b>) when internal pivots are discovered.<br/>"
                "6. <b>Handover Dossier:</b> Run <code>:export html</code> or <code>:export exam</code> before final submission to verify all answers.",
                callout_text,
            )
        ]
    ]
    t_ready = Table(exam_ready_box, colWidths=[540])
    t_ready.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F0FDF4")),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#10B981")),
                ("PADDING", (0, 0), (-1, -1), 3.5),
            ]
        )
    )
    story.append(t_ready)

    # Build document
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Successfully generated illustrated PDF at: {dest_path}")


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    screenshots_dir = repo_root / "docs" / "screenshots"

    target_paths = [repo_root / "docs" / "GLACIS_Field_Guide.pdf"]
    desktop = Path.home() / "Desktop"
    if desktop.is_dir():
        target_paths.insert(0, desktop / "GLACIS_Field_Guide.pdf")
        docs_media = desktop / "Documents_and_Media" / "GLACIS_Security_Docs"
        if docs_media.parent.is_dir():
            target_paths.insert(1, docs_media / "GLACIS_Field_Guide.pdf")

    for p in target_paths:
        p.parent.mkdir(parents=True, exist_ok=True)
        build_pdf(p, screenshots_dir)


if __name__ == "__main__":
    main()
