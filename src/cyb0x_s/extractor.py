"""Constrained Candidate Log Extractor for CYB0X-S (P4).

Parses terminal, tool, and scan logs for:
    - Targets (IPs, Hostnames)
    - Open Services (Port/Protocol)
    - Credentials (Usernames, Passwords, Hashes)
    - Flags / Objective Proofs

Strict Operational Guardrail:
NEVER auto-populates flags or credentials directly into the notebook.
Stages all detected artifacts as Candidates requiring explicit operator confirmation.
"""

from __future__ import annotations

import ipaddress
import re
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from cyb0x_s.db.store import NotebookStore


class CandidateType(str, Enum):
    TARGET = "TARGET"
    SERVICE = "SERVICE"
    CREDENTIAL = "CREDENTIAL"
    HASH = "HASH"
    FLAG = "FLAG"


class ExtractedCandidate(BaseModel):
    """An unconfirmed artifact staged for operator review."""
    candidate_id: int
    candidate_type: CandidateType
    summary: str
    target_ip: Optional[str] = None
    port: Optional[int] = None
    protocol: str = "tcp"
    service_name: str = ""
    version: str = ""
    username: Optional[str] = None
    secret: Optional[str] = None
    hash_value: Optional[str] = None
    hash_type: Optional[str] = None
    flag_value: Optional[str] = None
    context_line: str = ""
    confidence: str = "HIGH"  # HIGH, MED, LOW


# Precompiled regex patterns
IP_RE = re.compile(r"\b(?!(?:127\.0\.0\.1|0\.0\.0\.0|255\.255\.255\.255)\b)(?:[1-9]\d{0,2}\.){3}[1-9]\d{0,2}\b")
PORT_OPEN_RE = re.compile(r"\b(\d{1,5})/(tcp|udp)\s+open\s*([a-zA-Z0-9_\-\.]+)?(?:\s+(.*))?", re.IGNORECASE)
FLAG_RE = re.compile(r"\b([A-Za-z0-9_-]{2,16}\{[A-Za-z0-9_!@#$%^&*+=./-]{4,64}\})")
SHADOW_HASH_RE = re.compile(r"\$([156y]|2[aby])\$[a-zA-Z0-9./]+\$[a-zA-Z0-9./]+")
NTLM_PAIR_RE = re.compile(r"\b([a-zA-Z0-9._-]+):(?:\d+:)?([a-fA-F0-9]{32}:[a-fA-F0-9]{32})\b")
NETEXEC_CRED_RE = re.compile(r"\[\+\]\s+(?:(?:\d{1,3}\.){3}\d{1,3}:\d+\s+-\s+)?([a-zA-Z0-9._\\]+):([^\s\r\n]+)\s+(?:\(Pwn3d!\))?", re.IGNORECASE)
HYDRA_CRED_RE = re.compile(r"login:\s*([^\s]+)\s+password:\s*([^\s\r\n]+)", re.IGNORECASE)
COLON_CRED_RE = re.compile(r"\b([a-zA-Z0-9._-]+):([A-Za-z0-9!@#$%^&*()_+=-]{3,64})(?=\s|$|[.,;])")
SIMPLE_CRED_RE = re.compile(r"(?:username|user|login|account):\s*([^\s,;]+)\s+(?:password|pass|secret):\s*([^\s,;\r\n]+)", re.IGNORECASE)


def extract_candidates(raw_text: str, default_target_ip: Optional[str] = None) -> List[ExtractedCandidate]:
    """Scan raw log text and extract candidate targets, services, creds, hashes, and flags.

    Does NOT write anything to the database; purely returns candidate objects for staging.
    """
    candidates: List[ExtractedCandidate] = []
    seen_summaries: set[str] = set()
    next_id = 1

    lines = raw_text.splitlines()
    current_ip = default_target_ip

    for line in lines:
        cleaned_line = line.strip()
        if not cleaned_line:
            continue

        # 1. Detect IP in context (e.g. Nmap scan report for 10.10.10.5)
        ip_matches = IP_RE.findall(cleaned_line)
        for ip in ip_matches:
            try:
                addr = ipaddress.IPv4Address(ip)
                if not addr.is_multicast and not addr.is_reserved:
                    # Context check: if line looks like host discovery
                    if any(k in cleaned_line.lower() for k in ("scan report", "nmap", "host", "target", "ping", "netexec", "smb")):
                        current_ip = ip
                        key = f"TARGET:{ip}"
                        if key not in seen_summaries:
                            seen_summaries.add(key)
                            candidates.append(
                                ExtractedCandidate(
                                    candidate_id=next_id,
                                    candidate_type=CandidateType.TARGET,
                                    summary=f"Discovered Host: {ip}",
                                    target_ip=ip,
                                    context_line=cleaned_line[:80],
                                    confidence="HIGH",
                                )
                            )
                            next_id += 1
            except Exception:
                pass

        # 2. Detect Open Ports
        port_match = PORT_OPEN_RE.search(cleaned_line)
        if port_match:
            port_num = int(port_match.group(1))
            proto = port_match.group(2).lower()
            svc = (port_match.group(3) or "unknown").strip()
            ver = (port_match.group(4) or "").strip()
            key = f"SERVICE:{current_ip}:{port_num}/{proto}"
            if key not in seen_summaries and 1 <= port_num <= 65535:
                seen_summaries.add(key)
                candidates.append(
                    ExtractedCandidate(
                        candidate_id=next_id,
                        candidate_type=CandidateType.SERVICE,
                        summary=f"Open Port: {port_num}/{proto} ({svc} {ver})".strip(),
                        target_ip=current_ip,
                        port=port_num,
                        protocol=proto,
                        service_name=svc,
                        version=ver,
                        context_line=cleaned_line[:80],
                        confidence="HIGH",
                    )
                )
                next_id += 1

        # 3. Detect Flags / Proofs
        flag_match = FLAG_RE.search(cleaned_line)
        if flag_match:
            flag_val = flag_match.group(1)
            key = f"FLAG:{flag_val}"
            if key not in seen_summaries:
                seen_summaries.add(key)
                candidates.append(
                    ExtractedCandidate(
                        candidate_id=next_id,
                        candidate_type=CandidateType.FLAG,
                        summary=f"Flag Pattern: {flag_val[:30]}...",
                        target_ip=current_ip,
                        flag_value=flag_val,
                        context_line=cleaned_line[:80],
                        confidence="HIGH",
                    )
                )
                next_id += 1

        # 4. Detect Hashes
        shadow_match = SHADOW_HASH_RE.search(cleaned_line)
        if shadow_match:
            hash_val = shadow_match.group(0)
            algo_code = shadow_match.group(1)
            algo_map = {"6": "SHA-512 crypt", "5": "SHA-256 crypt", "1": "MD5 crypt", "y": "yescrypt", "2a": "bcrypt", "2b": "bcrypt"}
            algo_name = algo_map.get(algo_code, "crypt hash")
            key = f"HASH:{hash_val}"
            if key not in seen_summaries:
                seen_summaries.add(key)
                candidates.append(
                    ExtractedCandidate(
                        candidate_id=next_id,
                        candidate_type=CandidateType.HASH,
                        summary=f"{algo_name}: {hash_val[:24]}...",
                        target_ip=current_ip,
                        hash_value=hash_val,
                        hash_type=algo_name,
                        context_line=cleaned_line[:80],
                        confidence="HIGH",
                    )
                )
                next_id += 1

        # 5. Detect Credentials (NetExec / Hydra / User:Pass)
        cred_extracted = False

        # Hydra
        hydra_m = HYDRA_CRED_RE.search(cleaned_line)
        if hydra_m:
            u, p = hydra_m.group(1).strip(), hydra_m.group(2).strip()
            key = f"CRED:{current_ip}:{u}:{p}"
            if key not in seen_summaries:
                seen_summaries.add(key)
                candidates.append(
                    ExtractedCandidate(
                        candidate_id=next_id,
                        candidate_type=CandidateType.CREDENTIAL,
                        summary=f"Credential: {u} : {p}",
                        target_ip=current_ip,
                        username=u,
                        secret=p,
                        context_line=cleaned_line[:80],
                        confidence="HIGH",
                    )
                )
                next_id += 1
                cred_extracted = True

        # NetExec / CrackMapExec
        if not cred_extracted:
            nxc_m = NETEXEC_CRED_RE.search(cleaned_line)
            if nxc_m:
                u, p = nxc_m.group(1).strip(), nxc_m.group(2).strip()
                key = f"CRED:{current_ip}:{u}:{p}"
                if key not in seen_summaries and not u.endswith("$"):
                    seen_summaries.add(key)
                    candidates.append(
                        ExtractedCandidate(
                            candidate_id=next_id,
                            candidate_type=CandidateType.CREDENTIAL,
                            summary=f"Validated Credential: {u} : {p}",
                            target_ip=current_ip,
                            username=u,
                            secret=p,
                            context_line=cleaned_line[:80],
                            confidence="HIGH",
                        )
                    )
                    next_id += 1
                    cred_extracted = True

        # NTLM pair
        if not cred_extracted:
            ntlm_m = NTLM_PAIR_RE.search(cleaned_line)
            if ntlm_m:
                u, h = ntlm_m.group(1).strip(), ntlm_m.group(2).strip()
                key = f"HASH:{current_ip}:{u}:{h}"
                if key not in seen_summaries:
                    seen_summaries.add(key)
                    candidates.append(
                        ExtractedCandidate(
                            candidate_id=next_id,
                            candidate_type=CandidateType.HASH,
                            summary=f"NTLM Hash ({u}): {h[:24]}...",
                            target_ip=current_ip,
                            username=u,
                            hash_value=h,
                            hash_type="NTLM",
                            context_line=cleaned_line[:80],
                            confidence="HIGH",
                        )
                    )
                    next_id += 1

        # Colon-delimited credential (user:pass)
        if not cred_extracted and any(k in cleaned_line.lower() for k in ("cred", "password", "login", "user", "account", "auth")):
            colon_m = COLON_CRED_RE.search(cleaned_line)
            if colon_m:
                u, p = colon_m.group(1).strip(), colon_m.group(2).strip()
                if u.lower() not in ("http", "https", "ftp", "ssh", "socks5", "tcp", "udp", "port") and not u.isdigit():
                    key = f"CRED:{current_ip}:{u}:{p}"
                    if key not in seen_summaries:
                        seen_summaries.add(key)
                        candidates.append(
                            ExtractedCandidate(
                                candidate_id=next_id,
                                candidate_type=CandidateType.CREDENTIAL,
                                summary=f"Credential: {u} : {p}",
                                target_ip=current_ip,
                                username=u,
                                secret=p,
                                context_line=cleaned_line[:80],
                                confidence="HIGH",
                            )
                        )
                        next_id += 1
                        cred_extracted = True

    return candidates


def stage_and_commit_candidate(
    candidate: ExtractedCandidate,
    store: NotebookStore,
    target_id: Optional[int] = None,
) -> Tuple[bool, str]:
    """Explicitly commit a single operator-confirmed candidate into the SQLite database.

    Returns (success, message).
    """
    # Resolve target ID
    resolved_tid = target_id
    if resolved_tid is None and candidate.target_ip:
        target = store.get_target_by_ip(candidate.target_ip)
        if not target and candidate.candidate_type != CandidateType.TARGET:
            # Auto-create target if confirmed candidate belongs to a new IP
            target = store.add_target(candidate.target_ip)
        if target:
            resolved_tid = target.id

    if candidate.candidate_type == CandidateType.TARGET:
        if candidate.target_ip:
            existing = store.get_target_by_ip(candidate.target_ip)
            if not existing:
                t = store.add_target(candidate.target_ip)
                return True, f"Target {candidate.target_ip} created (ID: {t.id})"
            return False, f"Target {candidate.target_ip} already exists in workspace"
        return False, "Candidate has no IP address"

    elif candidate.candidate_type == CandidateType.SERVICE:
        if resolved_tid is not None and candidate.port:
            s = store.add_service(
                target_id=resolved_tid,
                port=candidate.port,
                protocol=candidate.protocol,
                service=candidate.service_name or "unknown",
                version=candidate.version,
            )
            return True, f"Service {candidate.port}/{candidate.protocol} recorded on target {candidate.target_ip or resolved_tid}"
        return False, "Target ID or port missing for service candidate"

    elif candidate.candidate_type == CandidateType.CREDENTIAL:
        if candidate.username and candidate.secret:
            c = store.add_credential(
                username=candidate.username,
                secret=candidate.secret,
                source="log_extractor",
                target_id=resolved_tid,
            )
            return True, f"Credential {candidate.username} : ******** recorded"
        return False, "Username or secret missing for credential candidate"

    elif candidate.candidate_type == CandidateType.HASH:
        if candidate.hash_value:
            # Record as finding or credential note
            u = candidate.username or "unknown"
            c = store.add_credential(
                username=f"{u} (hash)",
                secret=candidate.hash_value,
                source=f"log_extractor ({candidate.hash_type or 'hash'})",
                target_id=resolved_tid,
            )
            return True, f"Hash for {u} recorded as credential"
        return False, "Hash value missing"

    elif candidate.candidate_type == CandidateType.FLAG:
        if candidate.flag_value:
            if resolved_tid:
                store.update_target_details(resolved_tid, user_flag=candidate.flag_value)
                return True, f"Flag {candidate.flag_value[:20]}... saved to target {candidate.target_ip or resolved_tid}"
            else:
                p = store.add_exam_proof(
                    question_num="FLAG-EXTRACTED",
                    answer_proof=candidate.flag_value,
                    category="FLAG",
                    notes="Captured via log extractor",
                    target_id=resolved_tid,
                )
                return True, f"Flag {candidate.flag_value[:20]}... recorded as objective proof"
        return False, "Flag value missing"

    return False, "Unknown candidate type"
