"""Strongly typed Textual messages for decoupled event-driven UI communication."""

from __future__ import annotations

from typing import Optional

from textual.message import Message

from cyb0x_s.models import ChecklistItem, Service, Target


class TargetSelected(Message):
    """Emitted when a target is highlighted or activated."""

    def __init__(self, target_id: int, target: Optional[Target] = None) -> None:
        super().__init__()
        self.target_id = target_id
        self.target = target


class TargetScopeToggled(Message):
    """Emitted when active target scope is toggled."""

    def __init__(self, target_id: int, is_in_scope: bool) -> None:
        super().__init__()
        self.target_id = target_id
        self.is_in_scope = is_in_scope


class ServiceSelected(Message):
    """Emitted when a service is highlighted or activated."""

    def __init__(self, service: Service, target_ip: str) -> None:
        super().__init__()
        self.service = service
        self.target_ip = target_ip


class ChecklistStepSelected(Message):
    """Emitted when a checklist methodology step is highlighted."""

    def __init__(self, item: ChecklistItem, target_ip: str) -> None:
        super().__init__()
        self.item = item
        self.target_ip = target_ip


class DomainDataChanged(Message):
    """Granular data invalidation event to refresh specific UI panels."""

    def __init__(self, domain: str, target_id: Optional[int] = None) -> None:
        super().__init__()
        self.domain = domain  # 'targets', 'services', 'creds', 'checklist', 'notes', 'failures'
        self.target_id = target_id
