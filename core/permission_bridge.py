"""Bridge between capability permissions and the existing human confirmation gate."""

from __future__ import annotations

from typing import Callable

from core import confirm
from core.permission_manager import (
    PermissionDecision,
    PermissionManager,
    PermissionResult,
)
from core.permissions import CapabilityRequest


class PermissionBridge:
    """
    Apply permission decisions to trusted executable callbacks.

    The callback passed to submit() MUST come from the trusted host/action
    layer. Agents may provide the CapabilityRequest, but they never provide
    permission and never control confirmation resolution.
    """

    def __init__(self, permission_manager: PermissionManager | None = None):
        self._permissions = permission_manager or PermissionManager()

    def submit(
        self,
        request: CapabilityRequest,
        run: Callable[[], str],
    ) -> str:
        """
        Evaluate a capability request and either execute, queue confirmation,
        or deny it.

        Returns a user/model-facing status string.

        The executable callback is deliberately supplied separately from the
        agent-generated CapabilityRequest.
        """
        if not isinstance(request, CapabilityRequest):
            raise TypeError("request must be a CapabilityRequest")

        if not callable(run):
            raise TypeError("run must be callable")

        result = self._permissions.evaluate(request)

        if result.decision == PermissionDecision.DENY:
            return self._deny_message(result)

        if result.decision == PermissionDecision.ALLOW:
            try:
                return run() or "Done."
            except Exception as exc:
                return f"Action '{request.action}' failed: {exc}"

        if result.decision == PermissionDecision.APPROVAL_REQUIRED:
            return self._request_confirmation(request, result, run)

        # Defensive fallback. The enum currently makes this unreachable.
        return (
            f"Action '{request.action}' was not executed because its "
            f"permission state is unknown."
        )

    @staticmethod
    def _deny_message(result: PermissionResult) -> str:
        return (
            f"Action denied: capability '{result.capability}' is not "
            f"permitted. {result.reason}"
        )

    @staticmethod
    def _request_confirmation(
        request: CapabilityRequest,
        result: PermissionResult,
        run: Callable[[], str],
    ) -> str:
        """Place an approval-required action behind core.confirm."""
        if confirm.pending_title():
            return (
                "There is already a confirmation waiting on screen. "
                "Ask the user to answer that one first."
            )

        title = f"Approve {request.action}"

        detail = request.reason.strip()
        if not detail:
            detail = (
                f"The action '{request.action}' requires explicit human "
                f"approval because it uses the {result.capability} capability."
            )

        return confirm.request(
            key=f"permission-{request.action}",
            title=title,
            detail=detail,
            run=run,
        )
