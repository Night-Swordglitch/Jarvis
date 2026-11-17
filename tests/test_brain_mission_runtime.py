"""End-to-end tests for the Brain -> Management -> Scheduler runtime."""

import asyncio

import pytest

from core.agents import AgentRegistry, BaseAgent, AgentResult, MasterAgent
from core.agents.task import AgentTask
from core.brain import BrainManagementBridge, MissionPlan, PlanStep, PlanStore
from core.brain.runtime import BrainMissionRuntime
from core.dependency_graph import DependencyGraph
from core.events.bus import EventBus
from core.management.manager import ManagementManager
from core.management.state import ManagementState
from core.scheduler import Scheduler
from core.task_manager import TaskManager


class DemoAgent(BaseAgent):
    name = "demo_agent"
    description = "Test specialist."

    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    def can_handle(self, task):
        return True

    def run(self, task: AgentTask):
        self.calls.append(task)
        if self.fail:
            return AgentResult(
                agent_name=self.name,
                task_id=task.task_id,
                status="FAILED",
                summary="simulated specialist failure",
                errors=["simulated specialist failure"],
            )
        return AgentResult(
            agent_name=self.name,
            task_id=task.task_id,
            status="SUCCESS",
            summary=f"Completed: {task.objective}",
            data={"objective": task.objective},
            actions_requested=[{
                "action": "send_message",
                "parameters": {"text": "draft only"},
            }],
        )


class StaticPlanner:
    def __init__(self, plan=None, error=None):
        self.plan = plan
        self.error = error

    def create_plan(self, objective, context=None):
        if self.error:
            raise self.error
        return self.plan


def build_runtime(tmp_path, *, fail=False):
    state = ManagementState()
    events = EventBus()
    tasks = TaskManager(state, events)
    graph = DependencyGraph()
    management = ManagementManager(state, events, tasks, graph)
    scheduler = Scheduler(tasks, graph, max_workers=2)
    store = PlanStore(tmp_path / "brain-plans.json")
    bridge = BrainManagementBridge(management, store)

    agent = DemoAgent(fail=fail)
    registry = AgentRegistry()
    registry.register(agent)
    master = MasterAgent(
        registry,
        plan_store=store,
        management_bridge=bridge,
        event_bus=events,
    )
    master.goal_planner = StaticPlanner(MissionPlan(
        objective="Research then summarize",
        steps=[
            PlanStep("research", "Research the subject", "demo_agent"),
            PlanStep(
                "summary",
                "Summarize the evidence",
                "demo_agent",
                depends_on=["research"],
            ),
        ],
    ))

    def synthesize(objective, context, results):
        return AgentResult(
            agent_name="master",
            task_id="master-synthesis",
            status="SUCCESS" if any(item.success for item in results) else "FAILED",
            summary="Synthesized managed task results.",
            findings=["Synthesis complete."],
            data={"result_count": len(results)},
        )

    master.synthesize = synthesize
    runtime = BrainMissionRuntime(master, management, scheduler)
    return runtime, management, tasks, agent, store


def test_runtime_executes_plan_through_scheduler_and_dependency_gate(tmp_path):
    runtime, management, tasks, agent, store = build_runtime(tmp_path)

    result = asyncio.run(runtime.run("Research then summarize", {"source": "test"}))

    assert result["mission_status"] == "COMPLETED"
    assert result["plan"]["status"] == "COMPLETED"
    assert result["actions_executed"] == 0
    assert len(result["action_requests"]) == 2
    assert len(agent.calls) == 2
    assert agent.calls[1].context["dependency_results"]
    assert all(tasks.get_task(task_id).status == "COMPLETED" for task_id in result["task_ids"])
    assert store.get(result["plan"]["plan_id"]).status == "COMPLETED"
    assert management.mission.status == "COMPLETED"


def test_runtime_failure_blocks_dependents_without_automatic_retry(tmp_path):
    runtime, management, tasks, agent, _store = build_runtime(tmp_path, fail=True)

    result = asyncio.run(runtime.run("Research then summarize"))

    assert len(agent.calls) == 1
    assert result["mission_status"] == "FAILED"
    assert result["plan"]["status"] == "FAILED"
    assert result["scheduler"]["blocked"]
    assert management.mission.status == "FAILED"
    assert result["actions_executed"] == 0


def test_planning_failure_does_not_create_an_active_mission(tmp_path):
    runtime, management, _tasks, _agent, _store = build_runtime(tmp_path)
    runtime.master.goal_planner = StaticPlanner(error=RuntimeError("planner offline"))

    with pytest.raises(RuntimeError, match="planner offline"):
        asyncio.run(runtime.run("Research then summarize"))

    assert management.mission is None
