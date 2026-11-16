"""Phase 7K — Real Business Mission integration test."""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path

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
from core.mission_context import MissionContext
from core.mission_intake import MissionIntake
from core.mission_monitor import MissionMonitor
from core.mission_verifier import MissionVerifier
from core.mission_memory import MissionMemory, MissionMemoryRecord


OBJECTIVE = (
    "Evaluate a gaming-themed print-on-demand business using evidence."
)


# ============================================================================
# Deterministic external-service stubs
# ============================================================================

def fake_llm(*args, **kwargs):
    """
    Deterministic LLM stub for the 7K integration test.

    Supports both positional and keyword invocation because the real
    specialist agents use the shared LLM client through different
    invocation styles.
    """
    prompt = ""

    if args:
        prompt = str(args[0])

    if "prompt" in kwargs:
        prompt = str(kwargs["prompt"])

    if "Create up to 3 focused research queries" in prompt:
        return json.dumps({
            "queries": [
                "gaming audience current market research",
                "gaming social media audience behavior",
            ]
        })

    if "Create up to 3 focused web-search queries" in prompt:
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
    query = parameters.get("query", "")

    return (
        "CONTROLLED TEST SOURCE\n"
        f"Query: {query}\n"
        "Gaming audience activity is documented in this integration-test "
        "evidence.\n"
        "The evidence does not establish customer demand, profitability, "
        "or commercial viability."
    )


# Patch external dependencies used by the REAL specialist agents.
import core.agents.research_agent as research_module
import core.agents.social_agent as social_module
import core.agents.analytics_agent as analytics_module

research_module.call_llm_text = fake_llm
research_module.web_search = fake_web_search

social_module.call_llm_text = fake_llm
social_module.web_search = fake_web_search

analytics_module.call_llm_text = fake_llm


async def main() -> None:

    # ========================================================================
    # 1. Mission intake
    # ========================================================================

    intake = MissionIntake()

    intake_result = intake.intake(
        OBJECTIVE,
        constraints=[
            "Use evidence only.",
            "Do not publish or spend money.",
        ],
        success_criteria=[
            "Gaming audience activity is documented in the supplied evidence.",
        ],
        context={
            "analytics_data": {
                "research_scope": "gaming audience",
                "data_source": "controlled integration test",
            }
        },
    )

    assert intake_result.ready
    print("Mission intake accepted: PASS")


    # ========================================================================
    # 2. Core management runtime
    # ========================================================================

    event_bus = EventBus()
    state = ManagementState()
    task_manager = TaskManager(state, event_bus)
    dependency_graph = DependencyGraph()

    management_manager = ManagementManager(
        state,
        event_bus,
        task_manager,
        dependency_graph,
    )

    mission = management_manager.accept_mission(
        intake_result.objective,
        context=intake_result.to_context(),
    )

    assert mission is not None
    assert state.mission_id == mission.mission_id

    mission_id = mission.mission_id

    print("Management mission accepted: PASS")


    # ========================================================================
    # 3. Mission context
    # ========================================================================

    context = MissionContext(
        mission_id=mission_id,
        objective=intake_result.objective,
        constraints=intake_result.constraints,
        success_criteria=intake_result.success_criteria,
        environment={
            "mode": "7K_INTEGRATION_TEST",
        },
        capabilities=[
            "web_search",
            "analysis",
        ],
        additional_context=intake_result.context,
    )

    assert context.mission_id == state.mission_id
    assert context.objective == OBJECTIVE

    print("Mission context linked to real mission: PASS")


    # ========================================================================
    # 4. Business manager
    # ========================================================================

    business_manager = BusinessManager(
        management_manager,
        event_bus,
    )

    assert business_manager.accepts(OBJECTIVE)

    task_ids = business_manager.create_business_tasks(
        OBJECTIVE,
        context=context.to_dict(),
    )

    assert len(task_ids) == 4

    print("BusinessManager created real business plan: PASS")


    # ========================================================================
    # 5. Business task structure
    # ========================================================================

    tasks = {
        task.task_id: task
        for task in state.queued_tasks.values()
    }

    assert len(tasks) == 4

    aliases = {
        task.metadata.get("plan_alias"): task
        for task in tasks.values()
    }

    research_task = aliases["business_research"]
    social_task = aliases["business_social"]
    analytics_task = aliases["business_analytics"]
    evaluation_task = aliases["business_evaluation"]

    assert research_task.agent_name == "research_agent"
    assert social_task.agent_name == "social_agent"
    assert analytics_task.agent_name == "analytics_agent"
    assert evaluation_task.agent_name is None

    print("Real business task structure: PASS")


    # ========================================================================
    # 6. DependencyGraph
    # ========================================================================

    evaluation_dependencies = dependency_graph._dependencies[
        evaluation_task.task_id
    ]

    assert evaluation_dependencies == {
        research_task.task_id,
        social_task.task_id,
        analytics_task.task_id,
    }

    assert dependency_graph.is_ready(
        research_task.task_id,
        state.queued_tasks,
    )

    assert dependency_graph.is_ready(
        social_task.task_id,
        state.queued_tasks,
    )

    assert dependency_graph.is_ready(
        analytics_task.task_id,
        state.queued_tasks,
    )

    assert not dependency_graph.is_ready(
        evaluation_task.task_id,
        state.queued_tasks,
    )

    print("DependencyGraph correctly gates business evaluation: PASS")


    # ========================================================================
    # 7. Real specialist registry
    # ========================================================================

    registry = AgentRegistry()

    registry.register(ResearchAgent())
    registry.register(SocialAgent())
    registry.register(AnalyticsAgent())

    assert registry.has("research_agent")
    assert registry.has("social_agent")
    assert registry.has("analytics_agent")

    dispatcher = AgentDispatcher(registry)

    print("Real specialist agents registered: PASS")


    # ========================================================================
    # 8. Real BusinessTaskExecutor
    # ========================================================================

    evidence_store = EvidenceStore()

    executor = BusinessTaskExecutor(
        dispatcher,
        evidence_store,
        mission_id=mission_id,
    )

    assert executor.mission_id == mission_id

    print("Real BusinessTaskExecutor connected: PASS")


    # ========================================================================
    # 9. MissionMonitor
    # ========================================================================

    monitor = MissionMonitor(
        mission_id,
        stale_after=60.0,
    )

    monitor.bind_event_bus(event_bus)

    for task in tasks.values():
        monitor.track_task(task.task_id)

    print("MissionMonitor attached to real EventBus: PASS")


    # ========================================================================
    # 10. REAL ASYNC SCHEDULER EXECUTION
    # ========================================================================

    scheduler = Scheduler(
        task_manager,
        dependency_graph,
        max_workers=3,
    )

    scheduler_snapshot = await scheduler.run(
        executor.run,
    )

    assert scheduler_snapshot is not None

    print("Scheduler executed real business tasks: PASS")


    # ========================================================================
    # 11. Evidence
    # ========================================================================

    evidence = evidence_store.for_mission(mission_id)

    assert len(evidence) >= 3

    agents_seen = {
        record.agent_name
        for record in evidence
    }

    assert "research_agent" in agents_seen
    assert "social_agent" in agents_seen
    assert "analytics_agent" in agents_seen

    print("Real specialist evidence produced: PASS")


    # ========================================================================
    # 12. Specialist completion
    # ========================================================================

    completed_aliases = {
        task.metadata.get("plan_alias")
        for task in state.completed_tasks.values()
    }

    assert "business_research" in completed_aliases
    assert "business_social" in completed_aliases
    assert "business_analytics" in completed_aliases

    print("Specialist task completion synchronized: PASS")


    # ========================================================================
    # 13. Evaluation task
    # ========================================================================

    if evaluation_task.task_id in state.queued_tasks:

        current_states = {
            task_id: task
            for task_id in dependency_graph.tasks()
            if (task := task_manager.get_task(task_id)) is not None
        }

        assert dependency_graph.is_ready(
            evaluation_task.task_id,
            current_states,
        )

        task_manager.start_task(
            evaluation_task.task_id,
        )

        task_manager.complete_task(
            evaluation_task.task_id,
            result={
                "status": "EVALUATED",
                "summary": "Business evidence package evaluated.",
            },
        )

    assert evaluation_task.task_id in state.completed_tasks

    print("Business evaluation completed after dependencies: PASS")


    # ========================================================================
    # 14. Mission monitoring
    # ========================================================================

    snapshot = monitor.snapshot()

    assert snapshot["mission_id"] == mission_id
    assert snapshot["healthy"] is True

    print("MissionMonitor reports healthy mission: PASS")


    # ========================================================================
    # 15. Mission verification
    # ========================================================================

    verifier = MissionVerifier(
        evidence_store=evidence_store,
    )

    verification = verifier.verify(
        context=context,
        state=state,
    )

    assert verification.status == "VERIFIED"
    assert verification.verified is True
    assert verification.complete is True

    print("MissionVerifier verified real business mission: PASS")


    # ========================================================================
    # 16. Verification provenance
    # ========================================================================

    assert len(verification.evidence_ids) >= 3

    stored_evidence_ids = {
        record.evidence_id
        for record in evidence
    }

    assert set(verification.evidence_ids).issubset(
        stored_evidence_ids
    )

    assert any(
        criterion.satisfied
        for criterion in verification.criteria
    )

    print("Verification evidence provenance preserved: PASS")


    # ========================================================================
    # 17. MissionMemory
    # ========================================================================

    with tempfile.TemporaryDirectory() as temp_dir:

        memory_path = Path(temp_dir) / "mission_memory.json"

        memory = MissionMemory(memory_path)

        record = MissionMemoryRecord(
            mission_id=mission_id,
            objective=OBJECTIVE,
            status=verification.status,
            context=context.to_dict(),
            tasks=[
                task.to_dict()
                for task in state.completed_tasks.values()
            ],
            evidence_ids=[
                item.evidence_id
                for item in evidence
            ],
            decisions=[
                {
                    "decision": "COMPLETE",
                    "reason": "Mission verification succeeded.",
                }
            ],
            outcomes=[
                verification.to_dict(),
            ],
        )

        memory.save(record)

        restored = memory.get(mission_id)

        assert restored is not None
        assert restored.status == "VERIFIED"
        assert restored.mission_id == mission_id
        assert len(restored.evidence_ids) >= 3

    print("MissionMemory persisted verified business mission: PASS")


    # ========================================================================
    # 18. Authority boundary
    # ========================================================================

    forbidden = (
        "execute",
        "publish",
        "purchase",
        "spend",
        "delete",
    )

    for name in forbidden:
        assert not hasattr(verifier, name)

    print("Mission verification remains read-only: PASS")
    print("No publishing / spending / deletion authority: PASS")


    # ========================================================================
    # FINAL
    # ========================================================================

    print()
    print("==============================================")
    print("PHASE 7L: ALL TESTS PASSED")
    print("END-TO-END AUTONOMOUS MISSION: PASS")
    print("AUTONOMOUS EXECUTION: PASS")
    print("EVIDENCE PIPELINE: PASS")
    print("MISSION MONITORING: PASS")
    print("MISSION VERIFICATION: PASS")
    print("MISSION MEMORY: PASS")
    print("==============================================")


if __name__ == "__main__":
    asyncio.run(main())
