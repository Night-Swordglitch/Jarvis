"""Human approval orchestration and read model for MARK-L."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock
from typing import Any, Callable

from core import confirm
from core.permission_bridge import PermissionBridge
from core.permission_manager import PermissionDecision, PermissionManager
from core.permissions import CapabilityRequest


@dataclass
class ApprovalRequest:
    mission_id: str
    task_id: str
    action: str
    capability: str
    reason: str
    status: str = "PENDING"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("mission_id", "task_id", "action", "capability"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string.")
            setattr(self, name, value.strip())
        if not isinstance(self.reason, str):
            raise TypeError("reason must be a string.")
        if self.status not in {"PENDING", "APPROVED", "REJECTED", "EXPIRED", "DENIED"}:
            raise ValueError(f"Unknown approval status: {self.status}")
        self.capability = self.capability.upper()

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
    """Track approval projections while core.confirm retains decision authority."""

    def __init__(
        self,
        permission_manager: PermissionManager | None = None,
        permission_bridge: PermissionBridge | None = None,
    ) -> None:
        if permission_bridge is not None and not isinstance(permission_bridge, PermissionBridge):
            raise TypeError("permission_bridge must be a PermissionBridge.")
        self._permissions = permission_manager or PermissionManager()
        self._bridge = permission_bridge or PermissionBridge(self._permissions)
        self._pending: dict[str, ApprovalRequest] = {}
        self._history: list[ApprovalRequest] = []
        self._lock = RLock()

    def request(
        self,
        *,
        mission_id: str,
        task_id: str,
        capability_request: CapabilityRequest,
        run: Callable[[], str],
        approval_subject: str = "",
        on_approved: Callable[[], None] | None = None,
        on_rejected: Callable[[str], None] | None = None,
    ) -> str:
        if not isinstance(capability_request, CapabilityRequest):
            raise TypeError("capability_request must be a CapabilityRequest.")
        if not callable(run):
            raise TypeError("run must be callable.")
        if not isinstance(approval_subject, str):
            raise TypeError("approval_subject must be a string.")

        result = self._permissions.evaluate(capability_request)
        if result.decision == PermissionDecision.DENY:
            approval = ApprovalRequest(
                mission_id=mission_id, task_id=task_id,
                action=capability_request.action, capability=result.capability,
                reason=result.reason, status="DENIED",
            )
            with self._lock:
                self._history.append(approval)
            return self._bridge.submit(capability_request, run)

        if result.decision == PermissionDecision.ALLOW:
            return self._bridge.submit(capability_request, run)

        with self._lock:
            if task_id in self._pending:
                return "An approval already exists for this task."
            approval = ApprovalRequest(
                mission_id=mission_id, task_id=task_id,
                action=capability_request.action, capability=result.capability,
                reason=capability_request.reason.strip() or result.reason,
                metadata={"execution_id": approval_subject} if approval_subject else {},
            )
            self._pending[task_id] = approval

        def mark_rejected(status: str) -> None:
            with self._lock:
                current = self._pending.pop(task_id, None)
                if current is not None:
                    current.status = status if status in {"REJECTED", "EXPIRED", "DENIED"} else "DENIED"
                    self._history.append(current)
            if on_rejected:
                on_rejected(status)

        def approved_run() -> str:
            with self._lock:
                current = self._pending.pop(task_id, None)
                if current is not None:
                    current.status = "APPROVED"
                    self._history.append(current)
            if on_approved:
                on_approved()
            return run()

        response = self._bridge.submit(
            capability_request,
            approved_run,
            approval_subject=approval_subject,
            on_rejected=mark_rejected,
        )

        if not response.startswith("[CONFIRMATION_PENDING]"):
            mark_rejected("DENIED")
        return response

    def pending(self) -> list[ApprovalRequest]:
        # This call also triggers lazy expiry in core.confirm.
        confirm.pending_title()
        with self._lock:
            return list(self._pending.values())

    def pending_dicts(self) -> list[dict[str, Any]]:
        return [item.to_dict() for item in self.pending()]

    def history(self) -> list[ApprovalRequest]:
        with self._lock:
            return list(self._history)

    def history_dicts(self) -> list[dict[str, Any]]:
        return [item.to_dict() for item in self.history()]

    def snapshot(self) -> dict[str, Any]:
        pending = self.pending_dicts()
        return {
            "pending": pending,
            "history": self.history_dicts(),
            "pending_count": len(pending),
        }

    def clear_projection(self, task_id: str) -> None:
        """Remove only the read-model projection; never resolves the HUD prompt."""
        with self._lock:
            self._pending.pop(task_id, None)
