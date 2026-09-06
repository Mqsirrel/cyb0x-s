"""Command Line Interface for CYB0X-S (Safe Field Notebook).

Provides ultra-fast capture commands to record findings and discoveries in seconds.
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

from cyb0x_s.clipboard import copy_to_clipboard
from cyb0x_s.db.store import NotebookStore
from cyb0x_s.export import export_json, export_markdown, export_txt, import_json
from cyb0x_s.extractor import CandidateType, extract_candidates, stage_and_commit_candidate
from cyb0x_s.models import ChecklistStatus
from cyb0x_s.routes import build_network_topology, generate_proxychains_config, resolve_pivot_route
from cyb0x_s.scan_import import check_scan_already_imported, commit_scan_results, inspect_scan_file
from cyb0x_s.search import search_notebook
from cyb0x_s.templates import apply_template_to_store

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
@click.option("--theme", "-t", "theme_name", default=None, help="Color palette (slate, midnight, ember, cyber, sugary, candy, caramel).")
@click.pass_context
def cli(ctx: click.Context, db_path: Optional[str], workspace_name: Optional[str], theme_name: Optional[str] = None) -> None:
    """CYB0X-S — Conservative, passive, human-controlled field notebook."""
    ctx.ensure_object(dict)
    ctx.obj["db_path"] = db_path
    ctx.obj["theme_name"] = theme_name

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
    """Record a discovered credential (e.g. admin:password)."""
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
@click.option("--replace", "-r", is_flag=True, default=False, help="Replace existing checklist items instead of appending")
@click.pass_context
def checklist_template_cmd(ctx: click.Context, name: str, target: Optional[str], replace: bool = False) -> None:
    """Load a static methodology checklist template (ejpt, web, smb, pivoting, privesc)."""
    store = _get_store(ctx)
    t_obj = store.resolve_target(target) if target else store.get_active_target()
    target_id = t_obj.id if t_obj else None

    try:
        created = apply_template_to_store(store, name, target_id=target_id, replace=replace)
        t_info = f" for {t_obj.ip}" if t_obj else ""
        verb = "Switched to" if replace else "Applied"
        console.print(f"[green]✓ {verb} static template '{name}' ({len(created)} items){t_info}[/green]")
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


@cli.command("restore")
@click.argument("file_path", type=click.Path(exists=True))
@click.option("--name", default=None, help="Target workspace name")
@click.pass_context
def restore_cmd(ctx: click.Context, file_path: str, name: Optional[str]) -> None:
    """Restore workspace data from a JSON backup file."""
    store = _get_store(ctx)
    content = Path(file_path).read_text(encoding="utf-8")
    ws = import_json(store, content, workspace_name=name)
    console.print(f"[green]✓ Successfully imported workspace:[/green] [bold]{ws.name}[/bold]")


# -----------------------------------------------------------------------------
# Workspace Management
# -----------------------------------------------------------------------------

@cli.command("init")
@click.argument("directory", default=".", type=click.Path())
@click.option("--name", "-n", default=None, help="Workspace name (defaults to folder name)")
@click.option("--desc", "-d", default="", help="Workspace description")
@click.pass_context
def init_cmd(ctx: click.Context, directory: str, name: Optional[str], desc: str) -> None:
    """Initialize a dedicated assessment workspace directory with scaffolded folders."""
    store = _get_store(ctx)
    target_path = Path(directory).expanduser().resolve()
    ws_name = name.strip() if name else target_path.name
    if not ws_name or ws_name in (".", "/"):
        ws_name = "assessment"

    ws, resolved_path = store.init_workspace_directory(
        name=ws_name,
        target_dir=target_path,
        description=desc,
    )
    console.print(f"[green]✓ Workspace initialized & selected:[/green] [bold]{ws.name}[/bold]")
    console.print(f"  [dim]Location:[/dim] {resolved_path}")
    console.print("  [dim]Folders created:[/dim] scans/ enum/ screenshots/ notes/ loot/")
    console.print("  [dim]Scaffolded report:[/dim] findings.md")


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
    table.add_column("Root Path")
    table.add_column("Description")

    for ws in workspaces:
        is_active = "[green]✓[/green]" if ws.id == active.id else ""
        root = ws.root_path or "[dim]--[/dim]"
        table.add_row(str(ws.id), is_active, ws.name, root, ws.description)

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
@click.option("--path", "root_path", default="", help="Filesystem root path for workspace artifacts")
@click.pass_context
def ws_create(ctx: click.Context, name: str, desc: str, root_path: str) -> None:
    """Create a new workspace."""
    store = _get_store(ctx)
    ws = store.get_or_create_workspace(name=name, description=desc, root_path=root_path)
    store.set_active_workspace(ws.id)
    console.print(f"[green]✓ Created and selected workspace:[/green] [bold]{ws.name}[/bold]")
    if root_path:
        console.print(f"  [dim]Root Path:[/dim] {root_path}")


@workspace_group.command("init")
@click.argument("name")
@click.option("--path", "target_path", default=None, help="Directory path to scaffold (defaults to ./<name>)")
@click.option("--desc", default="", help="Workspace description")
@click.pass_context
def ws_init(ctx: click.Context, name: str, target_path: Optional[str], desc: str) -> None:
    """Initialize folder scaffolding for a new assessment workspace."""
    store = _get_store(ctx)
    dest = Path(target_path).expanduser().resolve() if target_path else Path.cwd() / name
    ws, resolved = store.init_workspace_directory(name=name, target_dir=dest, description=desc)
    console.print(f"[green]✓ Initialized workspace:[/green] [bold]{ws.name}[/bold]")
    console.print(f"  [dim]Directory:[/dim] {resolved}")
    console.print("  [dim]Scaffolding:[/dim] scans/ enum/ screenshots/ notes/ loot/ findings.md")


# -----------------------------------------------------------------------------
# Scan Ingestion & Evidence Attachment
# -----------------------------------------------------------------------------

@cli.command("import")
@click.argument("scan_file", type=click.Path(exists=True))
@click.option("--apply", is_flag=True, help="Skip interactive review and apply immediately.")
@click.option("--no-copy", is_flag=True, help="Do not copy the file into workspace scans/ directory.")
@click.option("--workspace", "-w", "workspace_name", default=None, help="Target workspace (defaults to active).")
@click.pass_context
def import_cmd(ctx: click.Context, scan_file: str, apply: bool, no_copy: bool, workspace_name: Optional[str]) -> None:
    """Import and parse an offline Nmap/scan output file into the workspace.

    Parses Nmap XML (-oX), normal text (-oN), greppable (-oG), or NetExec outputs.
    Preserves raw scan file in scans/ as evidence and presents a human review step.
    """
    store = _get_store(ctx)
    ws = store.get_active_workspace()
    if workspace_name:
        ws = store.get_or_create_workspace(name=workspace_name)

    file_path = Path(scan_file).expanduser().resolve()

    # Deduplication check
    existing = check_scan_already_imported(store, file_path, workspace_id=ws.id)
    if existing:
        console.print(f"[yellow]⚠️ Warning: This file was already imported on {existing.imported_at}[/yellow]")
        console.print(f"  [dim]Previous import ref:[/dim] {existing.file_path}")
        if not apply:
            if not click.confirm("Do you want to re-parse and update the targets?", default=False):
                console.print("[dim]Import cancelled.[/dim]")
                return

    try:
        targets_data = inspect_scan_file(file_path)
    except Exception as e:
        err_console.print(f"[red]Error parsing scan file: {e}[/red]")
        sys.exit(1)

    if not targets_data:
        console.print("[yellow]No active targets or open ports found in scan file.[/yellow]")
        return

    # Present review table
    table = Table(title=f"Scan Review: {file_path.name} (Workspace: {ws.name})")
    table.add_column("Target IP", style="bold cyan")
    table.add_column("Hostname", style="dim")
    table.add_column("OS")
    table.add_column("Port / Proto", justify="center")
    table.add_column("Service", style="green")
    table.add_column("Version", style="yellow")

    total_services = 0
    for t in targets_data:
        svcs = t.get("services", [])
        total_services += len(svcs)
        if not svcs:
            table.add_row(t["ip"], t.get("hostname", ""), t.get("os", "Unknown"), "--", "--", "--")
        else:
            for i, s in enumerate(svcs):
                ip_col = t["ip"] if i == 0 else ""
                hn_col = t.get("hostname", "") if i == 0 else ""
                os_col = t.get("os", "Unknown") if i == 0 else ""
                port_proto = f"{s['port']}/{s.get('protocol', 'tcp')}"
                table.add_row(ip_col, hn_col, os_col, port_proto, s.get("service", "unknown"), s.get("version", ""))

    console.print(table)
    console.print(f"[dim]Found {len(targets_data)} target(s) and {total_services} open service(s).[/dim]\n")

    if not apply:
        if not click.confirm(f"Commit these targets and services into '{ws.name}' and save raw scan as Evidence?", default=True):
            console.print("[yellow]Import aborted by operator.[/yellow]")
            return

    summary = commit_scan_results(
        store=store,
        file_path=file_path,
        targets_data=targets_data,
        workspace_id=ws.id,
        copy_to_scans=not no_copy,
    )

    console.print(f"\n[bold green]✓ Scan imported successfully into '{ws.name}'![/bold green]")
    console.print(f"  • Targets committed: [bold]{summary['targets_count']}[/bold]")
    console.print(f"  • Services committed: [bold]{summary['services_count']}[/bold]")
    console.print(f"  • Evidence preserved: [bold]{summary['evidence_path']}[/bold]")
    console.print(f"  • SHA-256 Checksum: [dim]{summary['file_hash'][:16]}...[/dim]")


# -----------------------------------------------------------------------------
# Flags, Footholds, PrivEsc & Failure Log (Notion Alignment)
# -----------------------------------------------------------------------------

@cli.command("flag")
@click.argument("flag_type", type=click.Choice(["user", "root", "u", "r"], case_sensitive=False))
@click.argument("value")
@click.option("--target", "-t", default=None, help="Target IP or ID")
@click.pass_context
def flag_cmd(ctx: click.Context, flag_type: str, value: str, target: Optional[str]) -> None:
    """Record a captured user or root flag (e.g. cyb0x-s flag user <flag_value>)."""
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
@click.argument("cmd_arg", required=False, default="")
@click.option("--vuln", default="", help="Vulnerability / CVE exploited")
@click.option("--cmd", default="", help="Exploit command executed")
@click.option("--context", default="", help="User context obtained (e.g. www-data)")
@click.option("--target", "-t", default=None, help="Target IP or ID")
@click.pass_context
def foothold_cmd_cli(ctx: click.Context, cmd_arg: str, vuln: str, cmd: str, context: str, target: Optional[str]) -> None:
    """Record initial foothold exploitation details."""
    store = _get_store(ctx)
    t = store.resolve_target(target)
    if not t:
        err_console.print("[red]Error: No target specified and no active target set.[/red]")
        sys.exit(1)
    actual_cmd = cmd or cmd_arg
    store.update_target_details(t.id, initial_access_vuln=vuln, foothold_cmd=actual_cmd, foothold_context=context)
    console.print(f"[green]✓ Recorded initial foothold on {t.ip}[/green]")


@cli.command("privesc")
@click.argument("vector_arg", required=False, default="")
@click.option("--vector", default="", help="Privilege escalation vector")
@click.option("--proof", default="", help="Root proof command (e.g. whoami && id && ip a)")
@click.option("--target", "-t", default=None, help="Target IP or ID")
@click.pass_context
def privesc_cmd_cli(ctx: click.Context, vector_arg: str, vector: str, proof: str, target: Optional[str]) -> None:
    """Record privilege escalation details and root proof."""
    store = _get_store(ctx)
    t = store.resolve_target(target)
    if not t:
        err_console.print("[red]Error: No target specified and no active target set.[/red]")
        sys.exit(1)
    actual_vector = vector or vector_arg
    store.update_target_details(t.id, privesc_vector=actual_vector, root_proof=proof)
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
# Offline Cheat Sheet & Playbook Lookup
# -----------------------------------------------------------------------------

@cli.command("ref")
@click.argument("query", default="")
@click.option("--target", "-t", default=None, help="Target IP for dynamic syntax substitution")
@click.option("--copy", "-c", is_flag=True, help="Copy first matching command to clipboard")
@click.pass_context
def ref_cmd(ctx: click.Context, query: str, target: Optional[str], copy: bool) -> None:
    """Search offline assessment cheat sheet and command references (e.g. cyb0x-s ref winrm)."""
    from cyb0x_s.reference import search_reference

    store = _get_store(ctx)
    t = store.resolve_target(target)
    target_ip = t.ip if t else (target or "")

    results = search_reference(query, target_ip=target_ip)
    if not results:
        console.print(f"[yellow]No reference commands found matching '{query}'. Try 'smb', 'winrm', 'sql', 'privesc'...[/yellow]")
        return

    console.print(f"[bold cyan]─── Assessment Reference Playbook: '{query}' ───[/bold cyan]\n" if query else "[bold cyan]─── Assessment Reference Playbook ───[/bold cyan]\n")

    for item in results:
        console.print(f"[bold magenta][{item['category']}][/bold magenta] [bold white]{item['title']}[/bold white]")
        console.print(f"  [bold yellow]❯ {item['command']}[/bold yellow]")
        console.print(f"  [dim]ℹ {item['desc']}[/dim]\n")

    if copy and results:
        first_cmd = results[0]["command"]
        copy_to_clipboard(first_cmd)
        console.print(f"[dim]→ Copied top command to clipboard: {first_cmd}[/dim]")


@cli.command("cheat", hidden=True)
@click.argument("query", default="")
@click.option("--target", "-t", default=None)
@click.option("--copy", "-c", is_flag=True)
@click.pass_context
def cheat_alias(ctx: click.Context, query: str, target: Optional[str], copy: bool) -> None:
    ctx.invoke(ref_cmd, query=query, target=target, copy=copy)


# -----------------------------------------------------------------------------
# Exam & Integrity Workflow Commands
# -----------------------------------------------------------------------------

ANSI_ESCAPE_RE = re.compile(
    r"(?:\x1B[@-Z\\-_]|[\x80-\x9A\x9C-\x9F]|(?:\x1B\[|\x9B)[0-?]*[ -/]*[@-~])"
)


@cli.command("audit")
@click.argument("target", required=False, default=None)
@click.option("--all", "audit_all", is_flag=True, help="Audit all targets in the active workspace")
@click.pass_context
def audit_cmd(ctx: click.Context, target: Optional[str], audit_all: bool) -> None:
    """Pre-reset integrity audit gate to verify proof before reverting a VM."""
    store = _get_store(ctx)

    targets_to_audit = []
    if audit_all:
        ws = store.get_active_workspace()
        targets_to_audit = store.list_targets(workspace_id=ws.id) if ws else []
        if not targets_to_audit:
            console.print("[yellow]No targets recorded in current workspace.[/yellow]")
            return
    else:
        t_obj = store.resolve_target(target) if target else store.get_active_target()
        if not t_obj:
            err_console.print("[red]Error: No target specified and no active target set. Try 'cyb0x-s audit <IP>' or '--all'.[/red]")
            sys.exit(1)
        targets_to_audit = [t_obj]

    for t in targets_to_audit:
        res = store.audit_target(t.id)
        if "error" in res:
            console.print(f"[red]{res['error']}[/red]")
            continue

        table = Table(
            title=f"Pre-Reset Integrity Audit — {t.ip} ({t.hostname or 'no-host'}) [{t.os}]",
            show_header=True,
            header_style="bold cyan",
        )
        table.add_column("Requirement / Check", style="bold white", width=28)
        table.add_column("Status", width=14, justify="center")
        table.add_column("Recorded Evidence / Proof Details", style="dim")

        for c in res["checks"]:
            if c["passed"]:
                status = "[green]✓ PASS[/green]"
            elif c["critical"]:
                status = "[bold red]✗ FAIL[/bold red]"
            else:
                status = "[yellow]○ OPTIONAL[/yellow]"
            table.add_row(c["name"], status, escape(str(c["detail"])))

        console.print(table)
        score_str = f"Score: {res['score']}"
        if res["ready_to_revert"]:
            console.print(f"[bold green]✓ {res['verdict']} ({score_str})[/bold green]\n")
        else:
            console.print(f"[bold red]⚠️  {res['verdict']} ({score_str})[/bold red]\n")


@cli.command("route")
@click.argument("destination", required=False, default=None)
@click.option("--proxychains", is_flag=True, help="Output proxychains4.conf configuration block")
@click.option("--mermaid", is_flag=True, help="Output Mermaid diagram syntax")
@click.pass_context
def route_cmd(ctx: click.Context, destination: Optional[str], proxychains: bool, mermaid: bool) -> None:
    """Passive multi-hop pivot routing and network topology graph.

    Calculates multi-hop routing paths, ProxyChains SOCKS configs,
    Chisel commands, and SSH jump tunnels based on operator-documented pivots.
    """
    store = _get_store(ctx)
    topo = build_network_topology(store)

    if proxychains:
        conf = generate_proxychains_config(topo)
        console.print(conf)
        return

    if mermaid:
        console.print(topo.mermaid_diagram)
        return

    if destination:
        target_obj = store.resolve_target(destination)
        dest_ip = target_obj.ip if target_obj else destination
        route = resolve_pivot_route(store, dest_ip)

        console.print(f"\n[bold cyan]Pivot Route to Destination:[/bold cyan] [bold white]{route.destination}[/bold white] (Subnet: {route.destination_subnet})")
        console.print(f"Hop Count: [bold]{route.hop_count}[/bold] ({'Direct Access' if route.is_direct else 'Multi-Hop Pivot Chain'})\n")

        console.print("[bold yellow]Visual Route Path:[/bold yellow]")
        console.print(f"  {route.ascii_diagram}\n")

        if route.hops:
            table = Table(title=f"Multi-Hop SOCKS Chain ({route.destination})")
            table.add_column("Hop #", style="cyan", width=8)
            table.add_column("Pivot Gateway", style="bold white", width=18)
            table.add_column("SOCKS Proxy", style="yellow", width=20)
            table.add_column("Destination Subnet", style="dim", width=20)
            table.add_column("Routing Notes", style="green")

            for h in route.hops:
                table.add_row(
                    str(h.hop_num),
                    f"{h.pivot_ip} ({h.pivot_hostname or 'host'})",
                    f"{h.proxy_type} {h.proxy_host}:{h.proxy_port}",
                    h.dest_subnet,
                    h.notes,
                )
            console.print(table)

            console.print("\n[bold cyan]Operator Helper Commands:[/bold cyan]")
            console.print(f"  [bold]ProxyChains:[/bold] [yellow]proxychains -q nmap -sT -Pn -p- {route.destination}[/yellow]")
            if route.ssh_jump_cmd:
                console.print(f"  [bold]SSH ProxyJump:[/bold] [yellow]{route.ssh_jump_cmd}[/yellow]")
            if route.chisel_client_cmd:
                console.print(f"  [bold]Chisel Client:[/bold] [yellow]{route.chisel_client_cmd}[/yellow]")
                console.print(f"  [bold]Chisel Server:[/bold] [yellow]{route.chisel_server_cmd}[/yellow]")
            console.print("")
        else:
            console.print("[green]Target is directly reachable on current network segment. No SOCKS proxy required.[/green]\n")
    else:
        # Show full topology
        console.print(f"\n[bold cyan]Network Topology Map:[/bold cyan] [bold]{topo.workspace_name}[/bold]")
        console.print(topo.ascii_map)

        if topo.pivots:
            p_table = Table(title="Documented Pivot Gateways")
            p_table.add_column("Pivot Host", style="bold white", width=18)
            p_table.add_column("Subnet", style="cyan", width=18)
            p_table.add_column("Assigned SOCKS Port", style="yellow", width=20)
            p_table.add_column("Pivot Route", style="dim")

            for p in topo.pivots:
                p_table.add_row(
                    f"{p['ip']} ({p.get('hostname') or 'host'})",
                    p["subnet"],
                    f"127.0.0.1:{p.get('port', 1080)}",
                    p["pivot_route"] or "Dual-homed gateway",
                )
            console.print(p_table)
            console.print("[dim yellow]Run 'cyb0x-s route <IP>' to calculate route hops to any host.[/dim yellow]\n")
            console.print("[dim]Use '--proxychains' to generate proxychains4.conf or '--mermaid' for diagrams.[/dim]\n")
        else:
            console.print("\n[dim]No pivot gateways documented yet. Document a pivot on a target with: :pivot <route> (e.g. :pivot 192.168.1.0/24 via socks5:1080)[/dim]\n")


@cli.command("extract")
@click.argument("file_path", required=False, default=None)
@click.option("--target", "-t", default=None, help="Default target IP to associate extracted artifacts with")
@click.option("--apply", "-a", is_flag=True, help="Confirm and commit all staged candidates into notebook")
@click.option("--interactive", "-i", is_flag=True, help="Interactively confirm or reject each staged candidate")
@click.pass_context
def extract_cmd(
    ctx: click.Context,
    file_path: Optional[str],
    target: Optional[str],
    apply: bool,
    interactive: bool,
) -> None:
    """Constrained log extractor (stages candidate targets, ports, creds, hashes, and flags).

    Scans terminal logs, tool outputs, or scan dumps.
    Never auto-populates directly: stages candidates for operator review.
    """
    store = _get_store(ctx)

    if file_path == "-" or (not file_path and not sys.stdin.isatty()):
        raw_text = sys.stdin.read()
    elif file_path:
        p = Path(file_path)
        if not p.exists():
            console.print(f"[bold red]Error:[/bold red] File not found: {file_path}")
            return
        raw_text = p.read_text(encoding="utf-8", errors="replace")
    else:
        console.print("[yellow]Usage: cyb0x-s extract <log_file> (or pipe command output via 'cat log.txt | cyb0x-s extract -')[/yellow]")
        return

    candidates = extract_candidates(raw_text, default_target_ip=target)
    if not candidates:
        console.print("[dim]No candidate targets, services, credentials, hashes, or flags detected in log.[/dim]")
        return

    console.print(f"\n[bold cyan]Detected Candidates ({len(candidates)} staged for review):[/bold cyan]")
    table = Table(title="Staged Artifact Candidates (Pending Operator Confirmation)")
    table.add_column("ID", style="cyan", width=5)
    table.add_column("Type", style="bold", width=12)
    table.add_column("Summary", style="bold white", width=36)
    table.add_column("Associated Target", style="magenta", width=18)
    table.add_column("Raw Match Context", style="dim")

    for c in candidates:
        type_style = {
            CandidateType.TARGET: "blue",
            CandidateType.SERVICE: "cyan",
            CandidateType.CREDENTIAL: "green",
            CandidateType.HASH: "yellow",
            CandidateType.FLAG: "bold magenta",
        }.get(c.candidate_type, "white")

        table.add_row(
            str(c.candidate_id),
            f"[{type_style}]{c.candidate_type.value}[/{type_style}]",
            c.summary,
            c.target_ip or "[dim]Global / None[/dim]",
            c.context_line[:50],
        )

    console.print(table)

    if apply:
        console.print("\n[bold green]Committing all candidates into workspace database...[/bold green]")
        committed = 0
        for c in candidates:
            success, msg = stage_and_commit_candidate(c, store)
            if success:
                committed += 1
                console.print(f"  [green]✓ {msg}[/green]")
            else:
                console.print(f"  [dim]• Skipped: {msg}[/dim]")
        console.print(f"\n[bold green]Done! {committed}/{len(candidates)} candidates committed to notebook.[/bold green]\n")

    elif interactive:
        console.print("\n[bold yellow]Interactive Candidate Confirmation Mode:[/bold yellow]")
        committed = 0
        accept_all = False
        for c in candidates:
            if not accept_all:
                resp = click.prompt(
                    f"Add candidate [{c.candidate_id}] {c.candidate_type.value} ({c.summary})? [y/N/all/q]",
                    default="n",
                ).strip().lower()

                if resp == "q":
                    console.print("[yellow]Aborted candidate import.[/yellow]")
                    break
                elif resp == "all":
                    accept_all = True
                elif resp not in ("y", "yes"):
                    console.print(f"[dim]Skipped candidate {c.candidate_id}.[/dim]")
                    continue

            success, msg = stage_and_commit_candidate(c, store)
            if success:
                committed += 1
                console.print(f"  [green]✓ {msg}[/green]")
            else:
                console.print(f"  [dim]• Skipped: {msg}[/dim]")
        console.print(f"\n[bold green]Done! {committed}/{len(candidates)} candidates committed to notebook.[/bold green]\n")

    else:
        console.print("\n[dim yellow]Candidates are staged in memory. No changes written to database.[/dim yellow]")
        console.print("[dim]Run with [bold]--apply[/bold] to commit all, or [bold]--interactive[/bold] to review one-by-one.[/dim]\n")


@cli.command("proof-cmd")
@click.option("--os", "os_name", type=click.Choice(["linux", "windows"], case_sensitive=False), default=None, help="Target operating system")
@click.option("--target", "-t", default=None, help="Target IP to auto-detect OS")
@click.option("--flag-path", default="", help="Custom flag path to append")
@click.option("--copy/--no-copy", default=True, help="Copy one-liner to clipboard (default: enabled)")
@click.pass_context
def proof_cmd_cli(ctx: click.Context, os_name: Optional[str], target: Optional[str], flag_path: str, copy: bool) -> None:
    """Generate and copy standard composite proof command (whoami, id, hostname, ip, flag)."""
    store = _get_store(ctx)

    detected_os = os_name
    if not detected_os:
        t_obj = store.resolve_target(target) if target else store.get_active_target()
        if t_obj and t_obj.os and t_obj.os.lower() != "unknown":
            if "win" in t_obj.os.lower():
                detected_os = "windows"
            else:
                detected_os = "linux"
        else:
            detected_os = "linux"

    if detected_os.lower() == "windows":
        flag_snippet = f"type {flag_path} 2>nul" if flag_path else "type proof.txt 2>nul || type C:\\Users\\Administrator\\Desktop\\proof.txt 2>nul"
        compound_cmd = f"whoami /priv && whoami && hostname && ipconfig && ({flag_snippet})"
        title = "Windows Composite Proof One-Liner (OffSec / INE Compliant)"
    else:
        flag_snippet = f"cat {flag_path} 2>/dev/null" if flag_path else "cat /root/proof.txt 2>/dev/null || cat proof.txt 2>/dev/null || cat /home/*/user.txt 2>/dev/null"
        compound_cmd = f"id && whoami && hostname && ip a && ({flag_snippet})"
        title = "Linux Composite Proof One-Liner (OffSec / INE Compliant)"

    console.print(f"[bold cyan]─── {title} ───[/bold cyan]")
    console.print(f"[bold yellow]{compound_cmd}[/bold yellow]")
    if copy:
        copy_to_clipboard(compound_cmd)
        console.print("[dim]→ Copied one-liner to clipboard[/dim]")


@cli.command("cmd")
@click.argument("command_text", required=False, default="")
@click.option("--golden", "-g", is_flag=True, help="Mark as verified breakthrough/reproduction step")
@click.option("--step", "-s", default="", help="Step label: foothold, privesc, pivot, enum, loot")
@click.option("--notes", "-n", default="", help="Notes on command outcome")
@click.option("--target", "-t", default=None, help="Target IP or ID")
@click.option("--list", "-l", "list_mode", is_flag=True, help="List command history")
@click.option("--golden-only", is_flag=True, help="List only golden breakthrough commands")
@click.pass_context
def cmd_cli(
    ctx: click.Context,
    command_text: str,
    golden: bool,
    step: str,
    notes: str,
    target: Optional[str],
    list_mode: bool,
    golden_only: bool,
) -> None:
    """Record or review commands in the command audit trail and Golden Replication Chain."""
    store = _get_store(ctx)
    t_obj = store.resolve_target(target) if target else store.get_active_target()
    t_id = t_obj.id if t_obj else None

    if list_mode:
        cmds = store.list_commands(target_id=t_id, limit=50, golden_only=golden_only)
        if not cmds:
            filter_str = " (golden only)" if golden_only else ""
            t_str = f" for {t_obj.ip}" if t_obj else ""
            console.print(f"[yellow]No commands recorded{filter_str}{t_str}.[/yellow]")
            return

        table = Table(
            title="Command History & Golden Replication Chain" if not golden_only else "🏆 Golden Reproduction Chain",
            show_header=True,
            header_style="bold cyan",
        )
        table.add_column("Type", width=12)
        table.add_column("Step", width=12)
        table.add_column("Command", style="bold yellow")
        table.add_column("Notes", style="dim")

        for c in cmds:
            type_badge = "[bold gold1]★ GOLDEN[/bold gold1]" if c.is_golden else "[dim]NORMAL[/dim]"
            step_badge = f"[cyan]{c.step}[/cyan]" if c.step else "-"
            table.add_row(type_badge, step_badge, escape(c.command), escape(c.notes))

        console.print(table)
        return

    if not command_text:
        err_console.print("[red]Usage: cyb0x-s cmd <COMMAND> [--golden] [--step <STEP>] [--notes <NOTES>] or --list[/red]")
        sys.exit(1)

    rec = store.add_command(
        command=command_text,
        target_id=t_id,
        notes=notes,
        is_golden=golden,
        step=step,
    )
    t_info = f" (Target: {t_obj.ip})" if t_obj else " (Global)"
    badge = " [bold gold1]★ GOLDEN REPRODUCTION STEP[/bold gold1]" if golden else ""
    step_info = f" [{step.upper()}]" if step else ""
    console.print(f"[green]✓ Recorded command{t_info}{badge}{step_info}:[/green] {rec.command}")


@cli.command("clean")
@click.argument("file_path", type=click.Path(exists=True), required=False, default=None)
@click.option("--copy", "-c", is_flag=True, help="Copy sanitized output to clipboard")
@click.pass_context
def clean_cmd(ctx: click.Context, file_path: Optional[str], copy: bool) -> None:
    """Sanitize raw terminal output by stripping ANSI color codes and control sequences."""
    if file_path:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            raw_text = f.read()
    else:
        if sys.stdin.isatty():
            err_console.print("[yellow]Reading from stdin... (Paste text and press Ctrl+D, or pipe via 'cat file | cyb0x-s clean')[/yellow]")
        raw_text = sys.stdin.read()

    # Strip ANSI escapes and carriage returns
    clean_text = ANSI_ESCAPE_RE.sub("", raw_text).replace("\r\n", "\n").replace("\r", "\n")

    # Output to stdout directly
    click.echo(clean_text, nl=False)

    if copy:
        copy_to_clipboard(clean_text)
        err_console.print("\n[dim]→ Copied sanitized text to clipboard[/dim]")


# -----------------------------------------------------------------------------
# Interactive TUI launcher
# -----------------------------------------------------------------------------

@cli.command("tui")
@click.option("--theme", "-t", "theme_name", default=None, help="Color palette (slate, midnight, ember, cyber, sugary, candy, caramel).")
@click.pass_context
def tui_cmd(ctx: click.Context, theme_name: Optional[str] = None) -> None:
    """Launch the interactive terminal user interface."""
    from cyb0x_s.tui.app import CyboxSafeApp

    store = _get_store(ctx)
    selected_theme = theme_name or ctx.obj.get("theme_name")
    app = CyboxSafeApp(store=store, theme=selected_theme)
    app.run()


def main() -> None:
    cli(obj={})


if __name__ == "__main__":
    main()
