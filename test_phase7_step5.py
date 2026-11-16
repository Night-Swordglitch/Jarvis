import asyncio

from core.agents.dispatcher import AgentDispatcher
from core.agents.registry import AgentRegistry
from core.agents.diagnostic_agent import DiagnosticAgent
from core.dependency_graph import DependencyGraph
from core.events.bus import EventBus
from core.management.business_executor import BusinessTaskExecutor
from core.management.evidence import EvidenceStore
from core.management.state import ManagementState
from core.scheduler import Scheduler
from core.task_manager import TaskManager


async def main():
    print("=== PHASE 7C — REAL AGENT EXECUTION TEST ===")

    # --------------------------------------------------------------
    # Existing Phase 6 management infrastructure
    # --------------------------------------------------------------

    state = ManagementState()
    event_bus = EventBus()
    task_manager = TaskManager(state, event_bus)
    dependency_graph = DependencyGraph()

    scheduler = Scheduler(
        task_manager,
        dependency_graph,
        max_workers=2,
    )

    print("Phase 6 execution infrastructure: PASS")

    # --------------------------------------------------------------
    # Existing real agent infrastructure
    # --------------------------------------------------------------

    registry = AgentRegistry()
    diagnostic_agent = DiagnosticAgent()

    registry.register(diagnostic_agent)

    assert registry.has(diagnostic_agent.name)
    assert diagnostic_agent.name in registry.names()

    dispatcher = AgentDispatcher(registry)

    print("Real specialist agent registered: PASS")
    print(f"Registered agent: {diagnostic_agent.name}")

    # --------------------------------------------------------------
    # Evidence ownership
    # --------------------------------------------------------------

    evidence = EvidenceStore()

    # --------------------------------------------------------------
    # Business execution bridge
    # --------------------------------------------------------------

    mission_id = "phase7c-test-mission"

    executor = BusinessTaskExecutor(
        dispatcher,
        evidence,
        mission_id=mission_id,
    )

    print("BusinessTaskExecutor connected: PASS")

    # --------------------------------------------------------------
    # Create an actual management task
    # --------------------------------------------------------------

    task = task_manager.create_task(
        objective="Perform a diagnostic health check of the MARK-L system.",
        priority=50,
        agent_name=diagnostic_agent.name,
        metadata={
            "context": {
                "source": "phase7c-test",
                "purpose": "real-agent-execution-validation",
            }
        },
    )

    assert task is not None
    assert task.agent_name == diagnostic_agent.name
    assert task.status == "QUEUED"

    dependency_graph.add_task(task.task_id)

    print("Management task created: PASS")

    # --------------------------------------------------------------
    # Execute through the REAL chain
    # --------------------------------------------------------------

    snapshot = await scheduler.run(executor.run)

    print("Scheduler → BusinessTaskExecutor → AgentDispatcher: PASS")

    # --------------------------------------------------------------
    # Verify TaskManager lifecycle
    # --------------------------------------------------------------

    completed = task_manager.get_task(task.task_id)

    assert completed is not None
    assert completed.status == "COMPLETED"

    print("TaskManager lifecycle completion: PASS")

    # --------------------------------------------------------------
    # Verify actual AgentResult-shaped output
    # --------------------------------------------------------------

    assert completed.result is not None

    result = completed.result

    assert isinstance(result, dict)
    assert result.get("agent_name") == diagnostic_agent.name
    assert result.get("task_id") == task.task_id
    assert result.get("status")

    print("Real AgentResult returned: PASS")

    # --------------------------------------------------------------
    # Verify evidence was produced
    # --------------------------------------------------------------

    records = evidence.for_mission(mission_id)

    assert isinstance(records, list)

    print(
        f"Evidence records produced: {len(records)}"
    )

    if result.get("summary") or result.get("findings"):
        assert len(records) > 0
        print("Agent evidence recorded: PASS")
    else:
        print("Agent produced no evidence-bearing output: PASS")

    # --------------------------------------------------------------
    # Verify scheduler state
    # --------------------------------------------------------------

    assert task.task_id not in scheduler.running_task_ids
    assert snapshot["task_states"][task.task_id] == "COMPLETED"

    print("Scheduler state synchronized: PASS")

    # --------------------------------------------------------------
    # Verify no second execution framework appeared
    # --------------------------------------------------------------

    assert not hasattr(executor, "execute_agent")
    assert not hasattr(executor, "dispatch_agent")

    print("No duplicate execution framework: PASS")

    print()
    print("==============================================")
    print("PHASE 7C FOUNDATION: ALL TESTS PASSED")
    print("MANAGEMENT TASK → REAL AGENT → RESULT: PASS")
    print("==============================================")


asyncio.run(main())
