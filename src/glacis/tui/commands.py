"""Fast capture and terminal command dispatching for GLACIS TUI."""

from __future__ import annotations

from typing import Any, Optional

from textual.widgets import ListView

from glacis.clipboard import copy_to_clipboard
from glacis.templates import apply_template_to_store
from glacis.tui.modals import ReferenceModal

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
    elif val.startswith("pivot "):
        return f":pivot {val[6:].strip()}"
    elif val in ("pivot", ":pivot"):
        return ":pivot"
    elif val.startswith("subnet "):
        return f":subnet {val[7:].strip()}"
    elif val.startswith("proof ") or val.startswith("question "):
        raw_val = val.replace("proof ", "", 1).replace("question ", "", 1).strip()
        return f":q {raw_val}"
    elif val.startswith(":import "):
        return val
    elif val.startswith("import "):
        return f":import {val[7:].strip()}"
    elif val in ("import", ":import"):
        return ":import"
    elif val.startswith(":ws "):
        return val
    elif val.startswith("workspace "):
        return f":ws {val[10:].strip()}"
    elif val.startswith("ws "):
        return f":ws {val[3:].strip()}"
    elif val in ("workspace", "ws", ":ws"):
        return ":ws"
    elif val.startswith("set lhost ") or val.startswith("lhost "):
        raw_val = val.replace("set lhost ", "", 1).replace("lhost ", "", 1).strip()
        return f":lhost {raw_val}"
    elif val in ("set lhost", "lhost", ":lhost"):
        return ":lhost"
    elif val.startswith("set lport ") or val.startswith("lport "):
        raw_val = val.replace("set lport ", "", 1).replace("lport ", "", 1).strip()
        return f":lport {raw_val}"
    elif val in ("set lport", "lport", ":lport"):
        return ":lport"
    elif val in ("export wordlists", ":export wordlists", "export creds", ":export creds"):
        return ":export wordlists"
    elif val.startswith(":crack "):
        return f":c crack {val[7:].strip()}"
    elif val.startswith("crack "):
        return f":c crack {val[6:].strip()}"
    elif val.startswith(("paste-ev", ":paste-ev", "paste-evidence", ":paste-evidence")):
        arg = val.split(maxsplit=1)[1].strip() if " " in val else ""
        return f":paste-ev {arg}".strip()
    elif val.startswith(":ev latest"):
        return f":ev latest {val[10:].strip()}".strip()
    elif val.startswith("ev latest"):
        return f":ev latest {val[9:].strip()}".strip()
    elif val.startswith(":evidence latest"):
        return f":ev latest {val[16:].strip()}".strip()
    elif val.startswith("evidence latest"):
        return f":ev latest {val[15:].strip()}".strip()
    elif val.startswith(":evidence "):
        return f":ev {val[10:].strip()}"
    elif val.startswith("evidence "):
        return f":ev {val[9:].strip()}"
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
    elif val == ":0":
        app.action_switch_tab("tab-pulse")
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
    elif val == ":exam on":
        if hasattr(app, "set_exam_mode"):
            app.set_exam_mode(True)
        return
    elif val == ":exam off":
        if hasattr(app, "set_exam_mode"):
            app.set_exam_mode(False)
        return
    elif val == ":exam":
        if hasattr(app, "set_exam_mode"):
            app.set_exam_mode(not getattr(app, "exam_mode", False))
        return
    elif val in (":welcome", ":start", ":onboarding"):
        if hasattr(app, "action_show_welcome"):
            app.action_show_welcome()
        return

    # Import command (:import [file])
    if val == ":import" or val.startswith(":import "):
        path = val[8:].strip() if len(val) > 7 else ""
        if hasattr(app, "action_import_scan"):
            app.action_import_scan(initial_file=path)
        return

    # Workspace command (:ws [switch|init|name])
    if val == ":ws" or val.startswith(":ws "):
        args = val[4:].strip() if len(val) > 3 else ""
        if not args:
            if hasattr(app, "action_manage_workspaces"):
                app.action_manage_workspaces()
            return
        parts = args.split(maxsplit=2)
        cmd = parts[0].lower()
        if cmd == "list":
            if hasattr(app, "action_manage_workspaces"):
                app.action_manage_workspaces()
            return
        elif cmd == "switch" and len(parts) > 1:
            target_ws = parts[1]
            ws = app.store.set_active_workspace(target_ws)
            app.refresh_all()
            app.notify(f"Switched to workspace: {ws.name}")
            return
        elif cmd == "init" and len(parts) > 1:
            name = parts[1]
            path_arg = parts[2] if len(parts) > 2 else name
            from pathlib import Path
            dest = Path(path_arg).expanduser().resolve()
            ws, _ = app.store.init_workspace_directory(name=name, target_dir=dest)
            app.refresh_all()
            app.notify(f"Initialized & switched to workspace: {ws.name}")
            return
        else:
            # Shorthand :ws <name>
            ws = app.store.set_active_workspace(args)
            app.refresh_all()
            app.notify(f"Switched to workspace: {ws.name}")
            return

    if val == ":lhost" or val.startswith(":lhost "):
        arg = val[6:].strip() if len(val) > 6 else ""
        if not arg:
            curr = app.store.get_lhost() if hasattr(app.store, "get_lhost") else ""
            app.notify(f"Current LHOST: {curr or 'unset'} (use :lhost <ip> or :lhost auto)")
            return
        if arg.lower() == "auto":
            from glacis.db.store import detect_local_vpn_ip

            detected = detect_local_vpn_ip()
            if detected:
                app.store.set_lhost(detected)
                app.notify(f"Auto-detected & set LHOST: {detected}")
            else:
                app.notify("Could not auto-detect VPN IP (tun0/wg0). Please specify manually.", severity="warning")
        else:
            app.store.set_lhost(arg)
            app.notify(f"LHOST set to: {arg}")
        app.refresh_all()
        return

    if val == ":lport" or val.startswith(":lport "):
        arg = val[6:].strip() if len(val) > 6 else ""
        if not arg:
            curr = app.store.get_lport() if hasattr(app.store, "get_lport") else "4444"
            app.notify(f"Current LPORT: {curr} (use :lport <port>)")
            return
        app.store.set_lport(arg)
        app.notify(f"LPORT set to: {arg}")
        app.refresh_all()
        return

    if val == ":export wordlists":
        try:
            u_file, p_file = app.store.export_wordlists_to_loot()
            app.notify(f"Exported: {u_file.name} and {p_file.name} to loot/")
            if hasattr(app, "refresh_loot_widget"):
                app.refresh_loot_widget()
        except Exception as e:
            app.notify(f"Export failed: {e}", severity="error")
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
    elif val.startswith(":pivot"):
        args = val[6:].strip()
        if not active:
            app.notify("No active target selected", severity="error")
        elif args.lower() in ("off", "none", "false", "0"):
            app.store.update_target_details(active.id, is_pivot=False, pivot_route="")
            app.refresh_targets()
            app.notify(f"Pivot disabled on {active.ip}")
        else:
            route = args if args and args.lower() not in ("on", "true", "1") else "192.168.1.0/24 via socks5:1080"
            app.store.update_target_details(active.id, is_pivot=True, pivot_route=route)
            app.refresh_targets()
            app.notify(f"Pivot set on {active.ip} ({route})")
    elif val.startswith(":subnet "):
        snet = val[8:].strip()
        if not active:
            app.notify("No active target selected", severity="error")
        else:
            app.store.update_target_details(active.id, subnet=snet)
            app.refresh_targets()
            app.notify(f"Subnet set on {active.ip}: {snet}")
    elif val.startswith(":q ") or val.startswith(":proof "):
        parts = val.split(maxsplit=2)
        if len(parts) >= 3:
            q_num = parts[1].strip().upper()
            if not q_num.startswith("Q") and q_num.isdigit():
                q_num = f"Q{q_num}"
            proof_val = parts[2].strip()
            app.store.add_exam_proof(
                question_num=q_num,
                answer_proof=proof_val,
                category="FLAG" if "flag" in proof_val.lower() else ("HASH" if len(proof_val) in (32, 65) else "ANSWER"),
                target_id=active.id if active else None,
            )
            app.refresh_all()
            app.notify(f"Recorded {q_num} proof: {proof_val[:24]}...")
        else:
            app.notify("Usage: :q <num> <proof_value>", severity="error")
    elif val in (":export exam", ":export evidence"):
        from pathlib import Path
        md = app.store.export_exam_evidence_markdown()
        out_file = Path("exam_evidence.md")
        out_file.write_text(md, encoding="utf-8")
        app.notify(f"Exported exam evidence to {out_file.resolve()}")
    elif val.startswith(":stuck ") or val.startswith(":dead "):
        stuck_txt = val.split(maxsplit=1)[1].strip()
        app.store.add_failure_log(target_id=target_id, where_stuck=stuck_txt)
        app.notify(f"Dead-end logged: {stuck_txt}")
    elif val.startswith(":clue "):
        clue_txt = val[6:].strip()
        app.store.add_failure_log(target_id=target_id, breakthrough_clue=clue_txt)
        app.notify(f"Breakthrough clue logged: {clue_txt}")
    elif val.startswith(":ref "):
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
    elif val.startswith((":c crack ", ":c update ")):
        parts = val.split(maxsplit=3)
        if len(parts) >= 4:
            try:
                c_id = int(parts[2])
                new_sec = parts[3].strip()
                updated = app.store.update_credential(c_id, secret=new_sec, status="cracked")
                if updated:
                    app.notify(f"Updated cred #{c_id} ({updated.username}) -> {new_sec}")
                    app.refresh_all()
                else:
                    app.notify(f"Credential #{c_id} not found", severity="error")
            except ValueError:
                app.notify("Usage: :c crack <id> <plaintext>", severity="error")
        else:
            app.notify("Usage: :c crack <id> <plaintext>", severity="error")
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
    elif val == ":paste-ev" or val.startswith(":paste-ev "):
        desc = val[9:].strip() if len(val) > 9 else "Clipboard screenshot"
        import time
        from pathlib import Path

        from glacis.clipboard import save_clipboard_image

        ws = app.store.get_active_workspace()
        ws_root = Path(ws.root_path).resolve() if ws and ws.root_path else Path.cwd()
        sc_dir = ws_root / "screenshots"
        sc_dir.mkdir(parents=True, exist_ok=True)

        tgt_ip = active.ip if active else "global"
        ts = int(time.time())
        dest_file = sc_dir / f"proof_{tgt_ip}_{ts}.png"

        saved = save_clipboard_image(dest_file)
        if saved:
            rel_path = f"screenshots/{dest_file.name}"
            app.store.add_evidence(
                path_or_ref=rel_path,
                target_id=target_id,
                evidence_type="screenshot",
                description=desc,
            )
            app.notify(f"Saved & attached screenshot: {rel_path}")
            if hasattr(app, "refresh_loot_widget"):
                app.refresh_loot_widget()
            app.refresh_all()
        else:
            app.notify("No image found in clipboard. (Copy an image or use :ev latest)", severity="warning")
    elif val.startswith(":ev latest"):
        desc = val[10:].strip() if len(val) > 10 else "Latest screenshot"
        import shutil
        from pathlib import Path

        from glacis.clipboard import find_latest_screenshot

        ws = app.store.get_active_workspace()
        ws_root = Path(ws.root_path).resolve() if ws and ws.root_path else Path.cwd()
        sc_dir = ws_root / "screenshots"
        sc_dir.mkdir(parents=True, exist_ok=True)

        latest = find_latest_screenshot([Path.home() / "Pictures" / "Screenshots", Path.home() / "Pictures", sc_dir])
        if latest:
            if latest.parent.resolve() != sc_dir.resolve():
                dest_file = sc_dir / latest.name
                shutil.copy2(latest, dest_file)
                rel_path = f"screenshots/{dest_file.name}"
            else:
                rel_path = f"screenshots/{latest.name}"

            app.store.add_evidence(
                path_or_ref=rel_path,
                target_id=target_id,
                evidence_type="screenshot",
                description=desc,
            )
            app.notify(f"Attached recent screenshot: {rel_path}")
            if hasattr(app, "refresh_loot_widget"):
                app.refresh_loot_widget()
            app.refresh_all()
        else:
            app.notify("No recent screenshot found in ~/Pictures or screenshots/", severity="warning")
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
