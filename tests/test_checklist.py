"""Tests for methodology checklists and static templates."""

import pytest
from cyb0x_s.db.store import NotebookStore
from cyb0x_s.models import ChecklistStatus
from cyb0x_s.templates import (
    apply_template_to_store,
    get_available_templates,
    load_template,
)


def test_static_template_loading() -> None:
    templates = get_available_templates()
    assert "linux" in templates
    assert "windows" in templates
    assert "web" in templates
    assert "smb" in templates
    assert "privesc" in templates
    assert "pivoting" in templates

    linux_tmpl = load_template("linux")
    assert linux_tmpl is not None
    assert linux_tmpl["category"] == "LINUX ENUMERATION"
    assert len(linux_tmpl["items"]) >= 5


def test_apply_template(store: NotebookStore) -> None:
    t = store.add_target("10.10.10.20")
    items = apply_template_to_store(store, "smb", target_id=t.id)
    assert len(items) > 0

    retrieved = store.list_checklist_items(target_id=t.id, category="SMB ENUMERATION")
    assert len(retrieved) == len(items)
    for item in retrieved:
        assert item.status == ChecklistStatus.TODO


def test_invalid_template_raises_error(store: NotebookStore) -> None:
    with pytest.raises(ValueError, match="Unknown template"):
        apply_template_to_store(store, "nonexistent_template")
