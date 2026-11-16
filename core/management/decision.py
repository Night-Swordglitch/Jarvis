"""Structured decisions produced by MARK-L's future Management Manager."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class DecisionType(str, Enum):
    """Allowed high-level management decisions."""

    CONTINUE = "CONTINUE"
    REPLAN = "REPLAN"
    CLARIFY = "CLARIFY"
    WAIT = "WAIT"
    APPROVAL = "APPROVAL"
    BLOCKED = "BLOCKED"
    COMPLETE = "COMPLETE"


@dataclass
class ManagementDecision:
    """A structured management decision.

    This model describes what Management wants to happen.
    It does not execute anything.
    """

    decision: DecisionType
    reason: str = ""
    tasks_to_start: list[str] = field(default_factory=list)
    tasks_to_pause: list[str] = field(default_factory=list)
    tasks_to_cancel: list[str] = field(default_factory=list)
    clarification_question: str | None = None
    user_update: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if isinstance(self.decision, str):
            self.decision = DecisionType(self.decision.upper())

        if not isinstance(self.decision, DecisionType):
            raise TypeError("decision must be a DecisionType.")

        if not isinstance(self.reason, str):
            raise TypeError("reason must be a string.")

        if not isinstance(self.user_update, str):
            raise TypeError("user_update must be a string.")

        if self.clarification_question is not None and not isinstance(
            self.clarification_question,
            str,
        ):
            raise TypeError("clarification_question must be a string or None.")

    def to_dict(self) -> dict[str, Any]:
        """Serialize the decision."""
        return {
            "decision": self.decision.value,
            "reason": self.reason,
            "tasks_to_start": list(self.tasks_to_start),
            "tasks_to_pause": list(self.tasks_to_pause),
            "tasks_to_cancel": list(self.tasks_to_cancel),
            "clarification_question": self.clarification_question,
            "user_update": self.user_update,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ManagementDecision":
        """Restore a decision from serialized data."""
        if not isinstance(data, dict):
            raise TypeError("Decision data must be a dictionary.")

        return cls(
            decision=data["decision"],
            reason=data.get("reason", ""),
            tasks_to_start=list(data.get("tasks_to_start", [])),
            tasks_to_pause=list(data.get("tasks_to_pause", [])),
            tasks_to_cancel=list(data.get("tasks_to_cancel", [])),
            clarification_question=data.get("clarification_question"),
            user_update=data.get("user_update", ""),
            metadata=dict(data.get("metadata", {})),
        )
