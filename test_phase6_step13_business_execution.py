import asyncio

from core.agents.base import BaseAgent
from core.agents.dispatcher import AgentDispatcher
from core.agents.registry import AgentRegistry
from core.agents.result import AgentResult
from core.events import EventBus
from core.management.business_executor import BusinessTaskExecutor
from core.management.business_manager import BusinessManager
from core.management.evidence import EvidenceStore
from core.management.manager import ManagementManager
from core.management.state import ManagementState
from core.task_manager import TaskManager
from core.dependency_graph import DependencyGraph
from core.scheduler import Scheduler


class FakeBusinessAgent(BaseAgent):
    def __init__(self, name: str):
        self.name = name
        self.description = f"Controlled test agent: {name}"

    def run(self, task):
        return AgentResult(
            agent_name=self.name,
            task_id=task.task_id,
            status="SUCCESS",
            summary=f"{self.name} completed the business task.",
            findings=[
                f"Verified test finding from {self.name}."
            ],
            data={
                "objective": task.objective,
                "context": dict(task.context),
            },
        )


async def main() -> None:
    print("=== PHASE 6 STEP 13 BUSINESS EXECUTION INTEGRATION TEST ===")

    state = ManagementState()
    events = EventBus()
    task_manager = TaskManager(state, events)
    graph = DependencyGraph()

    management_manager = ManagementManager(
        state,
        events,
        task_manager,
        graph,
    )

    business_manager = BusinessManager(
        management_manager,
        events,
    )

    mission = management_manager.accept_mission(
        "Build a gaming print-on-demand business",
        context={
            "region": "Singapore",
            "test_mode": True,
        },
    )

    print("Business mission: PASS")

    registry = AgentRegistry()

    registry.register(FakeBusinessAgent("research_agent"))
    registry.register(FakeBusinessAgent("social_agent"))
    registry.register(FakeBusinessAgent("analytics_agent"))

    dispatcher = AgentDispatcher(registry)

    print("Agent registry / dispatcher: PASS")

    evidence = EvidenceStore()

    executor = BusinessTaskExecutor(
        dispatcher,
        evidence,
        mission_id=mission.mission_id,
    )

    print("Business execution bridge: PASS")

    task_ids = business_manager.create_business_tasks(
        mission.objective,
        context=mission.context,
    )

    assert len(task_ids) == 4

    print("Business tasks created: PASS")

    specialist_tasks = []

    for task_id in task_ids:
        task = task_manager.get_task(task_id)

        assert task is not None

        if task.agent_name:
            specialist_tasks.append(task)

    assert len(specialist_tasks) == 3

    print("Specialist task discovery: PASS")

    scheduler = Scheduler(
        task_manager,
        graph,
        max_workers=3,
    )

    snapshot = await scheduler.run(executor.run)

    print("SCHEDULER SNAPSHOT:")
    print(snapshot)

    for task_id in task_ids:
        task = task_manager.get_task(task_id)
        print(
            "TASK:",
            task_id,
            "STATUS:",
            task.status if task else None,
            "AGENT:",
            task.agent_name if task else None,
            "RESULT:",
            task.result if task else None,
            "ERROR:",
            task.error if task else None,
        )

    assert all(
        snapshot["task_states"][task_id] == "COMPLETED"
        for task_id in task_ids
    )

    print("Scheduler execution: PASS")

    executed_agents = {
        task_manager.get_task(task_id).agent_name
        for task_id in task_ids
        if task_manager.get_task(task_id) is not None
        and task_manager.get_task(task_id).agent_name
    }

    assert executed_agents == {
        "research_agent",
        "social_agent",
        "analytics_agent",
    }

    print("Specialist agent execution: PASS")

    records = evidence.for_mission(
        mission.mission_id
    )

    assert len(records) >= 6

    evidence_agents = {
        record.agent_name
        for record in records
    }

    assert {
        "research_agent",
        "social_agent",
        "analytics_agent",
    }.issubset(evidence_agents)

    print("Evidence / provenance recording: PASS")

    for task in specialist_tasks:
        task_records = evidence.for_task(task.task_id)

        assert task_records

        assert all(
            record.task_id == task.task_id
            for record in task_records
        )

    print("Task-level provenance: PASS")

    evaluation = next(
        task_manager.get_task(task_id)
        for task_id in task_ids
        if task_manager.get_task(task_id).metadata["plan_alias"]
        == "business_evaluation"
    )

    assert evaluation.status == "COMPLETED"
    assert evaluation.agent_name is None

    print("Dependency-gated evaluation: PASS")

    assert not hasattr(business_manager, "dispatch")
    assert not hasattr(business_manager, "run_agent")

    print("Business manager authority boundary: PASS")

    assert scheduler.running_count == 0
    assert scheduler.cancelled is False

    print("Final scheduler state: PASS")

    print()
    print("PHASE 6 STEP 13: ALL TESTS PASSED")


if __name__ == "__main__":
    asyncio.run(main())


