"""Agent task primitives."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4
from typing import Any


@dataclass
class AgentTask:
    """A unit of work assigned to an agent."""

    objective: str
    context: dict[str, Any] = field(default_factory=dict)
    requested_by: str = "master"
    priority: int = 50
    task_id: str = field(default_factory=lambda: uuid4().hex)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def describe(self) -> str:
        """Return a compact human-readable description."""
        return (
            f"Task {self.task_id}: "
            f"{self.objective} "
            f"(requested_by={self.requested_by}, priority={self.priority})"
        )
