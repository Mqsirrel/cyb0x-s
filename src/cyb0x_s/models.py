"""Data models for CYB0X-S (Safe Field Notebook).

Strictly passive data structures representing operator-supplied observations.
No AI, no automatic classification, no dynamic attack generation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    """Return current UTC timestamp in ISO 8601 compatible format."""
    return datetime.now(timezone.utc)


class ChecklistStatus(str, Enum):
    """Explicit human-assigned checklist states."""
    TODO = "TODO"
    CHECKED = "CHECKED"
    DEFERRED = "DEFERRED"
    DEAD_END = "DEAD-END"

    @classmethod
    def from_str(cls, value: str) -> ChecklistStatus:
        """Parse status string safely."""
        val = value.strip().upper().replace(" ", "-").replace("_", "-")
        if val in ("CHECKED", "DONE", "COMPLETED"):
            return cls.CHECKED
        elif val in ("DEFERRED", "POSTPONED", "LATER"):
            return cls.DEFERRED
        elif val in ("DEAD-END", "DEADEND", "FAIL", "FAILED"):
            return cls.DEAD_END
        return cls.TODO

    def next_state(self) -> ChecklistStatus:
        """Cycle through states: TODO -> CHECKED -> DEFERRED -> DEAD-END -> TODO."""
        cycle = [ChecklistStatus.TODO, ChecklistStatus.CHECKED, ChecklistStatus.DEFERRED, ChecklistStatus.DEAD_END]
        idx = cycle.index(self)
        return cycle[(idx + 1) % len(cycle)]


class ServiceStatus(str, Enum):
    """Explicit human-assigned service investigation status."""
    UNTESTED = "UNTESTED"
    CHECKED = "CHECKED"
    DEFERRED = "DEFERRED"
    DEAD_END = "DEAD-END"

    @classmethod
    def from_str(cls, value: str) -> ServiceStatus:
        val = value.strip().upper().replace(" ", "-").replace("_", "-")
        if val in ("CHECKED", "DONE"):
            return cls.CHECKED
        elif val in ("DEFERRED", "LATER"):
            return cls.DEFERRED
        elif val in ("DEAD-END", "DEADEND"):
            return cls.DEAD_END
        return cls.UNTESTED


class SeverityLevel(str, Enum):
    """Optional manual severity assigned solely by the operator."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"

    @classmethod
    def from_str(cls, value: str) -> Optional[SeverityLevel]:
        val = value.strip().upper()
        for member in cls:
            if member.value == val:
                return member
        return None


class Workspace(BaseModel):
    """Top-level assessment or lab workspace."""
    id: Optional[int] = None
    name: str
    description: str = ""
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class Target(BaseModel):
    """Manually recorded target host."""
    id: Optional[int] = None
    workspace_id: int = 1
    ip: str
    hostname: str = ""
    os: str = "Unknown"
    notes: str = ""
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class Service(BaseModel):
    """Manually recorded service running on a target."""
    id: Optional[int] = None
    target_id: int
    port: int
    protocol: str = "tcp"
    service: str = "unknown"
    version: str = ""
    status: ServiceStatus = ServiceStatus.CHECKED
    notes: str = ""
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class Finding(BaseModel):
    """Security finding manually discovered by the operator."""
    id: Optional[int] = None
    target_id: Optional[int] = None
    title: str
    description: str = ""
    notes: str = ""
    severity: Optional[str] = None  # Optional user-chosen string or SeverityLevel
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class Credential(BaseModel):
    """Credential discovered by the user."""
    id: Optional[int] = None
    target_id: Optional[int] = None
    username: str
    secret: str
    source: str = ""
    service_scope: str = ""
    status: str = "untested"
    notes: str = ""
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    @property
    def masked_secret(self) -> str:
        """Default masked view of credential secret."""
        return "********"


class Lead(BaseModel):
    """Potential angle or lead noted by the operator."""
    id: Optional[int] = None
    target_id: Optional[int] = None
    title: str
    notes: str = ""
    status: str = "open"  # open, investigated, discarded
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class Evidence(BaseModel):
    """Reference to evidence, screenshot, or output recorded by operator."""
    id: Optional[int] = None
    target_id: Optional[int] = None
    evidence_type: str = "screenshot"  # screenshot, file, command_output, flag, other
    path_or_ref: str
    description: str = ""
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class Note(BaseModel):
    """Free-form field note."""
    id: Optional[int] = None
    target_id: Optional[int] = None
    content: str
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class ChecklistItem(BaseModel):
    """Manually controlled methodology checklist item."""
    id: Optional[int] = None
    target_id: Optional[int] = None
    category: str = "ENUMERATION"
    title: str
    status: ChecklistStatus = ChecklistStatus.TODO
    notes: str = ""
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class CommandRecord(BaseModel):
    """Command executed by the human operator recorded for audit trail."""
    id: Optional[int] = None
    target_id: Optional[int] = None
    command: str
    notes: str = ""
    created_at: datetime = Field(default_factory=_utcnow)
