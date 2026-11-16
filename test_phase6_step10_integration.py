import asyncio

from core.dependency_graph import DependencyGraph
from core.events import EventBus
from core.management import ManagementState
from core.reliability import ResourcePolicy, RetryPolicy
from core.scheduler import Scheduler
from core.task_manager import TaskManager


async def main() -> None:
    print("=== PHASE 6 STEP 10 RELIABILITY INTEGRATION TEST ===")

    # ------------------------------------------------------------
    # Foundation
    # ------------------------------------------------------------
    state = ManagementState()
    events = EventBus()
    task_manager = TaskManager(state, events)
    graph = DependencyGraph()

    # ------------------------------------------------------------
    # Existing scheduler compatibility
    # ------------------------------------------------------------
    scheduler = Scheduler(
        task_manager,
        graph,
        max_workers=2,
    )

    retry = RetryPolicy(
        max_attempts=3,
        retryable_errors=("temporary", "timeout"),
    )

    resources = ResourcePolicy(
        max_workers=2,
        max_cpu=8,
        max_memory_mb=16384,
    )

    assert scheduler.max_workers == 2
    assert retry.max_attempts == 3
    assert resources.max_workers == 2

    print("Reliability configuration: PASS")

    # ------------------------------------------------------------
    # Retry behavior model
    # ------------------------------------------------------------
    attempts = {"count": 0}

    async def retrying_runner(task):
        attempts["count"] += 1

        if attempts["count"] < 3:
            raise RuntimeError("temporary failure")

        return {
            "status": "success",
            "attempts": attempts["count"],
        }

    task = task_manager.create_task(
        "Retry integration task",
        metadata={
            "cpu": 2,
            "memory_mb": 1024,
        },
    )

    graph.add_task(task.task_id)

    # The current scheduler does not yet own RetryPolicy.
    # Prove that the policy correctly governs the runner lifecycle
    # before scheduler integration changes are made.
    current_attempt = 1
    result = None
    last_error = None

    while True:
        try:
            result = await retrying_runner(task)
            break
        except Exception as exc:
            last_error = str(exc)

            if not retry.can_retry(current_attempt, last_error):
                raise

            current_attempt += 1

    assert attempts["count"] == 3
    assert result["status"] == "success"

    print("Retry integration behavior: PASS")

    # ------------------------------------------------------------
    # Resource allocation around execution
    # ------------------------------------------------------------
    assert resources.can_allocate(
        workers=1,
        cpu=2,
        memory_mb=1024,
    )

    resources.allocate(
        workers=1,
        cpu=2,
        memory_mb=1024,
    )

    assert resources.used_workers == 1
    assert resources.used_cpu == 2
    assert resources.used_memory_mb == 1024

    resources.release(
        workers=1,
        cpu=2,
        memory_mb=1024,
    )

    assert resources.used_workers == 0
    assert resources.used_cpu == 0
    assert resources.used_memory_mb == 0

    print("Resource integration behavior: PASS")

    # ------------------------------------------------------------
    # Existing scheduler still executes normally
    # ------------------------------------------------------------
    normal_task = task_manager.create_task(
        "Normal scheduler integration task"
    )

    graph.add_task(normal_task.task_id)

    async def normal_runner(task):
        return {"ok": True}

    snapshot = await scheduler.run(normal_runner)

    completed = task_manager.get_task(normal_task.task_id)

    assert completed is not None
    assert completed.status == "COMPLETED"
    assert completed.result == {"ok": True}
    assert snapshot["task_states"][normal_task.task_id] == "COMPLETED"

    print("Scheduler compatibility: PASS")

    print()
    print("PHASE 6 STEP 10: RELIABILITY INTEGRATION TEST PASSED")


if __name__ == "__main__":
    asyncio.run(main())
