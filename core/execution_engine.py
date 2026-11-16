"""Trusted execution engine for MARK-L action executions."""

from __future__ import annotations

from typing import Any

from core.action_execution import ActionExecution, ActionExecutionStatus
from core.action_loader import ActionRegistry
from core.capability_registry import CapabilityRegistry
from core.permission_manager import PermissionDecision, PermissionManager


class ExecutionEngine:
    """Orchestrates ActionExecution through policy and trusted execution."""

    def __init__(
        self,
        action_registry: ActionRegistry,
        capability_registry: CapabilityRegistry | None = None,
        permission_manager: PermissionManager | None = None,
    ) -> None:
        if not isinstance(action_registry, ActionRegistry):
            raise TypeError("action_registry must be an ActionRegistry")

        self._actions = action_registry
        self._capabilities = capability_registry or CapabilityRegistry()
        self._permissions = permission_manager or PermissionManager()

    def execute(
        self,
        execution: ActionExecution,
        *,
        approval_granted: bool = False,
        context: dict[str, Any] | None = None,
    ) -> ActionExecution:
        """Drive one execution through policy and trusted action execution."""

        if not isinstance(execution, ActionExecution):
            raise TypeError("execution must be an ActionExecution")

        # Normal execution begins at PENDING.
        if execution.status == ActionExecutionStatus.PENDING:
            execution.transition(ActionExecutionStatus.POLICY_CHECK)

            capability = self._capabilities.capability_for_operation(
                execution.action,
                execution.parameters,
            )
            if capability is None:
                capability = self._capabilities.capability_for_action(
                    execution.action
                )

            if capability is None:
                execution.record_permission(PermissionDecision.DENY)
                execution.transition(ActionExecutionStatus.BLOCKED)
                execution.result = (
                    f"Action '{execution.action}' is not classified."
                )
                return execution

            execution.capability = capability

            permission = self._permissions.check(capability)
            execution.record_permission(permission.decision)

            if permission.decision == PermissionDecision.DENY:
                execution.transition(ActionExecutionStatus.BLOCKED)
                execution.result = permission.reason
                return execution

            if permission.decision == PermissionDecision.APPROVAL_REQUIRED:
                if not approval_granted:
                    execution.transition(
                        ActionExecutionStatus.AWAITING_APPROVAL
                    )
                    execution.result = permission.reason
                    return execution

                execution.approval = "APPROVED"

            execution.transition(ActionExecutionStatus.AUTHORIZED)

        # Approval has already happened through core.confirm.
        elif execution.status == ActionExecutionStatus.AWAITING_APPROVAL:
            if not approval_granted:
                raise ValueError(
                    "approval_granted=True is required to resume "
                    "an approval-waiting execution"
                )

            execution.approval = "APPROVED"
            execution.transition(ActionExecutionStatus.AUTHORIZED)

        else:
            raise ValueError(
                "execution must begin in PENDING or resume from "
                "AWAITING_APPROVAL"
            )

        execution.transition(ActionExecutionStatus.EXECUTING)

        run_context = context or {}

        try:
            result = self._actions.run(
                execution.action,
                execution.parameters,
                ctx=run_context,
            )
            execution.result = result
            execution.transition(ActionExecutionStatus.SUCCEEDED)
        except Exception as exc:
            execution.result = str(exc)
            execution.transition(ActionExecutionStatus.FAILED)

        return execution

