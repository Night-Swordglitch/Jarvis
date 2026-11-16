"""Phase 1 agent framework test."""

from core.agents import AgentTask, AgentRegistry, AgentDispatcher
from core.agents.tests.test_agent import TestAgent


def main() -> None:
    print()
    print("=" * 60)
    print("MARK-L AGENT PIPELINE TEST")
    print("=" * 60)

    # 1. Create registry
    registry = AgentRegistry()

    # 2. Create specialist
    agent = TestAgent()

    # 3. Register specialist
    registry.register(agent)

    print()
    print("[1] Registered agents:")
    print("    ", registry.names())

    # 4. Create task
    task = AgentTask(
        objective="Verify that the MARK-L agent system is operational.",
        context={
            "test": True,
            "phase": "1B",
        },
        requested_by="phase1_test",
    )

    print()
    print("[2] Created task:")
    print("    ", task.describe())

    # 5. Create dispatcher
    dispatcher = AgentDispatcher(registry)

    # 6. Dispatch task
    print()
    print("[3] Dispatching task...")

    result = dispatcher.dispatch(
        agent_name="test_agent",
        task=task,
    )

    # 7. Display result
    print()
    print("[4] Agent result:")
    print("    Agent:", result.agent_name)
    print("    Status:", result.status)
    print("    Success:", result.success)

    print()
    print("[5] Findings:")

    for finding in result.findings:
        print("    -", finding)

    print()
    print("[6] Data:")
    print("    ", result.data)

    # 8. Assertions
    assert result.agent_name == "test_agent"
    assert result.status == "SUCCESS"
    assert result.success is True
    assert result.task_id == task.task_id
    assert len(result.findings) >= 3

    print()
    print("=" * 60)
    print("PHASE 1B PIPELINE TEST: PASSED")
    print("=" * 60)
    print()


if __name__ == "__main__":
    main()
