import pytest

from core.dependency_graph import DependencyGraph
from core.events.bus import EventBus
from core.management.manager import ManagementManager
from core.management.state import ManagementState
from core.task_manager import TaskManager


def build_manager():
    state = ManagementState()
    events = EventBus()
    tasks = TaskManager(state, events)
    graph = DependencyGraph()
    manager = ManagementManager(state, events, tasks, graph)
    manager.accept_mission("Complete a two-step workflow")
    return manager, tasks, graph, state


def test_planned_dependencies_are_enforced_by_task_manager():
    manager, tasks, graph, state = build_manager()

    task_ids = manager.create_planned_tasks([
        {"id": "research", "objective": "Research the topic"},
        {
            "id": "summary",
            "objective": "Summarise the research",
            "dependencies": ["research"],
        },
    ])

    research_id, summary_id = task_ids
    summary = tasks.get_task(summary_id)

    assert summary is not None
    assert summary.dependencies == [research_id]
    assert graph.dependencies_of(summary_id) == [research_id]

    with pytest.raises(ValueError, match="unresolved dependencies"):
        tasks.start_task(summary_id)

    tasks.start_task(research_id)
    tasks.complete_task(research_id, {"notes": "Research complete"})

    started_summary = tasks.start_task(summary_id)
    assert started_summary.status == "RUNNING"


def test_unknown_dependency_is_rejected_before_tasks_are_created():
    manager, tasks, graph, state = build_manager()

    with pytest.raises(ValueError, match="unknown dependencies"):
        manager.create_planned_tasks([
            {
                "id": "summary",
                "objective": "Summarise missing research",
                "dependencies": ["research"],
            },
        ])

    assert state.task_count() == 0
    assert graph.tasks() == []


def test_duplicate_plan_alias_is_rejected_before_tasks_are_created():
    manager, tasks, graph, state = build_manager()

    with pytest.raises(ValueError, match="Duplicate planned task alias"):
        manager.create_planned_tasks([
            {"id": "step", "objective": "First step"},
            {"id": "step", "objective": "Second step"},
        ])

    assert state.task_count() == 0
    assert graph.tasks() == []


def test_management_decisions_ignore_failed_tasks_from_previous_missions():
    manager, tasks, _graph, state = build_manager()
    first_id = manager.create_planned_tasks([
        {"id": "old", "objective": "Old mission work"}
    ])[0]
    tasks.start_task(first_id)
    tasks.fail_task(first_id, "Old mission failure")
    manager.fail_mission("First mission ended unsuccessfully")

    manager.accept_mission("A new independent mission")
    new_id = manager.create_planned_tasks([
        {"id": "new", "objective": "New mission work"}
    ])[0]

    decision = manager.evaluate()
    assert decision.decision.value == "CONTINUE"
    assert tasks.get_task(new_id).metadata["mission_id"] == manager.mission.mission_id
    assert tasks.get_task(first_id).metadata["mission_id"] != manager.mission.mission_id


def test_fail_mission_is_terminal_and_allows_a_new_mission():
    manager, _tasks, _graph, _state = build_manager()

    decision = manager.fail_mission("Stop this mission")
    assert decision.decision.value == "BLOCKED"
    assert manager.mission.status == "FAILED"
    assert manager.running is False

    next_mission = manager.accept_mission("Next mission")
    assert next_mission.status == "CREATED"
    assert manager.running is True


def test_completed_tasks_from_previous_mission_do_not_complete_new_mission():
    manager, tasks, _graph, _state = build_manager()
    first_id = manager.create_planned_tasks([
        {"id": "old", "objective": "Complete old work"}
    ])[0]
    tasks.start_task(first_id)
    tasks.complete_task(first_id, {"done": True})
    manager.complete_mission()

    manager.accept_mission("A new mission with no tasks yet")
    decision = manager.evaluate()

    assert decision.decision.value == "WAIT"



def test_dependency_cycle_is_rejected_before_any_tasks_are_created():
    manager, tasks, graph, state = build_manager()

    with pytest.raises(ValueError, match="dependencies contain a cycle"):
        manager.create_planned_tasks([
            {
                "id": "research",
                "objective": "Research the topic",
                "dependencies": ["summary"],
            },
            {
                "id": "summary",
                "objective": "Summarise the topic",
                "dependencies": ["research"],
            },
        ])

    assert state.task_count() == 0
    assert graph.tasks() == []
