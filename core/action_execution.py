"""Action execution lifecycle model for MARK-L.

This module represents the lifecycle of one concrete action execution.

It does not execute actions, enforce permissions, request approval,
collect evidence, perform verification, or implement retry policy.

Those responsibilities belong to later architecture layers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import uuid4

from core.permission_manager import PermissionDecision


class ActionExecutionStatus(str, Enum):
    """Lifecycle states for one action execution."""

    PENDING = "PENDING"
    POLICY_CHECK = "POLICY_CHECK"
    BLOCKED = "BLOCKED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    AUTHORIZED = "AUTHORIZED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    EXECUTING = "EXECUTING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"


_TERMINAL_STATES = frozenset(
    {
        ActionExecutionStatus.BLOCKED,
        ActionExecutionStatus.REJECTED,
        ActionExecutionStatus.CANCELLED,
        ActionExecutionStatus.SUCCEEDED,
        ActionExecutionStatus.FAILED,
        ActionExecutionStatus.TIMED_OUT,
    }
)


_ALLOWED_TRANSITIONS: dict[
    ActionExecutionStatus, frozenset[ActionExecutionStatus]
] = {
    ActionExecutionStatus.PENDING: frozenset(
        {
            ActionExecutionStatus.POLICY_CHECK,
            ActionExecutionStatus.CANCELLED,
        }
    ),
    ActionExecutionStatus.POLICY_CHECK: frozenset(
        {
            ActionExecutionStatus.BLOCKED,
            ActionExecutionStatus.AWAITING_APPROVAL,
            ActionExecutionStatus.AUTHORIZED,
            ActionExecutionStatus.CANCELLED,
        }
    ),
    ActionExecutionStatus.AWAITING_APPROVAL: frozenset(
        {
            ActionExecutionStatus.AUTHORIZED,
            ActionExecutionStatus.REJECTED,
            ActionExecutionStatus.CANCELLED,
        }
    ),
    ActionExecutionStatus.AUTHORIZED: frozenset(
        {
            ActionExecutionStatus.EXECUTING,
            ActionExecutionStatus.CANCELLED,
        }
    ),
    ActionExecutionStatus.EXECUTING: frozenset(
        {
            ActionExecutionStatus.SUCCEEDED,
            ActionExecutionStatus.FAILED,
            ActionExecutionStatus.TIMED_OUT,
        }
    ),
}


@dataclass
class ActionExecution:
    """Stateful representation of one action execution attempt.

    The object records lifecycle state. It has no authority to execute
    actions or approve permissions.
    """

    action: str
    capability: str
    parameters: dict[str, Any] = field(default_factory=dict)
    intent: str = ""
    mission_id: str = ""
    task_id: str = ""
    risk: str = ""
    reversibility: str = ""
    permission: PermissionDecision | None = None
    approval: str = ""
    status: ActionExecutionStatus = ActionExecutionStatus.PENDING
    result: Any = None
    evidence: Any = None
    verification: Any = None
    execution_id: str = field(
        default_factory=lambda: f"exec-{uuid4().hex}"
    )

    def __post_init__(self) -> None:
        if not isinstance(self.action, str) or not self.action.strip():
            raise ValueError("action must be a non-empty string")

        if not isinstance(self.capability, str) or not self.capability.strip():
            raise ValueError("capability must be a non-empty string")

        if not isinstance(self.parameters, dict):
            raise TypeError("parameters must be a dictionary")

        self.action = self.action.strip()
        self.capability = self.capability.strip().upper()

        if isinstance(self.permission, str):
            try:
                self.permission = PermissionDecision(
                    self.permission.strip().upper()
                )
            except ValueError as exc:
                raise ValueError(
                    f"Unknown permission decision: {self.permission!r}"
                ) from exc

        if isinstance(self.status, str):
            try:
                self.status = ActionExecutionStatus(
                    self.status.strip().upper()
                )
            except ValueError as exc:
                raise ValueError(
                    f"Unknown execution status: {self.status!r}"
                ) from exc

    @property
    def terminal(self) -> bool:
        """Return whether the execution has reached a terminal state."""

        return self.status in _TERMINAL_STATES

    @classmethod
    def allowed_transitions(
        cls,
        status: ActionExecutionStatus | str,
    ) -> set[ActionExecutionStatus]:
        """Return the states reachable from the supplied state."""

        current = cls._normalize_status(status)
        return set(_ALLOWED_TRANSITIONS.get(current, frozenset()))

    @classmethod
    def can_transition(
        cls,
        current: ActionExecutionStatus | str,
        target: ActionExecutionStatus | str,
    ) -> bool:
        """Return whether a lifecycle transition is valid."""

        current_status = cls._normalize_status(current)
        target_status = cls._normalize_status(target)

        return target_status in _ALLOWED_TRANSITIONS.get(
            current_status,
            frozenset(),
        )

    def transition(self, target: ActionExecutionStatus | str) -> None:
        """Move this execution to a valid lifecycle state.

        Invalid transitions are rejected rather than silently changing state.
        """

        target_status = self._normalize_status(target)

        if not self.can_transition(self.status, target_status):
            raise ValueError(
                f"Invalid action execution transition: "
                f"{self.status.value} -> {target_status.value}"
            )

        self.status = target_status

    def record_permission(
        self,
        decision: PermissionDecision | str,
    ) -> None:
        """Record the host-side permission decision.

        This records policy output; it does not grant permission itself.
        """

        if isinstance(decision, str):
            try:
                decision = PermissionDecision(decision.strip().upper())
            except ValueError as exc:
                raise ValueError(
                    f"Unknown permission decision: {decision!r}"
                ) from exc

        if not isinstance(decision, PermissionDecision):
            raise TypeError(
                "decision must be a PermissionDecision or string"
            )

        self.permission = decision

    def to_dict(self) -> dict[str, Any]:
        """Serialize the execution into a JSON-compatible dictionary."""

        permission = (
            self.permission.value
            if isinstance(self.permission, PermissionDecision)
            else None
        )

        return {
            "execution_id": self.execution_id,
            "mission_id": self.mission_id,
            "task_id": self.task_id,
            "action": self.action,
            "capability": self.capability,
            "parameters": dict(self.parameters),
            "intent": self.intent,
            "risk": self.risk,
            "reversibility": self.reversibility,
            "permission": permission,
            "approval": self.approval,
            "status": self.status.value,
            "result": self.result,
            "evidence": self.evidence,
            "verification": self.verification,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ActionExecution":
        """Restore an execution from serialized state."""

        if not isinstance(data, dict):
            raise TypeError("data must be a dictionary")

        return cls(
            execution_id=str(data.get("execution_id", "")).strip()
            or f"exec-{uuid4().hex}",
            mission_id=str(data.get("mission_id", "")),
            task_id=str(data.get("task_id", "")),
            action=data.get("action", ""),
            capability=data.get("capability", ""),
            parameters=dict(data.get("parameters", {})),
            intent=str(data.get("intent", "")),
            risk=str(data.get("risk", "")),
            reversibility=str(data.get("reversibility", "")),
            permission=data.get("permission"),
            approval=str(data.get("approval", "")),
            status=data.get(
                "status",
                ActionExecutionStatus.PENDING.value,
            ),
            result=data.get("result"),
            evidence=data.get("evidence"),
            verification=data.get("verification"),
        )

    @staticmethod
    def _normalize_status(
        status: ActionExecutionStatus | str,
    ) -> ActionExecutionStatus:
        if isinstance(status, ActionExecutionStatus):
            return status

        if isinstance(status, str):
            try:
                return ActionExecutionStatus(status.strip().upper())
            except ValueError as exc:
                raise ValueError(
                    f"Unknown execution status: {status!r}"
                ) from exc

        raise TypeError(
            "status must be an ActionExecutionStatus or string"
        )
