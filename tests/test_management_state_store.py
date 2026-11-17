"""Tests for durable ManagementState persistence and restart recovery."""

import json

from core.dependency_graph import DependencyGraph
from core.events import Event, EventBus
from core.management.mission import Mission
from core.management.state import ManagementState, TaskState
from core.management.state_store import ManagementStateStore


def test_management_state_round_trip_preserves_task_groups(tmp_path):
    state = ManagementState(
        mission_id="mission-1",
        objective="Research a topic",
        status="RUNNING",
        completed_tasks={
            "done": TaskState(
                "done",
                "Completed work",
                status="COMPLETED",
                result={"finding": "verified"},
                metadata={"mission_id": "mission-1"},
            )
        },
    )
    store = ManagementStateStore(tmp_path / "management.json")
    store.save(state)

    restored = store.load()

    assert restored.mission_id == "mission-1"
    assert restored.completed_tasks["done"].result == {"finding": "verified"}
    assert restored.task_count() == 1


def test_restart_marks_interrupted_tasks_terminal_without_resuming(tmp_path):
    mission = Mission(
        objective="Run a managed mission",
        mission_id="mission-2",
        status="RUNNING",
    )
    state = ManagementState(
        mission_id=mission.mission_id,
        objective=mission.objective,
        status="RUNNING",
        active_tasks={
            "running": TaskState(
                "running",
                "Task interrupted mid-run",
                status="RUNNING",
                metadata={"mission_id": mission.mission_id},
            )
        },
        queued_tasks={
            "queued": TaskState(
                "queued",
                "Task waiting to start",
                status="QUEUED",
                metadata={"mission_id": mission.mission_id},
            )
        },
        completed_tasks={
            "done": TaskState(
                "done",
                "Completed task",
                status="COMPLETED",
                result={"ok": True},
                metadata={"mission_id": mission.mission_id},
            )
        },
        metadata={"mission": mission.to_dict()},
    )
    store = ManagementStateStore(tmp_path / "management.json")
    store.save(state)

    restored = store.load()

    assert "running" not in restored.active_tasks
    assert restored.failed_tasks["running"].status == "FAILED"
    assert "queued" not in restored.queued_tasks
    assert restored.blocked_tasks["queued"].status == "BLOCKED"
    assert restored.completed_tasks["done"].status == "COMPLETED"
    assert restored.status == "FAILED"
    assert restored.metadata["mission"]["status"] == "FAILED"
    assert restored.metadata["restart_recovery"]["requires_review"] is True


def test_state_store_redacts_sensitive_keys_recursively(tmp_path):
    state = ManagementState(
        metadata={
            "api_key": "top-secret",
            "nested": {"refresh_token": "also-secret", "safe": "visible"},
        }
    )
    path = tmp_path / "management.json"
    ManagementStateStore(path).save(state)

    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["metadata"]["api_key"] == "[REDACTED]"
    assert saved["metadata"]["nested"]["refresh_token"] == "[REDACTED]"
    assert saved["metadata"]["nested"]["safe"] == "visible"


def test_state_store_persists_after_event_bus_events(tmp_path):
    state = ManagementState()
    bus = EventBus()
    store = ManagementStateStore(tmp_path / "management.json")
    store.bind(state, bus)

    state.metadata["last_change"] = "event-persisted"
    bus.publish(Event("TEST_STATE_CHANGE", {}))

    restored = ManagementStateStore(tmp_path / "management.json").load()
    assert restored.metadata["last_change"] == "event-persisted"
    store.close()


def test_dependency_graph_is_rebuilt_from_restored_tasks(tmp_path):
    state = ManagementState(
        queued_tasks={
            "first": TaskState("first", "First", status="QUEUED"),
            "second": TaskState(
                "second",
                "Second",
                status="QUEUED",
                dependencies=["first"],
            ),
        }
    )
    graph = DependencyGraph()
    store = ManagementStateStore(tmp_path / "management.json")

    store.restore_dependency_graph(state, graph)

    assert graph.tasks() == ["first", "second"]
    assert graph.dependencies_of("second") == ["first"]


def test_missing_persisted_dependency_blocks_task_safely():
    state = ManagementState(
        queued_tasks={
            "orphan": TaskState(
                "orphan",
                "Task with missing dependency",
                status="QUEUED",
                dependencies=["missing"],
            )
        }
    )
    graph = DependencyGraph()

    ManagementStateStore("unused.json").restore_dependency_graph(state, graph)

    assert "orphan" not in state.queued_tasks
    assert state.blocked_tasks["orphan"].status == "BLOCKED"


def test_management_manager_restores_failed_mission_and_accepts_new_work(tmp_path):
    from core.management.manager import ManagementManager
    from core.task_manager import TaskManager

    mission = Mission(
        objective="Interrupted mission",
        mission_id="mission-restored",
        status="FAILED",
    )
    state = ManagementState(
        mission_id=mission.mission_id,
        objective=mission.objective,
        status="FAILED",
        metadata={"mission": mission.to_dict()},
    )
    bus = EventBus()
    tasks = TaskManager(state, bus)
    manager = ManagementManager(state, bus, tasks, DependencyGraph())

    assert manager.mission.mission_id == mission.mission_id
    assert manager.running is False
    next_mission = manager.accept_mission("A fresh mission")
    assert next_mission.status == "CREATED"
