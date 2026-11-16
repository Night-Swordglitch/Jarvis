"""Human approval integration for trusted action executions."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from core.action_execution import ActionExecution, ActionExecutionStatus
from core.approval_center import ApprovalCenter
from core.execution_engine import ExecutionEngine
from core.permissions import CapabilityRequest


_SENSITIVE_KEY_PARTS = (
    "password", "token", "secret", "api_key", "apikey", "credential"
)


def _safe_parameters(value: Any) -> Any:
    """Redact common secret-bearing fields from the human approval summary."""
    if isinstance(value, dict):
        cleaned = {}
        for key, item in value.items():
            key_text = str(key)
            if any(part in key_text.lower() for part in _SENSITIVE_KEY_PARTS):
                cleaned[key_text] = "[REDACTED]"
            else:
                cleaned[key_text] = _safe_parameters(item)
        return cleaned
    if isinstance(value, list):
        return [_safe_parameters(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_safe_parameters(item) for item in value)
    return value


class ActionApprovalIntegration:
    """Connect execution lifecycle to the one-time human approval gate."""

    def __init__(
        self,
        engine: ExecutionEngine,
        approval_center: ApprovalCenter | None = None,
    ) -> None:
        if not isinstance(engine, ExecutionEngine):
            raise TypeError("engine must be an ExecutionEngine")
        self._engine = engine
        self._approvals = approval_center or ApprovalCenter()

    def submit(
        self,
        execution: ActionExecution,
        *,
        mission_id: str,
        task_id: str,
        context: dict[str, Any] | None = None,
    ) -> str:
        if not isinstance(execution, ActionExecution):
            raise TypeError("execution must be an ActionExecution")
        if execution.status != ActionExecutionStatus.AWAITING_APPROVAL:
            raise ValueError("execution must be AWAITING_APPROVAL before approval submission")
        if not execution.capability:
            raise ValueError("execution must have a classified capability")
        if not isinstance(context, (dict, type(None))):
            raise TypeError("context must be a dictionary")

        try:
            safe_context = deepcopy(context) if context is not None else {}
            safe_parameters = _safe_parameters(deepcopy(execution.parameters))
        except Exception as exc:
            execution.transition(ActionExecutionStatus.REJECTED)
            execution.result = "Approval rejected: request data could not be safely copied."
            raise ValueError(execution.result) from exc

        reason = execution.intent.strip() or "This action requires explicit approval."
        reason += f"\nAction: {execution.action}\nParameters: {safe_parameters!r}"

        request = CapabilityRequest(
            capability=execution.capability,
            action=execution.action,
            reason=reason,
            context=safe_context,
        )

        def approved_run() -> str:
            self._engine.execute(execution, context=safe_context)
            return str(execution.result or "Execution finished.")

        def rejected(status: str) -> None:
            self._engine.reject_pending_approval(
                execution, f"Human approval {status.lower()}."
            )

        response = self._approvals.request(
            mission_id=mission_id,
            task_id=task_id,
            capability_request=request,
            run=approved_run,
            approval_subject=execution.execution_id,
            on_rejected=rejected,
        )
        if not response.startswith("[CONFIRMATION_PENDING]"):
            self._engine.reject_pending_approval(
                execution, "Approval could not be queued; action was not executed."
            )
        return response

    def approval_center(self) -> ApprovalCenter:
        return self._approvals
