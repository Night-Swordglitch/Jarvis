"""Phase 8D — Action Execution Lifecycle contract test."""

from core.action_execution import (
    ActionExecution,
    ActionExecutionStatus,
)
from core.permission_manager import PermissionDecision


def check(label: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(label)
    print(f"{label}: PASS")


print("=== PHASE 8D — ACTION EXECUTION LIFECYCLE TEST ===")

# Foundation
execution = ActionExecution(
    action="web_search",
    capability="READ",
    parameters={"query": "MARK-L"},
    intent="Research MARK-L architecture",
    mission_id="mission-001",
    task_id="task-001",
)

check(
    "Execution foundation",
    execution.status == ActionExecutionStatus.PENDING,
)

check(
    "Execution ID generation",
    execution.execution_id.startswith("exec-"),
)

# Valid lifecycle transitions
execution.transition(ActionExecutionStatus.POLICY_CHECK)

check(
    "Pending to policy check",
    execution.status == ActionExecutionStatus.POLICY_CHECK,
)

execution.record_permission(PermissionDecision.ALLOW)
execution.transition(ActionExecutionStatus.AUTHORIZED)

check(
    "ALLOW to authorized",
    execution.status == ActionExecutionStatus.AUTHORIZED,
)

execution.transition(ActionExecutionStatus.EXECUTING)

check(
    "Authorized to executing",
    execution.status == ActionExecutionStatus.EXECUTING,
)

execution.transition(ActionExecutionStatus.SUCCEEDED)

check(
    "Executing to succeeded",
    execution.status == ActionExecutionStatus.SUCCEEDED,
)

check(
    "Terminal state detection",
    execution.terminal,
)

# Approval path
approval = ActionExecution(
    action="publish_result",
    capability="PUBLISH",
)

approval.transition(ActionExecutionStatus.POLICY_CHECK)
approval.record_permission(PermissionDecision.APPROVAL_REQUIRED)
approval.transition(ActionExecutionStatus.AWAITING_APPROVAL)

check(
    "Approval-required to awaiting approval",
    approval.status == ActionExecutionStatus.AWAITING_APPROVAL,
)

approval.transition(ActionExecutionStatus.AUTHORIZED)
approval.transition(ActionExecutionStatus.EXECUTING)
approval.transition(ActionExecutionStatus.FAILED)

check(
    "Approved execution failure",
    approval.status == ActionExecutionStatus.FAILED,
)

# Denial path
blocked = ActionExecution(
    action="unknown_action",
    capability="UNKNOWN",
)

blocked.transition(ActionExecutionStatus.POLICY_CHECK)
blocked.record_permission(PermissionDecision.DENY)
blocked.transition(ActionExecutionStatus.BLOCKED)

check(
    "DENY to blocked",
    blocked.status == ActionExecutionStatus.BLOCKED,
)

# Rejection path
rejected = ActionExecution(
    action="publish_result",
    capability="PUBLISH",
)

rejected.transition(ActionExecutionStatus.POLICY_CHECK)
rejected.transition(ActionExecutionStatus.AWAITING_APPROVAL)
rejected.transition(ActionExecutionStatus.REJECTED)

check(
    "Approval rejection",
    rejected.status == ActionExecutionStatus.REJECTED,
)

# Cancellation
cancelled = ActionExecution(
    action="web_search",
    capability="READ",
)

cancelled.transition(ActionExecutionStatus.CANCELLED)

check(
    "Cancellation",
    cancelled.status == ActionExecutionStatus.CANCELLED,
)

# Timeout
timed_out = ActionExecution(
    action="web_search",
    capability="READ",
)

timed_out.transition(ActionExecutionStatus.POLICY_CHECK)
timed_out.transition(ActionExecutionStatus.AUTHORIZED)
timed_out.transition(ActionExecutionStatus.EXECUTING)
timed_out.transition(ActionExecutionStatus.TIMED_OUT)

check(
    "Execution timeout",
    timed_out.status == ActionExecutionStatus.TIMED_OUT,
)

# Invalid transitions
invalid = ActionExecution(
    action="web_search",
    capability="READ",
)

invalid_rejected = False

try:
    invalid.transition(ActionExecutionStatus.SUCCEEDED)
except ValueError:
    invalid_rejected = True

check(
    "Invalid transition rejected",
    invalid_rejected,
)

terminal_transition_rejected = False

try:
    execution.transition(ActionExecutionStatus.EXECUTING)
except ValueError:
    terminal_transition_rejected = True

check(
    "Terminal state cannot transition",
    terminal_transition_rejected,
)

# Explicit transition matrix
check(
    "Transition matrix",
    ActionExecution.can_transition(
        ActionExecutionStatus.PENDING,
        ActionExecutionStatus.POLICY_CHECK,
    )
    and ActionExecution.can_transition(
        ActionExecutionStatus.POLICY_CHECK,
        ActionExecutionStatus.BLOCKED,
    )
    and ActionExecution.can_transition(
        ActionExecutionStatus.POLICY_CHECK,
        ActionExecutionStatus.AWAITING_APPROVAL,
    )
    and ActionExecution.can_transition(
        ActionExecutionStatus.POLICY_CHECK,
        ActionExecutionStatus.AUTHORIZED,
    )
    and ActionExecution.can_transition(
        ActionExecutionStatus.EXECUTING,
        ActionExecutionStatus.SUCCEEDED,
    )
    and not ActionExecution.can_transition(
        ActionExecutionStatus.SUCCEEDED,
        ActionExecutionStatus.EXECUTING,
    ),
)

# Serialization
serialized = execution.to_dict()
restored = ActionExecution.from_dict(serialized)

check(
    "Serialization",
    restored.to_dict() == serialized,
)

# Permission authority separation
check(
    "Permission decision is recorded",
    execution.permission == PermissionDecision.ALLOW,
)

check(
    "No execution authority",
    not hasattr(execution, "run")
    and not hasattr(execution, "execute"),
)

print()
print("==============================================")
print("PHASE 8D: ACTION EXECUTION LIFECYCLE — PASS")
print("==============================================")
