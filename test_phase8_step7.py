from core.action_execution import ActionExecution, ActionExecutionStatus
from core.execution_evidence import ExecutionEvidence, ExecutionEvidenceRecorder
from core.management.evidence import EvidenceStore


def check(label, condition):
    print(f"{label}: {'PASS' if condition else 'FAIL'}")
    if not condition:
        raise AssertionError(label)


print("=== PHASE 8G - EVIDENCE CONTRACT TEST ===")

execution = ActionExecution(
    action="web_search",
    capability="READ",
    execution_id="exec-8g-001",
    mission_id="mission-8g",
    task_id="task-8g",
    intent="Find evidence",
)

execution.transition(ActionExecutionStatus.POLICY_CHECK)
execution.transition(ActionExecutionStatus.AUTHORIZED)
execution.transition(ActionExecutionStatus.EXECUTING)
execution.result = "Search completed successfully."
execution.transition(ActionExecutionStatus.SUCCEEDED)

evidence = ExecutionEvidence.from_execution(execution)

check("Execution evidence created", evidence.execution_id == "exec-8g-001")
check("Mission linkage preserved", evidence.mission_id == "mission-8g")
check("Task linkage preserved", evidence.task_id == "task-8g")
check("Action linkage preserved", evidence.action == "web_search")
check("Terminal execution required", evidence.status == "SUCCEEDED")

payload = evidence.to_dict()

check("Evidence contract serializes", payload["execution_id"] == "exec-8g-001")

record = evidence.to_record()

check(
    "Existing EvidenceRecord used",
    record.details["execution_id"] == "exec-8g-001",
)

store = EvidenceStore()
recorder = ExecutionEvidenceRecorder(store)
stored = recorder.record(evidence)

check(
    "Existing EvidenceStore receives evidence",
    store.get(stored.evidence_id) is stored,
)

check(
    "Mission retrieval works",
    len(store.for_mission("mission-8g")) == 1,
)

check(
    "Task retrieval works",
    len(store.for_task("task-8g")) == 1,
)

check(
    "Execution identity survives storage",
    store.get(stored.evidence_id).details["execution_id"] == "exec-8g-001",
)

try:
    pending = ActionExecution(
        action="web_search",
        capability="READ",
        execution_id="exec-pending",
        mission_id="mission-8g",
        task_id="task-8g",
        intent="Not finished",
    )
    ExecutionEvidence.from_execution(pending)
    terminal_guard = False
except ValueError:
    terminal_guard = True

check("Non-terminal execution rejected", terminal_guard)
check("Recorder exposes no execution runner", not hasattr(recorder, "run"))
check("Recorder exposes no verification authority", not hasattr(recorder, "verify"))

print()
print("PHASE 8G: EVIDENCE CONTRACT - PASS")
