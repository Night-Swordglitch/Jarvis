"""Trusted execution bridge for actions requested by specialist agents."""

from __future__ import annotations

from typing import Any, Callable

from core.action_capabilities import capability_for_operation
from core.permission_bridge import PermissionBridge
from core.permissions import CapabilityRequest


class AgentActionExecutor:
    """
    Converts agent action requests into permission-gated trusted executions.

    Agents provide intent only. The host classifies the requested action and
    supplies the executable callback; agent-supplied capability labels are
    never trusted.
    """

    def __init__(
        self,
        action_runner: Callable[[str, dict[str, Any]], str],
        permission_bridge: PermissionBridge | None = None,
    ):
        if not callable(action_runner):
            raise TypeError("action_runner must be callable")

        self._action_runner = action_runner
        self._permissions = permission_bridge or PermissionBridge()

    def submit(self, request_data: dict[str, Any]) -> str:
        """Process one agent-generated action request safely."""

        if not isinstance(request_data, dict):
            return "Agent action request rejected: expected an object."

        raw_action = request_data.get("action", "")
        raw_reason = request_data.get("reason", "")
        context = request_data.get("context", {})

        if not isinstance(raw_action, str) or not raw_action.strip():
            return "Agent action request rejected: missing or invalid action."

        if not isinstance(raw_reason, str):
            return "Agent action request rejected: reason must be text."

        action = raw_action.strip()
        reason = raw_reason.strip()

        if not isinstance(context, dict):
            return (
                f"Agent action '{action}' rejected: "
                "context must be an object."
            )

        # Copy the top-level mapping so later caller mutations cannot replace
        # the parameters after the permission decision has been made.
        safe_context = dict(context)

        # Classify both direct actions and operation-specific requests.
        # Unknown actions fail closed. The agent's capability field is ignored.
        capability = capability_for_operation(action, safe_context)

        if capability is None:
            return (
                f"Agent action '{action}' denied: "
                "the host has not classified this action or operation."
            )

        request = CapabilityRequest(
            capability=capability,
            action=action,
            reason=reason,
            context=safe_context,
        )

        return self._permissions.submit(
            request,
            lambda: self._action_runner(action, safe_context),
        )
