import asyncio
import json

from core.events.bus import EventBus
from core.management.state import ManagementState
from core.task_manager import TaskManager
from core.dependency_graph import DependencyGraph
from core.scheduler import Scheduler
from core.management.manager import ManagementManager
from core.management.evidence import EvidenceStore
from core.management.business_manager import BusinessManager
from core.management.business_executor import BusinessTaskExecutor
from core.agents.registry import AgentRegistry
from core.agents.dispatcher import AgentDispatcher
from core.agents.research_agent import ResearchAgent
from core.agents.social_agent import SocialAgent
from core.agents.analytics_agent import AnalyticsAgent
from core.mission_intake import MissionIntake

import core.agents.research_agent as research_module
import core.agents.social_agent as social_module
import core.agents.analytics_agent as analytics_module


OBJECTIVE = "Evaluate a gaming-themed print-on-demand business using evidence."


def fake_llm(*, prompt, system=None, timeout=None):
    p = str(prompt)

    if "Create up to 3 focused research queries" in p:
        return json.dumps({
            "queries": [
                "gaming audience current market research",
                "gaming social media audience behavior",
            ]
        })

    if "Create up to 3 focused web-search queries" in p:
        return json.dumps({
            "queries": [
                "gaming social media audience research",
                "gaming TikTok Instagram YouTube research",
            ]
        })

    return (
        "SUMMARY:\n"
        "Gaming audience activity is documented in the supplied evidence.\n\n"
        "KEY FINDINGS:\n"
        "- Gaming audience activity is documented in the supplied evidence.\n"
        "- The supplied evidence does not establish demand or profitability.\n"
    )


def fake_web_search(*, parameters):
    return (
        "CONTROLLED TEST SOURCE\n"
        f"Query: {parameters.get('query', '')}\n"
        "Gaming audience activity is documented in this evidence.\n"
    )


research_module.call_llm_text = fake_llm
research_module.web_search = fake_web_search
social_module.call_llm_text = fake_llm
social_module.web_search = fake_web_search
analytics_module.call_llm_text = fake_llm


async def main():
    intake = MissionIntake().intake(
        OBJECTIVE,
        success_criteria=[
            "Gaming audience activity is documented in the supplied evidence."
        ],
        context={
            "analytics_data": {
                "research_scope": "gaming audience",
                "data_source": "controlled integration test",
            }
        },
    )

    bus = EventBus()
    state = ManagementState()
    tm = TaskManager(state, bus)
    graph = DependencyGraph()

    manager = ManagementManager(
        state,
        bus,
        tm,
        graph,
    )

    mission = manager.accept_mission(
        intake.objective,
        context=intake.to_context(),
    )

    business = BusinessManager(manager, bus)

    business.create_business_tasks(
        OBJECTIVE,
        context=intake.to_context(),
    )

    registry = AgentRegistry()
    registry.register(ResearchAgent())
    registry.register(SocialAgent())
    registry.register(AnalyticsAgent())

    dispatcher = AgentDispatcher(registry)
    evidence_store = EvidenceStore()

    executor = BusinessTaskExecutor(
        dispatcher,
        evidence_store,
        mission_id=mission.mission_id,
    )

    scheduler = Scheduler(
        tm,
        graph,
        max_workers=3,
    )

    snapshot = await scheduler.run(executor.run)

    print("\n=== SCHEDULER SNAPSHOT ===")
    print(json.dumps(snapshot, indent=2, default=str))

    print("\n=== ALL TASKS ===")

    for task_id in graph.tasks():
        task = tm.get_task(task_id)

        print("\nTASK:", task_id)
        print("ALIAS:", task.metadata.get("plan_alias"))
        print("AGENT:", task.agent_name)
        print("STATUS:", task.status)
        print("RESULT:", repr(task.result))
        print("ERROR:", repr(task.error))
        print("METADATA:", repr(task.metadata))

    print("\n=== EVIDENCE ===")

    for item in evidence_store.for_mission(mission.mission_id):
        print("\nAGENT:", item.agent_name)
        print("STATUS:", item.status)
        print("CLAIM:", item.claim)
        print("DETAILS:", item.details)

    print("\n=== EVIDENCE COUNT ===")
    print(len(evidence_store.for_mission(mission.mission_id)))


asyncio.run(main())
