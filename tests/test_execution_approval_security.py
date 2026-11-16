"""Regression tests for execution-bound, one-time human approval."""

import time

import pytest

import core.confirm as confirm
from core.action_approval import ActionApprovalIntegration
from core.action_execution import ActionExecution, ActionExecutionStatus
from core.action_loader import ActionRecord, ActionRegistry
from core.approval_center import ApprovalCenter
from core.capability_registry import CapabilityRegistry
from core.execution_engine import ExecutionEngine


@pytest.fixture
def approval_system():
    shown = []
    calls = []

    def show(title, detail):
        shown.append((title, detail))

    def hide():
        pass

    def handler(parameters, **kwargs):
        calls.append(dict(parameters))
        return "completed"

    confirm.bind(show, hide)
    registry = ActionRegistry(
        {
            "publish_action": ActionRecord(
                name="publish_action",
                description="test publish",
                parameters={},
                handler=handler,
                file="test",
                valid=True,
            )
        },
        logger=lambda _message: None,
    )
    capabilities = CapabilityRegistry(
        action_capabilities={"publish_action": "PUBLISH"}
    )
    engine = ExecutionEngine(registry, capability_registry=capabilities)
    center = ApprovalCenter()
    integration = ActionApprovalIntegration(engine, center)
    yield engine, center, integration, shown, calls
    confirm.resolve(False)
    confirm.bind(None, None)


def make_execution():
    return ActionExecution(
        action="publish_action",
        capability="READ",
        parameters={"destination": "public-feed", "message": "hello"},
        intent="Publish the prepared message",
        mission_id="mission-security",
        task_id="task-security",
    )


def wait_for_status(execution, status):
    for _ in range(100):
        if execution.status == status:
            return
        time.sleep(0.01)
    assert execution.status == status


def test_boolean_cannot_bypass_approval(approval_system):
    engine, _center, _integration, _shown, calls = approval_system
    execution = make_execution()
    engine.execute(execution)
    assert execution.status == ActionExecutionStatus.AWAITING_APPROVAL
    with pytest.raises(TypeError):
        engine.execute(execution, approval_granted=True)
    with pytest.raises(PermissionError):
        engine.execute(execution)
    assert calls == []


def test_human_approval_is_bound_and_single_use(approval_system):
    engine, center, integration, shown, calls = approval_system
    execution = make_execution()
    engine.execute(execution)
    response = integration.submit(
        execution, mission_id=execution.mission_id, task_id=execution.task_id
    )
    assert response.startswith("[CONFIRMATION_PENDING]")
    assert len(shown) == 1
    assert "public-feed" in shown[0][1]
    assert calls == []

    confirm.resolve(True)
    wait_for_status(execution, ActionExecutionStatus.SUCCEEDED)
    assert execution.approval == "APPROVED"
    assert calls == [{"destination": "public-feed", "message": "hello"}]
    assert center.pending() == []
    assert center.history()[-1].status == "APPROVED"

    with pytest.raises(ValueError):
        engine.execute(execution)
    assert len(calls) == 1


def test_rejection_closes_execution_without_running(approval_system):
    engine, center, integration, _shown, calls = approval_system
    execution = make_execution()
    engine.execute(execution)
    integration.submit(
        execution, mission_id=execution.mission_id, task_id=execution.task_id
    )
    confirm.resolve(False)

    assert execution.status == ActionExecutionStatus.REJECTED
    assert "rejected" in execution.result.lower()
    assert calls == []
    assert center.pending() == []
    assert center.history()[-1].status == "REJECTED"


def test_changed_parameters_invalidate_approval(approval_system):
    engine, _center, integration, _shown, calls = approval_system
    execution = make_execution()
    engine.execute(execution)
    integration.submit(
        execution, mission_id=execution.mission_id, task_id=execution.task_id
    )

    execution.parameters["destination"] = "different-destination"
    confirm.resolve(True)
    wait_for_status(execution, ActionExecutionStatus.REJECTED)

    assert calls == []
    assert "changed after" in execution.result.lower()


def test_approval_detail_redacts_common_secret_fields(approval_system):
    _engine, _center, integration, shown, _calls = approval_system
    execution = make_execution()
    execution.parameters["api_key"] = "do-not-display"
    _engine.execute(execution)
    integration.submit(
        execution, mission_id=execution.mission_id, task_id=execution.task_id
    )

    assert "[REDACTED]" in shown[0][1]
    assert "do-not-display" not in shown[0][1]


def test_approval_cannot_be_transferred_to_another_object(approval_system):
    engine, _center, integration, _shown, calls = approval_system
    execution = make_execution()
    engine.execute(execution)
    integration.submit(
        execution, mission_id=execution.mission_id, task_id=execution.task_id
    )

    forged = ActionExecution(
        action=execution.action,
        capability=execution.capability,
        parameters=dict(execution.parameters),
        intent=execution.intent,
        mission_id=execution.mission_id,
        task_id=execution.task_id,
        execution_id=execution.execution_id,
        status=ActionExecutionStatus.AWAITING_APPROVAL,
    )

    with pytest.raises(ValueError, match="different execution object"):
        engine.execute(forged)

    assert calls == []
    confirm.resolve(True)
    wait_for_status(execution, ActionExecutionStatus.SUCCEEDED)
    assert len(calls) == 1
