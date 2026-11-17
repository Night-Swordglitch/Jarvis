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
from core.management.state_store import ManagementStateStore
from core.scheduler import Scheduler
from core.task_manager import TaskManager


class DemoAgent(BaseAgent):
    name = "demo_agent"
    description = "Test specialist."

    def __init__(self, fail=False, fail_on=None, partial_on=None):
        self.calls = []
        self.fail = fail
        self.fail_on = set(fail_on or [])
        self.partial_on = set(partial_on or [])

    def can_handle(self, task):
        return True

    def run(self, task: AgentTask):
        self.calls.append(task)
        if task.objective in self.partial_on:
            return AgentResult(
                agent_name=self.name,
                task_id=task.task_id,
                status="PARTIAL",
                summary="Only partial work was completed.",
                findings=["Partial result."],
            )
        if self.fail or task.objective in self.fail_on:
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
            data={"objective": task.objective, "api_key": "test-secret"},
            actions_requested=[{
                "action": "send_message",
                "parameters": {"text": "draft only"},
            }],
        )


class StaticPlanner:
    def __init__(self, plan=None, error=None, recovery_plan=None):
        self.plan = plan
        self.error = error
        self.recovery_plan = recovery_plan

    def create_plan(self, objective, context=None):
        if self.error:
            raise self.error
        if context and context.get("recovery_context") and self.recovery_plan:
            return self.recovery_plan
        return self.plan


def build_runtime(tmp_path, *, fail=False, fail_on=None, partial_on=None, recovery_plan=None):
    state = ManagementState()
    events = EventBus()
    tasks = TaskManager(state, events)
    graph = DependencyGraph()
    management = ManagementManager(state, events, tasks, graph)
    scheduler = Scheduler(tasks, graph, max_workers=2)
    store = PlanStore(tmp_path / "brain-plans.json")
    bridge = BrainManagementBridge(management, store)

    agent = DemoAgent(fail=fail, fail_on=fail_on, partial_on=partial_on)
    registry = AgentRegistry()
    registry.register(agent)
    master = MasterAgent(
        registry,
        plan_store=store,
        management_bridge=bridge,
        event_bus=events,
    )
    assert master.plan_store is store
    master.goal_planner = StaticPlanner(
        plan=MissionPlan(
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
        ),
        recovery_plan=recovery_plan,
    )

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
    unrelated = tasks.create_task("Unrelated task from another mission")
    runtime.scheduler.dependency_graph.add_task(unrelated.task_id)

    result = asyncio.run(runtime.run("Research then summarize", {"source": "test"}))

    assert result["mission_status"] == "COMPLETED"
    assert result["plan"]["status"] == "COMPLETED"
    assert result["actions_executed"] == 0
    assert len(result["action_requests"]) == 2
    assert len(agent.calls) == 2
    assert agent.calls[1].context["dependency_results"]
    assert all(tasks.get_task(task_id).status == "COMPLETED" for task_id in result["task_ids"])
    assert tasks.get_task(unrelated.task_id).status == "QUEUED"
    assert unrelated.task_id not in result["scheduler"]["task_states"]
    assert store.get(result["plan"]["plan_id"]).status == "COMPLETED"
    assert management.mission.status == "COMPLETED"


def test_runtime_failure_blocks_dependents_and_proposes_recovery_without_retry(tmp_path):
    recovery_plan = MissionPlan(
        objective="Research then summarize",
        steps=[
            PlanStep(
                "alternate_research",
                "Try an alternate evidence source",
                "demo_agent",
            )
        ],
        summary="Alternative research route.",
    )
    runtime, management, tasks, agent, store = build_runtime(
        tmp_path,
        fail=True,
        recovery_plan=recovery_plan,
    )

    result = asyncio.run(runtime.run("Research then summarize"))

    assert len(agent.calls) == 1
    assert result["mission_status"] == "FAILED"
    assert result["plan"]["status"] == "FAILED"
    assert result["scheduler"]["blocked"]
    assert result["monitor"]["healthy"] is False
    assert result["replan_proposal"] is not None
    assert set(result["replan_proposal"]["failed_task_ids"]) == set(result["task_ids"])
    recovery_id = result["replan_proposal"]["metadata"]["brain_plan_id"]
    assert store.get(recovery_id).status == "READY"
    assert tasks.state.task_count() == 2  # proposal was not queued or retried
    assert management.mission.status == "FAILED"
    assert result["actions_executed"] == 0


def test_recovery_proposal_preserves_completed_work(tmp_path):
    recovery_plan = MissionPlan(
        objective="Research then summarize",
        steps=[
            PlanStep(
                "alternate_summary",
                "Prepare the summary using a different structure",
                "demo_agent",
            )
        ],
        summary="Alternative summary route.",
    )
    runtime, _management, tasks, agent, store = build_runtime(
        tmp_path,
        fail_on={"Summarize the evidence"},
        recovery_plan=recovery_plan,
    )

    result = asyncio.run(runtime.run("Research then summarize"))

    assert [call.objective for call in agent.calls] == [
        "Research the subject",
        "Summarize the evidence",
    ]
    assert tasks.get_task(result["task_ids"][0]).status == "COMPLETED"
    assert result["replan_proposal"] is not None
    assert result["replan_proposal"]["metadata"]["preserved_completed_steps"] == [
        "research"
    ]
    recovery_id = result["replan_proposal"]["metadata"]["brain_plan_id"]
    proposed = store.get(recovery_id)
    assert proposed is not None
    assert all(step.objective != "Research the subject" for step in proposed.steps)


def test_planning_failure_does_not_create_an_active_mission(tmp_path):
    runtime, management, _tasks, _agent, _store = build_runtime(tmp_path)
    runtime.master.goal_planner = StaticPlanner(error=RuntimeError("planner offline"))

    with pytest.raises(RuntimeError, match="planner offline"):
        asyncio.run(runtime.run("Research then summarize"))

    assert management.mission is None


def test_synthesis_failure_does_not_mark_completed_tasks_as_a_completed_mission(tmp_path):
    runtime, management, tasks, _agent, _store = build_runtime(tmp_path)

    def failed_synthesis(objective, context, results):
        return AgentResult(
            agent_name="master",
            task_id="master-synthesis",
            status="FAILED",
            summary="Synthesis service unavailable.",
            errors=["Synthesis service unavailable."],
        )

    runtime.master.synthesize = failed_synthesis
    result = asyncio.run(runtime.run("Research then summarize"))

    assert all(tasks.get_task(task_id).status == "COMPLETED" for task_id in result["task_ids"])
    assert result["mission_status"] == "FAILED"
    assert management.mission.status == "FAILED"
    assert result["management_decision"]["decision"] == "BLOCKED"



def test_scheduler_shutdown_marks_running_work_cancelled():
    async def scenario():
        state = ManagementState()
        events = EventBus()
        tasks = TaskManager(state, events)
        graph = DependencyGraph()
        scheduler = Scheduler(tasks, graph, max_workers=1)
        task = tasks.create_task("A task interrupted during shutdown")
        graph.add_task(task.task_id)
        started = asyncio.Event()

        async def runner(_task):
            started.set()
            await asyncio.Event().wait()

        execution = asyncio.create_task(
            scheduler.run(runner, task_ids={task.task_id})
        )
        await asyncio.wait_for(started.wait(), timeout=2)
        await scheduler.shutdown()
        snapshot = await asyncio.wait_for(execution, timeout=2)

        restored_task = tasks.get_task(task.task_id)
        assert restored_task is not None
        assert restored_task.status == "CANCELLED"
        assert snapshot["task_states"][task.task_id] == "CANCELLED"

    asyncio.run(scenario())



def test_runtime_terminalizes_mission_when_scheduler_aborts(tmp_path):
    runtime, management, tasks, agent, _store = build_runtime(tmp_path)

    async def fail_scheduler(_runner, *, task_ids=None):
        raise RuntimeError("scheduler state mismatch")

    runtime.scheduler.run = fail_scheduler
    result = asyncio.run(runtime.run("Research then summarize"))

    assert result["scheduler_error"] == "RuntimeError: scheduler state mismatch"
    assert result["mission_status"] == "FAILED"
    assert management.mission.status == "FAILED"
    assert all(
        tasks.get_task(task_id).status == "BLOCKED"
        for task_id in result["task_ids"]
    )
    assert agent.calls == []
    assert result["actions_executed"] == 0



def test_runtime_rejects_a_scheduler_with_a_different_task_manager(tmp_path):
    runtime, management, _tasks, _agent, _store = build_runtime(tmp_path)
    other_state = ManagementState()
    other_events = EventBus()
    other_tasks = TaskManager(other_state, other_events)
    other_scheduler = Scheduler(other_tasks, DependencyGraph())

    with pytest.raises(ValueError, match="share one TaskManager"):
        BrainMissionRuntime(runtime.master, management, other_scheduler)


def test_runtime_rejects_a_scheduler_with_a_different_dependency_graph(tmp_path):
    runtime, management, _tasks, _agent, _store = build_runtime(tmp_path)
    other_scheduler = Scheduler(
        management.task_manager,
        DependencyGraph(),
    )

    with pytest.raises(ValueError, match="share one DependencyGraph"):
        BrainMissionRuntime(runtime.master, management, other_scheduler)


def test_saved_recovery_plan_runs_only_after_explicit_resume_request(tmp_path):
    recovery_plan = MissionPlan(
        objective="Research then summarize",
        steps=[
            PlanStep(
                "alternate_summary",
                "Prepare the summary using a different structure",
                "demo_agent",
            )
        ],
        summary="Alternative summary route.",
    )
    runtime, management, tasks, agent, store = build_runtime(
        tmp_path,
        fail_on={"Summarize the evidence"},
        recovery_plan=recovery_plan,
    )

    first_result = asyncio.run(runtime.run("Research then summarize"))
    recovery_id = first_result["replan_proposal"]["metadata"]["brain_plan_id"]
    proposal_record = management.state.metadata["replan_proposals"][recovery_id]
    assert proposal_record["status"] == "PROPOSED"
    assert store.get(recovery_id).status == "READY"

    # The test explicitly accepts the saved proposal by calling run_saved_plan.
    agent.fail_on.clear()
    resumed_result = asyncio.run(runtime.run_saved_plan(recovery_id))

    assert resumed_result["mission_status"] == "COMPLETED"
    assert resumed_result["plan"]["status"] == "COMPLETED"
    assert len(agent.calls) == 3
    resume_context = agent.calls[-1].context["recovery_context"]
    assert resume_context["user_approved_resume"] is True
    completed_research = next(
        item for item in resume_context["completed_steps"]
        if item["objective"] == "Research the subject"
    )
    assert completed_research["result"]["data"]["api_key"] == "[REDACTED]"
    assert tasks.get_task(first_result["task_ids"][0]).status == "COMPLETED"
    assert store.get(recovery_id).status == "COMPLETED"
    assert management.state.metadata["replan_proposals"][recovery_id]["status"] == "COMPLETED"

    with pytest.raises(ValueError, match="Only a READY saved recovery plan"):
        asyncio.run(runtime.run_saved_plan(recovery_id))


def test_saved_plan_cannot_be_run_without_a_proposed_recovery_record(tmp_path):
    runtime, _management, _tasks, _agent, store = build_runtime(tmp_path)
    plan = MissionPlan(
        objective="Research then summarize",
        steps=[PlanStep("single", "Do safe research", "demo_agent")],
    )
    store.save(plan)

    with pytest.raises(ValueError, match="not an unaccepted recovery proposal"):
        asyncio.run(runtime.run_saved_plan(plan.plan_id))



def test_proposed_recovery_plan_can_be_explicitly_resumed_after_restart(tmp_path):
    recovery_plan = MissionPlan(
        objective="Research then summarize",
        steps=[
            PlanStep(
                "alternate_summary",
                "Prepare an alternate summary from completed research",
                "demo_agent",
            )
        ],
        summary="Alternative summary after restart.",
    )
    runtime, management, _tasks, agent, plan_store = build_runtime(
        tmp_path,
        fail_on={"Summarize the evidence"},
        recovery_plan=recovery_plan,
    )
    first_result = asyncio.run(runtime.run("Research then summarize"))
    recovery_id = first_result["replan_proposal"]["metadata"]["brain_plan_id"]

    state_path = tmp_path / "management-state.json"
    ManagementStateStore(state_path).save(management.state)

    restored_state = ManagementStateStore(state_path).load()
    restored_events = EventBus()
    restored_tasks = TaskManager(restored_state, restored_events)
    restored_graph = DependencyGraph()
    ManagementStateStore(state_path).restore_dependency_graph(
        restored_state,
        restored_graph,
    )
    restored_management = ManagementManager(
        restored_state,
        restored_events,
        restored_tasks,
        restored_graph,
    )
    restored_bridge = BrainManagementBridge(restored_management, plan_store)
    for saved_plan in plan_store.all():
        if saved_plan.status in {"RUNNING", "PARTIAL", "FAILED"}:
            restored_bridge.restore_plan(saved_plan.plan_id)

    resumed_agent = DemoAgent()
    registry = AgentRegistry()
    registry.register(resumed_agent)
    restored_master = MasterAgent(
        registry,
        plan_store=plan_store,
        management_bridge=restored_bridge,
        event_bus=restored_events,
    )

    def synthesize(objective, context, results):
        return AgentResult(
            agent_name="master",
            task_id="master-synthesis",
            status="SUCCESS",
            summary="Recovery synthesis completed.",
            findings=["Recovery complete."],
        )

    restored_master.synthesize = synthesize
    restored_scheduler = Scheduler(restored_tasks, restored_graph, max_workers=2)
    restored_runtime = BrainMissionRuntime(
        restored_master,
        restored_management,
        restored_scheduler,
    )

    resumed = asyncio.run(restored_runtime.run_saved_plan(recovery_id))

    assert resumed["mission_status"] == "COMPLETED"
    assert resumed_agent.calls[0].context["recovery_context"]["user_approved_resume"] is True
    assert any(
        item["objective"] == "Research the subject"
        for item in resumed_agent.calls[0].context["recovery_context"]["completed_steps"]
    )
    assert plan_store.get(recovery_id).status == "COMPLETED"
    assert restored_state.metadata["replan_proposals"][recovery_id]["status"] == "COMPLETED"



def test_runtime_does_not_mark_partial_specialist_output_as_completed(tmp_path):
    runtime, management, tasks, agent, _store = build_runtime(
        tmp_path,
        partial_on={"Research the subject"},
    )

    result = asyncio.run(runtime.run("Research then summarize"))

    assert result["mission_status"] == "FAILED"
    assert len(agent.calls) == 1
    first_task = tasks.get_task(result["task_ids"][0])
    second_task = tasks.get_task(result["task_ids"][1])
    assert first_task.status == "FAILED"
    assert second_task.status == "BLOCKED"
    assert management.mission.status == "FAILED"
    assert result["actions_executed"] == 0
