from core.events import EventBus
from core.management import ManagementState
from core.task_manager import TaskManager


print("=== PHASE 6 STEP 2 TASK MANAGER TEST ===")


state = ManagementState()
events = EventBus()

received = []


def capture(event):
    received.append(event)


events.subscribe("*", capture)

manager = TaskManager(
    state,
    events,
)


# ---------------------------------------------------------
# Create
# ---------------------------------------------------------

task = manager.create_task(
    "Test research task",
    priority=80,
    agent_name="research_agent",
)

assert task.status == "QUEUED"
assert task.task_id in state.queued_tasks

print("Task creation: PASS")


# ---------------------------------------------------------
# Priority ordering
# ---------------------------------------------------------

low = manager.create_task(
    "Low priority task",
    priority=20,
)

high = manager.create_task(
    "High priority task",
    priority=90,
)

queued = manager.queued_tasks()

assert queued[0].task_id == high.task_id
assert queued[-1].task_id == low.task_id

print("Priority ordering: PASS")


# ---------------------------------------------------------
# Start
# ---------------------------------------------------------

manager.start_task(task.task_id)

assert task.status == "RUNNING"
assert task.task_id in state.active_tasks
assert task.task_id not in state.queued_tasks

print("Task start: PASS")


# ---------------------------------------------------------
# Complete
# ---------------------------------------------------------

manager.complete_task(
    task.task_id,
    {
        "result": "Research completed.",
    },
)

assert task.status == "COMPLETED"
assert task.task_id in state.completed_tasks
assert task.result["result"] == "Research completed."

print("Task completion: PASS")


# ---------------------------------------------------------
# Dependency
# ---------------------------------------------------------

dependency = manager.create_task(
    "Dependency task",
)

dependent = manager.create_task(
    "Dependent task",
    dependencies=[dependency.task_id],
)

assert not manager.dependencies_satisfied(dependent)

print("Dependency blocking: PASS")

manager.start_task(dependency.task_id)

manager.complete_task(
    dependency.task_id,
    {"ok": True},
)

assert manager.dependencies_satisfied(dependent)

print("Dependency resolution: PASS")


# ---------------------------------------------------------
# Failure
# ---------------------------------------------------------

failed = manager.create_task(
    "Failure test",
)

manager.start_task(failed.task_id)

manager.fail_task(
    failed.task_id,
    "Intentional test failure.",
)

assert failed.status == "FAILED"
assert failed.task_id in state.failed_tasks
assert failed.error == "Intentional test failure."

print("Task failure: PASS")


# ---------------------------------------------------------
# Blocking
# ---------------------------------------------------------

blocked = manager.create_task(
    "Blocked test",
)

manager.block_task(
    blocked.task_id,
    "Waiting for external dependency.",
)

assert blocked.status == "BLOCKED"
assert blocked.task_id in state.blocked_tasks

print("Task blocking: PASS")


# ---------------------------------------------------------
# Cancellation
# ---------------------------------------------------------

cancelled = manager.create_task(
    "Cancellation test",
)

manager.cancel_task(
    cancelled.task_id,
)

assert cancelled.status == "CANCELLED"
assert cancelled.task_id in state.failed_tasks

print("Task cancellation: PASS")


# ---------------------------------------------------------
# Event verification
# ---------------------------------------------------------

event_types = [
    event.event_type
    for event in received
]

required_events = {
    "TASK_CREATED",
    "TASK_QUEUED",
    "TASK_STARTED",
    "TASK_COMPLETED",
    "TASK_FAILED",
    "TASK_BLOCKED",
    "TASK_CANCELLED",
}

assert required_events.issubset(set(event_types))

print("Lifecycle events: PASS")


# ---------------------------------------------------------
# Single bucket invariant
# ---------------------------------------------------------

for task_id in (
    list(state.active_tasks)
    + list(state.queued_tasks)
    + list(state.blocked_tasks)
    + list(state.completed_tasks)
    + list(state.failed_tasks)
):
    occurrences = sum(
        task_id in group
        for group in (
            state.active_tasks,
            state.queued_tasks,
            state.blocked_tasks,
            state.completed_tasks,
            state.failed_tasks,
        )
    )

    assert occurrences == 1


print("Single-bucket invariant: PASS")


print("")
print("PHASE 6 STEP 2: ALL TESTS PASSED")
