import asyncio

from core.events.bus import EventBus
from core.events.events import Event
from core.management.state import ManagementState
from core.task_manager import TaskManager
from core.dependency_graph import DependencyGraph
from core.scheduler import Scheduler
from core.management.manager import ManagementManager
from core.management.evidence import EvidenceStore, EvidenceRecord
from core.management.dashboard import DashboardProjector
from core.management.dashboard_events import DashboardEventBridge


print("=== PHASE 6 STEP 20 — 6O FULL-SYSTEM SIMULATION ===")


async def main():
    # ─────────────────────────────────────────────────────────────────────
    # 1. Construct the complete management nervous system
    # ─────────────────────────────────────────────────────────────────────

    state = ManagementState()
    bus = EventBus()
    tasks = TaskManager(state, bus)
    graph = DependencyGraph()
    scheduler = Scheduler(tasks, graph, max_workers=3)
    evidence = EvidenceStore()

    manager = ManagementManager(
        state,
        bus,
        tasks,
        graph,
    )

    projector = DashboardProjector(
        state,
        graph,
        evidence,
        scheduler,
    )

    received = []

    bridge = DashboardEventBridge(
        bus,
        on_event=lambda event: received.append(event),
    )

    bridge.start()

    print("Management nervous system construction: PASS")


    # ─────────────────────────────────────────────────────────────────────
    # 2. Mission -> plan -> dependency graph
    # ─────────────────────────────────────────────────────────────────────

    manager.accept_mission(
        "Execute a full MARK-L autonomous operations simulation."
    )

    plan = [
        {
            "objective": "Research operation",
            "priority": 80,
            "agent_name": None,
            "dependencies": [],
        },
        {
            "objective": "Analytics operation",
            "priority": 70,
            "agent_name": None,
            "dependencies": [],
        },
        {
            "objective": "Synthesis operation",
            "priority": 60,
            "agent_name": None,
            "dependencies": ["task_1", "task_2"],
        },
    ]

    created = manager.create_planned_tasks(plan)

    assert len(created) == 3
    assert len(state.queued_tasks) == 3

    ids = list(state.queued_tasks.keys())

    research_id = ids[0]
    analytics_id = ids[1]
    synthesis_id = ids[2]

    assert graph.has_task(research_id)
    assert graph.has_task(analytics_id)
    assert graph.has_task(synthesis_id)

    print("Mission -> plan -> dependency graph: PASS")


    # ─────────────────────────────────────────────────────────────────────
    # 3. Real dependency-aware scheduler
    # ─────────────────────────────────────────────────────────────────────

    execution_order = []
    concurrent_started = asyncio.Event()

    async def runner(task):
        execution_order.append(("start", task.task_id))

        if task.task_id in (research_id, analytics_id):
            concurrent_started.set()
            await asyncio.sleep(0.05)

            execution_order.append(("complete", task.task_id))

            return {
                "status": "PASS",
                "task_id": task.task_id,
            }

        completed = {
            item[1]
            for item in execution_order
            if item[0] == "complete"
        }

        assert research_id in completed
        assert analytics_id in completed

        execution_order.append(("complete", task.task_id))

        return {
            "status": "PASS",
            "task_id": task.task_id,
        }

    await scheduler.run(runner)

    assert concurrent_started.is_set()

    assert research_id in state.completed_tasks
    assert analytics_id in state.completed_tasks
    assert synthesis_id in state.completed_tasks

    print("Concurrent dependency-aware execution: PASS")


    # ─────────────────────────────────────────────────────────────────────
    # 4. Failure path + isolated recovery task
    # ─────────────────────────────────────────────────────────────────────

    recovery_task = tasks.create_task(
        "Recovery operation",
        priority=50,
    )

    failure_task = tasks.create_task(
        "Controlled failure operation",
        priority=40,
    )

    graph.add_task(recovery_task.task_id)
    graph.add_task(failure_task.task_id)

    async def failure_runner(task):
        if task.task_id == failure_task.task_id:
            raise RuntimeError("Controlled 6O failure")

        return {
            "status": "RECOVERED",
            "task_id": task.task_id,
        }

    await scheduler.run(failure_runner)

    assert failure_task.task_id in state.failed_tasks
    assert recovery_task.task_id in state.completed_tasks

    print("Failure isolation + recovery execution: PASS")


    # ─────────────────────────────────────────────────────────────────────
    # 5. Evidence + provenance
    # ─────────────────────────────────────────────────────────────────────

    record = EvidenceRecord(
        mission_id=state.mission_id,
        task_id=synthesis_id,
        agent_name="phase6_step20",
        source="phase6_step20",
        claim="Full-system simulation completed successfully.",
        details={
            "status": "FULL_SYSTEM_PASS",
            "executed_tasks": 5,
        },
        status="VERIFIED",
        confidence=1.0,
    )

    stored = evidence.add(record)

    assert stored.evidence_id == record.evidence_id
    assert len(evidence) == 1

    mission_evidence = evidence.for_mission(state.mission_id)

    assert mission_evidence
    assert mission_evidence[0].task_id == synthesis_id

    task_evidence = evidence.for_task(synthesis_id)

    assert task_evidence
    assert task_evidence[0].claim == (
        "Full-system simulation completed successfully."
    )

    assert evidence.latest() is not None
    assert evidence.get(record.evidence_id) is record
    assert evidence.search("FULL_SYSTEM_PASS")

    print("Evidence + provenance: PASS")


    # ─────────────────────────────────────────────────────────────────────
    # 6. Dashboard projection
    # ─────────────────────────────────────────────────────────────────────

    snapshot = projector.snapshot().to_dict()

    assert snapshot["mission"]["mission_id"] == state.mission_id

    completed_ids = {
        task["task_id"]
        for task in snapshot["tasks"]["completed"]
    }

    failed_ids = {
        task["task_id"]
        for task in snapshot["tasks"]["failed"]
    }

    assert research_id in completed_ids
    assert analytics_id in completed_ids
    assert synthesis_id in completed_ids
    assert recovery_task.task_id in completed_ids
    assert failure_task.task_id in failed_ids

    assert snapshot["evidence"]

    print("Dashboard projection of full system state: PASS")


    # ─────────────────────────────────────────────────────────────────────
    # 7. Live event bridge
    # ─────────────────────────────────────────────────────────────────────

    bus.publish(
        Event(
            event_type="FULL_SYSTEM_SIMULATION",
            payload={
                "mission_id": state.mission_id,
                "completed": len(completed_ids),
                "failed": len(failed_ids),
            },
        )
    )

    assert bridge.event_count >= 1
    assert bridge.last_event is not None
    assert received

    assert received[-1].event_type == "FULL_SYSTEM_SIMULATION"

    print("EventBus -> live dashboard event bridge: PASS")


    # ─────────────────────────────────────────────────────────────────────
    # 8. Dashboard immutability
    # ─────────────────────────────────────────────────────────────────────

    before = projector.snapshot().to_dict()
    after = projector.snapshot().to_dict()

    assert before == after

    print("Dashboard read-only guarantee: PASS")


    # ─────────────────────────────────────────────────────────────────────
    # 9. Final integrity checks
    # ─────────────────────────────────────────────────────────────────────

    assert state.mission_id
    assert state.objective
    assert len(state.completed_tasks) >= 4
    assert len(state.failed_tasks) >= 1
    assert bridge.event_count >= 1
    assert snapshot["scheduler"]["max_workers"] == 3
    assert len(evidence) == 1

    print("Full-system integrity checks: PASS")

    print()
    print("==============================================")
    print("PHASE 6 STEP 20: ALL TESTS PASSED")
    print("6O FULL-SYSTEM SIMULATION: PASS")
    print("==============================================")


if __name__ == "__main__":
    asyncio.run(main())
