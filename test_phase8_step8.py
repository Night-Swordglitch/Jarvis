from core.management.evidence import EvidenceRecord, EvidenceStore
from core.management.state import ManagementState, TaskState
from core.mission_context import MissionContext
from core.mission_verifier import MissionVerifier, VerificationResult
from core.verification_contract import VerificationContract


def check(label, condition):
    print(f"{label}: {'PASS' if condition else 'FAIL'}")
    if not condition:
        raise AssertionError(label)


print("=== PHASE 8H - VERIFICATION CONTRACT TEST ===")

store = EvidenceStore()

store.add(
    EvidenceRecord(
        mission_id="mission-8h",
        task_id="task-8h",
        agent_name="execution_engine",
        source="execution_engine",
        claim="Action 'web_search' completed with status SUCCEEDED.",
        details={
            "execution_id": "exec-8h-001",
            "action": "web_search",
            "execution_status": "SUCCEEDED",
            "result": "Search completed successfully.",
        },
    )
)

context = MissionContext(
    mission_id="mission-8h",
    objective="Complete the research mission",
    success_criteria=[
        "web_search",
    ],
)

state = ManagementState(
    mission_id="mission-8h",
    objective="Complete the research mission",
    status="COMPLETED",
)

state.completed_tasks["task-8h"] = TaskState(
    task_id="task-8h",
    objective="Perform web search",
    status="COMPLETED",
)

verifier = MissionVerifier(evidence_store=store)
contract = VerificationContract(verifier)

result = contract.verify(
    context=context,
    state=state,
)

check(
    "Verification result returned",
    isinstance(result, VerificationResult),
)

check(
    "Mission verification succeeds",
    result.verified is True,
)

check(
    "Verification status is VERIFIED",
    result.status == "VERIFIED",
)

check(
    "Evidence reaches verifier",
    len(result.evidence_ids) == 1,
)

check(
    "Criterion is satisfied",
    len(result.criteria) == 1
    and result.criteria[0].satisfied is True,
)

serialized = contract.serialize(result)

check(
    "Verification result serializes",
    serialized["status"] == "VERIFIED",
)

check(
    "Verification preserves evidence IDs",
    len(serialized["evidence_ids"]) == 1,
)

# Verify that the contract remains read-only with respect to management state.
before = state.to_dict()

contract.verify(
    context=context,
    state=state,
)

after = state.to_dict()

check(
    "Verification does not mutate management state",
    before == after,
)

check(
    "Contract exposes no action runner",
    not hasattr(contract, "run"),
)

check(
    "Contract exposes no permission authority",
    not hasattr(contract, "approve"),
)

check(
    "Contract delegates to existing verifier",
    contract.verifier() is verifier,
)

# Mismatched mission state must remain a verifier concern.
wrong_state = ManagementState(
    mission_id="different-mission",
    objective="Different mission",
)

mismatch = contract.verify(
    context=context,
    state=wrong_state,
)

check(
    "Mission mismatch is rejected by verification",
    mismatch.verified is False
    and mismatch.status == "FAILED",
)

print()
print("PHASE 8H: VERIFICATION CONTRACT - PASS")
