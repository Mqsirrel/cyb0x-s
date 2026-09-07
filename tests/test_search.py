"""Tests for unified cross-entity SQLite FTS5 search with BM25 ranking."""

from glacis.db.store import NotebookStore
from glacis.search import search_notebook


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


def test_fts_prefix_and_multiword(store: NotebookStore) -> None:
    t = store.add_target("10.10.10.55", hostname="samba-server", os_name="Linux")
    store.add_service(target_id=t.id, port=445, service="smb", version="Samba 4.3")
    store.add_note("Ran enum4linux on domain controller", target_id=t.id)

    # Prefix match
    matches = search_notebook(store, "enum4*")
    assert len(matches) >= 1
    assert matches[0].entity_type == "note"

    # Multi-word AND match
    matches = search_notebook(store, "samba 4.3")
    assert len(matches) >= 1
    assert matches[0].entity_type == "service"


def test_fts_ranking_bm25(store: NotebookStore) -> None:
    t = store.add_target("10.10.10.60", hostname="db.local", os_name="Linux")
    # Item A: mentions mysql once
    store.add_note("Discovered port 3306 with mysql running", target_id=t.id)
    # Item B: title specifically about mysql and mentions mysql multiple times
    store.add_finding(
        title="MySQL unauthenticated root access",
        description="mysql database allows root mysql login without password",
        target_id=t.id,
    )

    matches = search_notebook(store, "mysql")
    assert len(matches) >= 2
    # Item with multiple mysql mentions and title match should rank higher (appear first)
    assert matches[0].entity_type == "finding"
    assert matches[0].score is not None
    assert matches[1].score is not None
    # SQLite BM25 returns lower (more negative) score for higher relevance
    assert matches[0].score <= matches[1].score


def test_fts_live_trigger_sync(store: NotebookStore) -> None:
    t = store.add_target("10.10.10.70", hostname="target-sync", os_name="Linux")
    note = store.add_note("Confidential token secret_jwt_token_9999", target_id=t.id)

    # Note is immediately findable
    matches = search_notebook(store, "secret_jwt_token_9999")
    assert len(matches) == 1

    # Delete note: should disappear from FTS immediately
    store.delete_note(note.id)
    matches = search_notebook(store, "secret_jwt_token_9999")
    assert len(matches) == 0


def test_rebuild_fts(store: NotebookStore) -> None:
    t = store.add_target("10.10.10.80", hostname="rebuild-test", os_name="Linux")
    store.add_service(target_id=t.id, port=22, service="ssh", version="OpenSSH 8.9")
    store.add_note("SSH key extracted", target_id=t.id)

    # Purge virtual table directly
    with store.conn:
        store.conn.execute("DELETE FROM notebook_fts;")

    # Search returns 0
    assert search_notebook(store, "OpenSSH") == []

    # Rebuild FTS
    store.rebuild_fts()

    # Search finds it again
    matches = search_notebook(store, "OpenSSH")
    assert len(matches) == 1
    assert matches[0].entity_type == "service"


def test_fts_syntax_fallback(store: NotebookStore) -> None:
    t = store.add_target("10.10.10.90", hostname="fallback-box", os_name="Linux")
    store.add_note("Special string with unmatched quotes and punctuation: foo'bar\"baz", target_id=t.id)

    # Even with weird characters, search succeeds without exception
    matches = search_notebook(store, "foo'bar\"baz")
    assert isinstance(matches, list)
