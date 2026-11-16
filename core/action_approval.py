"""Human approval integration for MARK-L action executions."""

from __future__ import annotations

from typing import Any

from core.action_execution import ActionExecution, ActionExecutionStatus
from core.approval_center import ApprovalCenter
from core.capability_registry import CapabilityRegistry
from core.execution_engine import ExecutionEngine
from core.permissions import CapabilityRequest


class ActionApprovalIntegration:
    """Connects ActionExecution lifecycle state to existing approval infrastructure."""

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
        """Submit an approval-required execution to the existing approval chain."""

        if not isinstance(execution, ActionExecution):
            raise TypeError("execution must be an ActionExecution")

        if execution.status != ActionExecutionStatus.AWAITING_APPROVAL:
            raise ValueError(
                "execution must be AWAITING_APPROVAL before approval submission"
            )

        capability = execution.capability
        if not capability:
            raise ValueError("execution must have a classified capability")

        request = CapabilityRequest(
            capability=capability,
            action=execution.action,
            reason=execution.intent,
            context=context or {},
        )

        def approved_run() -> str:
            execution.approval = "APPROVED"
            self._engine.execute(
                execution,
                approval_granted=True,
                context=context,
            )
            return str(execution.result or "Done.")

        return self._approvals.request(
            mission_id=mission_id,
            task_id=task_id,
            capability_request=request,
            run=approved_run,
        )

    def approval_center(self) -> ApprovalCenter:
        return self._approvals
