"""Phase 7H — Replanning Engine tests."""

from core.events.bus import EventBus
from core.management.manager import ManagementManager
from core.management.state import ManagementState
from core.mission_replanner import ReplanProposal, ReplanningEngine
from core.task_manager import TaskManager
from core.dependency_graph import DependencyGraph
from core.mission_monitor import MissionMonitor


def main() -> None:
    print("\n=== PHASE 7H — REPLANNING ENGINE TEST ===")

    # ---------------------------------------------------------
    # Foundation
    # ---------------------------------------------------------
    state = ManagementState()
    event_bus = EventBus()
    task_manager = TaskManager(state, event_bus)
    dependency_graph = DependencyGraph()

    manager = ManagementManager(
        state,
        event_bus,
        task_manager,
        dependency_graph,
    )

    manager.accept_mission(
        "Launch a successful product campaign",
        context={"phase": "7H"},
    )

    initial_plan = manager.create_plan()

    assert initial_plan
    assert state.current_plan == initial_plan

    print("ManagementManager initial plan: PASS")

    # ---------------------------------------------------------
    # Real monitor
    # ---------------------------------------------------------
    monitor = MissionMonitor(
        manager.mission.mission_id,
        stale_after=60.0,
    )
    monitor.bind_event_bus(event_bus)

    task = task_manager.create_task(
        "Research product market",
        priority=50,
    )

    monitor.track_task(task.task_id)

    task_manager.start_task(task.task_id)
    task_manager.fail_task(
        task.task_id,
        error="Research source unavailable",
    )

    snapshot = monitor.snapshot()

    assert snapshot["healthy"] is False
    assert snapshot["status"] == "DEGRADED"
    assert task.task_id in snapshot["stale_tasks"] or task.task_id in snapshot["observed_tasks"]

    print("MissionMonitor degraded state detected: PASS")

    # ---------------------------------------------------------
    # Replanning proposal
    # ---------------------------------------------------------
    engine = ReplanningEngine()

    proposal = engine.propose(
        mission_id=manager.mission.mission_id,
        objective=manager.mission.objective,
        monitor_snapshot=snapshot,
        current_plan=initial_plan,
    )

    assert proposal is not None
    assert isinstance(proposal, ReplanProposal)
    assert proposal.mission_id == manager.mission.mission_id
    assert task.task_id in proposal.failed_task_ids
    assert proposal.ready
    assert proposal.plan

    print("ReplanningEngine produced proposal: PASS")
    print("Failed task captured in proposal: PASS")
    print("Proposal contains revised plan: PASS")

    # ---------------------------------------------------------
    # Serialization
    # ---------------------------------------------------------
    restored = ReplanProposal.from_dict(proposal.to_dict())

    assert restored.to_dict() == proposal.to_dict()
    assert restored.to_planner_output()

    print("ReplanProposal serialization: PASS")

    # ---------------------------------------------------------
    # Authority boundary
    # ---------------------------------------------------------
    forbidden = {
        "run",
        "execute",
        "cancel",
        "retry",
        "approve",
        "resolve",
        "dispatch",
        "replan",
        "apply",
        "install_plan",
    }

    engine_methods = set(dir(engine))

    assert not forbidden.intersection(engine_methods)

    print("No execution / approval / retry / mutation authority: PASS")

    # ---------------------------------------------------------
    # ManagementManager remains authoritative
    # ---------------------------------------------------------
    revised_plan = manager.create_plan(
        planner_output=proposal.to_planner_output()
    )

    assert revised_plan
    assert state.current_plan == revised_plan
    assert state.current_plan != initial_plan

    print("ManagementManager accepted proposed plan: PASS")
    print("ManagementManager remains plan authority: PASS")

    monitor.unbind_event_bus()

    print("\n==============================================")
    print("PHASE 7H: ALL TESTS PASSED")
    print("REPLANNING PROPOSAL: PASS")
    print("MANAGEMENT AUTHORITY BOUNDARY: PASS")
    print("==============================================")


if __name__ == "__main__":
    main()
