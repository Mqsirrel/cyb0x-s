#!/usr/bin/env python3
"""Build a comprehensive, beautifully styled PDF Operator Guide for CYB0X-S.

Targeted for eJPTv2 / eCPPT practical pentesting exams and security operators.
Outputs to:
  1. /home/albraa/Desktop/CYB0X-S_Operator_Guide.pdf
  2. /home/albraa/Documents/antigravity/kind-lavoisier/cyb0x-s/docs/CYB0X-S_Operator_Guide.pdf
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    HRFlowable,
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
                792 - 25,
                "CYB0X-S · Operator Guide & Practical Exam Workflow Reference (eJPTv2 / eCPPT)",
            )
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.5)
            self.line(36, 792 - 28, 612 - 36, 792 - 28)

        # Running Bottom Footer (All Pages)
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(36, 32, 612 - 36, 32)

        footer_left = "100% Offline & Passive · Local Storage Only · INE Exam Integrity Compliant"
        footer_right = f"Page {self._pageNumber} of {total_pages}"
        self.drawString(36, 20, footer_left)
        self.drawRightString(612 - 36, 20, footer_right)

        self.restoreState()


def build_pdf(dest_path: Path) -> None:
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(dest_path),
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=34,
    )

    styles = getSampleStyleSheet()

    # Base typography palette
    C_PRIMARY = colors.HexColor("#0F172A")    # slate-900
    C_SECONDARY = colors.HexColor("#0284C7")  # sky-600
    C_LINE = colors.HexColor("#CBD5E1")

    # Custom styles
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=C_PRIMARY,
        spaceAfter=2,
    )
    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9.5,
        leading=12,
        textColor=C_SECONDARY,
        spaceAfter=8,
    )
    h1_style = ParagraphStyle(
        "SectionH1",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        textColor=C_PRIMARY,
        spaceBefore=6,
        spaceAfter=3,
    )
    body_style = ParagraphStyle(
        "BodyDark",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=10.8,
        textColor=C_PRIMARY,
        spaceAfter=2,
    )
    table_body_style = ParagraphStyle(
        "TableBody",
        parent=body_style,
        fontSize=7.6,
        leading=9.8,
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
        fontSize=8,
        leading=10,
        textColor=colors.white,
    )
    th_center = ParagraphStyle(
        "TableHeaderCenter",
        parent=th_style,
        alignment=1,
    )
    code_style = ParagraphStyle(
        "CodeText",
        parent=styles["Normal"],
        fontName="Courier",
        fontSize=7.2,
        leading=9.0,
        textColor=colors.HexColor("#0F172A"),
    )
    code_bold = ParagraphStyle(
        "CodeBold",
        parent=code_style,
        fontName="Courier-Bold",
        textColor=colors.HexColor("#0369A1"),
    )
    badge_style = ParagraphStyle(
        "KeyBadge",
        parent=styles["Normal"],
        fontName="Courier-Bold",
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor("#0284C7"),
    )
    callout_text = ParagraphStyle(
        "CalloutText",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.8,
        leading=10.5,
        textColor=colors.HexColor("#1E293B"),
    )

    story = []

    # =========================================================================
    # PAGE 1: TITLE, MENTAL MODEL, 4 STATIONS & COCKPIT ANATOMY
    # =========================================================================
    story.append(Paragraph("CYB0X-S: OPERATOR GUIDE & PRACTICAL WORKFLOW REFERENCE", title_style))
    story.append(Paragraph("High-Speed Offline Penetration Testing Worksheet · eJPTv2 / eCPPT Practical Companion", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=C_SECONDARY, spaceBefore=0, spaceAfter=6))

    # Introduction & Exam Safety Card
    intro_table_data = [
        [
            Paragraph("<b>What is CYB0X-S?</b><br/>"
                      "CYB0X-S is a fast, keyboard-driven terminal worksheet and operational cockpit designed to eliminate exam cognitive overload. "
                      "It provides an offline state machine for host discovery, port tracking, credential reuse, syntax cheatsheets, and question proofs. "
                      "<b>It does not run autonomous exploits or rely on AI.</b> You retain 100% human control while CYB0X-S manages your operational memory.", callout_text),
            Paragraph("<b>INE eJPT / eCPPT Exam Compliance</b><br/>"
                      "• <b>100% Passive & Offline:</b> Runs entirely on localhost via local SQLite database.<br/>"
                      "• <b>Zero Autonomous Action:</b> Commands are copied to your clipboard; YOU execute them.<br/>"
                      "• <b>Zero Cloud / AI Dependencies:</b> No external API calls, leaks, or prohibited LLMs.<br/>"
                      "• <b>Permitted Personal Notes:</b> Functions strictly as a local worksheet and syntax lookup.", callout_text),
        ]
    ]
    t_intro = Table(intro_table_data, colWidths=[270, 270])
    t_intro.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#F8FAFC")),
        ("BACKGROUND", (1, 0), (1, 0), colors.HexColor("#F0FDF4")),
        ("BOX", (0, 0), (0, 0), 0.5, C_LINE),
        ("BOX", (1, 0), (1, 0), 0.5, colors.HexColor("#86EFAC")),
        ("PADDING", (0, 0), (-1, -1), 5),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(t_intro)
    story.append(Spacer(1, 6))

    # Section 1: The 4 Stations
    story.append(Paragraph("1. The Four Operational Stations (Switch with Keys 1, 2, 3, 4)", h1_style))
    stations_data = [
        [
            Paragraph("Station", th_style),
            Paragraph("Name & Purpose", th_style),
            Paragraph("What You See & Do Here", th_style),
            Paragraph("Hotkey", th_style),
        ],
        [
            Paragraph("<b>Station 1</b>", body_bold),
            Paragraph("<b>Cockpit (Workbench)</b><br/>Primary attack surface station", body_style),
            Paragraph("Targets tree, open ports, service status triage, methodology checklist, field notes, and interactive command console.", body_style),
            Paragraph("<b>[1]</b>", badge_style),
        ],
        [
            Paragraph("<b>Station 2</b>", body_bold),
            Paragraph("<b>Playbook Browser</b><br/>Methodology & cheatsheet search", body_style),
            Paragraph("Browse full tactical playbooks (eJPT workflow, Web App OWASP, Active Directory, Pivoting, Linux & Windows PrivEsc). Search commands with instant copy.", body_style),
            Paragraph("<b>[2]</b>", badge_style),
        ],
        [
            Paragraph("<b>Station 3</b>", body_bold),
            Paragraph("<b>Credential Matrix</b><br/>2D Vault & Lateral Spray Grid", body_style),
            Paragraph("2D grid of discovered credentials (rows) × target services (cols). Press <b>[Enter]</b> to compile & copy spray commands; press <b>[Space]</b> to cycle verification state.", body_style),
            Paragraph("<b>[3]</b>", badge_style),
        ],
        [
            Paragraph("<b>Station 4</b>", body_bold),
            Paragraph("<b>Exam Proofs & Loot</b><br/>Q1–Q35 ledger & flags", body_style),
            Paragraph("Track exam question answers (Q1–Q35 via <code>:q</code> or <code>[a]</code>), user/root flags, and <b>Failure Logs</b>. Run <code>:export exam</code> to generate an offline Markdown submission report.", body_style),
            Paragraph("<b>[4]</b>", badge_style),
        ],
    ]
    t_stations = Table(stations_data, colWidths=[65, 145, 290, 40])
    t_stations.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), C_PRIMARY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ("GRID", (0, 0), (-1, -1), 0.5, C_LINE),
        ("PADDING", (0, 0), (-1, -1), 3.5),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(t_stations)
    story.append(Spacer(1, 6))

    # Section 2: Anatomy of Station 1 Cockpit
    story.append(Paragraph("2. Station 1 Anatomy & Screen Real Estate", h1_style))
    story.append(Paragraph(
        "Cockpit is mathematically arranged in a zero-overflow 4-quadrant layout with a dedicated sidebar and bottom console bar:",
        body_style,
    ))

    cockpit_layout_data = [
        [
            Paragraph("<b>SIDEBAR (Left 28% width)</b><br/>"
                      "• <b>ATTACK SURFACE:</b> Collapsible tree of target IPs and hostnames. Displays live service badges.<br/>"
                      "• <b>CREDENTIALS PREVIEW:</b> Discovered usernames and masked passwords. Press <b>[Space]</b> to reveal.<br/>"
                      "<i>Tip: Press <b>[b]</b> anytime to toggle/collapse sidebar and give 100% width to Workbench!</i>", callout_text),
            Paragraph("<b>WORKBENCH (Right 72% width)</b><br/>"
                      "• <b>SERVICES & PORTS (Top):</b> Port, protocol, version, and potential. Press <b>[Space]</b> to cycle triage status. Highlight service to auto-filter checklist!<br/>"
                      "• <b>METHODOLOGY (Lower-Left):</b> Step-by-step checklist with progress bar. Auto-tracks current port.<br/>"
                      "• <b>NOTES & FINDINGS (Lower-Right):</b> Live scratchpad for leads, vulns, and flags.", callout_text),
        ],
        [
            Paragraph("<b>BOTTOM CONSOLE BAR (Full Width)</b> — Fast-capture command line & live syntax guidance drawer.<br/>"
                      "• <b>Top Line:</b> Ready-to-paste command with target IP pre-substituted. Press <b>[Enter]</b> or <b>[y]</b> to copy.<br/>"
                      "• <b>Second Line:</b> Tactical explanation and parameter tip.<br/>"
                      "• <b>Input Row:</b> Press <b>[:]</b> to focus. Type natural notes, commands (e.g. <code>:w rockyou</code>), or capture data.", callout_text),
            Paragraph("<b>TOP MACHINE STATUS STRIP</b> — Instant context on current active target.<br/>"
                      "• Shows Target IP, Hostname, OS, Scope badge (<code>[IN-SCOPE]</code>).<br/>"
                      "• Live progress bar showing methodology completion percentage.<br/>"
                      "• <b>NEXT ACTION</b> recommendation highlighting the immediate next step.", callout_text),
        ]
    ]
    t_cockpit = Table(cockpit_layout_data, colWidths=[270, 270])
    t_cockpit.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ("BOX", (0, 0), (0, 0), 0.5, C_LINE),
        ("BOX", (1, 0), (1, 0), 0.5, C_LINE),
        ("BOX", (0, 1), (0, 1), 0.5, C_LINE),
        ("BOX", (1, 1), (1, 1), 0.5, C_LINE),
        ("PADDING", (0, 0), (-1, -1), 4.5),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(t_cockpit)

    story.append(PageBreak())

    # =========================================================================
    # PAGE 2: COMPLETE KEYBOARD SHORTCUTS CHEATSHEET
    # =========================================================================
    story.append(Paragraph("3. Complete Keyboard Shortcuts Cheatsheet (\"Muscle Memory Map\")", h1_style))
    story.append(Paragraph(
        "CYB0X-S is 100% operational from the keyboard. Single-letter keys trigger immediate actions unless an input dialog is active.",
        body_style,
    ))

    keys_data = [
        [
            Paragraph("Key", th_style),
            Paragraph("Category", th_style),
            Paragraph("Action & Operational Behavior", th_style),
        ],
        # Station navigation
        [Paragraph("<b>1, 2, 3, 4</b>", badge_style), Paragraph("Station", body_style), Paragraph("Switch immediately to Station 1 (Cockpit), 2 (Playbooks), 3 (Creds Matrix), or 4 (Loot).", body_style)],
        [Paragraph("<b>w</b>", badge_style), Paragraph("Navigation", body_style), Paragraph("<b>Cycle Panels:</b> Sequentially rotates focus across all 5 panels in Cockpit without using Tab.", body_style)],
        [Paragraph("<b>h / l</b>", badge_style), Paragraph("Navigation", body_style), Paragraph("<b>Column Jump:</b> Press <b>h</b> to jump to Sidebar (left); press <b>l</b> to jump to Workbench (right).", body_style)],
        [Paragraph("<b>j / k</b>", badge_style), Paragraph("Navigation", body_style), Paragraph("<b>Vim Navigation:</b> Move highlight down (j) or up (k) in the active list or tree.", body_style)],
        [Paragraph("<b>[ / ]</b>", badge_style), Paragraph("Targeting", body_style), Paragraph("<b>Target Switcher:</b> Switch immediately to previous [ or next ] target machine in your workspace.", body_style)],
        [Paragraph("<b>b</b>", badge_style), Paragraph("Display", body_style), Paragraph("<b>Sidebar Toggle:</b> Collapse sidebar to give 100% horizontal width to Workbench (press b again to restore).", body_style)],
        [Paragraph("<b>:</b> (colon)", badge_style), Paragraph("Console", body_style), Paragraph("<b>Focus Command Bar:</b> Instantly activates the bottom console input ready to type.", body_style)],
        [Paragraph("<b>Esc</b>", badge_style), Paragraph("Console", body_style), Paragraph("<b>Dismiss / Blur:</b> Clears the command input and returns cursor focus directly to the workbench list.", body_style)],
        # Tactical Actions
        [Paragraph("<b>Space</b>", badge_style), Paragraph("Triage / Reveal", body_style), Paragraph("• <b>On Service:</b> Cycle status: <code>UNTESTED</code> → <code>[CHECKED]</code> → <code>[DEAD-END]</code> → <code>[DEFERRED]</code>.<br/>• <b>On Credential:</b> Reveal/mask secret password.<br/>• <b>In Station 3 Matrix:</b> Cycle test state: <code>[UNTESTED]</code> → <code>[VALID]</code> → <code>[PWN3D]</code> → <code>[INVALID]</code>.", body_style)],
        [Paragraph("<b>, / .</b>", badge_style), Paragraph("Tool Carousel", body_style), Paragraph("<b>Multi-Tool Recipe Carousel:</b> When a service is highlighted, press <b>.</b> (next) or <b>,</b> (prev) to cycle alternative tool recipes in the console (e.g. feroxbuster → gobuster → nikto → curl).", body_style)],
        [Paragraph("<b>Enter</b>", badge_style), Paragraph("Execute / Copy", body_style), Paragraph("• <b>On Guidance / Service:</b> Copies the previewed tool command to system clipboard.<br/>• <b>In Station 3 Matrix:</b> Compiles and copies ready-to-run spray command for highlighted credential & port.", body_style)],
        [Paragraph("<b>y</b>", badge_style), Paragraph("Copy", body_style), Paragraph("<b>Quick Copy:</b> Copies the selected entity's primary value (IP address, port, password, or checklist command).", body_style)],
        [Paragraph("<b>z</b>", badge_style), Paragraph("Layout", body_style), Paragraph("<b>Zoom:</b> Maximize the focused panel to full-screen; press <b>z</b> again to restore 4-quadrant layout.", body_style)],
        [Paragraph("<b>T</b>", badge_style), Paragraph("Theme", body_style), Paragraph("<b>Theme Picker:</b> Open visual theme modal with 10 vibrant palettes (press <b>d</b> to set default).", body_style)],
        [Paragraph("<b>/</b> or <b>Ctrl+F</b>", badge_style), Paragraph("Search", body_style), Paragraph("<b>Global Fuzzy Search:</b> Search across targets, services, credentials, checklists, and notes.", body_style)],
        [Paragraph("<b>r</b>", badge_style), Paragraph("Reference", body_style), Paragraph("<b>Cheat Sheet:</b> Open offline practical reference dialog for quick syntax inspection.", body_style)],
        # Fast Add Hotkeys
        [Paragraph("<b>t</b>", badge_style), Paragraph("Fast Capture", body_style), Paragraph("Open <b>Add Target</b> dialog (or type <code>:t &lt;ip&gt; [host] [os]</code> in console).", body_style)],
        [Paragraph("<b>s</b>", badge_style), Paragraph("Fast Capture", body_style), Paragraph("Open <b>Add Service</b> dialog (or type <code>:s &lt;port/proto&gt; &lt;service&gt;</code> in console).", body_style)],
        [Paragraph("<b>c</b>", badge_style), Paragraph("Fast Capture", body_style), Paragraph("Open <b>Add Credential</b> dialog (or type <code>:c &lt;user:pass&gt; [scope]</code> in console).", body_style)],
        [Paragraph("<b>n</b>", badge_style), Paragraph("Fast Capture", body_style), Paragraph("Open <b>Add Note</b> dialog (or type <code>:n &lt;text&gt;</code> in console).", body_style)],
        [Paragraph("<b>f</b>", badge_style), Paragraph("Fast Capture", body_style), Paragraph("Open <b>Add Finding / Vulnerability</b> dialog (or type <code>:f &lt;title&gt;</code> in console).", body_style)],
        [Paragraph("<b>m</b>", badge_style), Paragraph("Methodology", body_style), Paragraph("Open <b>Methodology Picker</b> dialog (or type <code>:m &lt;name&gt;</code> in console).", body_style)],
        [Paragraph("<b>a</b>", badge_style), Paragraph("Exam Proof", body_style), Paragraph("In Station 4: Open <b>Add Exam Proof</b> modal to link question number (Q1–Q35) to proof evidence.", body_style)],
        [Paragraph("<b>d</b>", badge_style), Paragraph("Manage", body_style), Paragraph("Delete highlighted entity (requires confirmation).", body_style)],
    ]
    t_keys = Table(keys_data, colWidths=[65, 75, 400])
    t_keys.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), C_PRIMARY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ("GRID", (0, 0), (-1, -1), 0.5, C_LINE),
        ("PADDING", (0, 0), (-1, -1), 2),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(t_keys)
    story.append(Spacer(1, 6))

    # Pro-Tip Callout at bottom of Page 2
    protip_box = [
        [
            Paragraph("<b>PRO-TIP: THE ZERO-MOUSE OPERATOR FLOW</b><br/>"
                      "1. Highlight any port in <b>SERVICES & PORTS</b> with <code>j</code> / <code>k</code>.<br/>"
                      "2. Watch the bottom console display the exact syntax with the target IP already substituted.<br/>"
                      "3. Press <code>.</code> to cycle alternative tools (e.g., feroxbuster → gobuster → nikto → curl).<br/>"
                      "4. Press <code>Enter</code> to copy the command directly to your terminal clipboard, switch to your tmux/terminal pane, and run it!<br/>"
                      "5. Press <code>Space</code> to mark the port <code>[CHECKED]</code> or <code>[DEAD-END]</code>.", callout_text)
        ]
    ]
    t_protip = Table(protip_box, colWidths=[540])
    t_protip.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F0F9FF")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#0284C7")),
        ("PADDING", (0, 0), (-1, -1), 4.5),
    ]))
    story.append(t_protip)

    story.append(PageBreak())

    # =========================================================================
    # PAGE 3: CONSOLE SYNTAX & STEP-BY-STEP PRACTICAL WORKFLOW
    # =========================================================================
    story.append(Paragraph("4. Bottom Console Syntax & Wordlist Accelerators", h1_style))
    console_cmd_data = [
        [
            Paragraph("Console Command", th_style),
            Paragraph("Description & Operational Effect", th_style),
            Paragraph("Example Syntax", th_style),
        ],
        [
            Paragraph("<b>:w &lt;alias&gt;</b>", code_bold),
            Paragraph("<b>Wordlist Accelerator:</b> Instantly copies standard Kali / SecLists paths to clipboard.", table_body_style),
            Paragraph("<code>:w rockyou</code> &nbsp; <code>:w common</code> &nbsp; <code>:w medium</code><br/><code>:w raft-d</code> &nbsp; <code>:w raft-f</code> &nbsp; <code>:w users</code>", code_style),
        ],
        [
            Paragraph("<b>:t &lt;ip&gt; [opts]</b>", code_bold),
            Paragraph("Add target with optional host, OS, subnet, and pivot flag.", table_body_style),
            Paragraph("<code>:t 10.10.10.5 host linux 10.10.10.0/24 pivot</code>", code_style),
        ],
        [
            Paragraph("<b>:pivot / :subnet</b>", code_bold),
            Paragraph("Tag pivot machine / assign subnet CIDR for Station 1 tree grouping.", table_body_style),
            Paragraph("<code>:pivot 10.10.10.5 172.16.1.0/24</code><br/><code>:subnet 10.10.10.5 10.10.10.0/24</code>", code_style),
        ],
        [
            Paragraph("<b>:s &lt;port&gt; &lt;svc&gt;</b>", code_bold),
            Paragraph("Record newly discovered port & service on active target.", table_body_style),
            Paragraph("<code>:s 445/tcp smb</code> &nbsp; <code>:s 8080 http</code>", code_style),
        ],
        [
            Paragraph("<b>:c &lt;user:pass&gt; [scope]</b>", code_bold),
            Paragraph("Record discovered credential with optional service scope.", table_body_style),
            Paragraph("<code>:c admin:Secret123! SMB</code> &nbsp; <code>:c root:toor SSH</code>", code_style),
        ],
        [
            Paragraph("<b>:q / :export</b>", code_bold),
            Paragraph("Pin exam question proof (Q1–Q35) or export markdown exam dossier.", table_body_style),
            Paragraph("<code>:q 7 /var/www/wp-config.php</code><br/><code>:export exam</code> &nbsp; <code>:export report</code>", code_style),
        ],
        [
            Paragraph("<b>:uflag / :rflag &lt;hash&gt;</b>", code_bold),
            Paragraph("Record user flag or root/admin flag into Station 4 Loot Ledger.", table_body_style),
            Paragraph("<code>:uflag 7a9e...</code> &nbsp; <code>:rflag f04b...</code>", code_style),
        ],
        [
            Paragraph("<b>:st &lt;where&gt; / :cl &lt;clue&gt;</b>", code_bold),
            Paragraph("Record stuck point (rabbit hole) and breakthrough clue.", table_body_style),
            Paragraph("<code>:st stuck on wp-login</code> &nbsp; <code>:cl found backup.zip</code>", code_style),
        ],
        [
            Paragraph("<b>:m &lt;template&gt;</b>", code_bold),
            Paragraph("Instantiate standard checklist template (replace or append).", table_body_style),
            Paragraph("<code>:m ejpt</code> &nbsp; <code>:m web</code> &nbsp; <code>:m smb append</code>", code_style),
        ],
        [
            Paragraph("<b>:theme &lt;name&gt;</b>", code_bold),
            Paragraph("Switch theme live (e.g. sugary, caramel, midnight, cyber).", table_body_style),
            Paragraph("<code>:theme sugary</code> &nbsp; <code>:theme midnight</code>", code_style),
        ],
    ]
    t_console = Table(console_cmd_data, colWidths=[115, 260, 165])
    t_console.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), C_PRIMARY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ("GRID", (0, 0), (-1, -1), 0.5, C_LINE),
        ("PADDING", (0, 0), (-1, -1), 1.2),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(t_console)
    story.append(Spacer(1, 2))

    # Section 5: The 5-Phase Battle Plan
    story.append(Paragraph("5. Step-by-Step Practical Exam Workflow (\"The Battle Plan\")", h1_style))
    story.append(Paragraph(
        "Follow this methodical 5-phase execution cycle to maintain relentless momentum and pass calmly:",
        body_style,
    ))

    phases_data = [
        [
            Paragraph(
                "<font color='#0284C7'><b>PHASE 1: SCOPING & HOST DISCOVERY</b></font><br/>"
                "<b>1. Host Discovery:</b> Identify alive target IPs (<code>nmap -sn 10.10.10.0/24</code> or arp-scan).<br/>"
                "<b>2. Fast Add to CYB0X-S:</b> Type <code>:t 10.10.10.20</code> into console. Assign subnets: <code>:subnet 10.10.10.20 10.10.10.0/24</code>.<br/>"
                "<b>3. Scope & Routing:</b> Tag dual-homed pivot machines with <code>:pivot 10.10.10.20 172.16.1.0/24</code> for automatic guidance.<br/>"
                "<b>4. Import XML Option:</b> Mass scans can be imported directly: <code>cyb0x-s import /path/to/scan.xml</code>.",
                table_body_style,
            )
        ],
        [
            Paragraph(
                "<font color='#0284C7'><b>PHASE 2: DETAILED PORT & SERVICE ENUMERATION</b></font><br/>"
                "<b>1. Full Port Sweep:</b> <code>nmap -sS -p- --min-rate 1000 &lt;IP&gt;</code>, then version scan: <code>nmap -sV -sC -p &lt;ports&gt; &lt;IP&gt;</code>.<br/>"
                "<b>2. Record Open Services:</b> Type <code>:s 80 http</code>, <code>:s 445 smb</code>, <code>:s 3306 mysql</code> into the console.<br/>"
                "<b>3. Inspect Tactical Guidance:</b> Highlight each service in <code>SERVICES & PORTS</code>. Press <code>.</code> to cycle tool recipes (whatweb → feroxbuster → gobuster → nikto → curl). Press <b>[Enter]</b> to copy.<br/>"
                "<b>4. Service Triage with [Space]:</b> Cycle status: <code>UNTESTED</code> → <code>[CHECKED]</code> → <code>[DEAD-END]</code> → <code>[DEFERRED]</code>.",
                table_body_style,
            )
        ],
        [
            Paragraph(
                "<font color='#0284C7'><b>PHASE 3: WEB & LOW-HANGING FRUIT EXPLOITATION</b></font><br/>"
                "<b>1. Inspect Anonymous / Default Access:</b> Check anonymous FTP (<code>:s 21</code>), null SMB shares (<code>:s 445</code>), and SNMP strings (<code>:s 161</code>).<br/>"
                "<b>2. Directory Fuzzing:</b> Type <code>:w common</code> or <code>:w medium</code> to copy the SecLists directory path. Paste directly into feroxbuster or gobuster.<br/>"
                "<b>3. Cross-Filtering:</b> Highlighting a service in <code>SERVICES & PORTS</code> auto-scrolls the <b>Methodology</b> checklist to that service's testing steps!",
                table_body_style,
            )
        ],
        [
            Paragraph(
                "<font color='#0284C7'><b>PHASE 4: CREDENTIAL SPRAYING & LATERAL MOVEMENT (STATION 3)</b></font><br/>"
                "<b>1. Record Every Credential:</b> Whenever you find creds (web configs, DB dumps, code), press <b>[c]</b> or type <code>:c user:pass scope</code>.<br/>"
                "<b>2. Open Station 3 Matrix:</b> Press <b>[3]</b> to switch to the 2D Credential Spray Matrix.<br/>"
                "<b>3. Instant Spray Generation:</b> Highlight any cell and press <b>[Enter]</b> to compile & copy ready-to-run spray commands (netexec, evil-winrm).<br/>"
                "<b>4. Record Verification State:</b> Press <b>[Space]</b> on the cell to cycle: <code>[UNTESTED]</code> → <code>[VALID]</code> → <code>[PWN3D]</code> → <code>[INVALID]</code>. State persists in SQLite!",
                table_body_style,
            )
        ],
        [
            Paragraph(
                "<font color='#0284C7'><b>PHASE 5: PRIVESC, PIVOTING & EVIDENCE CAPTURE (STATION 4)</b></font><br/>"
                "<b>1. Pivoting & Route Addition:</b> Tag pivot hosts with <code>:pivot</code> to see dynamic proxy guidance in the console bar.<br/>"
                "<b>2. Privilege Escalation:</b> Switch to Station 2 (press <b>[2]</b>) and search Linux SUID, sudo -l, Cron jobs, or Windows tokens / services.<br/>"
                "<b>3. Capture Question Evidence & Flags:</b> Log question proofs with <code>:q &lt;num&gt; &lt;proof&gt;</code> (or press <b>[a]</b> in Station 4). Record flags with <code>:uflag</code> / <code>:rflag</code>.<br/>"
                "<b>4. Export Exam Submission Bundle:</b> Run <code>:export exam</code> to write a clean Markdown report with all Q1–Q35 evidence, flags, and pivot paths!",
                table_body_style,
            )
        ],
    ]
    t_phases = Table(phases_data, colWidths=[540])
    t_phases.setStyle(TableStyle([
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ("GRID", (0, 0), (-1, -1), 0.5, C_LINE),
        ("PADDING", (0, 0), (-1, -1), 2.0),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(t_phases)
    story.append(Spacer(1, 2))

    # Anti-Rabbit-Hole Box
    rabbit_hole_box = [
        [
            Paragraph("<b>THE 20-MINUTE ROTATION RULE (EXAM GOLDEN RULE)</b><br/>"
                      "If you have been analyzing a single service for more than 20 minutes without a new lead: "
                      "<b>STOP</b>. Press <b>[Space]</b> on the service to mark it <code>[DEFERRED]</code>. "
                      "Type <code>:stuck &lt;service description&gt;</code> to log where you are stuck, press <b>]</b> to rotate to another machine or port, "
                      "and harvest low-hanging fruit elsewhere. 80% of exam failures occur because students spend 3 hours trapped down an unexploitable rabbit hole!", callout_text)
        ]
    ]
    t_rabbit = Table(rabbit_hole_box, colWidths=[540])
    t_rabbit.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFFBEB")),
        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#F59E0B")),
        ("PADDING", (0, 0), (-1, -1), 4.5),
    ]))
    story.append(t_rabbit)

    story.append(PageBreak())

    # =========================================================================
    # PAGE 4: CREDENTIAL SPRAY MATRIX, TEMPLATES & EXAM READINESS
    # =========================================================================
    story.append(Paragraph("6. Station 3 Deep Dive: 2D Credential Spray Matrix", h1_style))
    story.append(Paragraph(
        "In multi-machine exams (like eJPTv2 / eCPPT), credential reuse across SSH, SMB, WinRM, and Web portals is the #1 lateral movement technique. "
        "Station 3 prevents credential amnesia by organizing credentials against in-scope authenticating services:",
        body_style,
    ))

    matrix_demo_data = [
        [
            Paragraph("Credential (Row)", th_style),
            Paragraph("10.10.10.20:22 (SSH)", th_center),
            Paragraph("10.10.10.20:445 (SMB)", th_center),
            Paragraph("10.10.10.25:5985 (WinRM)", th_center),
            Paragraph("10.10.10.30:3389 (RDP)", th_center),
        ],
        [
            Paragraph("<code>admin : P@ssword123</code>", code_style),
            Paragraph("<font color='#059669'><b>[VALID]</b></font>", body_style),
            Paragraph("<font color='#0284C7'><b>[PWN3D]</b></font>", body_style),
            Paragraph("<font color='#D97706'>[UNTESTED]</font>", body_style),
            Paragraph("<font color='#DC2626'>[INVALID]</font>", body_style),
        ],
        [
            Paragraph("<code>guest : &lt;empty&gt;</code>", code_style),
            Paragraph("<font color='#DC2626'>[INVALID]</font>", body_style),
            Paragraph("<font color='#059669'><b>[VALID]</b></font>", body_style),
            Paragraph("<font color='#DC2626'>[INVALID]</font>", body_style),
            Paragraph("<font color='#D97706'>[UNTESTED]</font>", body_style),
        ],
        [
            Paragraph("<code>dbuser : dbpass2024</code>", code_style),
            Paragraph("<font color='#D97706'>[UNTESTED]</font>", body_style),
            Paragraph("<font color='#DC2626'>[INVALID]</font>", body_style),
            Paragraph("<font color='#D97706'>[UNTESTED]</font>", body_style),
            Paragraph("<font color='#D97706'>[UNTESTED]</font>", body_style),
        ],
    ]
    t_matrix_demo = Table(matrix_demo_data, colWidths=[140, 100, 100, 100, 100])
    t_matrix_demo.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), C_PRIMARY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ("GRID", (0, 0), (-1, -1), 0.5, C_LINE),
        ("PADDING", (0, 0), (-1, -1), 2.5),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(t_matrix_demo)
    story.append(Spacer(1, 3))
    story.append(Paragraph(
        "<b>Navigation:</b> Use arrow keys to select any cell. Press <b>[Enter]</b> to instantly copy the command (e.g. <code>netexec smb 10.10.10.20 -u admin -p 'P@ssword123'</code>). "
        "Press <b>[Space]</b> to cycle status: <code>[UNTESTED]</code> → <code>[VALID]</code> → <code>[PWN3D]</code> → <code>[INVALID]</code>.",
        body_style,
    ))
    story.append(Spacer(1, 6))

    # Section 7: Available Methodology Templates
    story.append(Paragraph("7. Built-In Methodology Templates (Type :m <name>)", h1_style))
    tmpl_data = [
        [Paragraph("Template Alias", th_style), Paragraph("Methodology Category", th_style), Paragraph("Key Checklist Steps & Focus", th_style)],
        [Paragraph("<b>:m ejpt</b>", code_bold), Paragraph("eJPT Practical Pentest", body_style), Paragraph("Full 12-step structured workflow: Scope recon → Host discovery → Full TCP scan → Service detection → Low-hanging fruit → Web fuzzing → Auth inspection → Exploitation → Pivoting → PrivEsc.", body_style)],
        [Paragraph("<b>:m web</b>", code_bold), Paragraph("OWASP Web Assessment", body_style), Paragraph("Technology profiling (whatweb) → Content discovery (feroxbuster/gobuster) → Input parameter fuzzing → Authentication bypass → SQL Injection → File inclusion (LFI/RFI) → Upload forms.", body_style)],
        [Paragraph("<b>:m smb</b>", code_bold), Paragraph("SMB & Active Directory", body_style), Paragraph("Null session shares (smbclient/smbmap) → User & group enumeration (rpcclient) → Password policy check → Anonymous signing audit → Vulnerability scan (MS17-010, ZeroLogon).", body_style)],
        [Paragraph("<b>:m pivoting</b>", code_bold), Paragraph("Network Pivoting & Routing", body_style), Paragraph("Dual-homed adapter discovery (ip a) → Internal route table inspect → Proxychains & Chisel server setup → Port forwarding (socat) → Internal segment host sweep.", body_style)],
        [Paragraph("<b>:m privesc_linux</b>", code_bold), Paragraph("Linux Local PrivEsc", body_style), Paragraph("sudo -l commands → SUID/SGID binaries (GTFOBins) → Capabilities (getcap) → World-writable scripts & crontabs → Internal listening ports → Password files (/etc/shadow permissions).", body_style)],
        [Paragraph("<b>:m privesc_windows</b>", code_bold), Paragraph("Windows Local PrivEsc", body_style), Paragraph("whoami /priv (SeImpersonate) → Unquoted service paths → Modifiable service binaries → Stored credentials (cmdkey /list) → AlwaysInstallElevated → SAM/SYSTEM registry backup.", body_style)],
    ]
    t_tmpl = Table(tmpl_data, colWidths=[90, 130, 320])
    t_tmpl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), C_PRIMARY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ("GRID", (0, 0), (-1, -1), 0.5, C_LINE),
        ("PADDING", (0, 0), (-1, -1), 2.5),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(t_tmpl)
    story.append(Spacer(1, 6))

    # Section 8: Exam-Day Quick Checklist & Database Safety
    story.append(Paragraph("8. Exam-Day Readiness & CLI Reference", h1_style))
    exam_ready_box = [
        [
            Paragraph("<b>EXAM START PROCEDURES:</b><br/>"
                      "1. Open terminal on your host or VM and start: <code>cyb0x-s</code><br/>"
                      "2. Pick your favorite visual theme: press <b>[T]</b>, select palette (e.g. <i>Sugary</i>, <i>Midnight</i>, <i>Slate</i>, or <i>Cyber</i>), press <b>[d]</b> to save as default.<br/>"
                      "3. Import initial Nmap scan: type <code>cyb0x-s import /path/to/scan.xml</code> or fast-add targets with <code>:t &lt;ip&gt;</code> (with optional subnet & pivot tags).<br/>"
                      "4. <b>Offline Markdown Submission Bundle:</b> Run <code>:export exam</code> at any time to output a structured markdown report containing all Q1–Q35 evidence, flags, credentials, and pivot paths.<br/>"
                      "5. <b>Database Safety:</b> Stored in <code>~/.local/share/cyb0x-s/worksheets.db</code>. 100% local, persistent, zero network calls, and fully compliant with INE exam rules.", callout_text)
        ]
    ]
    t_ready = Table(exam_ready_box, colWidths=[540])
    t_ready.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F0FDF4")),
        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#10B981")),
        ("PADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(t_ready)

    # Build document
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Successfully generated PDF at: {dest_path}")


def main() -> None:
    desktop_pdf = Path("/home/albraa/Desktop/CYB0X-S_Operator_Guide.pdf")
    repo_pdf = Path(__file__).resolve().parent.parent / "docs" / "CYB0X-S_Operator_Guide.pdf"

    build_pdf(desktop_pdf)
    build_pdf(repo_pdf)


if __name__ == "__main__":
    main()
