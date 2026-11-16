"""Central capability permission policy for MARK-L."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from core.permissions import CapabilityRequest


class PermissionDecision(str, Enum):
    """Deterministic permission outcomes."""

    ALLOW = "ALLOW"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    DENY = "DENY"


@dataclass(frozen=True)
class PermissionResult:
    """Result of a deterministic capability check."""

    capability: str
    decision: PermissionDecision
    reason: str
    action: str = ""

    @property
    def allowed(self) -> bool:
        """Whether the capability is currently permitted."""
        return self.decision != PermissionDecision.DENY

    @property
    def requires_approval(self) -> bool:
        """Whether explicit human approval is required."""
        return self.decision == PermissionDecision.APPROVAL_REQUIRED

    def to_dict(self) -> dict[str, str | bool]:
        """Return a serializable representation."""
        return {
            "capability": self.capability,
            "action": self.action,
            "decision": self.decision.value,
            "reason": self.reason,
            "allowed": self.allowed,
            "requires_approval": self.requires_approval,
        }


class PermissionManager:
    """
    Central deterministic capability policy.

    The PermissionManager decides whether a capability is:
      - automatically allowed,
      - allowed only after human approval, or
      - denied.

    It never executes an action and never replaces core.confirm.
    """

    _AUTO_ALLOW = frozenset(
        {
            "READ",
            "ANALYZE",
            "DRAFT",
        }
    )

    _REQUIRES_APPROVAL = frozenset(
        {
            "PUBLISH",
            "DELETE",
            "SPEND",
            "FINANCIAL",
        }
    )

    def check(self, capability: str) -> PermissionResult:
        """Evaluate a raw capability name."""
        normalized = self._normalize(capability)

        if normalized in self._AUTO_ALLOW:
            return PermissionResult(
                capability=normalized,
                action="",
                decision=PermissionDecision.ALLOW,
                reason=f"{normalized} is an automatically permitted capability.",
            )

        if normalized in self._REQUIRES_APPROVAL:
            return PermissionResult(
                capability=normalized,
                action="",
                decision=PermissionDecision.APPROVAL_REQUIRED,
                reason=f"{normalized} requires explicit human approval.",
            )

        return PermissionResult(
            capability=normalized,
            action="",
            decision=PermissionDecision.DENY,
            reason=f"Unknown capability '{normalized}' is denied by default.",
        )

    def evaluate(self, request: CapabilityRequest) -> PermissionResult:
        """
        Evaluate a structured capability request.

        The request itself never grants permission. The deterministic
        policy decides the result.
        """
        if not isinstance(request, CapabilityRequest):
            raise TypeError("evaluate() requires a CapabilityRequest")

        result = self.check(request.capability)

        return PermissionResult(
            capability=result.capability,
            action=request.action,
            decision=result.decision,
            reason=result.reason,
        )

    @staticmethod
    def _normalize(capability: str) -> str:
        """Normalize capability input without changing its meaning."""
        if not isinstance(capability, str):
            return ""

        return capability.strip().upper()
