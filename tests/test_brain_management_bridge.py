"""Integration tests for Brain plans managed by the task lifecycle."""

import pytest

from core.brain import BrainManagementBridge, MissionPlan, PlanStep, PlanStore
from core.dependency_graph import DependencyGraph
from core.events.bus import EventBus
from core.management.manager import ManagementManager
from core.management.state import ManagementState
from core.task_manager import TaskManager


def build_system(tmp_path):
    state = ManagementState()
    events = EventBus()
    tasks = TaskManager(state, events)
    management = ManagementManager(state, events, tasks, DependencyGraph())
    plan_store = PlanStore(tmp_path / "plans.json")
    bridge = BrainManagementBridge(management, plan_store)
    return management, tasks, bridge, plan_store


def make_plan():
    return MissionPlan(
        objective="Research and prepare a summary",
        steps=[
            PlanStep("research", "Research the subject", "research_agent"),
            PlanStep(
                "summary", "Prepare a grounded summary", "writing_agent",
                depends_on=["research"],
            ),
        ],
    )


def test_bridge_queues_plan_and_preserves_task_dependency_gate(tmp_path):
    management, tasks, bridge, store = build_system(tmp_path)
    plan = make_plan()
    management.accept_mission(plan.objective)

    research_id, summary_id = bridge.submit(plan)

    assert plan.status == "RUNNING"
    assert management.state.status == "RUNNING"
    assert len(management.state.current_plan) == 2
    assert management.state.to_dict()["current_plan"][0]["id"] == "research"
    assert tasks.get_task(summary_id).dependencies == [research_id]
    assert tasks.get_task(summary_id).metadata["brain_plan_id"] == plan.plan_id
    assert store.get(plan.plan_id).status == "RUNNING"
    with pytest.raises(ValueError, match="unresolved dependencies"):
        tasks.start_task(summary_id)


def test_bridge_mirrors_authoritative_task_events_and_persists_progress(tmp_path):
    management, tasks, bridge, store = build_system(tmp_path)
    plan = make_plan()
    management.accept_mission(plan.objective)
    research_id, summary_id = bridge.submit(plan)

    tasks.start_task(research_id)
    assert plan.steps[0].status == "RUNNING"

    tasks.complete_task(research_id, {"finding": "Evidence collected"})
    assert plan.steps[0].status == "COMPLETED"
    assert plan.steps[0].result == {"finding": "Evidence collected"}

    tasks.start_task(summary_id)
    tasks.complete_task(summary_id, {"summary": "Ready"})
    assert plan.status == "COMPLETED"
    assert [step.status for step in plan.steps] == ["COMPLETED", "COMPLETED"]

    restored = store.get(plan.plan_id)
    assert restored is not None
    assert restored.status == "COMPLETED"
    assert restored.steps[1].result == {"summary": "Ready"}


def test_bridge_does_not_run_dependent_step_after_upstream_failure(tmp_path):
    management, tasks, bridge, _store = build_system(tmp_path)
    plan = make_plan()
    management.accept_mission(plan.objective)
    research_id, summary_id = bridge.submit(plan)

    tasks.start_task(research_id)
    tasks.fail_task(research_id, "Research source unavailable")

    assert plan.steps[0].status == "FAILED"
    assert plan.steps[1].status == "PENDING"
    assert plan.status == "FAILED"
    with pytest.raises(ValueError, match="unresolved dependencies"):
        tasks.start_task(summary_id)


def test_bridge_rejects_plan_without_matching_active_mission(tmp_path):
    management, _tasks, bridge, _store = build_system(tmp_path)
    plan = make_plan()
    management.accept_mission("A different objective")

    with pytest.raises(ValueError, match="must match"):
        bridge.submit(plan)


def test_bridge_rejects_reused_or_already_running_plan(tmp_path):
    management, _tasks, bridge, _store = build_system(tmp_path)
    plan = make_plan()
    management.accept_mission(plan.objective)
    bridge.submit(plan)

    with pytest.raises(ValueError, match="fresh READY"):
        bridge.submit(plan)


def test_master_agent_queues_plan_through_bridge_without_dispatching_agents(tmp_path):
    from types import SimpleNamespace
    from core.agents.master import MasterAgent
    from core.agents.registry import AgentRegistry

    management, tasks, bridge, _store = build_system(tmp_path)
    plan = make_plan()
    management.accept_mission(plan.objective)
    registry = AgentRegistry()
    registry.register(SimpleNamespace(name="research_agent", description="Research"))
    registry.register(SimpleNamespace(name="writing_agent", description="Writing"))
    master = MasterAgent(registry, management_bridge=bridge)

    task_ids = master.queue_plan(plan)

    assert len(task_ids) == 2
    assert all(tasks.get_task(task_id).status == "QUEUED" for task_id in task_ids)
    assert plan.status == "RUNNING"


def test_master_agent_rejects_unregistered_specialists_before_queueing(tmp_path):
    from types import SimpleNamespace
    from core.agents.master import MasterAgent
    from core.agents.registry import AgentRegistry

    management, _tasks, bridge, _store = build_system(tmp_path)
    plan = make_plan()
    management.accept_mission(plan.objective)
    registry = AgentRegistry()
    registry.register(SimpleNamespace(name="research_agent", description="Research"))
    master = MasterAgent(registry, management_bridge=bridge)

    with pytest.raises(ValueError, match="unregistered agent"):
        master.queue_plan(plan)

    assert management.state.task_count() == 0


def test_master_agent_requires_bridge_before_queueing_plan():
    from core.agents.master import MasterAgent
    from core.agents.registry import AgentRegistry

    master = MasterAgent(AgentRegistry())
    with pytest.raises(RuntimeError, match="No BrainManagementBridge"):
        master.queue_plan(make_plan())


def test_bridge_restores_plan_tracking_from_loaded_task_metadata(tmp_path):
    management, tasks, bridge, store = build_system(tmp_path)
    plan = make_plan()
    management.accept_mission(plan.objective)
    research_id, summary_id = bridge.submit(plan)

    tasks.start_task(research_id)
    tasks.complete_task(research_id, {"finding": "Persisted finding"})
    bridge.close()

    recovered_bridge = BrainManagementBridge(management, store)
    restored = recovered_bridge.restore_plan(plan.plan_id)

    assert restored is not None
    assert restored.steps[0].status == "COMPLETED"
    assert restored.steps[0].result == {"finding": "Persisted finding"}
    assert restored.steps[1].status == "PENDING"

    tasks.start_task(summary_id)
    tasks.complete_task(summary_id, {"summary": "Recovered successfully"})
    assert restored.status == "COMPLETED"
    assert store.get(plan.plan_id).steps[1].result == {
        "summary": "Recovered successfully"
    }


def test_bridge_restore_requires_plan_store():
    state = ManagementState()
    events = EventBus()
    tasks = TaskManager(state, events)
    management = ManagementManager(state, events, tasks, DependencyGraph())
    bridge = BrainManagementBridge(management)

    with pytest.raises(RuntimeError, match="PlanStore"):
        bridge.restore_plan("missing")


def test_managed_master_disables_parallel_standalone_plan_execution(tmp_path):
    from core.agents.master import MasterAgent
    from core.agents.registry import AgentRegistry

    _management, _tasks, bridge, store = build_system(tmp_path)
    master = MasterAgent(
        AgentRegistry(),
        plan_store=store,
        management_bridge=bridge,
    )

    with pytest.raises(RuntimeError, match="Direct plan execution is disabled"):
        master.execute_plan(make_plan())
