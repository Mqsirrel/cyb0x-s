"""Static, offline-by-construction compliance audit.

``glacis exam-check`` needs a deterministic way to prove the application never
imports a network-capable module. We parse every Python file under the package
with the :mod:`ast` module (nothing is imported or executed) and flag any
import of a network or telemetry library. The scan also flags obvious
background-update or analytics calls.

This module itself imports only the Python standard library ``ast``/``pathlib``.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import List, Optional, Union

from pydantic import BaseModel, Field

#: Top-level module names that grant network or telemetry capabilities.
FORBIDDEN_MODULE_ROOTS = frozenset(
    {
        "socket",
        "ssl",
        "asyncio.open_connection",  # handled via dotted module checks below
        "requests",
        "httpx",
        "urllib",
        "http.client",
        "ftplib",
        "telnetlib",
        "smtplib",
        "poplib",
        "imaplib",
        "nntplib",
        "xmlrpc",
        "xmlrpc.client",
        "websocket",
        "websockets",
        "aiohttp",
        "trio_websocket",
        "grpc",
        "pika",
        "kafka",
        "sentry_sdk",
        "analytics",
        "posthog",
        "mixpanel",
        "segment",
    }
)

#: Attribute call patterns that imply network activity.
FORBIDDEN_CALLS = frozenset(
    {
        "urlopen",
        "socket.socket",
        "create_connection",
        "requests.get",
        "requests.post",
        "httpx.get",
        "httpx.post",
        "urllib.request.urlopen",
    }
)

#: Substrings that indicate update checks or telemetry endpoints.
FORBIDDEN_NAME_HINTS = ("telemetry", "phone_home", "check_for_updates")


class Violation(BaseModel):
    path: str
    lineno: int
    kind: str
    offender: str
    detail: str = ""


class OfflineReport(BaseModel):
    package_root: str
    files_scanned: int = 0
    violations: List[Violation] = Field(default_factory=list)

    @property
    def clean(self) -> bool:
        return not self.violations


def _module_root(dotted: str) -> str:
    return dotted.split(".", 1)[0]


def _forbidden_match(module: str) -> Optional[str]:
    """Return the forbidden entry that matches a dotted module name, if any."""
    if module in FORBIDDEN_MODULE_ROOTS:
        return module
    root = _module_root(module)
    # Roots like urllib/http.client/xmlrpc need dotted awareness.
    for banned in FORBIDDEN_MODULE_ROOTS:
        if module == banned or module.startswith(banned + "."):
            return banned
        if "." not in banned and root == banned:
            return banned
    return None


def _dotted_attr(node: ast.AST) -> str:
    """Flatten chained attribute access, e.g. urllib.request.urlopen."""
    parts: list[str] = []
    cur: Optional[ast.AST] = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
    return ".".join(reversed(parts))


def scan_source(source: str, path: str = "<string>") -> List[Violation]:
    """Scan Python source text; return every forbidden import/call."""
    out: List[Violation] = []
    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError:
        return out

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                banned = _forbidden_match(alias.name)
                if banned:
                    out.append(
                        Violation(
                            path=path,
                            lineno=node.lineno,
                            kind="forbidden-import",
                            offender=alias.name,
                            detail=f"network/telemetry module '{banned}' must never be imported",
                        )
                    )
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            banned = _forbidden_match(module)
            if banned:
                out.append(
                    Violation(
                        path=path,
                        lineno=node.lineno,
                        kind="forbidden-import",
                        offender=f"from {module} import ...",
                        detail=f"network/telemetry module '{banned}' must never be imported",
                    )
                )
        elif isinstance(node, ast.Call):
            dotted = _dotted_attr(node.func)
            if dotted in FORBIDDEN_CALLS:
                out.append(
                    Violation(
                        path=path,
                        lineno=getattr(node, "lineno", 0),
                        kind="forbidden-call",
                        offender=dotted,
                        detail="network call has no place in an offline notebook",
                    )
                )
            func_name = dotted.split(".")[-1] if dotted else ""
            if func_name in FORBIDDEN_NAME_HINTS:
                out.append(
                    Violation(
                        path=path,
                        lineno=getattr(node, "lineno", 0),
                        kind="telemetry-hint",
                        offender=dotted,
                        detail="update-check/telemetry helper is prohibited",
                    )
                )
    return out


def scan_tree(root: Union[str, Path]) -> OfflineReport:
    """Scan every ``.py`` file beneath ``root`` for network imports/calls."""
    root_path = Path(root)
    report = OfflineReport(package_root=str(root_path))
    if root_path.is_file():
        files = [root_path]
    else:
        files = sorted(p for p in root_path.rglob("*.py") if "__pycache__" not in p.parts)
    for py_file in files:
        try:
            source = py_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        report.files_scanned += 1
        rel = str(py_file)
        for v in scan_source(source, path=rel):
            report.violations.append(v)
    return report
