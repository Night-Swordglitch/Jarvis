"""Trusted execution bridge for actions requested by specialist agents."""

from __future__ import annotations

from typing import Any, Callable

from core.action_capabilities import capability_for_action
from core.permission_bridge import PermissionBridge
from core.permissions import CapabilityRequest


class AgentActionExecutor:
    """
    Converts agent action requests into permission-gated trusted executions.

    Agents provide intent only. The host determines the capability and
    supplies the executable callback.
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

        action = str(request_data.get("action", "")).strip()
        reason = str(request_data.get("reason", "")).strip()
        context = request_data.get("context", {})
        print("[AGENT-FIDELITY] action=" + repr(action) + " context=" + repr(context))

        if not action:
            return "Agent action request rejected: missing action."

        if not isinstance(context, dict):
            return (
                f"Agent action '{action}' rejected: "
                "context must be an object."
            )

        # The agent's capability field is deliberately ignored.
        capability = capability_for_action(action)

        if capability is None:
            return (
                f"Agent action '{action}' denied: "
                "the host has not classified this action."
            )

        request = CapabilityRequest(
            capability=capability,
            action=action,
            reason=reason,
            context=context,
        )

        return self._permissions.submit(
            request,
            lambda: self._action_runner(action, context),
        )

