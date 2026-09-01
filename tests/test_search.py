"""Tests for unified cross-entity search."""

from cyb0x_s.db.store import NotebookStore
from cyb0x_s.search import search_notebook


def test_cross_entity_search(store: NotebookStore) -> None:
    t = store.add_target("10.10.10.20", hostname="jenkins.local", os_name="Linux")
    store.add_service(target_id=t.id, port=8080, service="HTTP", version="Jenkins 2.300")
    store.add_finding(title="Jenkins unauthenticated dashboard", target_id=t.id)
    store.add_credential(username="admin", secret="secret", source="jenkins.xml", target_id=t.id)
    store.add_note("Discovered jenkins master key", target_id=t.id)
    store.add_evidence("jenkins_screenshot.png", target_id=t.id, description="Jenkins login")

    # Search for 'jenkins'
    matches = search_notebook(store, "jenkins")
    assert len(matches) >= 5

    types = {m.entity_type for m in matches}
    assert "target" in types
    assert "service" in types
    assert "finding" in types
    assert "credential" in types
    assert "note" in types
    assert "evidence" in types


def test_empty_search(store: NotebookStore) -> None:
    assert search_notebook(store, "") == []
    assert search_notebook(store, "   ") == []
    assert search_notebook(store, "nonexistent_term_xyz_123") == []
