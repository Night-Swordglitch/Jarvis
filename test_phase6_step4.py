import asyncio

from core.dependency_graph import DependencyGraph
from core.scheduler import Scheduler
from core.task_manager import TaskManager
from core.management.state import ManagementState
from core.events.bus import EventBus


def make_manager(mission_id: str, objective: str) -> TaskManager:
    state = ManagementState(
        mission_id=mission_id,
        objective=objective,
    )
    event_bus = EventBus()
    return TaskManager(state, event_bus)


def create_task(
    manager: TaskManager,
    graph: DependencyGraph,
    objective: str,
):
    task = manager.create_task(
        objective=objective,
    )

    graph.add_task(task.task_id)

    return task


async def main() -> None:
    print("=== PHASE 6 STEP 4 CONCURRENT SCHEDULER TEST ===")

    # ------------------------------------------------------------
    # Main scheduler setup
    #
    # T1 ──┐
    #      ├──> T4
    # T2 ──┘
    #
    # T3 is independent.
    # ------------------------------------------------------------

    task_manager = make_manager(
        "scheduler-test",
        "Phase 6 Step 4 scheduler test",
    )

    graph = DependencyGraph()

    t1 = create_task(
        task_manager,
        graph,
        "Independent task one",
    )

    t2 = create_task(
        task_manager,
        graph,
        "Independent task two",
    )

    t3 = create_task(
        task_manager,
        graph,
        "Independent task three",
    )

    t4 = create_task(
        task_manager,
        graph,
        "Depends on task one and task two",
    )

    graph.add_dependency(t4.task_id, t1.task_id)
    graph.add_dependency(t4.task_id, t2.task_id)

    print("Scheduler task setup: PASS")

    # ------------------------------------------------------------
    # Concurrency tracking
    # ------------------------------------------------------------

    active = 0
    maximum_active = 0
    execution_order = []

    async def runner(task):
        nonlocal active, maximum_active

        active += 1

        maximum_active = max(
            maximum_active,
            active,
        )

        execution_order.append(
            f"START:{task.task_id}"
        )

        await asyncio.sleep(0.05)

        execution_order.append(
            f"END:{task.task_id}"
        )

        active -= 1

        return {
            "result": f"Completed {task.task_id}"
        }

    # ------------------------------------------------------------
    # Run scheduler
    # ------------------------------------------------------------

    scheduler = Scheduler(
        task_manager,
        graph,
        max_workers=3,
    )

    result = await scheduler.run(runner)

    assert maximum_active >= 2

    print("Concurrent execution: PASS")

    assert maximum_active <= 3

    print("Worker limit: PASS")

    # ------------------------------------------------------------
    # Dependency ordering
    # ------------------------------------------------------------

    t1_end = execution_order.index(
        f"END:{t1.task_id}"
    )

    t2_end = execution_order.index(
        f"END:{t2.task_id}"
    )

    t4_start = execution_order.index(
        f"START:{t4.task_id}"
    )

    assert t1_end < t4_start
    assert t2_end < t4_start

    print("Dependency-aware execution: PASS")

    # ------------------------------------------------------------
    # Final lifecycle states
    # ------------------------------------------------------------

    assert (
        task_manager.get_task(t1.task_id).status
        == "COMPLETED"
    )

    assert (
        task_manager.get_task(t2.task_id).status
        == "COMPLETED"
    )

    assert (
        task_manager.get_task(t3.task_id).status
        == "COMPLETED"
    )

    assert (
        task_manager.get_task(t4.task_id).status
        == "COMPLETED"
    )

    print("Task lifecycle integration: PASS")

    # ------------------------------------------------------------
    # Scheduler snapshot
    # ------------------------------------------------------------

    assert result["running"] == []
    assert result["ready"] == []
    assert result["waiting"] == []
    assert result["blocked"] == []

    print("Scheduler final snapshot: PASS")

    # ------------------------------------------------------------
    # Failure propagation
    # ------------------------------------------------------------

    failure_manager = make_manager(
        "scheduler-failure-test",
        "Failure propagation test",
    )

    failure_graph = DependencyGraph()

    f1 = create_task(
        failure_manager,
        failure_graph,
        "Failure source",
    )

    f2 = create_task(
        failure_manager,
        failure_graph,
        "Dependent task",
    )

    failure_graph.add_dependency(
        f2.task_id,
        f1.task_id,
    )

    failure_scheduler = Scheduler(
        failure_manager,
        failure_graph,
        max_workers=2,
    )

    async def failing_runner(task):
        if task.task_id == f1.task_id:
            raise RuntimeError(
                "intentional test failure"
            )

        raise AssertionError(
            "Dependent task should never execute."
        )

    await failure_scheduler.run(
        failing_runner
    )

    assert (
        failure_manager.get_task(f1.task_id).status
        == "FAILED"
    )

    assert (
        failure_manager.get_task(f2.task_id).status
        == "BLOCKED"
    )

    print("Failure propagation: PASS")

    # ------------------------------------------------------------
    # Independent branch survives failure
    # ------------------------------------------------------------

    independent_manager = make_manager(
        "scheduler-independent-test",
        "Independent branch test",
    )

    independent_graph = DependencyGraph()

    a = create_task(
        independent_manager,
        independent_graph,
        "Failure branch",
    )

    b = create_task(
        independent_manager,
        independent_graph,
        "Dependent branch",
    )

    c = create_task(
        independent_manager,
        independent_graph,
        "Independent branch",
    )

    independent_graph.add_dependency(
        b.task_id,
        a.task_id,
    )

    independent_scheduler = Scheduler(
        independent_manager,
        independent_graph,
        max_workers=2,
    )

    async def branch_runner(task):
        if task.task_id == a.task_id:
            raise RuntimeError(
                "intentional branch failure"
            )

        return {
            "result": "independent success"
        }

    await independent_scheduler.run(
        branch_runner
    )

    assert (
        independent_manager.get_task(a.task_id).status
        == "FAILED"
    )

    assert (
        independent_manager.get_task(b.task_id).status
        == "BLOCKED"
    )

    assert (
        independent_manager.get_task(c.task_id).status
        == "COMPLETED"
    )

    print("Independent branch isolation: PASS")

    # ------------------------------------------------------------
    # Final
    # ------------------------------------------------------------

    print()
    print("PHASE 6 STEP 4: ALL TESTS PASSED")


if __name__ == "__main__":
    asyncio.run(main())
