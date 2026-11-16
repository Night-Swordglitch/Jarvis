"""Tests for MARK-L's bounded planning brain."""

import pytest

from core.agents.base import BaseAgent
from core.agents.dispatcher import AgentDispatcher
from core.agents.registry import AgentRegistry
from core.agents.result import AgentResult
from core.agents.task import AgentTask
from core.agents.master import MasterAgent
from core.brain import BrainMemory, GoalPlanner, MissionPlan, PlanExecutor, PlanStep, PlanStore, PlanningError


class RecordingAgent(BaseAgent):
    name = "research_agent"
    description = "Performs test research tasks."

    def __init__(self, *, fail=False):
        self.calls = []
        self.fail = fail

    def can_handle(self, task):
        return True

    def run(self, task):
        self.calls.append(task)
        if self.fail:
            return AgentResult(
                agent_name=self.name,
                task_id=task.task_id,
                status="FAILED",
                summary="simulated failure",
                errors=["simulated failure"],
            )
        return AgentResult(
            agent_name=self.name,
            task_id=task.task_id,
            status="SUCCESS",
            summary="completed",
            findings=[task.objective],
            actions_requested=[{"action": "send_message", "parameters": {"text": "draft"}}],
        )


def registry_with_agent(agent=None):
    registry = AgentRegistry()
    registry.register(agent or RecordingAgent())
    return registry


def test_planner_builds_validated_plan_from_llm_json():
    registry = registry_with_agent()
    response = {
        "summary": "Research then summarize.",
        "steps": [
            {
                "step_id": "research",
                "objective": "Research the topic",
                "agent_name": "research_agent",
                "depends_on": [],
                "success_criteria": ["Evidence is collected"],
                "priority": 70,
            },
            {
                "step_id": "summary",
                "objective": "Summarize the research",
                "agent_name": "research_agent",
                "depends_on": ["research"],
                "success_criteria": ["Summary is grounded in evidence"],
            },
        ],
    }
    planner = GoalPlanner(registry, llm=lambda **_kwargs: __import__("json").dumps(response))
    plan = planner.create_plan("Understand the topic", context={"source": "user"})
    assert plan.status == "READY"
    assert len(plan.steps) == 2
    assert plan.steps[1].depends_on == ["research"]
    assert MissionPlan.from_dict(plan.to_dict()).to_dict() == plan.to_dict()


def test_planner_rejects_unknown_agent_and_cycles():
    registry = registry_with_agent()
    unknown = {
        "steps": [{
            "step_id": "x", "objective": "Do work",
            "agent_name": "made_up_agent", "depends_on": [],
        }]
    }
    planner = GoalPlanner(registry, llm=lambda **_kwargs: __import__("json").dumps(unknown))
    with pytest.raises(PlanningError, match="unregistered agent"):
        planner.create_plan("Test objective")

    cycle = {
        "steps": [
            {"step_id": "a", "objective": "A", "agent_name": "research_agent", "depends_on": ["b"]},
            {"step_id": "b", "objective": "B", "agent_name": "research_agent", "depends_on": ["a"]},
        ]
    }
    planner = GoalPlanner(registry, llm=lambda **_kwargs: __import__("json").dumps(cycle))
    with pytest.raises(PlanningError, match="cycle"):
        planner.create_plan("Test objective")


def test_planner_rejects_invalid_json_and_empty_plan():
    registry = registry_with_agent()
    with pytest.raises(PlanningError, match="valid JSON"):
        GoalPlanner(registry, llm=lambda **_kwargs: "not json").create_plan("Test")
    with pytest.raises(PlanningError, match="between 1"):
        GoalPlanner(registry, llm=lambda **_kwargs: '{"steps": []}').create_plan("Test")


def test_executor_obeys_dependencies_and_records_action_requests_without_running_them():
    agent = RecordingAgent()
    registry = registry_with_agent(agent)
    plan = MissionPlan(
        objective="Research and summarize",
        steps=[
            PlanStep(
                step_id="summary",
                objective="Summarize the findings",
                agent_name="research_agent",
                depends_on=["research"],
            ),
            PlanStep(
                step_id="research",
                objective="Collect evidence",
                agent_name="research_agent",
            ),
        ],
    )

    result = PlanExecutor(registry, AgentDispatcher(registry)).execute(plan)

    assert plan.status == "COMPLETED"
    assert [step.status for step in plan.steps] == ["COMPLETED", "COMPLETED"]
    assert [task.objective for task in agent.calls] == [
        "Collect evidence",
        "Summarize the findings",
    ]
    assert "research" in agent.calls[1].context["dependency_results"]
    assert result["actions_executed"] == 0
    assert result["action_requests"][0]["action"] == "send_message"


def test_executor_blocks_dependents_when_dependency_fails():
    agent = RecordingAgent(fail=True)
    registry = registry_with_agent(agent)
    plan = MissionPlan(
        objective="Dependent plan",
        steps=[
            PlanStep(
                step_id="followup",
                objective="Continue only after research",
                agent_name="research_agent",
                depends_on=["research"],
            ),
            PlanStep(
                step_id="research",
                objective="Research the topic",
                agent_name="research_agent",
            ),
        ],
    )

    result = PlanExecutor(registry).execute(plan)
    assert plan.status == "FAILED"
    assert plan.steps[0].status == "BLOCKED"
    assert plan.steps[1].status == "FAILED"
    assert len(agent.calls) == 1
    assert result["actions_executed"] == 0


def test_plan_rejects_self_dependency_and_unknown_dependency():
    with pytest.raises(ValueError, match="cannot depend on itself"):
        MissionPlan(
            objective="Bad plan",
            steps=[PlanStep("one", "Do one", "research_agent", ["one"])],
        )
    with pytest.raises(ValueError, match="unknown dependencies"):
        MissionPlan(
            objective="Bad plan",
            steps=[PlanStep("one", "Do one", "research_agent", ["missing"])],
        )


def test_master_exposes_plan_and_execution_interfaces():
    agent = RecordingAgent()
    registry = registry_with_agent(agent)
    master = MasterAgent(registry)
    master.goal_planner = GoalPlanner(
        registry,
        llm=lambda **_kwargs: (
            '{"steps":[{"step_id":"inspect","objective":"Inspect the topic",'
            '"agent_name":"research_agent","depends_on":[]}]}'
        ),
    )

    plan = master.create_plan("Inspect the topic")
    assert isinstance(plan, MissionPlan)
    result = master.execute_plan(plan)
    assert result["status"] == "COMPLETED"
    restored = master.load_plan(plan.plan_id)
    assert restored is not None
    assert restored.status == "COMPLETED"
    assert restored.steps[0].status == "COMPLETED"
    assert len(agent.calls) == 1


def test_plan_store_round_trips_progress_and_removes_records(tmp_path):
    store = PlanStore(tmp_path / "brain" / "plans.json")
    plan = MissionPlan(
        objective="Persist this plan",
        steps=[PlanStep("inspect", "Inspect source", "research_agent")],
    )
    store.save(plan)
    restored = store.get(plan.plan_id)
    assert restored is not None
    assert restored.to_dict() == plan.to_dict()
    assert len(store) == 1
    assert store.remove(plan.plan_id) is True
    assert store.get(plan.plan_id) is None
    assert store.remove(plan.plan_id) is False


def test_brain_memory_recalls_project_facts_only():
    memory = BrainMemory(loader=lambda: {
        "identity": {"name": {"value": "Private Identity"}},
        "relationships": {"relative": {"value": "Private relationship"}},
        "projects": {
            "lunevia_store": {"value": "LUNEVIA storefront uses Printify and USD."},
            "jarvis": {"value": "MARK-L JARVIS has a specialist agent architecture."},
        },
    })
    results = memory.recall_project_context("Improve the JARVIS agent architecture")
    assert len(results) == 1
    assert results[0]["key"] == "jarvis"
    assert "Private" not in str(results)


def test_planner_includes_relevant_project_memory_as_context():
    registry = registry_with_agent()
    captured = {}
    memory = BrainMemory(loader=lambda: {
        "projects": {
            "jarvis": {"value": "JARVIS uses a local Ollama model."},
        }
    })

    def fake_llm(**kwargs):
        captured["prompt"] = kwargs["prompt"]
        return (
            '{"steps":[{"step_id":"inspect","objective":"Inspect the agent framework",'
            '"agent_name":"research_agent","depends_on":[]}]}'
        )

    GoalPlanner(registry, llm=fake_llm, memory_provider=memory).create_plan(
        "Improve JARVIS agent framework"
    )
    assert "JARVIS uses a local Ollama model" in captured["prompt"]
