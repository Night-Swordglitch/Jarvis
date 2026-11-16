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
