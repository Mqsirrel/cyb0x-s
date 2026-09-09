"""Tests for the standalone HTML report export."""

from __future__ import annotations

from glacis.db.store import NotebookStore
from glacis.report import build_html_report


def _seed(store: NotebookStore) -> None:
    t = store.add_target("10.10.10.20", hostname="dc01", os_name="Linux")
    store.add_service(target_id=t.id, port=445, service="SMB", version="Samba 4.3")
    store.add_finding("Anonymous share access", target_id=t.id, severity="HIGH", description="backups readable")
    store.add_credential("admin", "SuperSecret99", target_id=t.id, source="backup.zip")
    store.add_checklist_item("SMB enumeration", target_id=t.id)
    store.add_note("check archive.zip", target_id=t.id)
    store.add_evidence("screenshots/share.png", target_id=t.id)


def test_report_is_selfcontained(store: NotebookStore) -> None:
    _seed(store)
    html = build_html_report(store)
    assert html.startswith("<!doctype html>")
    # zero external assets: no CDN, no scripts, no linked css
    assert "https://" not in html and "http://" not in html
    assert "<script" not in html
    assert '<link rel="stylesheet"' not in html
    assert "@media print" in html


def test_report_contains_all_sections(store: NotebookStore) -> None:
    _seed(store)
    html = build_html_report(store)
    for fragment in (
        "Workspace pulse", "Next actions", "Target scorecards",
        "Timeline", "Services", "Findings", "Credentials",
        "Methodology", "Evidence", "Field notes",
    ):
        assert fragment in html


def test_report_masks_credentials_by_default(store: NotebookStore) -> None:
    _seed(store)
    html = build_html_report(store, reveal_creds=False)
    assert "SuperSecret99" not in html
    assert "•••" in html

    revealed = build_html_report(store, reveal_creds=True)
    assert "SuperSecret99" in revealed


def test_report_escapes_html_injection(store: NotebookStore) -> None:
    t = store.add_target("10.10.10.20")
    store.add_finding('<script>alert("x")</script>', target_id=t.id)
    store.add_note('<img src=x onerror=alert(1)>', target_id=t.id)
    html = build_html_report(store)
    assert "<script>alert" not in html
    assert "&lt;script&gt;" in html
    assert "<img src=x" not in html


def test_report_renders_empty_workspace(store: NotebookStore) -> None:
    html = build_html_report(store)
    assert "GLACIS" in html
    assert "No targets recorded" in html


def test_report_severity_and_status_chips(store: NotebookStore) -> None:
    _seed(store)
    html = build_html_report(store)
    assert "chip high" in html
    assert "IN-SCOPE" in html
    assert "CHECKED" in html


def test_report_follows_palette(store: NotebookStore) -> None:
    _seed(store)
    slate = build_html_report(store, palette_name="slate")
    ember = build_html_report(store, palette_name="ember")
    # ember palette accent differs from slate -> CSS custom property changes
    assert "--c-accent:" in slate and "--c-accent:" in ember
    assert slate != ember


def test_report_sparkline_present(store: NotebookStore) -> None:
    _seed(store)
    html = build_html_report(store)
    assert '<svg class="spark"' in html
    assert html.count("<rect") == 14  # one bar per day
