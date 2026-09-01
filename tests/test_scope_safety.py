"""Scope & Safety Verification Audit Test.

Rigorously verifies that CYB0X-S contains ZERO AI, zero autonomous tooling,
zero background scanners, and zero outbound network/LLM dependencies.
"""

import ast
from pathlib import Path
import cyb0x_s

DISALLOWED_IMPORTS = {
    # AI / LLM SDKs
    "openai",
    "anthropic",
    "google.generativeai",
    "google.ai",
    "langchain",
    "langchain_core",
    "llama_index",
    "ollama",
    "litellm",
    "cohere",
    "transformers",
    "huggingface_hub",
    # Active scanning & network exploitation tools
    "nmap",
    "scapy",
    "paramiko",
    "pwn",
    "impacket",
    # Outbound HTTP client libraries (ensure completely local-first)
    "requests",
    "httpx",
    "aiohttp",
    "urllib.request",
}

BANNED_PHRASES = [
    "ai assistant",
    "attack planner",
    "next attack",
    "recommended exploit",
    "automated pentesting",
    "autonomous exploitation",
]


def test_default_mode_is_safe() -> None:
    """Verify that CYB0X-S mode is strictly SAFE."""
    assert cyb0x_s.__mode__ == "SAFE"


def test_no_disallowed_imports_in_source_tree() -> None:
    """AST parse every source file in cyb0x_s and verify no prohibited packages are imported."""
    src_dir = Path(__file__).resolve().parent.parent / "src" / "cyb0x_s"
    assert src_dir.is_dir()

    for py_file in src_dir.rglob("*.py"):
        code = py_file.read_text(encoding="utf-8")
        tree = ast.parse(code, filename=str(py_file))

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root_pkg = alias.name.split(".")[0]
                    assert root_pkg not in DISALLOWED_IMPORTS, (
                        f"Prohibited import '{alias.name}' detected in {py_file.name}!"
                    )
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    root_pkg = node.module.split(".")[0]
                    assert root_pkg not in DISALLOWED_IMPORTS, (
                        f"Prohibited import from '{node.module}' detected in {py_file.name}!"
                    )


def test_no_banned_ai_marketing_phrases_in_code() -> None:
    """Verify that codebase does not describe itself as an AI assistant, attack planner, etc."""
    src_dir = Path(__file__).resolve().parent.parent / "src" / "cyb0x_s"
    for py_file in src_dir.rglob("*.py"):
        content_lower = py_file.read_text(encoding="utf-8").lower()
        for phrase in BANNED_PHRASES:
            assert phrase not in content_lower, (
                f"Banned concept/phrase '{phrase}' found in {py_file.name}!"
            )


def test_passive_record_retention_fidelity(store) -> None:
    """Confirm note commands store verbatim input without auto-converting into credentials or findings."""
    # If the user passes "admin:password" into a note, it MUST stay a note and NOT auto-classify as a credential
    note = store.add_note("admin:SecretPassword123")
    assert note.content == "admin:SecretPassword123"

    # Credentials table must remain completely empty
    creds = store.list_credentials()
    assert len(creds) == 0

    # Findings table must remain completely empty
    findings = store.list_findings()
    assert len(findings) == 0
