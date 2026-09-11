"""Static, offline metadata about well-known network services.

This module is a frozen, human-curated reference table — exactly like the
playbook data in :mod:`glacis.reference`. It contains **no scanning logic** and
never contacts a network: it only lets GLACIS label and correlate service
records that the operator already entered by hand or imported from a scan the
operator ran themselves.

Keeping the table here (instead of buried inside a Textual widget) lets the
deterministic triage engine, the credential spray matrix and future stations
share one source of truth.
"""

from __future__ import annotations

from typing import Dict, FrozenSet, Tuple

#: Services that commonly present an authentication surface.
AUTH_SERVICE_NAMES: FrozenSet[str] = frozenset(
    {
        "ssh",
        "smb",
        "microsoft-ds",
        "netbios-ssn",
        "winrm",
        "wsman",
        "rdp",
        "ms-wbt-server",
        "mysql",
        "mssql",
        "ms-sql-s",
        "ftp",
        "http",
        "https",
        "web",
        "postgres",
        "postgresql",
        "vnc",
        "telnet",
        "msrpc",
        "microsoft-rpc",
        "pop3",
        "imap",
        "imaps",
        "pop3s",
        "snmp",
        "ldap",
        "kerberos-sec",
        "redis",
        "mongo",
        "mongodb",
    }
)

#: Port numbers that commonly present an authentication surface.
AUTH_SERVICE_PORTS: FrozenSet[int] = frozenset(
    {21, 22, 23, 25, 80, 110, 143, 389, 443, 445, 465, 587, 636, 993, 995,
     1433, 1521, 2049, 2375, 3306, 3389, 5432, 5900, 5985, 5986, 6379,
     8080, 8443, 27017}
)

#: Foundational services every host-level recon pass usually accounts for.
#: Used purely as a static checklist hint ("you recorded a dead end but never
#: recorded the basics") — never as an instruction to probe anything.
COMMON_FOUNDATION_PORTS: FrozenSet[int] = frozenset({22, 80, 139, 443, 445, 3389})

#: Short, human labels for well-known ports (offline reference only).
PORT_LABELS: Dict[int, str] = {
    21: "FTP",
    22: "SSH",
    23: "Telnet",
    25: "SMTP",
    53: "DNS",
    80: "HTTP",
    88: "Kerberos",
    110: "POP3",
    111: "rpcbind",
    135: "MSRPC",
    139: "NetBIOS",
    143: "IMAP",
    389: "LDAP",
    443: "HTTPS",
    445: "SMB",
    465: "SMTPS",
    587: "SMTP",
    636: "LDAPS",
    993: "IMAPS",
    995: "POP3S",
    1433: "MSSQL",
    1521: "Oracle",
    2049: "NFS",
    2375: "Docker",
    3306: "MySQL",
    3389: "RDP",
    5432: "PostgreSQL",
    5900: "VNC",
    5985: "WinRM",
    5986: "WinRM/TLS",
    6379: "Redis",
    8080: "HTTP-ALT",
    8443: "HTTPS-ALT",
    27017: "MongoDB",
}


def is_auth_service(service_name: str, port: int) -> bool:
    """Return True when the recorded service commonly accepts credentials."""
    name = (service_name or "").strip().lower()
    return name in AUTH_SERVICE_NAMES or int(port) in AUTH_SERVICE_PORTS


def auth_service_pairs(targets, services) -> Tuple[Tuple[object, object], ...]:
    """Return ``(target, service)`` pairs for in-scope authenticating services.

    Pure filtering over already-recorded data; performs no network activity.
    """
    in_scope = {t.id: t for t in targets if getattr(t, "is_in_scope", True)}
    pairs = []
    for s in services:
        t = in_scope.get(getattr(s, "target_id", None))
        if t is not None and is_auth_service(getattr(s, "service", ""), getattr(s, "port", 0)):
            pairs.append((t, s))
    return tuple(pairs)
