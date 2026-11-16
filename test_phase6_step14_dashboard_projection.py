"""Phase 6 Step 14 dashboard projection test."""

from core.dependency_graph import DependencyGraph
from core.events.bus import EventBus
from core.management.dashboard import DashboardProjector
from core.management.evidence import EvidenceRecord, EvidenceStore
from core.management.manager import ManagementManager
from core.management.state import ManagementState
from core.scheduler import Scheduler
from core.task_manager import TaskManager


def main() -> None:
    state = ManagementState()
    event_bus = EventBus()

    task_manager = TaskManager(
        state,
        event_bus,
    )

    dependency_graph = DependencyGraph()

    manager = ManagementManager(
        state,
        event_bus,
        task_manager,
        dependency_graph,
    )

    mission = manager.accept_mission(
        "Build a gaming print-on-demand business",
        context={
            "region": "Singapore",
            "test_mode": True,
        },
    )

    assert state.mission_id == mission.mission_id
    assert state.objective == "Build a gaming print-on-demand business"

    task_a = task_manager.create_task(
        "Research the gaming market",
        priority=80,
        agent_name="research_agent",
    )

    task_b = task_manager.create_task(
        "Analyze audience metrics",
        priority=70,
        agent_name="analytics_agent",
        dependencies=[task_a.task_id],
    )

    task_c = task_manager.create_task(
        "Prepare social content",
        priority=60,
        agent_name="social_agent",
    )

    task_d = task_manager.create_task(
        "Evaluate collected evidence",
        priority=50,
        agent_name=None,
        dependencies=[
            task_a.task_id,
            task_b.task_id,
            task_c.task_id,
        ],
    )

    for task in (task_a, task_b, task_c, task_d):
        dependency_graph.add_task(task.task_id)

    dependency_graph.add_dependency(
        task_b.task_id,
        task_a.task_id,
    )

    dependency_graph.add_dependency(
        task_d.task_id,
        task_a.task_id,
    )

    dependency_graph.add_dependency(
        task_d.task_id,
        task_b.task_id,
    )

    dependency_graph.add_dependency(
        task_d.task_id,
        task_c.task_id,
    )

    task_manager.start_task(task_a.task_id)
    task_manager.complete_task(
        task_a.task_id,
        result={"finding": "verified"},
    )

    task_manager.start_task(task_b.task_id)
    task_manager.complete_task(
        task_b.task_id,
        result={"metric": 42},
    )

    task_manager.start_task(task_c.task_id)
    task_manager.fail_task(
        task_c.task_id,
        "test failure",
    )

    manager.request_clarification(
        "Need confirmation before evaluation."
    )

    manager.request_approval(
        "Approve business evidence evaluation."
    )

    evidence_store = EvidenceStore()

    evidence_store.add(
        EvidenceRecord(
            mission_id=mission.mission_id,
            task_id=task_a.task_id,
            agent_name="research_agent",
            source="test_source",
            claim="Gaming research completed.",
            details={"verified": True},
            status="VERIFIED",
            confidence=0.95,
        )
    )

    evidence_store.add(
        EvidenceRecord(
            mission_id=mission.mission_id,
            task_id=task_b.task_id,
            agent_name="analytics_agent",
            source="test_metrics",
            claim="Audience metric verified.",
            details={"metric": 42},
            status="VERIFIED",
            confidence=0.90,
        )
    )

    scheduler = Scheduler(
        task_manager,
        dependency_graph,
        max_workers=3,
    )

    projector = DashboardProjector(
        state,
        dependency_graph,
        evidence_store,
        scheduler,
    )

    snapshot = projector.snapshot()
    data = snapshot.to_dict()

    # Mission
    assert data["mission"]["mission_id"] == mission.mission_id
    assert data["mission"]["objective"] == (
        "Build a gaming print-on-demand business"
    )

    # Task lifecycle projection
    assert len(data["tasks"]["queued"]) == 1
    assert len(data["tasks"]["completed"]) == 2
    assert len(data["tasks"]["failed"]) == 1
    assert len(data["tasks"]["active"]) == 0
    assert len(data["tasks"]["blocked"]) == 0

    # Agent aggregation
    assert "research_agent" in data["agents"]
    assert "analytics_agent" in data["agents"]
    assert "social_agent" in data["agents"]

    assert data["agents"]["research_agent"]["completed"] == 1
    assert data["agents"]["analytics_agent"]["completed"] == 1
    assert data["agents"]["social_agent"]["failed"] == 1

    # Dependency projection
    assert task_a.task_id in data["dependencies"]
    assert task_b.task_id in data["dependencies"]

    assert task_a.task_id in data["dependencies"][task_b.task_id][
        "dependencies"
    ]

    # Evidence projection
    assert data["evidence"]["available"] is True
    assert data["evidence"]["count"] == 2
    assert len(data["evidence"]["records"]) == 2

    # Scheduler projection
    assert data["scheduler"]["max_workers"] == 3
    assert data["scheduler"]["running"] == []
    assert data["scheduler"]["cancelled"] is False

    # Management context
    assert len(data["approvals"]) == 1
    assert len(data["questions"]) == 1

    # Read-only behavior:
    # snapshot conversion must not mutate the source state.
    before_queued = dict(state.queued_tasks)
    before_completed = dict(state.completed_tasks)
    before_failed = dict(state.failed_tasks)

    second_snapshot = projector.snapshot()
    second_data = second_snapshot.to_dict()

    assert second_data == data

    assert state.queued_tasks == before_queued
    assert state.completed_tasks == before_completed
    assert state.failed_tasks == before_failed

    # Snapshot must be frozen.
    try:
        snapshot.mission = {}
        raise AssertionError("DashboardSnapshot is mutable")
    except AttributeError:
        pass

    print("=== PHASE 6 STEP 14 DASHBOARD PROJECTION TEST ===")
    print("Management state projection: PASS")
    print("Mission projection: PASS")
    print("Task lifecycle projection: PASS")
    print("Agent aggregation: PASS")
    print("Dependency projection: PASS")
    print("Evidence projection: PASS")
    print("Scheduler projection: PASS")
    print("Approval / clarification projection: PASS")
    print("Read-only behavior: PASS")
    print("Snapshot immutability: PASS")
    print("PHASE 6 STEP 14: ALL TESTS PASSED")


if __name__ == "__main__":
    main()





