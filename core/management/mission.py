"""Mission models for MARK-L's management layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Mission:
    """A high-level objective managed by the Management Manager."""

    objective: str
    context: dict[str, Any] = field(default_factory=dict)
    mission_id: str = field(default_factory=lambda: str(uuid4()))
    status: str = "CREATED"
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def __post_init__(self) -> None:
        if not isinstance(self.objective, str) or not self.objective.strip():
            raise ValueError("Mission objective must be a non-empty string.")

        if not isinstance(self.context, dict):
            raise TypeError("Mission context must be a dictionary.")

        self.objective = self.objective.strip()

    def update_status(self, status: str) -> None:
        """Update mission status."""
        if not isinstance(status, str) or not status.strip():
            raise ValueError("Mission status must be a non-empty string.")

        self.status = status.strip().upper()
        self.updated_at = _now()

    def to_dict(self) -> dict[str, Any]:
        """Serialize the mission."""
        return {
            "mission_id": self.mission_id,
            "objective": self.objective,
            "context": dict(self.context),
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Mission":
        """Restore a mission from serialized data."""
        if not isinstance(data, dict):
            raise TypeError("Mission data must be a dictionary.")

        return cls(
            objective=data["objective"],
            context=dict(data.get("context", {})),
            mission_id=data.get("mission_id", str(uuid4())),
            status=data.get("status", "CREATED"),
            created_at=data.get("created_at", _now()),
            updated_at=data.get("updated_at", _now()),
        )
