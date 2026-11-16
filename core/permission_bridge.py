"""Bridge between capability permissions and the human confirmation gate."""

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
    """Route trusted callbacks through deterministic permission policy."""

    def __init__(self, permission_manager: PermissionManager | None = None):
        self._permissions = permission_manager or PermissionManager()

    def submit(
        self,
        request: CapabilityRequest,
        run: Callable[[], str],
        *,
        approval_subject: str = "",
        on_rejected: Callable[[str], None] | None = None,
    ) -> str:
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
            if confirm.pending_title():
                return (
                    "There is already a confirmation waiting on screen. "
                    "Ask the user to answer that one first."
                )
            title = f"Approve {request.action}"
            detail = request.reason.strip() or (
                f"The action '{request.action}' requires explicit human "
                f"approval because it uses the {result.capability} capability."
            )
            return confirm.request(
                key=f"permission-{request.action}",
                title=title,
                detail=detail,
                run=run,
                approval_subject=approval_subject,
                on_rejected=on_rejected,
            )

        return f"Action '{request.action}' was not executed: unknown permission state."

    @staticmethod
    def _deny_message(result: PermissionResult) -> str:
        return (
            f"Action denied: capability '{result.capability}' is not "
            f"permitted. {result.reason}"
        )
