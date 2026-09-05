#!/usr/bin/env python3
"""Build a comprehensive, beautifully styled illustrated PDF Operator Guide for CYB0X-S.

Targeted for eJPTv2 / eCPPT practical pentesting exams and security operators.
Includes high-resolution UI screenshots from docs/screenshots/.
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
                792 - 25,
                "CYB0X-S · Operator Guide & Practical Exam Workflow Reference (eJPTv2 / eCPPT)",
            )
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.5)
            self.line(36, 792 - 28, 612 - 36, 792 - 28)

        # Running Bottom Footer (All Pages)
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(36, 30, 612 - 36, 30)

        footer_left = "100% Offline & Passive · Local SQLite Storage · INE Exam Integrity Compliant"
        footer_right = f"Page {self._pageNumber} of {total_pages}"
        self.drawString(36, 18, footer_left)
        self.drawRightString(612 - 36, 18, footer_right)

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
                ("TOPPADDING", (0, 0), (-1, 0), 4),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 2),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 1), (-1, 1), 3),
                ("BOTTOMPADDING", (0, 1), (-1, 1), 4),
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
        topMargin=34,
        bottomMargin=32,
    )

    styles = getSampleStyleSheet()

    # Base typography palette (zero red, cohesive royal sapphire & slate)
    C_PRIMARY = colors.HexColor("#0F172A")    # slate-900
    C_ACCENT = colors.HexColor("#1D63B8")     # royal sapphire blue
    C_LINE = colors.HexColor("#CBD5E1")       # slate-300
    C_MUTED = colors.HexColor("#475569")      # slate-600

    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=19,
        textColor=C_PRIMARY,
        spaceAfter=1,
    )
    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.8,
        leading=11,
        textColor=C_ACCENT,
        spaceAfter=5,
    )
    h1_style = ParagraphStyle(
        "SectionH1",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=13.5,
        textColor=C_PRIMARY,
        spaceBefore=4,
        spaceAfter=3,
    )
    body_style = ParagraphStyle(
        "BodyDark",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.6,
        leading=10.2,
        textColor=C_PRIMARY,
        spaceAfter=2,
    )
    table_body_style = ParagraphStyle(
        "TableBody",
        parent=body_style,
        fontSize=7.2,
        leading=9.2,
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
        fontSize=7.6,
        leading=9.5,
        textColor=colors.white,
    )
    code_style = ParagraphStyle(
        "CodeText",
        parent=styles["Normal"],
        fontName="Courier",
        fontSize=7.0,
        leading=8.8,
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
        fontSize=7.2,
        leading=9.0,
        textColor=C_ACCENT,
    )
    callout_text = ParagraphStyle(
        "CalloutText",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.3,
        leading=9.8,
        textColor=colors.HexColor("#1E293B"),
    )
    caption_style = ParagraphStyle(
        "FigureCaption",
        parent=styles["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=7.0,
        leading=8.5,
        textColor=C_MUTED,
        alignment=1,
    )

    story = []

    # =========================================================================
    # PAGE 1: TITLE, COMPLIANCE, 4 STATIONS & STATION 1 COCKPIT ANATOMY
    # =========================================================================
    story.append(Paragraph("CYB0X-S: OPERATOR GUIDE & PRACTICAL WORKFLOW REFERENCE", title_style))
    story.append(Paragraph("High-Speed Offline Penetration Testing Worksheet · eJPTv2 / eCPPT Practical Companion", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=C_ACCENT, spaceBefore=0, spaceAfter=4))

    # Intro & Exam Compliance Card
    intro_table_data = [
        [
            Paragraph(
                "<b>What is CYB0X-S?</b><br/>"
                "CYB0X-S is a fast, keyboard-driven terminal worksheet and operational cockpit designed to eliminate exam cognitive overload. "
                "It provides an offline state machine for host discovery, port tracking, credential reuse, syntax cheatsheets, and question proofs. "
                "<b>It does not run autonomous exploits or rely on AI.</b> You retain 100% human control while CYB0X-S manages your operational memory.",
                callout_text,
            ),
            Paragraph(
                "<b>INE eJPT / eCPPT Exam Compliance</b><br/>"
                "• <b>100% Passive & Offline:</b> Runs entirely on localhost via local SQLite database.<br/>"
                "• <b>Zero Autonomous Action:</b> Commands are copied to your clipboard; YOU execute them.<br/>"
                "• <b>Zero Cloud / AI Dependencies:</b> No external API calls, leaks, or prohibited LLMs.<br/>"
                "• <b>Permitted Personal Notes:</b> Functions strictly as a local worksheet and syntax lookup.",
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
                ("PADDING", (0, 0), (-1, -1), 4),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(t_intro)
    story.append(Spacer(1, 4))

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
            Paragraph("<b>Cockpit (Workbench)</b>", body_style),
            Paragraph("Targets tree, open ports, service triage status, methodology checklist, scratchpad notes, and interactive command console.", body_style),
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
            Paragraph("2D grid of discovered credentials (rows) × target services (cols). Press <b>[Enter]</b> to compile & copy spray commands; <b>[Space]</b> to cycle verification state.", body_style),
            Paragraph("<b>[3]</b>", badge_style),
        ],
        [
            Paragraph("<b>Station 4</b>", body_bold),
            Paragraph("<b>Exam Proofs & Loot</b>", body_style),
            Paragraph("Track assessment question answers (via <code>:q</code> or <code>[a]</code>), user/root flags, and <b>Failure Logs</b>. Run <code>:export exam</code> for offline Markdown submission dossier.", body_style),
            Paragraph("<b>[4]</b>", badge_style),
        ],
    ]
    t_stations = Table(stations_data, colWidths=[60, 125, 315, 40])
    t_stations.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), C_PRIMARY),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                ("GRID", (0, 0), (-1, -1), 0.5, C_LINE),
                ("PADDING", (0, 0), (-1, -1), 2.5),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    story.append(t_stations)
    story.append(Spacer(1, 4))

    # Section 2: Station 1 Cockpit Visual Architecture & Figure 1
    story.append(Paragraph("2. Station 1 Cockpit Architecture & Real-Time Workspace", h1_style))
    fig1 = make_screenshot_card(
        screenshots_dir / "01-worksheet.png",
        "Figure 1: Station 1 Cockpit — Attack Surface Tree (left), Services & Port Triage (top), Methodology Checklist (mid), and Bottom Command Console.",
        width=480,
        height=210,
        caption_style=caption_style,
    )
    story.append(fig1)

    story.append(PageBreak())

    # =========================================================================
    # PAGE 2: COMPLETE KEYBOARD MATRIX & REFERENCE CHEATSHEET MODAL
    # =========================================================================
    story.append(Paragraph("3. Complete Keyboard Shortcuts Cheatsheet (\"Muscle Memory Map\")", h1_style))
    story.append(Paragraph(
        "CYB0X-S is 100% operational from the keyboard. Single-letter keys trigger immediate actions unless an input modal is active:",
        body_style,
    ))

    keys_data = [
        [
            Paragraph("Key", th_style),
            Paragraph("Category", th_style),
            Paragraph("Action & Operational Behavior", th_style),
        ],
        [Paragraph("<b>1, 2, 3, 4</b>", badge_style), Paragraph("Station", body_style), Paragraph("Switch immediately to Station 1 (Cockpit), 2 (Playbooks), 3 (Creds Matrix), or 4 (Loot).", body_style)],
        [Paragraph("<b>w</b>", badge_style), Paragraph("Navigation", body_style), Paragraph("<b>Cycle Panels:</b> Sequentially rotate focus across all panels in Cockpit without Tab.", body_style)],
        [Paragraph("<b>h / l</b>", badge_style), Paragraph("Navigation", body_style), Paragraph("<b>Column Jump:</b> Press <b>h</b> for Sidebar (left); press <b>l</b> for Workbench (right).", body_style)],
        [Paragraph("<b>j / k</b>", badge_style), Paragraph("Navigation", body_style), Paragraph("<b>Vim Navigation:</b> Move highlight down (j) or up (k) in the active list or tree.", body_style)],
        [Paragraph("<b>[ / ]</b>", badge_style), Paragraph("Targeting", body_style), Paragraph("<b>Target Switcher:</b> Switch immediately to previous [ or next ] target machine.", body_style)],
        [Paragraph("<b>b</b>", badge_style), Paragraph("Display", body_style), Paragraph("<b>Sidebar Toggle:</b> Collapse sidebar to give 100% width to Workbench (press b again to restore).", body_style)],
        [Paragraph("<b>:</b> (colon)", badge_style), Paragraph("Console", body_style), Paragraph("<b>Focus Command Bar:</b> Instantly activates the bottom console input ready to type.", body_style)],
        [Paragraph("<b>Esc</b>", badge_style), Paragraph("Console", body_style), Paragraph("<b>Dismiss / Blur:</b> Clears command input and returns focus directly to the active workbench.", body_style)],
        [Paragraph("<b>Space</b>", badge_style), Paragraph("Triage / Reveal", body_style), Paragraph("• <b>On Service:</b> Cycle triage status: <code>UNTESTED</code> → <code>[CHECKED]</code> → <code>[DEAD-END]</code> → <code>[DEFERRED]</code>.<br/>• <b>On Credential:</b> Reveal/mask secret password.<br/>• <b>In Station 3 Matrix:</b> Cycle test state: <code>[UNTESTED]</code> → <code>[VALID]</code> → <code>[PWN3D]</code> → <code>[INVALID]</code>.", body_style)],
        [Paragraph("<b>, / .</b>", badge_style), Paragraph("Recipe Carousel", body_style), Paragraph("<b>Tool Carousel:</b> When a service is highlighted, press <b>.</b> (next) or <b>,</b> (prev) to cycle alternative tool recipes in the console (e.g. feroxbuster → gobuster → nikto → curl).", body_style)],
        [Paragraph("<b>Enter</b>", badge_style), Paragraph("Execute / Copy", body_style), Paragraph("• <b>On Guidance / Service:</b> Copies the previewed tool command to system clipboard.<br/>• <b>In Station 3 Matrix:</b> Compiles & copies ready-to-run spray command for credential & port.", body_style)],
        [Paragraph("<b>y</b>", badge_style), Paragraph("Quick Copy", body_style), Paragraph("Copies selected entity's primary value (IP address, port, password, or checklist command).", body_style)],
        [Paragraph("<b>z</b>", badge_style), Paragraph("Layout", body_style), Paragraph("<b>Zoom:</b> Maximize the focused panel to full-screen; press <b>z</b> again to restore normal layout.", body_style)],
        [Paragraph("<b>T</b>", badge_style), Paragraph("Theme", body_style), Paragraph("<b>Theme Picker:</b> Open visual theme modal with 10 vibrant palettes (press <b>d</b> to set default).", body_style)],
        [Paragraph("<b>/</b> or <b>Ctrl+F</b>", badge_style), Paragraph("Search", body_style), Paragraph("<b>Global Fuzzy Search:</b> Search across targets, services, credentials, checklists, and notes.", body_style)],
        [Paragraph("<b>r</b>", badge_style), Paragraph("Reference", body_style), Paragraph("<b>Quick Reference Modal:</b> Open offline practical cheatsheet for instant syntax lookup.", body_style)],
        [Paragraph("<b>t / s / c / n</b>", badge_style), Paragraph("Fast Capture", body_style), Paragraph("Modal dialogs to quickly add Target (t), Service (s), Credential (c), or Note (n).", body_style)],
        [Paragraph("<b>a</b>", badge_style), Paragraph("Question Proof", body_style), Paragraph("In Station 4: Open <b>Add Proof</b> modal to link question/item number to proof evidence.", body_style)],
    ]
    t_keys = Table(keys_data, colWidths=[65, 75, 400])
    t_keys.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), C_PRIMARY),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                ("GRID", (0, 0), (-1, -1), 0.5, C_LINE),
                ("PADDING", (0, 0), (-1, -1), 1.5),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(t_keys)
    story.append(Spacer(1, 4))

    # Figure 2: Quick Reference Cheatsheet Modal
    fig2 = make_screenshot_card(
        screenshots_dir / "07-reference.png",
        "Figure 2: Practical Reference Cheatsheet Modal (Hotkey [r]) — Instant syntax lookup for Nmap, NetExec, Hydra, Chisel, and LinPEAS.",
        width=470,
        height=185,
        caption_style=caption_style,
    )
    story.append(fig2)
    story.append(Spacer(1, 4))

    # Pro-Tip Box
    protip_box = [
        [
            Paragraph(
                "<b>PRO-TIP: THE ZERO-MOUSE OPERATOR FLOW</b><br/>"
                "1. Highlight any port in <b>SERVICES & PORTS</b> with <code>j</code> / <code>k</code>.<br/>"
                "2. Watch the bottom console display the exact syntax with the target IP already substituted.<br/>"
                "3. Press <code>.</code> to cycle alternative tools (e.g., feroxbuster → gobuster → nikto → curl).<br/>"
                "4. Press <code>Enter</code> to copy the command directly to your terminal clipboard, switch to your tmux/terminal pane, and run it!<br/>"
                "5. Press <code>Space</code> to mark the port <code>[CHECKED]</code> or <code>[DEAD-END]</code>.",
                callout_text,
            )
        ]
    ]
    t_protip = Table(protip_box, colWidths=[540])
    t_protip.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F0F9FF")),
                ("BOX", (0, 0), (-1, -1), 0.5, C_ACCENT),
                ("PADDING", (0, 0), (-1, -1), 3.5),
            ]
        )
    )
    story.append(t_protip)

    story.append(PageBreak())

    # =========================================================================
    # PAGE 3: CONSOLE SYNTAX & 5-PHASE PRACTICAL BATTLE PLAN
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
            Paragraph("Pin assessment question proof or export markdown evidence dossier.", table_body_style),
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
            Paragraph("Switch theme live (e.g. sugary, midnight, slate, caramel, cyber).", table_body_style),
            Paragraph("<code>:theme sugary</code> &nbsp; <code>:theme midnight</code>", code_style),
        ],
    ]
    t_console = Table(console_cmd_data, colWidths=[115, 260, 165])
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
    story.append(Spacer(1, 2))

    # Section 5: The 5-Phase Battle Plan
    story.append(Paragraph("5. Step-by-Step Practical Exam Workflow (\"The Battle Plan\")", h1_style))
    phases_data = [
        [
            Paragraph(
                "<font color='#1D63B8'><b>PHASE 1: SCOPING & HOST DISCOVERY</b></font><br/>"
                "<b>1. Host Discovery:</b> Identify alive target IPs (<code>nmap -sn 10.10.10.0/24</code> or arp-scan).<br/>"
                "<b>2. Fast Add to CYB0X-S:</b> Type <code>:t 10.10.10.20</code> into console. Assign subnets: <code>:subnet 10.10.10.20 10.10.10.0/24</code>.<br/>"
                "<b>3. Scope & Routing:</b> Tag dual-homed pivot machines with <code>:pivot 10.10.10.20 172.16.1.0/24</code> for automatic guidance.<br/>"
                "<b>4. Import XML Option:</b> Mass scans can be imported directly: <code>cyb0x-s import /path/to/scan.xml</code>.",
                table_body_style,
            )
        ],
        [
            Paragraph(
                "<font color='#1D63B8'><b>PHASE 2: DETAILED PORT & SERVICE ENUMERATION</b></font><br/>"
                "<b>1. Full Port Sweep:</b> <code>nmap -sS -p- --min-rate 1000 &lt;IP&gt;</code>, then version scan: <code>nmap -sV -sC -p &lt;ports&gt; &lt;IP&gt;</code>.<br/>"
                "<b>2. Record Open Services:</b> Type <code>:s 80 http</code>, <code>:s 445 smb</code>, <code>:s 3306 mysql</code> into the console.<br/>"
                "<b>3. Inspect Tactical Guidance:</b> Highlight each service in <code>SERVICES & PORTS</code>. Press <code>.</code> to cycle tool recipes (whatweb → feroxbuster → gobuster → nikto → curl). Press <b>[Enter]</b> to copy.<br/>"
                "<b>4. Service Triage with [Space]:</b> Cycle status: <code>UNTESTED</code> → <code>[CHECKED]</code> → <code>[DEAD-END]</code> → <code>[DEFERRED]</code>.",
                table_body_style,
            )
        ],
        [
            Paragraph(
                "<font color='#1D63B8'><b>PHASE 3: WEB & LOW-HANGING FRUIT EXPLOITATION</b></font><br/>"
                "<b>1. Inspect Anonymous / Default Access:</b> Check anonymous FTP (<code>:s 21</code>), null SMB shares (<code>:s 445</code>), and SNMP strings (<code>:s 161</code>).<br/>"
                "<b>2. Directory Fuzzing:</b> Type <code>:w common</code> or <code>:w medium</code> to copy the SecLists directory path. Paste directly into feroxbuster or gobuster.<br/>"
                "<b>3. Cross-Filtering:</b> Highlighting a service in <code>SERVICES & PORTS</code> auto-scrolls the <b>Methodology</b> checklist to that service's testing steps!",
                table_body_style,
            )
        ],
        [
            Paragraph(
                "<font color='#1D63B8'><b>PHASE 4: CREDENTIAL SPRAYING & LATERAL MOVEMENT (STATION 3)</b></font><br/>"
                "<b>1. Record Every Credential:</b> Whenever you find creds (web configs, DB dumps, code), press <b>[c]</b> or type <code>:c user:pass scope</code>.<br/>"
                "<b>2. Open Station 3 Matrix:</b> Press <b>[3]</b> to switch to the 2D Credential Spray Matrix.<br/>"
                "<b>3. Instant Spray Generation:</b> Highlight any cell and press <b>[Enter]</b> to compile & copy ready-to-run spray commands (netexec, evil-winrm).<br/>"
                "<b>4. Record Verification State:</b> Press <b>[Space]</b> on the cell to cycle: <code>[UNTESTED]</code> → <code>[VALID]</code> → <code>[PWN3D]</code> → <code>[INVALID]</code>. State persists in SQLite!",
                table_body_style,
            )
        ],
        [
            Paragraph(
                "<font color='#1D63B8'><b>PHASE 5: PRIVESC, PIVOTING & EVIDENCE CAPTURE (STATION 4)</b></font><br/>"
                "<b>1. Pivoting & Route Addition:</b> Tag pivot hosts with <code>:pivot</code> to see dynamic proxy guidance in the console bar.<br/>"
                "<b>2. Privilege Escalation:</b> Switch to Station 2 (press <b>[2]</b>) and search Linux SUID, sudo -l, Cron jobs, or Windows tokens / services.<br/>"
                "<b>3. Capture Question Evidence & Flags:</b> Log question proofs with <code>:q &lt;num&gt; &lt;proof&gt;</code> (or press <b>[a]</b> in Station 4). Record flags with <code>:uflag</code> / <code>:rflag</code>.<br/>"
                "<b>4. Export Assessment Submission Bundle:</b> Run <code>:export exam</code> to write a clean Markdown report with all evidence, flags, and pivot paths!",
                table_body_style,
            )
        ],
    ]
    t_phases = Table(phases_data, colWidths=[540])
    t_phases.setStyle(
        TableStyle(
            [
                ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                ("GRID", (0, 0), (-1, -1), 0.5, C_LINE),
                ("PADDING", (0, 0), (-1, -1), 1.8),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(t_phases)
    story.append(Spacer(1, 2))

    # Anti-Rabbit-Hole Box
    rabbit_hole_box = [
        [
            Paragraph(
                "<b>THE 20-MINUTE ROTATION RULE (EXAM GOLDEN RULE)</b><br/>"
                "If you have been analyzing a single service for more than 20 minutes without a new lead: "
                "<b>STOP</b>. Press <b>[Space]</b> on the service to mark it <code>[DEFERRED]</code>. "
                "Type <code>:stuck &lt;service description&gt;</code> to log where you are stuck, press <b>]</b> to rotate to another machine or port, "
                "and harvest low-hanging fruit elsewhere. 80% of exam failures occur because candidates spend 3 hours trapped down an unexploitable rabbit hole!",
                callout_text,
            )
        ]
    ]
    t_rabbit = Table(rabbit_hole_box, colWidths=[540])
    t_rabbit.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFFBEB")),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#F59E0B")),
                ("PADDING", (0, 0), (-1, -1), 4.0),
            ]
        )
    )
    story.append(t_rabbit)

    story.append(PageBreak())

    # =========================================================================
    # PAGE 4: STATION 3 DEEP DIVE — 2D CREDENTIAL SPRAY MATRIX
    # =========================================================================
    story.append(Paragraph("6. Station 3 Deep Dive: 2D Credential Spray Matrix", h1_style))
    story.append(Paragraph(
        "In multi-machine exams (like eJPTv2 / eCPPT), credential reuse across SSH, SMB, WinRM, and Web portals is the primary lateral movement technique. "
        "Station 3 prevents credential amnesia by organizing all discovered credentials (rows) against all discovered target services (columns) in an interactive 2D grid:",
        body_style,
    ))

    # Figure 3: Station 3 Creds Matrix UI
    fig3 = make_screenshot_card(
        screenshots_dir / "03-creds.png",
        "Figure 3: Station 3 Credential Matrix — Interactive 2D grid of discovered accounts against authenticating services with status badges.",
        width=480,
        height=215,
        caption_style=caption_style,
    )
    story.append(fig3)
    story.append(Spacer(1, 4))

    # Controls & State Lifecycle Table
    matrix_controls_data = [
        [
            Paragraph("Action / Key", th_style),
            Paragraph("Mechanism & Tactical Utility", th_style),
            Paragraph("Persistence & Exam Value", th_style),
        ],
        [
            Paragraph("<b>Arrow Keys / Vim</b>", badge_style),
            Paragraph("Navigate freely across cells in the 2D grid.", table_body_style),
            Paragraph("Instant visual overview of which accounts were tested where.", table_body_style),
        ],
        [
            Paragraph("<b>[Space]</b> (Cycle State)", badge_style),
            Paragraph("Cycles through: <code>[UNTESTED]</code> → <code>[VALID]</code> (Green) → <code>[PWN3D]</code> (Blue) → <code>[INVALID]</code> (Plum).", table_body_style),
            Paragraph("Persisted instantly to local SQLite database. Never guess if you tried a password.", table_body_style),
        ],
        [
            Paragraph("<b>[Enter]</b> (Copy Command)", badge_style),
            Paragraph("Automatically compiles and copies the exact command line to your clipboard (e.g. <code>netexec smb 10.10.10.20 -u admin -p 'P@ssword123'</code>).", table_body_style),
            Paragraph("Zero typos under stress; supports SSH, SMB, WinRM, RDP, MySQL, and MSSQL.", table_body_style),
        ],
        [
            Paragraph("<b>[c]</b> (Fast Add)", badge_style),
            Paragraph("Opens modal to record newly discovered credentials (or type <code>:c user:pass [scope]</code>).", table_body_style),
            Paragraph("Automatically expands the matrix with a new row across all existing targets.", table_body_style),
        ],
    ]
    t_matrix_ctrl = Table(matrix_controls_data, colWidths=[105, 235, 200])
    t_matrix_ctrl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), C_PRIMARY),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                ("GRID", (0, 0), (-1, -1), 0.5, C_LINE),
                ("PADDING", (0, 0), (-1, -1), 2.0),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(t_matrix_ctrl)
    story.append(Spacer(1, 4))

    # Lateral Movement Workflow Box
    lat_mov_box = [
        [
            Paragraph(
                "<b>LATERAL MOVEMENT WORKFLOW SUMMARY:</b><br/>"
                "1. <b>Harvest:</b> Extract credentials from web app configs (<code>wp-config.php</code>, <code>.env</code>), DB dumps, or SAM registry hive.<br/>"
                "2. <b>Input:</b> Press <b>[c]</b> in CYB0X-S to add the username and password.<br/>"
                "3. <b>Matrix Spray:</b> Press <b>[3]</b> to open the grid. Highlight the intersection of the new credential with port 445 (SMB) or 22 (SSH).<br/>"
                "4. <b>Execute:</b> Press <b>[Enter]</b> to copy the pre-built NetExec/SSH command, paste and run in your terminal.<br/>"
                "5. <b>Record:</b> If admin/pwn3d, press <b>[Space]</b> twice to set <code>[PWN3D]</code>. You now have your next pivot point!",
                callout_text,
            )
        ]
    ]
    t_lat = Table(lat_mov_box, colWidths=[540])
    t_lat.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F0F9FF")),
                ("BOX", (0, 0), (-1, -1), 0.5, C_ACCENT),
                ("PADDING", (0, 0), (-1, -1), 4.0),
            ]
        )
    )
    story.append(t_lat)

    story.append(PageBreak())

    # =========================================================================
    # PAGE 5: STATION 4 DEEP DIVE — QUESTION PROOFS & LOOT LEDGER
    # =========================================================================
    story.append(Paragraph("7. Station 4 Deep Dive: Question Proofs & Loot Ledger", h1_style))
    story.append(Paragraph(
        "Practical exams require concrete evidence: hashes, specific directory names, database records, usernames, or service versions. "
        "Station 4 provides a dedicated ledger to link lab findings directly to question numbers, plus a Failure Log to manage stuck points:",
        body_style,
    ))

    # Figure 4: Station 4 Loot & Proofs UI
    fig4 = make_screenshot_card(
        screenshots_dir / "04-loot.png",
        "Figure 4: Station 4 Proofs & Loot Ledger — Question Proofs, User/Root Flags, and Failure / Rabbit Hole Logs.",
        width=480,
        height=215,
        caption_style=caption_style,
    )
    story.append(fig4)
    story.append(Spacer(1, 4))

    # Station 4 Components & Workflow Table
    proof_table_data = [
        [
            Paragraph("Module / Feature", th_style),
            Paragraph("Hotkeys & Console Syntax", th_style),
            Paragraph("Operational Purpose & Deliverable", th_style),
        ],
        [
            Paragraph("<b>Question Proofs</b>", body_bold),
            Paragraph("Press <b>[a]</b> (modal) or<br/><code>:q &lt;num&gt; &lt;proof&gt; [notes]</code>", code_style),
            Paragraph("Links evidence directly to an exam question number (e.g. <code>:q 14 /etc/passwd root hash</code>). Prevents having to re-exploit targets at exam end.", table_body_style),
        ],
        [
            Paragraph("<b>Loot & Flags Tracker</b>", body_bold),
            Paragraph("<code>:uflag &lt;hash&gt;</code> (user flag)<br/><code>:rflag &lt;hash&gt;</code> (root flag)", code_style),
            Paragraph("Captures proof hashes with timestamps and associated target IP. Safely stored in local SQLite database.", table_body_style),
        ],
        [
            Paragraph("<b>Failure Log (Anti-Rabbit Hole)</b>", body_bold),
            Paragraph("<code>:st &lt;stuck_point&gt;</code><br/><code>:cl &lt;breakthrough_clue&gt;</code>", code_style),
            Paragraph("Records dead-ends and breakthroughs so you never repeat failed brute-force or injection attempts.", table_body_style),
        ],
        [
            Paragraph("<b>Markdown Submission Dossier</b>", body_bold),
            Paragraph("Type <code>:export exam</code> or<br/><code>:export report</code> in console", code_style),
            Paragraph("Generates an instant offline Markdown report (<code>exam_proofs.md</code>) summarizing all answered questions, flags, and credentials.", table_body_style),
        ],
    ]
    t_proof = Table(proof_table_data, colWidths=[120, 160, 260])
    t_proof.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), C_PRIMARY),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                ("GRID", (0, 0), (-1, -1), 0.5, C_LINE),
                ("PADDING", (0, 0), (-1, -1), 2.0),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(t_proof)
    story.append(Spacer(1, 4))

    # Exam Submission Dossier Callout
    dossier_box = [
        [
            Paragraph(
                "<b>THE OFFLINE SUBMISSION DOSSIER (<code>:export exam</code>):</b><br/>"
                "At any time, or before finalizing your exam answers in the INE portal, run <code>:export exam</code> in the bottom console. "
                "CYB0X-S exports a complete, self-contained Markdown file containing: (1) Target Inventory & Subnet Map, (2) Solved Questions 1–35 with exact evidence strings, "
                "(3) Captured User & Root Flags, (4) Discovered Credentials & Verification States, and (5) Audit Trail of all tested services. "
                "Keep this document open in your text editor while answering the 35 exam questions to achieve 100% submission confidence.",
                callout_text,
            )
        ]
    ]
    t_dossier = Table(dossier_box, colWidths=[540])
    t_dossier.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F0FDF4")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#10B981")),
                ("PADDING", (0, 0), (-1, -1), 4.0),
            ]
        )
    )
    story.append(t_dossier)

    story.append(PageBreak())

    # =========================================================================
    # PAGE 6: STATION 2 PLAYBOOKS, TEMPLATES & EXAM READINESS
    # =========================================================================
    story.append(Paragraph("8. Station 2 Playbooks & Built-In Methodology Templates", h1_style))
    story.append(Paragraph(
        "Station 2 serves as an offline tactical encyclopedia. You can search playbooks for specific attack chains, inspect commands, and copy snippets with a single keystroke:",
        body_style,
    ))

    # Figure 5: Station 2 Playbooks UI
    fig5 = make_screenshot_card(
        screenshots_dir / "02-playbooks.png",
        "Figure 5: Station 2 Playbook Browser — Tactical guides, command recipes, and methodology references with instant keyboard copy.",
        width=480,
        height=200,
        caption_style=caption_style,
    )
    story.append(fig5)
    story.append(Spacer(1, 4))

    # Built-In Methodology Templates Table
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
                ("PADDING", (0, 0), (-1, -1), 2.0),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(t_tmpl)
    story.append(Spacer(1, 4))

    # Exam-Day Readiness & CLI Reference Box
    exam_ready_box = [
        [
            Paragraph(
                "<b>EXAM START PROCEDURES:</b><br/>"
                "1. Open terminal on your host or VM and launch: <code>cyb0x-s</code><br/>"
                "2. Pick your visual theme: press <b>[T]</b>, select palette (e.g. <i>Sugary</i>, <i>Midnight</i>, <i>Slate</i>, or <i>Cyber</i>), press <b>[d]</b> to save as default.<br/>"
                "3. Import initial Nmap scan: run <code>cyb0x-s import /path/to/scan.xml</code> or fast-add targets with <code>:t &lt;ip&gt;</code>.<br/>"
                "4. <b>Offline Markdown Submission Bundle:</b> Run <code>:export exam</code> at any time to output a structured markdown report containing all recorded evidence, flags, credentials, and pivot paths.<br/>"
                "5. <b>Database Safety:</b> Stored in <code>~/.local/share/cyb0x-s/worksheets.db</code>. 100% local, persistent, zero network calls, and fully compliant with INE exam rules.",
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
                ("PADDING", (0, 0), (-1, -1), 4.5),
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
    desktop_pdf = Path("/home/albraa/Desktop/CYB0X-S_Operator_Guide.pdf")
    repo_pdf = repo_root / "docs" / "CYB0X-S_Operator_Guide.pdf"

    build_pdf(desktop_pdf, screenshots_dir)
    build_pdf(repo_pdf, screenshots_dir)


if __name__ == "__main__":
    main()
