from pathlib import Path
from tempfile import TemporaryDirectory

from core.action_execution import ActionExecution, ActionExecutionStatus
from core.execution_state import ExecutionStateStore


def check(label, condition):
    print(f"{label}: {'PASS' if condition else 'FAIL'}")
    if not condition:
        raise AssertionError(label)


print("=== PHASE 8K - PERSISTENT EXECUTION STATE TEST ===")

with TemporaryDirectory() as temp_dir:
    path = Path(temp_dir) / "executions.json"

    store = ExecutionStateStore(path)

    execution = ActionExecution(
        action="test_action",
        capability="READ",
        parameters={"query": "MARK-LIV"},
        intent="test persistence",
        mission_id="mission-8k",
        task_id="task-8k",
    )

    execution.transition(ActionExecutionStatus.POLICY_CHECK)
    execution.transition(ActionExecutionStatus.AUTHORIZED)
    execution.transition(ActionExecutionStatus.EXECUTING)

    execution.result = "execution completed"

    execution.transition(ActionExecutionStatus.SUCCEEDED)

    original_id = execution.execution_id

    store.save(execution)

    check(
        "Execution state file created",
        path.exists(),
    )

    check(
        "Execution stored",
        len(store) == 1,
    )

    restored = store.get(original_id)

    check(
        "Execution restored",
        restored is not None,
    )

    check(
        "Execution identity preserved",
        restored.execution_id == original_id,
    )

    check(
        "Action preserved",
        restored.action == "test_action",
    )

    check(
        "Parameters preserved",
        restored.parameters == {"query": "MARK-LIV"},
    )

    check(
        "Mission linkage preserved",
        restored.mission_id == "mission-8k",
    )

    check(
        "Task linkage preserved",
        restored.task_id == "task-8k",
    )

    check(
        "Result preserved",
        restored.result == "execution completed",
    )

    check(
        "Terminal status preserved",
        restored.status == ActionExecutionStatus.SUCCEEDED,
    )

    all_executions = store.all()

    check(
        "All executions can be restored",
        len(all_executions) == 1
        and all_executions[0].execution_id == original_id,
    )

    removed = store.remove(original_id)

    check(
        "Execution can be removed",
        removed is True,
    )

    check(
        "Removed execution is absent",
        store.get(original_id) is None,
    )

    check(
        "State store exposes no execution runner",
        not hasattr(store, "execute")
        and not hasattr(store, "_action_runner"),
    )

    check(
        "State store exposes no permission authority",
        not hasattr(store, "approve")
        and not hasattr(store, "check_permission"),
    )

    check(
        "State store exposes no verification authority",
        not hasattr(store, "verify"),
    )


print()
print("PHASE 8K: PERSISTENT EXECUTION STATE - PASS")
