from pathlib import Path
from tempfile import TemporaryDirectory

from core.action_loader import ActionRecord, ActionRegistry
from core.capability_registry import CapabilityRegistry
from core.execution_engine import ExecutionEngine
from core.execution_evidence import ExecutionEvidence, ExecutionEvidenceRecorder
from core.execution_state import ExecutionStateStore
from core.action_execution import ActionExecution, ActionExecutionStatus
from core.management.evidence import EvidenceStore
from core.management.state import ManagementState
from core.mission_context import MissionContext
from core.mission_verifier import MissionVerifier
from core.verification_contract import VerificationContract


def check(label, condition):
    print(f"{label}: {'PASS' if condition else 'FAIL'}")
    if not condition:
        raise AssertionError(label)


print("=== PHASE 8L - REAL INTEGRATION TEST ===")

calls = []


def trusted_handler(parameters):
    calls.append(dict(parameters))
    return "integration success"


record = ActionRecord(
    name="integration_action",
    description="Phase 8L integration action",
    parameters={
        "type": "object",
        "properties": {},
    },
    handler=trusted_handler,
    file="phase8l_test",
    valid=True,
)


registry = ActionRegistry(
    {"integration_action": record},
    logger=lambda message: None,
)


capabilities = CapabilityRegistry(
    action_capabilities={
        "integration_action": "READ",
    }
)


engine = ExecutionEngine(
    registry,
    capability_registry=capabilities,
)


execution = ActionExecution(
    action="integration_action",
    capability="READ",
    parameters={"value": "phase8l"},
    intent="Run the Phase 8 integration test",
    mission_id="mission-8l",
    task_id="task-8l",
)


result = engine.execute(execution)


check(
    "Execution succeeds through real engine",
    result.status == ActionExecutionStatus.SUCCEEDED,
)


check(
    "Trusted handler executed",
    len(calls) == 1,
)


check(
    "Handler parameters preserved",
    calls[0] == {"value": "phase8l"},
)


check(
    "Permission was recorded",
    execution.permission is not None,
)


check(
    "Execution reaches terminal state",
    execution.terminal is True,
)


with TemporaryDirectory() as temp_dir:

    state_store = ExecutionStateStore(
        Path(temp_dir) / "executions.json"
    )

    state_store.save(execution)

    restored = state_store.get(
        execution.execution_id
    )

    check(
        "Execution survives persistence",
        restored is not None,
    )


evidence_store = EvidenceStore()

evidence = ExecutionEvidence.from_execution(
    execution
)

recorder = ExecutionEvidenceRecorder(
    evidence_store
)

recorded = recorder.record(evidence)


check(
    "Execution evidence created",
    recorded is not None,
)


check(
    "Evidence reaches existing EvidenceStore",
    len(evidence_store) == 1,
)


check(
    "Evidence preserves execution identity",
    recorded.details["execution_id"]
    == execution.execution_id,
)


state = ManagementState(
    mission_id="mission-8l",
    objective="Run the Phase 8 integration test",
)

state.completed_tasks["task-8l"] = {
    "status": "COMPLETED"
}


context = MissionContext(
    mission_id="mission-8l",
    objective="Run the Phase 8 integration test",
    success_criteria=[
        "integration_action"
    ],
)


verifier = MissionVerifier(
    evidence_store=evidence_store
)

contract = VerificationContract(
    verifier
)


verification = contract.verify(
    context=context,
    state=state,
)


check(
    "Verification succeeds",
    verification.verified is True,
)


check(
    "Verification status is VERIFIED",
    verification.status == "VERIFIED",
)


check(
    "Success criterion is satisfied",
    verification.criteria[0].satisfied is True,
)


check(
    "Verification preserves evidence identity",
    execution.execution_id
    in recorded.details["execution_id"],
)


check(
    "Full execution chain completed",
    (
        execution.status == ActionExecutionStatus.SUCCEEDED
        and len(calls) == 1
        and len(evidence_store) == 1
        and verification.verified
    ),
)


print()
print("PHASE 8L: REAL INTEGRATION TESTS - PASS")
