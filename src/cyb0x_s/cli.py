"""Command Line Interface for CYB0X-S (Safe Field Notebook).

Provides ultra-fast capture commands to record operator discoveries in seconds.
Strictly passive: stores verbatim inputs without classification, parsing, or autonomous actions.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.markup import escape
from rich.table import Table

from cyb0x_s.clipboard import copy_to_clipboard, extract_copy_value
from cyb0x_s.db.store import NotebookStore, get_default_db_path
from cyb0x_s.export import export_json, export_markdown, export_txt, import_json
from cyb0x_s.models import ChecklistStatus, ServiceStatus
from cyb0x_s.search import search_notebook
from cyb0x_s.templates import apply_template_to_store, get_available_templates

console = Console()
err_console = Console(stderr=True)

BANNER = """[bold cyan]CYB0X-S WORKSHEET[/bold cyan]
[dim]Field Notes & Methodology Worksheet • Human-controlled[/dim]"""


def _get_store(ctx: click.Context) -> NotebookStore:
    if "store" not in ctx.obj:
        db_path = ctx.obj.get("db_path")
        ctx.obj["store"] = NotebookStore(db_path)
    return ctx.obj["store"]


@click.group(invoke_without_command=True)
@click.option("--db", "db_path", type=click.Path(), default=None, help="Custom SQLite database file path.")
@click.option("--workspace", "-w", "workspace_name", default=None, help="Assessment workspace name.")
@click.pass_context
def cli(ctx: click.Context, db_path: Optional[str], workspace_name: Optional[str]) -> None:
    """CYB0X-S — Conservative, passive, human-controlled field notebook."""
    ctx.ensure_object(dict)
    ctx.obj["db_path"] = db_path

    # If no subcommand is given, launch the TUI
    if ctx.invoked_subcommand is None:
        ctx.invoke(tui_cmd)


# -----------------------------------------------------------------------------
# Target Commands
# -----------------------------------------------------------------------------

@cli.command("target")
@click.argument("ip")
@click.option("--hostname", "-h", default="", help="Hostname or FQDN")
@click.option("--os", "os_name", default="Unknown", help="Target operating system")
@click.option("--notes", "-n", default="", help="General target notes")
@click.option("--copy", "-c", is_flag=True, help="Copy target IP to clipboard")
@click.pass_context
def target_cmd(ctx: click.Context, ip: str, hostname: str, os_name: str, notes: str, copy: bool) -> None:
    """Record a target machine (e.g. cyb0x-s target 10.10.10.20)."""
    store = _get_store(ctx)
    target = store.add_target(ip=ip, hostname=hostname, os_name=os_name, notes=notes)
    console.print(f"[green]✓ Target recorded:[/green] [bold]{target.ip}[/bold] (ID: {target.id})")
    if copy:
        copy_to_clipboard(target.ip)
        console.print("[dim]→ Copied IP to clipboard[/dim]")


# Alias 't' for target
@cli.command("t", hidden=True)
@click.argument("ip")
@click.option("--hostname", "-h", default="")
@click.option("--os", "os_name", default="Unknown")
@click.option("--notes", "-n", default="")
@click.option("--copy", "-c", is_flag=True)
@click.pass_context
def target_alias(ctx: click.Context, ip: str, hostname: str, os_name: str, notes: str, copy: bool) -> None:
    ctx.invoke(target_cmd, ip=ip, hostname=hostname, os_name=os_name, notes=notes, copy=copy)


# -----------------------------------------------------------------------------
# Service Commands
# -----------------------------------------------------------------------------

@cli.command("service")
@click.argument("args", nargs=-1, required=True)
@click.option("--version", "-v", default="", help="Software version string")
@click.option("--status", default="CHECKED", help="Investigation status (UNTESTED, CHECKED, DEFERRED, DEAD-END)")
@click.option("--notes", "-n", default="", help="Observations on this service")
@click.option("--target", "-t", default=None, help="Target IP or ID (defaults to active target)")
@click.option("--copy", "-c", is_flag=True, help="Copy IP:port to clipboard")
@click.pass_context
def service_cmd(
    ctx: click.Context,
    args: tuple[str, ...],
    version: str,
    status: str,
    notes: str,
    target: Optional[str],
    copy: bool,
) -> None:
    """Record a service.

    Syntax examples:
      cyb0x-s service 10.10.10.20 445/tcp SMB
      cyb0x-s service 445/tcp SMB
      cyb0x-s service 80 HTTP --version "Apache 2.4"
    """
    store = _get_store(ctx)

    # Parse arguments flexibly: [target_ip] <port[/proto]> [service_name]
    target_obj = None
    port_proto_str = ""
    service_name = "unknown"

    if len(args) == 3:
        # e.g. 10.10.10.20 445/tcp SMB
        target_obj = store.resolve_target(args[0])
        if not target_obj:
            # Create target on the fly
            target_obj = store.add_target(args[0])
        port_proto_str = args[1]
        service_name = args[2]
    elif len(args) == 2:
        # Could be "10.10.10.20 80" or "80/tcp HTTP"
        if "/" in args[0] or args[0].isdigit():
            port_proto_str = args[0]
            service_name = args[1]
        else:
            target_obj = store.resolve_target(args[0])
            port_proto_str = args[1]
    elif len(args) == 1:
        port_proto_str = args[0]
    else:
        err_console.print("[red]Usage: cyb0x-s service [TARGET] <PORT/PROTO> [SERVICE][/red]")
        sys.exit(1)

    if not target_obj:
        target_obj = store.resolve_target(target)
    if not target_obj:
        err_console.print("[red]Error: No target specified and no active target set.[/red]")
        sys.exit(1)

    # Parse port and proto
    m = re.match(r"^(\d+)(?:/([a-zA-Z]+))?$", port_proto_str)
    if not m:
        err_console.print(f"[red]Invalid port specification '{port_proto_str}'. Expected format like 445 or 445/tcp[/red]")
        sys.exit(1)

    port = int(m.group(1))
    proto = m.group(2) or "tcp"

    svc = store.add_service(
        target_id=target_obj.id,
        port=port,
        protocol=proto,
        service=service_name,
        version=version,
        status=status,
        notes=notes,
    )
    console.print(
        f"[green]✓ Service recorded:[/green] [bold]{target_obj.ip}:{svc.port}/{svc.protocol}[/bold] {svc.service} ({svc.version or 'no version'})"
    )
    if copy:
        val = f"{target_obj.ip}:{svc.port}"
        copy_to_clipboard(val)
        console.print(f"[dim]→ Copied {val} to clipboard[/dim]")


# Alias 's' for service
@cli.command("s", hidden=True)
@click.argument("args", nargs=-1, required=True)
@click.option("--version", "-v", default="")
@click.option("--status", default="CHECKED")
@click.option("--notes", "-n", default="")
@click.option("--target", "-t", default=None)
@click.option("--copy", "-c", is_flag=True)
@click.pass_context
def service_alias(
    ctx: click.Context, args: tuple[str, ...], version: str, status: str, notes: str, target: Optional[str], copy: bool
) -> None:
    ctx.invoke(service_cmd, args=args, version=version, status=status, notes=notes, target=target, copy=copy)


# -----------------------------------------------------------------------------
# Note Commands
# -----------------------------------------------------------------------------

@cli.command("note")
@click.argument("content")
@click.option("--target", "-t", default=None, help="Associate note with a target IP or ID")
@click.pass_context
def note_cmd(ctx: click.Context, content: str, target: Optional[str]) -> None:
    """Record a free-form field note."""
    store = _get_store(ctx)
    t_obj = store.resolve_target(target) if target else store.get_active_target()
    target_id = t_obj.id if t_obj else None
    store.add_note(content=content, target_id=target_id)
    t_info = f" (Target: {t_obj.ip})" if t_obj else " (Global)"
    console.print(f"[green]✓ Note recorded{t_info}:[/green] {content}")


# Alias 'n' for note
@cli.command("n", hidden=True)
@click.argument("content")
@click.option("--target", "-t", default=None)
@click.pass_context
def note_alias(ctx: click.Context, content: str, target: Optional[str]) -> None:
    ctx.invoke(note_cmd, content=content, target=target)


# -----------------------------------------------------------------------------
# Finding Commands
# -----------------------------------------------------------------------------

@cli.command("finding")
@click.argument("title")
@click.option("--target", "-t", default=None, help="Target IP or ID")
@click.option("--desc", "-d", default="", help="Detailed description")
@click.option("--notes", "-n", default="", help="Additional observations")
@click.option("--severity", "-s", default=None, help="User-assigned severity (INFO, LOW, MEDIUM, HIGH, CRITICAL)")
@click.pass_context
def finding_cmd(
    ctx: click.Context,
    title: str,
    target: Optional[str],
    desc: str,
    notes: str,
    severity: Optional[str],
) -> None:
    """Record a manually discovered security finding."""
    store = _get_store(ctx)
    t_obj = store.resolve_target(target) if target else store.get_active_target()
    target_id = t_obj.id if t_obj else None

    f = store.add_finding(
        title=title,
        target_id=target_id,
        description=desc,
        notes=notes,
        severity=severity,
    )
    t_info = f" for {t_obj.ip}" if t_obj else ""
    sev_str = f" [{f.severity}]" if f.severity else ""
    console.print(f"[green]✓ Finding recorded{t_info}:[/green] [bold]{f.title}[/bold]{sev_str}")


# Alias 'f' for finding
@cli.command("f", hidden=True)
@click.argument("title")
@click.option("--target", "-t", default=None)
@click.option("--desc", "-d", default="")
@click.option("--notes", "-n", default="")
@click.option("--severity", "-s", default=None)
@click.pass_context
def finding_alias(
    ctx: click.Context, title: str, target: Optional[str], desc: str, notes: str, severity: Optional[str]
) -> None:
    ctx.invoke(finding_cmd, title=title, target=target, desc=desc, notes=notes, severity=severity)


# -----------------------------------------------------------------------------
# Credential Commands
# -----------------------------------------------------------------------------

@cli.command("cred")
@click.argument("cred_pair")
@click.option("--source", "-s", default="", help="Source of credential (e.g. backup.zip, shadow)")
@click.option("--target", "-t", default=None, help="Target IP or ID")
@click.option("--scope", default="", help="Service or domain scope (e.g. SSH, SMB, web)")
@click.option("--status", default="untested", help="Credential status (untested, valid, invalid)")
@click.option("--notes", "-n", default="", help="Observations on credential")
@click.option("--copy", "-c", is_flag=True, help="Copy password to clipboard")
@click.pass_context
def cred_cmd(
    ctx: click.Context,
    cred_pair: str,
    source: str,
    target: Optional[str],
    scope: str,
    status: str,
    notes: str,
    copy: bool,
) -> None:
    """Record a credential discovered by the operator (e.g. admin:password)."""
    store = _get_store(ctx)
    t_obj = store.resolve_target(target) if target else store.get_active_target()
    target_id = t_obj.id if t_obj else None

    if ":" in cred_pair:
        username, secret = cred_pair.split(":", 1)
    else:
        username = cred_pair
        secret = ""

    c = store.add_credential(
        username=username,
        secret=secret,
        source=source,
        target_id=target_id,
        service_scope=scope,
        status=status,
        notes=notes,
    )
    t_info = f" ({t_obj.ip})" if t_obj else ""
    console.print(f"[green]✓ Credential saved{t_info}:[/green] [bold]{c.username}[/bold] : ********")
    if copy:
        copy_to_clipboard(c.secret)
        console.print("[dim]→ Copied secret to clipboard[/dim]")


# Alias 'c' for cred
@cli.command("c", hidden=True)
@click.argument("cred_pair")
@click.option("--source", "-s", default="")
@click.option("--target", "-t", default=None)
@click.option("--scope", default="")
@click.option("--status", default="untested")
@click.option("--notes", "-n", default="")
@click.option("--copy", "-c", is_flag=True)
@click.pass_context
def cred_alias(
    ctx: click.Context, cred_pair: str, source: str, target: Optional[str], scope: str, status: str, notes: str, copy: bool
) -> None:
    ctx.invoke(cred_cmd, cred_pair=cred_pair, source=source, target=target, scope=scope, status=status, notes=notes, copy=copy)


# -----------------------------------------------------------------------------
# Checklist Commands
# -----------------------------------------------------------------------------

@cli.group("checklist")
def checklist_group() -> None:
    """Manage manual methodology checklists."""
    pass


@checklist_group.command("add")
@click.argument("title")
@click.option("--category", "-c", default="ENUMERATION", help="Checklist category")
@click.option("--target", "-t", default=None, help="Target IP or ID")
@click.option("--status", default="TODO", help="Status: TODO, CHECKED, DEFERRED, DEAD-END")
@click.option("--notes", "-n", default="", help="Notes on checklist item")
@click.pass_context
def checklist_add_cmd(
    ctx: click.Context,
    title: str,
    category: str,
    target: Optional[str],
    status: str,
    notes: str,
) -> None:
    """Add a manual checklist item."""
    store = _get_store(ctx)
    t_obj = store.resolve_target(target) if target else store.get_active_target()
    target_id = t_obj.id if t_obj else None

    item = store.add_checklist_item(
        title=title,
        category=category,
        target_id=target_id,
        status=status,
        notes=notes,
    )
    console.print(f"[green]✓ Checklist item added:[/green] \\[{escape(item.status.value)}] {escape(item.title)}")


@checklist_group.command("check")
@click.argument("pattern")
@click.option("--target", "-t", default=None, help="Target IP or ID")
@click.pass_context
def checklist_check_cmd(ctx: click.Context, pattern: str, target: Optional[str]) -> None:
    """Mark matching checklist item as CHECKED."""
    store = _get_store(ctx)
    t_obj = store.resolve_target(target) if target else store.get_active_target()
    target_id = t_obj.id if t_obj else None

    items = store.list_checklist_items(target_id=target_id)
    matched = [i for i in items if pattern.lower() in i.title.lower() or str(i.id) == pattern]

    if not matched:
        console.print(f"[yellow]No checklist item matching '{pattern}' found.[/yellow]")
        return

    for item in matched:
        updated = store.update_checklist_status(item.id, ChecklistStatus.CHECKED)
        console.print(f"[green]✓ Checked:[/green] {updated.title}")


@checklist_group.command("template")
@click.argument("name")
@click.option("--target", "-t", default=None, help="Target IP or ID")
@click.pass_context
def checklist_template_cmd(ctx: click.Context, name: str, target: Optional[str]) -> None:
    """Load a static methodology checklist template (linux, windows, web, smb, privesc, pivoting)."""
    store = _get_store(ctx)
    t_obj = store.resolve_target(target) if target else store.get_active_target()
    target_id = t_obj.id if t_obj else None

    try:
        created = apply_template_to_store(store, name, target_id=target_id)
        t_info = f" for {t_obj.ip}" if t_obj else ""
        console.print(f"[green]✓ Applied static template '{name}' ({len(created)} items){t_info}[/green]")
    except ValueError as e:
        err_console.print(f"[red]{e}[/red]")


@checklist_group.command("list")
@click.option("--target", "-t", default=None, help="Target IP or ID")
@click.pass_context
def checklist_list_cmd(ctx: click.Context, target: Optional[str]) -> None:
    """List current checklist items."""
    store = _get_store(ctx)
    t_obj = store.resolve_target(target) if target else store.get_active_target()
    target_id = t_obj.id if t_obj else None

    items = store.list_checklist_items(target_id=target_id)
    if not items:
        console.print("[dim]No checklist items recorded.[/dim]")
        return

    table = Table(title="Methodology Checklist", title_justify="left")
    table.add_column("ID", justify="right", style="dim")
    table.add_column("Status", justify="center")
    table.add_column("Category", style="cyan")
    table.add_column("Item")

    for item in items:
        if item.status == ChecklistStatus.CHECKED:
            st = "[green]✓ CHECKED[/green]"
        elif item.status == ChecklistStatus.DEFERRED:
            st = "[yellow]~ DEFERRED[/yellow]"
        elif item.status == ChecklistStatus.DEAD_END:
            st = "[red]✗ DEAD-END[/red]"
        else:
            st = "[white]□ TODO[/white]"
        table.add_row(str(item.id), st, item.category, item.title)

    console.print(table)


# -----------------------------------------------------------------------------
# Evidence & Leads Commands
# -----------------------------------------------------------------------------

@cli.command("evidence")
@click.argument("path_or_ref")
@click.option("--type", "ev_type", default="screenshot", help="Evidence type (screenshot, file, command_output, flag)")
@click.option("--desc", "-d", default="", help="Description of evidence")
@click.option("--target", "-t", default=None, help="Target IP or ID")
@click.pass_context
def evidence_cmd(ctx: click.Context, path_or_ref: str, ev_type: str, desc: str, target: Optional[str]) -> None:
    """Record an evidence or screenshot reference."""
    store = _get_store(ctx)
    t_obj = store.resolve_target(target) if target else store.get_active_target()
    target_id = t_obj.id if t_obj else None

    ev = store.add_evidence(
        path_or_ref=path_or_ref,
        target_id=target_id,
        evidence_type=ev_type,
        description=desc,
    )
    console.print(f"[green]✓ Evidence recorded:[/green] \\[{escape(ev.evidence_type)}] {escape(ev.path_or_ref)} - {escape(ev.description)}")


@cli.command("lead")
@click.argument("title")
@click.option("--target", "-t", default=None, help="Target IP or ID")
@click.option("--notes", "-n", default="", help="Observations on lead")
@click.pass_context
def lead_cmd(ctx: click.Context, title: str, target: Optional[str], notes: str) -> None:
    """Record an operational lead to explore later."""
    store = _get_store(ctx)
    t_obj = store.resolve_target(target) if target else store.get_active_target()
    target_id = t_obj.id if t_obj else None

    ld = store.add_lead(title=title, target_id=target_id, notes=notes)
    console.print(f"[green]✓ Lead recorded:[/green] {ld.title}")


# -----------------------------------------------------------------------------
# Search Commands
# -----------------------------------------------------------------------------

@cli.command("search")
@click.argument("query")
@click.pass_context
def search_cmd(ctx: click.Context, query: str) -> None:
    """Fast keyword search across all notes, findings, services, creds, and evidence."""
    store = _get_store(ctx)
    matches = search_notebook(store, query)

    if not matches:
        console.print(f"[dim]No matches found for query:[/dim] '{query}'")
        return

    table = Table(title=f"Search Results for '{query}' ({len(matches)} matches)")
    table.add_column("Type", style="cyan", width=12)
    table.add_column("Target", style="magenta", width=16)
    table.add_column("Title", style="bold")
    table.add_column("Details", style="dim")

    for m in matches:
        table.add_row(
            m.entity_type.upper(),
            m.target_ip or "Global",
            m.title,
            m.snippet,
        )

    console.print(table)


# -----------------------------------------------------------------------------
# Export & Import Commands
# -----------------------------------------------------------------------------

@cli.command("export")
@click.option("--format", "-f", "fmt", type=click.Choice(["md", "json", "txt"]), default="md", help="Export format")
@click.option("--output", "-o", type=click.Path(), default=None, help="Save to file (prints to stdout if omitted)")
@click.option("--reveal-creds", is_flag=True, help="Include unmasked passwords in export")
@click.pass_context
def export_cmd(ctx: click.Context, fmt: str, output: Optional[str], reveal_creds: bool) -> None:
    """Export the workspace to standalone Markdown, JSON, or TXT."""
    store = _get_store(ctx)

    if fmt == "md":
        content = export_markdown(store, reveal_creds=reveal_creds)
    elif fmt == "json":
        content = export_json(store)
    else:
        content = export_txt(store)

    if output:
        out_path = Path(output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(content, encoding="utf-8")
        console.print(f"[green]✓ Exported workspace to:[/green] {out_path.resolve()}")
    else:
        sys.stdout.write(content)
        if not content.endswith("\n"):
            sys.stdout.write("\n")


@cli.command("import")
@click.argument("file_path", type=click.Path(exists=True))
@click.option("--name", default=None, help="Target workspace name")
@click.pass_context
def import_cmd(ctx: click.Context, file_path: str, name: Optional[str]) -> None:
    """Import workspace data from a JSON backup file."""
    store = _get_store(ctx)
    content = Path(file_path).read_text(encoding="utf-8")
    ws = import_json(store, content, workspace_name=name)
    console.print(f"[green]✓ Successfully imported workspace:[/green] [bold]{ws.name}[/bold]")


# -----------------------------------------------------------------------------
# Workspace Management
# -----------------------------------------------------------------------------

@cli.group("workspace")
def workspace_group() -> None:
    """Manage assessments and workspaces."""
    pass


@workspace_group.command("list")
@click.pass_context
def ws_list(ctx: click.Context) -> None:
    """List all workspaces."""
    store = _get_store(ctx)
    workspaces = store.list_workspaces()
    active = store.get_active_workspace()

    table = Table(title="Workspaces")
    table.add_column("ID", justify="right", style="dim")
    table.add_column("Active", justify="center")
    table.add_column("Name", style="bold cyan")
    table.add_column("Description")

    for ws in workspaces:
        is_active = "[green]✓[/green]" if ws.id == active.id else ""
        table.add_row(str(ws.id), is_active, ws.name, ws.description)

    console.print(table)


@workspace_group.command("switch")
@click.argument("name_or_id")
@click.pass_context
def ws_switch(ctx: click.Context, name_or_id: str) -> None:
    """Switch active workspace."""
    store = _get_store(ctx)
    ws = store.set_active_workspace(name_or_id)
    console.print(f"[green]✓ Active workspace switched to:[/green] [bold]{ws.name}[/bold]")


@workspace_group.command("create")
@click.argument("name")
@click.option("--desc", default="", help="Workspace description")
@click.pass_context
def ws_create(ctx: click.Context, name: str, desc: str) -> None:
    """Create a new workspace."""
    store = _get_store(ctx)
    ws = store.get_or_create_workspace(name=name, description=desc)
    store.set_active_workspace(ws.id)
    console.print(f"[green]✓ Created and selected workspace:[/green] [bold]{ws.name}[/bold]")


# -----------------------------------------------------------------------------
# Flags, Footholds, PrivEsc & Failure Log (Notion Alignment)
# -----------------------------------------------------------------------------

@cli.command("flag")
@click.argument("flag_type", type=click.Choice(["user", "root", "u", "r"], case_sensitive=False))
@click.argument("value")
@click.option("--target", "-t", default=None, help="Target IP or ID")
@click.pass_context
def flag_cmd(ctx: click.Context, flag_type: str, value: str, target: Optional[str]) -> None:
    """Record a captured user or root flag (e.g. cyb0x-s flag user eJPT{hash})."""
    store = _get_store(ctx)
    t = store.resolve_target(target)
    if not t:
        err_console.print("[red]Error: No target specified and no active target set.[/red]")
        sys.exit(1)
    is_user = flag_type.lower() in ("user", "u")
    if is_user:
        store.update_target_details(t.id, user_flag=value)
        console.print(f"[green]✓ Recorded user flag on {t.ip}:[/green] [bold cyan]{value}[/bold cyan]")
    else:
        store.update_target_details(t.id, root_flag=value)
        console.print(f"[green]✓ Recorded root flag on {t.ip}:[/green] [bold yellow]{value}[/bold yellow]")


@cli.command("foothold")
@click.option("--vuln", default="", help="Vulnerability / CVE exploited")
@click.option("--cmd", default="", help="Exploit command executed")
@click.option("--context", default="", help="User context obtained (e.g. www-data)")
@click.option("--target", "-t", default=None, help="Target IP or ID")
@click.pass_context
def foothold_cmd_cli(ctx: click.Context, vuln: str, cmd: str, context: str, target: Optional[str]) -> None:
    """Record initial foothold exploitation details."""
    store = _get_store(ctx)
    t = store.resolve_target(target)
    if not t:
        err_console.print("[red]Error: No target specified and no active target set.[/red]")
        sys.exit(1)
    store.update_target_details(t.id, initial_access_vuln=vuln, foothold_cmd=cmd, foothold_context=context)
    console.print(f"[green]✓ Recorded initial foothold on {t.ip}[/green]")


@cli.command("privesc")
@click.option("--vector", default="", help="Privilege escalation vector")
@click.option("--proof", default="", help="Root proof command (e.g. whoami && id && ip a)")
@click.option("--target", "-t", default=None, help="Target IP or ID")
@click.pass_context
def privesc_cmd_cli(ctx: click.Context, vector: str, proof: str, target: Optional[str]) -> None:
    """Record privilege escalation details and root proof."""
    store = _get_store(ctx)
    t = store.resolve_target(target)
    if not t:
        err_console.print("[red]Error: No target specified and no active target set.[/red]")
        sys.exit(1)
    store.update_target_details(t.id, privesc_vector=vector, root_proof=proof)
    console.print(f"[green]✓ Recorded privilege escalation on {t.ip}[/green]")


@cli.command("stuck")
@click.option("--stuck", "where_stuck", default="", help="Where did you get stuck / false path?")
@click.option("--clue", "breakthrough_clue", default="", help="What clue or finding unlocked the box?")
@click.option("--rule", "rule_for_next_time", default="", help="Permanent takeaway / rule for next time")
@click.option("--target", "-t", default=None, help="Target IP or ID")
@click.pass_context
def failure_cmd_cli(
    ctx: click.Context,
    where_stuck: str,
    breakthrough_clue: str,
    rule_for_next_time: str,
    target: Optional[str],
) -> None:
    """Record breakthrough and rabbit hole analysis (Failure Log)."""
    store = _get_store(ctx)
    t = store.resolve_target(target)
    t_id = t.id if t else None
    store.add_failure_log(
        target_id=t_id,
        where_stuck=where_stuck,
        breakthrough_clue=breakthrough_clue,
        rule_for_next_time=rule_for_next_time,
    )
    console.print("[green]✓ Recorded breakthrough & rabbit hole analysis entry[/green]")


# -----------------------------------------------------------------------------
# Interactive TUI launcher
# -----------------------------------------------------------------------------

@cli.command("tui")
@click.pass_context
def tui_cmd(ctx: click.Context) -> None:
    """Launch the interactive terminal user interface."""
    from cyb0x_s.tui.app import CyboxSafeApp

    store = _get_store(ctx)
    app = CyboxSafeApp(store=store)
    app.run()


def main() -> None:
    cli(obj={})


if __name__ == "__main__":
    main()
