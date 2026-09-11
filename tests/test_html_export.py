"""Tests for the self-contained printable HTML handover export."""

from __future__ import annotations

from click.testing import CliRunner

from glacis.cli import cli
from glacis.exporter_html import export_html


def test_html_is_self_contained(seeded_store) -> None:
    html = export_html(seeded_store)
    assert html.lstrip().startswith("<!DOCTYPE html>")
    # No external resources at all: no CDN, scripts, remote images or fonts.
    assert "http://" not in html
    assert "https://" not in html
    assert "<script" not in html.lower()
    assert "cdn." not in html.lower()
    assert "<style>" in html and "</style>" in html


def test_html_contains_recorded_content(seeded_store) -> None:
    target = seeded_store.list_targets()[0]
    seeded_store.update_target_details(
        target.id, hostname="webbox", os_name="Linux",
        initial_access_vuln="weak creds", privesc_vector="sudo nmap",
    )
    html = export_html(seeded_store)
    assert "webbox" in html
    assert target.ip in html
    assert "weak creds" in html
    assert "sudo nmap" in html
    # Credentials are masked by default.
    creds = seeded_store.list_credentials()
    if creds:
        assert creds[0].secret not in html
    html2 = export_html(seeded_store, reveal_creds=True)
    if creds:
        assert creds[0].secret in html2
    # Footer marks the report as offline-generated.
    assert "offline" in html2.lower()


def test_html_escapes_user_content(store) -> None:
    t = store.add_target("10.7.7.7")
    store.add_note("<script>alert(1)</script>", target_id=t.id)
    store.add_finding("xss <img src=x>", target_id=t.id, description="<b>desc</b>")
    html = export_html(store)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
    assert "&lt;img" in html


def test_html_handles_empty_workspace(store) -> None:
    html = export_html(store)
    assert "GLACIS" in html
    assert html.lstrip().startswith("<!DOCTYPE html>")


def test_cli_html_export(tmp_path, seeded_store, monkeypatch) -> None:
    db = tmp_path / "n.db"
    # Re-create seed data in a file-backed DB so the CLI can open it.
    from glacis.db.store import NotebookStore as NS

    file_store = NS(db)
    t = file_store.add_target("10.8.8.8")
    file_store.add_note("cli export note", target_id=t.id)
    file_store.close()

    runner = CliRunner()
    out = tmp_path / "report.html"
    result = runner.invoke(
        cli, ["--db", str(db), "export", "-f", "html", "-o", str(out)],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    content = out.read_text(encoding="utf-8")
    assert content.startswith("<!DOCTYPE html>")
    assert "10.8.8.8" in content
    assert "http://" not in content and "https://" not in content
