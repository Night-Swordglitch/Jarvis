"""Phase 8E — Execution Engine contract test."""

from core.action_execution import ActionExecution, ActionExecutionStatus
from core.action_loader import ActionRecord, ActionRegistry
from core.capability_registry import CapabilityRegistry
from core.execution_engine import ExecutionEngine
from core.permission_manager import PermissionDecision


def check(label: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(label)
    print(f"{label}: PASS")


print("=== PHASE 8E — EXECUTION ENGINE TEST ===")


# ---------------------------------------------------------
# Test infrastructure
# ---------------------------------------------------------

logs = []


def logger(message: str) -> None:
    logs.append(message)


capabilities = CapabilityRegistry(
    action_capabilities={
        "test_action": "READ",
        "publish_action": "PUBLISH",
        "failing_action": "READ",
    }
)


# ---------------------------------------------------------
# Trusted test actions
# ---------------------------------------------------------

called = []


def test_handler(parameters, **kwargs):
    called.append(parameters)
    return f"Executed: {parameters.get('value')}"


def publish_handler(parameters, **kwargs):
    called.append(parameters)
    return "Published."


def failing_handler(parameters, **kwargs):
    raise RuntimeError("intentional failure")


records = {
    "test_action": ActionRecord(
        name="test_action",
        description="Test execution action",
        parameters={},
        handler=test_handler,
        file="test",
        valid=True,
    ),
    "publish_action": ActionRecord(
        name="publish_action",
        description="Test approval-required action",
        parameters={},
        handler=publish_handler,
        file="test",
        valid=True,
    ),
    "failing_action": ActionRecord(
        name="failing_action",
        description="Failure test",
        parameters={},
        handler=failing_handler,
        file="test",
        valid=True,
    ),
}


registry = ActionRegistry(records, logger)

engine = ExecutionEngine(
    registry,
    capability_registry=capabilities,
)


# ---------------------------------------------------------
# ALLOW path
# ---------------------------------------------------------

execution = ActionExecution(
    action="test_action",
    capability="READ",
    parameters={"value": "hello"},
)

result = engine.execute(execution)

check(
    "Allow execution succeeds",
    result.status == ActionExecutionStatus.SUCCEEDED,
)

check(
    "Permission recorded",
    result.permission == PermissionDecision.ALLOW,
)

check(
    "Handler executed",
    called == [{"value": "hello"}],
)


# ---------------------------------------------------------
# Unknown action → BLOCKED
# ---------------------------------------------------------

blocked = ActionExecution(
    action="unknown_action",
    capability="READ",
)

result = engine.execute(blocked)

check(
    "Unknown action blocked",
    result.status == ActionExecutionStatus.BLOCKED,
)

check(
    "Unknown action never reaches handler",
    len(called) == 1,
)


# ---------------------------------------------------------
# Approval-required path
# ---------------------------------------------------------

approval = ActionExecution(
    action="publish_action",
    capability="READ",
)

result = engine.execute(approval)

check(
    "Approval-required action waits",
    result.status == ActionExecutionStatus.AWAITING_APPROVAL,
)

check(
    "Approval is not auto-granted",
    result.approval == "",
)

check(
    "Host classification overrides supplied capability",
    result.capability == "PUBLISH",
)

# The engine must not accept a caller-supplied Boolean as approval proof.
approved = ActionExecution(
    action="publish_action",
    capability="READ",
)

result = engine.execute(approved)

check(
    "Second approval-required action waits",
    result.status == ActionExecutionStatus.AWAITING_APPROVAL,
)

forged_approval_rejected = False
try:
    engine.execute(approved, approval_granted=True)
except TypeError:
    forged_approval_rejected = True

check(
    "Caller-supplied approval Boolean is rejected",
    forged_approval_rejected,
)

check(
    "Forged approval does not execute handler",
    len(called) == 1,
)


# ---------------------------------------------------------
# Failure path
# ---------------------------------------------------------

class FailingRegistry(ActionRegistry):
    def run(self, name, parameters, ctx=None):
        raise RuntimeError("intentional failure")


failure_registry = FailingRegistry(
    {"failing_action": records["failing_action"]},
    logger,
)

failure_engine = ExecutionEngine(
    failure_registry,
    capability_registry=capabilities,
)

failure = ActionExecution(
    action="failing_action",
    capability="READ",
)

result = failure_engine.execute(failure)

check(
    "Handler failure recorded",
    result.status == ActionExecutionStatus.FAILED,
)

check(
    "Failure result recorded",
    "intentional failure" in str(result.result),
)


# ---------------------------------------------------------
# Lifecycle integrity
# ---------------------------------------------------------

check(
    "Execution reaches terminal state",
    execution.terminal,
)

check(
    "Engine does not expose action execution callback",
    not hasattr(engine, "run"),
)


print()
print("==============================================")
print("PHASE 8E: EXECUTION ENGINE — PASS")
print("==============================================")
