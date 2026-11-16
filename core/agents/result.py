"""Agent result primitives."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class AgentResult:
    """Standard result returned by every agent."""

    agent_name: str
    task_id: str
    status: str
    summary: str = ""
    findings: list[str] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)
    actions_requested: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    completed_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @property
    def success(self) -> bool:
        """Whether the agent completed successfully."""
        return self.status.upper() in {"SUCCESS", "PARTIAL"}

    def to_dict(self) -> dict[str, Any]:
        """Return a serializable representation."""
        return {
            "agent_name": self.agent_name,
            "task_id": self.task_id,
            "status": self.status,
            "summary": self.summary,
            "findings": list(self.findings),
            "data": dict(self.data),
            "actions_requested": list(self.actions_requested),
            "errors": list(self.errors),
            "completed_at": self.completed_at,
        }

