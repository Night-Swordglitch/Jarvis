"""Phase 7J — Mission Verification tests."""

from core.management.evidence import EvidenceRecord, EvidenceStore
from core.management.state import ManagementState, TaskState
from core.mission_context import MissionContext
from core.mission_verifier import (
    CriterionResult,
    MissionVerifier,
    VerificationResult,
)


def main() -> None:
    print("\n=== PHASE 7J — MISSION VERIFICATION TEST ===")

    mission_id = "mission-7j"

    context = MissionContext(
        mission_id=mission_id,
        objective="Launch the product campaign",
        success_criteria=[
            "campaign launched",
        ],
    )

    state = ManagementState(
        mission_id=mission_id,
        objective=context.objective,
        status="RUNNING",
    )

    completed_task = TaskState(
        task_id="task-launch",
        objective="Launch campaign",
        status="COMPLETED",
        result={
            "summary": "campaign launched successfully",
        },
    )

    state.completed_tasks[completed_task.task_id] = completed_task

    evidence_store = EvidenceStore()

    evidence = EvidenceRecord(
        mission_id=mission_id,
        task_id="task-launch",
        agent_name="business_agent",
        source="campaign_system",
        claim="campaign launched",
        details={
            "result": "success",
        },
        status="VERIFIED",
        confidence=1.0,
    )

    evidence_store.add(evidence)

    verifier = MissionVerifier(
        evidence_store=evidence_store,
    )

    # ---------------------------------------------------------
    # Successful verification
    # ---------------------------------------------------------
    result = verifier.verify(
        context=context,
        state=state,
    )

    assert isinstance(result, VerificationResult)
    assert result.verified is True
    assert result.complete is True
    assert result.status == "VERIFIED"
    assert len(result.criteria) == 1
    assert result.criteria[0].satisfied is True
    assert evidence.evidence_id in result.evidence_ids

    print("Successful mission verification: PASS")
    print("Success criterion verified from evidence: PASS")
    print("Evidence provenance preserved: PASS")

    # ---------------------------------------------------------
    # Serialization
    # ---------------------------------------------------------
    restored = VerificationResult.from_dict(
        result.to_dict()
    )

    assert restored.to_dict() == result.to_dict()

    print("VerificationResult serialization: PASS")

    # ---------------------------------------------------------
    # Failed mission
    # ---------------------------------------------------------
    failed_state = ManagementState(
        mission_id=mission_id,
        objective=context.objective,
        status="RUNNING",
    )

    failed_task = TaskState(
        task_id="task-launch",
        objective="Launch campaign",
        status="FAILED",
        error="Publishing failed.",
    )

    failed_state.failed_tasks[failed_task.task_id] = failed_task

    failed_result = verifier.verify(
        context=context,
        state=failed_state,
    )

    assert failed_result.verified is False
    assert failed_result.status == "FAILED"
    assert "task-launch" in failed_result.failed_task_ids

    print("Failed task prevents verification: PASS")

    # ---------------------------------------------------------
    # Incomplete mission
    # ---------------------------------------------------------
    incomplete_state = ManagementState(
        mission_id=mission_id,
        objective=context.objective,
        status="RUNNING",
    )

    incomplete_state.active_tasks["task-launch"] = TaskState(
        task_id="task-launch",
        objective="Launch campaign",
        status="RUNNING",
    )

    incomplete_result = verifier.verify(
        context=context,
        state=incomplete_state,
    )

    assert incomplete_result.verified is False
    assert incomplete_result.status == "INCOMPLETE"

    print("Active task prevents premature verification: PASS")

    # ---------------------------------------------------------
    # No success criteria
    # ---------------------------------------------------------
    no_criteria_context = MissionContext(
        mission_id=mission_id,
        objective=context.objective,
        success_criteria=[],
    )

    no_criteria_result = verifier.verify(
        context=no_criteria_context,
        state=state,
    )

    assert no_criteria_result.verified is False
    assert no_criteria_result.status == "INCOMPLETE"

    print("Missing success criteria prevents verification: PASS")

    # ---------------------------------------------------------
    # Custom evaluator
    # ---------------------------------------------------------
    def evaluator(
        criterion,
        context,
        state,
        evidence,
    ):
        return CriterionResult(
            criterion=criterion,
            satisfied=True,
            reason="Trusted verification evaluator confirmed criterion.",
            evidence_ids=[record.evidence_id for record in evidence],
        )

    custom_verifier = MissionVerifier(
        evidence_store=evidence_store,
        evaluator=evaluator,
    )

    custom_result = custom_verifier.verify(
        context=context,
        state=state,
    )

    assert custom_result.verified is True

    print("Injected verification evaluator: PASS")

    # ---------------------------------------------------------
    # Read-only boundary
    # ---------------------------------------------------------
    before_state = state.to_dict()
    before_context = context.to_dict()
    before_evidence = [x.to_dict() for x in evidence_store.all()]

    verifier.verify(
        context=context,
        state=state,
    )

    assert state.to_dict() == before_state
    assert context.to_dict() == before_context
    assert [x.to_dict() for x in evidence_store.all()] == before_evidence

    print("Verification is read-only: PASS")

    # ---------------------------------------------------------
    # Authority boundary
    # ---------------------------------------------------------
    forbidden = {
        "execute",
        "run",
        "approve",
        "resolve",
        "cancel",
        "retry",
        "replan",
        "dispatch",
        "modify",
        "update_state",
    }

    verifier_methods = set(dir(verifier))

    assert not forbidden.intersection(verifier_methods)

    print("No execution / approval / retry / replanning authority: PASS")

    print("\n==============================================")
    print("PHASE 7J: ALL TESTS PASSED")
    print("MISSION VERIFICATION: PASS")
    print("READ-ONLY BOUNDARY: PASS")
    print("EVIDENCE-BASED VERIFICATION: PASS")
    print("==============================================")


if __name__ == "__main__":
    main()
