"""Trusted execution engine with execution-bound human approval."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from core import confirm
from core.action_execution import ActionExecution, ActionExecutionStatus
from core.action_loader import ActionRegistry
from core.capability_registry import CapabilityRegistry
from core.permission_manager import PermissionDecision, PermissionManager


class ExecutionEngine:
    """Orchestrate policy checks, one-time approval and trusted execution."""

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
        self._approval_snapshots: dict[str, tuple[ActionExecution, str, dict[str, Any]]] = {}

    def reject_pending_approval(self, execution: ActionExecution, reason: str) -> None:
        """Close a pending approval without executing its action."""
        if not isinstance(execution, ActionExecution):
            raise TypeError("execution must be an ActionExecution")
        if execution.status != ActionExecutionStatus.AWAITING_APPROVAL:
            return
        confirm.revoke_approval(execution.execution_id)
        self._approval_snapshots.pop(execution.execution_id, None)
        execution.transition(ActionExecutionStatus.REJECTED)
        execution.result = reason

    def execute(
        self,
        execution: ActionExecution,
        *,
        context: dict[str, Any] | None = None,
    ) -> ActionExecution:
        """Execute an action; approval-required actions need a UI-issued grant."""

        if not isinstance(execution, ActionExecution):
            raise TypeError("execution must be an ActionExecution")
        if context is not None and not isinstance(context, dict):
            raise TypeError("context must be a dictionary")

        if execution.status == ActionExecutionStatus.PENDING:
            execution.transition(ActionExecutionStatus.POLICY_CHECK)

            capability = self._capabilities.capability_for_operation(
                execution.action, execution.parameters
            )
            if capability is None:
                capability = self._capabilities.capability_for_action(
                    execution.action
                )

            if capability is None:
                execution.record_permission(PermissionDecision.DENY)
                execution.transition(ActionExecutionStatus.BLOCKED)
                execution.result = f"Action '{execution.action}' is not classified."
                return execution

            execution.capability = capability
            permission = self._permissions.check(capability)
            execution.record_permission(permission.decision)

            if permission.decision == PermissionDecision.DENY:
                execution.transition(ActionExecutionStatus.BLOCKED)
                execution.result = permission.reason
                return execution

            if permission.decision == PermissionDecision.APPROVAL_REQUIRED:
                try:
                    snapshot = deepcopy(execution.parameters)
                except Exception:
                    execution.transition(ActionExecutionStatus.BLOCKED)
                    execution.result = "Action parameters could not be safely snapshotted."
                    return execution
                self._approval_snapshots[execution.execution_id] = (
                    execution,
                    execution.action,
                    snapshot,
                )
                execution.transition(ActionExecutionStatus.AWAITING_APPROVAL)
                execution.result = permission.reason
                return execution

            execution.transition(ActionExecutionStatus.AUTHORIZED)

        elif execution.status == ActionExecutionStatus.AWAITING_APPROVAL:
            snapshot = self._approval_snapshots.get(execution.execution_id)
            if snapshot is None:
                raise ValueError(
                    "No active approval snapshot exists for this execution."
                )

            approved_execution, approved_action, approved_parameters = snapshot
            if execution is not approved_execution:
                raise ValueError(
                    "Approval is bound to a different execution object."
                )

            if (
                execution.action != approved_action
                or execution.parameters != approved_parameters
            ):
                confirm.revoke_approval(execution.execution_id)
                self._approval_snapshots.pop(execution.execution_id, None)
                execution.transition(ActionExecutionStatus.REJECTED)
                execution.result = (
                    "Execution rejected because its action or parameters "
                    "changed after the approval request."
                )
                raise ValueError(execution.result)

            if not confirm.consume_approval(execution.execution_id):
                raise PermissionError(
                    "A one-time human approval from the confirmation UI "
                    "is required to resume this execution."
                )

            self._approval_snapshots.pop(execution.execution_id, None)
            execution.approval = "APPROVED"
            execution.transition(ActionExecutionStatus.AUTHORIZED)

        else:
            raise ValueError(
                "Execution must begin in PENDING or resume from "
                "AWAITING_APPROVAL."
            )

        execution.transition(ActionExecutionStatus.EXECUTING)
        try:
            run_parameters = deepcopy(execution.parameters)
            run_context = deepcopy(context) if context is not None else {}
            result = self._actions.run(
                execution.action, run_parameters, ctx=run_context
            )
            execution.result = result
            execution.transition(ActionExecutionStatus.SUCCEEDED)
        except Exception as exc:
            execution.result = str(exc)
            execution.transition(ActionExecutionStatus.FAILED)
        return execution
