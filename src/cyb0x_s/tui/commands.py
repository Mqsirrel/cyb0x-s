"""Fast capture and terminal command dispatching for CYB0X-S TUI."""

from __future__ import annotations

from typing import Any, Optional

from textual.widgets import ListView

from cyb0x_s.clipboard import copy_to_clipboard
from cyb0x_s.templates import apply_template_to_store
from cyb0x_s.tui.modals import ReferenceModal

WORDLIST_ALIASES: dict[str, str] = {
    "rockyou": "/usr/share/wordlists/rockyou.txt",
    "common": "/usr/share/wordlists/dirb/common.txt",
    "c": "/usr/share/wordlists/dirb/common.txt",
    "medium": "/usr/share/wordlists/dirbuster/directory-list-2.3-medium.txt",
    "m": "/usr/share/wordlists/dirbuster/directory-list-2.3-medium.txt",
    "big": "/usr/share/wordlists/dirb/big.txt",
    "small": "/usr/share/wordlists/dirb/small.txt",
    "raft-d": "/usr/share/seclists/Discovery/Web-Content/raft-medium-directories.txt",
    "raft-f": "/usr/share/seclists/Discovery/Web-Content/raft-medium-files.txt",
    "users": "/usr/share/seclists/Usernames/top-usernames-shortlist.txt",
    "passwords": "/usr/share/seclists/Passwords/Common-Credentials/top-20-common-passwords.txt",
    "fasttrack": "/usr/share/wordlists/fasttrack.txt",
}


def normalize_command(raw: str) -> str:
    """Normalize human-friendly shorthand and natural language into canonical commands."""
    val = raw.strip()
    if not val:
        return ""

    if val.startswith("add target ") or val.startswith("target "):
        raw_val = val.replace("add target ", "", 1).replace("target ", "", 1).strip()
        return f":t {raw_val}"
    elif val.startswith("add service ") or val.startswith("service "):
        raw_val = val.replace("add service ", "", 1).replace("service ", "", 1).strip()
        return f":s {raw_val}"
    elif val.startswith("add cred ") or val.startswith("cred "):
        raw_val = val.replace("add cred ", "", 1).replace("cred ", "", 1).strip()
        return f":c {raw_val}"
    elif val.startswith("add note ") or val.startswith("note "):
        raw_val = val.replace("add note ", "", 1).replace("note ", "", 1).strip()
        return f":n {raw_val}"
    elif val.startswith("add finding ") or val.startswith("finding "):
        raw_val = val.replace("add finding ", "", 1).replace("finding ", "", 1).strip()
        return f":f {raw_val}"
    elif val.startswith("wordlist ") or val.startswith(":w "):
        raw_val = val.replace("wordlist ", "", 1).replace(":w ", "", 1).strip()
        return f":w {raw_val}"
    elif val in ("wordlist", ":w"):
        return ":w"
    elif val.startswith("theme ") or val.startswith("palette "):
        raw_val = val.replace("theme ", "", 1).replace("palette ", "", 1).strip()
        return f":theme {raw_val}"
    elif val in ("theme", "palette"):
        return ":theme"
    return val


def execute_command(app: Any, raw: str) -> None:
    """Execute a command entered via the console / command bar."""
    val = normalize_command(raw)
    if not val:
        return

    # Direct Help triggers
    if val in ("?", "help", ":help", ":?"):
        if hasattr(app, "action_show_help"):
            app.action_show_help()
        elif hasattr(app, "action_help"):
            app.action_help()
        return

    if val in ("quit", "exit"):
        if hasattr(app, "action_quit_app"):
            app.action_quit_app()
        else:
            app.exit()
        return

    # Tab switching via command: :1, :2, :3, :4
    if val == ":1":
        app.action_switch_tab("tab-worksheet")
        return
    elif val == ":2":
        app.action_switch_tab("tab-playbooks")
        return
    elif val == ":3":
        app.action_switch_tab("tab-creds")
        return
    elif val == ":4":
        app.action_switch_tab("tab-loot")
        return

    active = app.store.get_active_target()
    target_id = active.id if active else None

    if val.startswith(":uflag ") or val.startswith(":flag user "):
        uflag = val.split(maxsplit=1)[1].replace("user ", "").strip()
        if active:
            app.store.update_target_details(active.id, user_flag=uflag)
            app.refresh_targets()
            app.notify(f"User flag saved: {uflag}")
        else:
            app.notify("No active target set", severity="error")
    elif val.startswith(":rflag ") or val.startswith(":flag root "):
        rflag = val.split(maxsplit=1)[1].replace("root ", "").strip()
        if active:
            app.store.update_target_details(active.id, root_flag=rflag)
            app.refresh_targets()
            app.notify(f"Root flag saved: {rflag}")
        else:
            app.notify("No active target set", severity="error")
    elif val.startswith(":foothold "):
        fh = val[10:].strip()
        if active:
            app.store.update_target_details(active.id, initial_access_vuln=fh)
            app.refresh_targets()
            app.notify(f"Foothold saved: {fh}")
    elif val.startswith(":privesc "):
        pe = val[9:].strip()
        if active:
            app.store.update_target_details(active.id, privesc_vector=pe)
            app.notify(f"PrivEsc saved: {pe}")
    elif val.startswith(":stuck ") or val.startswith(":dead "):
        stuck_txt = val.split(maxsplit=1)[1].strip()
        app.store.add_failure_log(target_id=target_id, where_stuck=stuck_txt)
        app.notify(f"Dead-end logged: {stuck_txt}")
    elif val.startswith(":clue "):
        clue_txt = val[6:].strip()
        app.store.add_failure_log(target_id=target_id, breakthrough_clue=clue_txt)
        app.notify(f"Breakthrough clue logged: {clue_txt}")
    elif val.startswith(":ref ") or val.startswith(":cheat "):
        active_ip = active.ip if active else ""

        def on_cmd_selected(cmd: Optional[str]) -> None:
            if cmd:
                copy_to_clipboard(cmd)
                app.notify(f"Copied command: {cmd}")

        app.push_screen(ReferenceModal(target_ip=active_ip), callback=on_cmd_selected)
        return
    elif val.startswith(":n "):
        note_text = val[3:].strip()
        app.store.add_note(content=note_text, target_id=target_id)
        app.notify(f"Note added: {note_text}")
    elif val.startswith(":f "):
        finding_text = val[3:].strip()
        app.store.add_finding(title=finding_text, target_id=target_id)
        app.notify(f"Finding added: {finding_text}")
    elif val.startswith(":c "):
        cred_str = val[3:].strip()
        if ":" in cred_str:
            u, p = cred_str.split(":", 1)
        else:
            u, p = cred_str, ""
        app.store.add_credential(username=u, secret=p, target_id=target_id)
        app.notify(f"Cred added: {u}")
    elif val.startswith(":t "):
        ip = val[3:].strip()
        app.store.add_target(ip=ip)
        app.refresh_targets()
        app.notify(f"Target added: {ip}")
    elif val.startswith(":s "):
        parts = val[3:].strip().split()
        if parts and active:
            port_proto = parts[0]
            svc_name = parts[1] if len(parts) > 1 else "unknown"
            proto = "tcp"
            if "/" in port_proto:
                port_str, proto = port_proto.split("/", 1)
            else:
                port_str = port_proto
            try:
                app.store.add_service(
                    target_id=active.id,
                    port=int(port_str),
                    protocol=proto,
                    service=svc_name,
                )
                app.notify(f"Service added: {port_str}/{proto} {svc_name}")
            except ValueError:
                app.notify("Invalid port", severity="error")
    elif val.startswith(":ev "):
        ev_path = val[4:].strip()
        app.store.add_evidence(path_or_ref=ev_path, target_id=target_id)
        app.notify(f"Evidence logged: {ev_path}")
    elif val.startswith(":theme"):
        parts = val.split(maxsplit=2)
        if len(parts) == 1:
            app.action_cycle_theme()
        elif len(parts) == 3 and parts[1].lower() in ("default", "set-default", "def", "save"):
            app.set_default_theme(parts[2].strip().lower())
        else:
            arg = val[6:].strip()
            if arg.lower().startswith("default ") or arg.lower().startswith("set-default "):
                def_target = arg.split(maxsplit=1)[1].strip()
                app.set_default_theme(def_target)
            else:
                app.apply_theme(arg.lower())
        return
    elif val.startswith((":trans", ":glass")):
        parts = val.split()
        if len(parts) > 1 and parts[1].lower() in ("on", "1", "yes", "true"):
            app.toggle_transparency(True, persist=True)
            app.notify("Glass transparency enabled (saved as default)")
        elif len(parts) > 1 and parts[1].lower() in ("off", "0", "no", "false"):
            app.toggle_transparency(False, persist=True)
            app.notify("Solid background enabled (saved as default)")
        else:
            state = app.toggle_transparency(persist=True)
            msg = "Glass transparency enabled" if state else "Solid background enabled"
            app.notify(f"{msg} (saved as default)")
    elif val.startswith((":m ", ":template ", ":methodology ")):
        arg = val.split(maxsplit=1)[1].strip()
        parts = arg.split()
        tmpl_name = parts[0].lower()
        replace_mode = not (len(parts) > 1 and parts[1].lower() in ("append", "add", "+"))
        try:
            items = apply_template_to_store(
                app.store, tmpl_name, target_id=target_id, replace=replace_mode
            )
            try:
                ck_list = app.query_one("#list-checklist", ListView)
                ck_list.index = 0
            except Exception:
                pass
            app.refresh_all()
            action_word = "Switched to" if replace_mode else "Appended"
            app.notify(f"{action_word} {tmpl_name.upper()} methodology ({len(items)} items)")
        except ValueError as e:
            app.notify(str(e), severity="error")
        return
    elif val in (":m", ":template", ":methodology"):
        app.action_apply_template()
        return
    elif val.startswith(":w"):
        alias = val[2:].strip().lower()
        if not alias:
            avail = ", ".join(list(WORDLIST_ALIASES.keys())[:6])
            app.notify(f"Wordlists: {avail}... (e.g. :w rockyou)")
            return
        path = WORDLIST_ALIASES.get(alias)
        if path:
            copy_to_clipboard(path)
            try:
                console = app.query_one("#guidance-box")
                console.show_copied_feedback(path)
            except Exception:
                pass
            app.notify(f"Copied wordlist: {path}")
        else:
            app.notify(f"Unknown wordlist '{alias}'. Try: {', '.join(list(WORDLIST_ALIASES.keys())[:5])}")
        return
    elif val.startswith("/"):
        app.action_open_search()
        return
    elif val == ":q":
        app.exit()
        return
    else:
        app.store.add_note(content=val, target_id=target_id)
        app.notify(f"Note added: {val}")

    app.refresh_all()
