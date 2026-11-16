"""Phase 7I — Human Approval Center.

This module does NOT replace core.confirm.

It provides a structured, serializable view of approval requests while
delegating the actual permission and human-confirmation authority to the
existing PermissionManager, PermissionBridge, and core.confirm chain.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from core import confirm
from core.permission_bridge import PermissionBridge
from core.permission_manager import PermissionDecision, PermissionManager
from core.permissions import CapabilityRequest


@dataclass
class ApprovalRequest:
    """Structured representation of a human approval request."""

    mission_id: str
    task_id: str
    action: str
    capability: str
    reason: str
    status: str = "PENDING"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.mission_id, str) or not self.mission_id.strip():
            raise ValueError("mission_id must be a non-empty string.")

        if not isinstance(self.task_id, str) or not self.task_id.strip():
            raise ValueError("task_id must be a non-empty string.")

        if not isinstance(self.action, str) or not self.action.strip():
            raise ValueError("action must be a non-empty string.")

        if not isinstance(self.capability, str) or not self.capability.strip():
            raise ValueError("capability must be a non-empty string.")

        if not isinstance(self.reason, str):
            raise TypeError("reason must be a string.")

        if self.status not in {
            "PENDING",
            "APPROVED",
            "REJECTED",
            "EXPIRED",
            "DENIED",
        }:
            raise ValueError(f"Unknown approval status: {self.status}")

        self.mission_id = self.mission_id.strip()
        self.task_id = self.task_id.strip()
        self.action = self.action.strip()
        self.capability = self.capability.strip().upper()

    def to_dict(self) -> dict[str, Any]:
        return {
            "mission_id": self.mission_id,
            "task_id": self.task_id,
            "action": self.action,
            "capability": self.capability,
            "reason": self.reason,
            "status": self.status,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ApprovalRequest":
        if not isinstance(data, dict):
            raise TypeError("Approval data must be a dictionary.")

        return cls(
            mission_id=data["mission_id"],
            task_id=data["task_id"],
            action=data["action"],
            capability=data["capability"],
            reason=data.get("reason", ""),
            status=data.get("status", "PENDING"),
            metadata=dict(data.get("metadata", {})),
        )


class ApprovalCenter:
    """Human-approval orchestration and state projection.

    Authority rules:
      - PermissionManager decides whether approval is required.
      - PermissionBridge routes approval-required actions.
      - core.confirm owns the actual human confirmation.
      - ApprovalCenter never resolves confirmation itself.
      - ApprovalCenter never executes an action directly.
    """

    def __init__(
        self,
        permission_manager: PermissionManager | None = None,
        permission_bridge: PermissionBridge | None = None,
    ) -> None:
        if permission_bridge is not None and not isinstance(
            permission_bridge,
            PermissionBridge,
        ):
            raise TypeError("permission_bridge must be a PermissionBridge.")

        self._permissions = permission_manager or PermissionManager()
        self._bridge = permission_bridge or PermissionBridge(self._permissions)

        self._pending: dict[str, ApprovalRequest] = {}
        self._history: list[ApprovalRequest] = []

    def request(
        self,
        *,
        mission_id: str,
        task_id: str,
        capability_request: CapabilityRequest,
        run: Callable[[], str],
    ) -> str:
        """Submit a trusted action through the existing permission chain."""

        if not isinstance(capability_request, CapabilityRequest):
            raise TypeError(
                "capability_request must be a CapabilityRequest."
            )

        if not callable(run):
            raise TypeError("run must be callable.")

        result = self._permissions.evaluate(capability_request)

        if result.decision == PermissionDecision.DENY:
            approval = ApprovalRequest(
                mission_id=mission_id,
                task_id=task_id,
                action=capability_request.action,
                capability=result.capability,
                reason=result.reason,
                status="DENIED",
            )
            self._history.append(approval)
            return self._bridge.submit(capability_request, run)

        if result.decision == PermissionDecision.ALLOW:
            return self._bridge.submit(capability_request, run)

        if confirm.pending_title():
            return (
                "There is already a confirmation waiting on screen. "
                "Ask the user to answer that one first."
            )

        approval = ApprovalRequest(
            mission_id=mission_id,
            task_id=task_id,
            action=capability_request.action,
            capability=result.capability,
            reason=(
                capability_request.reason.strip()
                or result.reason
            ),
            status="PENDING",
        )

        self._pending[approval.task_id] = approval

        response = self._bridge.submit(capability_request, run)

        # If the bridge could not actually place the confirmation,
        # do not falsely advertise a pending approval.
        if not confirm.pending_title():
            self._pending.pop(approval.task_id, None)
            approval.status = "DENIED"
            self._history.append(approval)

        return response

    def pending(self) -> list[ApprovalRequest]:
        """Return current pending approval projections."""
        active: list[ApprovalRequest] = []

        for task_id, approval in list(self._pending.items()):
            if not confirm.pending_title():
                approval.status = "EXPIRED"
                self._history.append(approval)
                self._pending.pop(task_id, None)
                continue

            active.append(approval)

        return list(active)

    def pending_dicts(self) -> list[dict[str, Any]]:
        return [approval.to_dict() for approval in self.pending()]

    def history(self) -> list[ApprovalRequest]:
        return list(self._history)

    def history_dicts(self) -> list[dict[str, Any]]:
        return [approval.to_dict() for approval in self._history]

    def snapshot(self) -> dict[str, Any]:
        return {
            "pending": self.pending_dicts(),
            "history": self.history_dicts(),
            "pending_count": len(self.pending()),
        }

    def clear_projection(self, task_id: str) -> None:
        """Remove a projection without resolving the actual confirmation.

        This only changes ApprovalCenter's read model. It deliberately does
        not call core.confirm.resolve().
        """
        self._pending.pop(task_id, None)
