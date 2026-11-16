"""Phase 8F — Human Approval Integration contract test."""

import time

import core.confirm as confirm
from core.action_approval import ActionApprovalIntegration
from core.action_execution import ActionExecution, ActionExecutionStatus
from core.action_loader import ActionRecord, ActionRegistry
from core.approval_center import ApprovalCenter
from core.capability_registry import CapabilityRegistry
from core.execution_engine import ExecutionEngine


def check(label: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(label)
    print(f"{label}: PASS")


print("=== PHASE 8F — HUMAN APPROVAL INTEGRATION TEST ===")


# ---------------------------------------------------------
# Test infrastructure
# ---------------------------------------------------------

logs = []


def logger(message: str) -> None:
    logs.append(message)


shown = []


def show(title, detail):
    shown.append((title, detail))


def hide():
    pass


confirm.bind(show, hide, logger)


# ---------------------------------------------------------
# Trusted PUBLISH action
# ---------------------------------------------------------

called = []


def publish_handler(parameters, **kwargs):
    called.append(parameters)
    return "Published successfully."


record = ActionRecord(
    name="publish_action",
    description="Approval-required test action",
    parameters={},
    handler=publish_handler,
    file="test",
    valid=True,
)

registry = ActionRegistry(
    {"publish_action": record},
    logger,
)

capabilities = CapabilityRegistry(
    action_capabilities={
        "publish_action": "PUBLISH",
    }
)

engine = ExecutionEngine(
    registry,
    capability_registry=capabilities,
)

approvals = ApprovalCenter()

integration = ActionApprovalIntegration(
    engine,
    approvals,
)


# ---------------------------------------------------------
# Create execution and reach approval state
# ---------------------------------------------------------

execution = ActionExecution(
    action="publish_action",
    capability="READ",
    mission_id="mission-8f",
    task_id="task-8f",
)

result = engine.execute(execution)

check(
    "Execution enters approval state",
    result.status == ActionExecutionStatus.AWAITING_APPROVAL,
)

check(
    "Host classification is PUBLISH",
    result.capability == "PUBLISH",
)


# ---------------------------------------------------------
# Submit to existing approval infrastructure
# ---------------------------------------------------------

response = integration.submit(
    execution,
    mission_id="mission-8f",
    task_id="task-8f",
)

check(
    "Approval request submitted",
    "[CONFIRMATION_PENDING]" in response,
)

check(
    "HUD confirmation shown",
    len(shown) == 1,
)

check(
    "Approval projection is pending",
    len(approvals.pending()) == 1,
)

check(
    "Action has not executed yet",
    called == [],
)


# ---------------------------------------------------------
# Human confirms
# ---------------------------------------------------------

confirm.resolve(True)

for _ in range(50):
    if execution.status == ActionExecutionStatus.SUCCEEDED:
        break
    time.sleep(0.01)

check(
    "Human approval authorizes execution",
    execution.approval == "APPROVED",
)

check(
    "Approved execution succeeds",
    execution.status == ActionExecutionStatus.SUCCEEDED,
)

check(
    "Trusted handler executes once",
    len(called) == 1,
)


# ---------------------------------------------------------
# Cancellation path
# ---------------------------------------------------------

shown.clear()
called.clear()

cancelled = ActionExecution(
    action="publish_action",
    capability="READ",
    mission_id="mission-cancel",
    task_id="task-cancel",
)

engine.execute(cancelled)

integration.submit(
    cancelled,
    mission_id="mission-cancel",
    task_id="task-cancel",
)

confirm.resolve(False)

time.sleep(0.05)

check(
    "Cancellation does not execute action",
    called == [],
)


# ---------------------------------------------------------
# Authority integrity
# ---------------------------------------------------------

check(
    "ApprovalCenter remains projection/routing layer",
    not hasattr(approvals, "execute"),
)

check(
    "Integration does not expose action runner",
    not hasattr(integration, "run"),
)


print()
print("==============================================")
print("PHASE 8F: HUMAN APPROVAL INTEGRATION — PASS")
print("==============================================")
