"""Phase 1C Master Agent test."""

import asyncio

from core.agents import (
    AgentRegistry,
    AgentDispatcher,
    MasterAgent,
)

from core.agents.tests.test_agent import TestAgent


def build_master():
    registry = AgentRegistry()
    registry.register(TestAgent())

    dispatcher = AgentDispatcher(registry)
    master = MasterAgent(
        registry=registry,
        dispatcher=dispatcher,
    )

    return registry, dispatcher, master


async def main():
    print()
    print("=" * 64)
    print("MARK-L MASTER ORCHESTRATION TEST")
    print("=" * 64)

    # --------------------------------------------------------
    # 1. Build registry
    # --------------------------------------------------------

    registry, dispatcher, master = build_master()

    print()
    print("[1] Available agents:")

    for agent in registry.all():
        print(f"    - {agent.name}: {agent.description}")

    # --------------------------------------------------------
    # 2. Master initialized
    # --------------------------------------------------------

    print()
    print("[2] Master initialized.")
    print("    Master:", master.name)

    # --------------------------------------------------------
    # 3. Give Master an objective
    # --------------------------------------------------------

    objective = (
        "Verify that the Master can coordinate "
        "a specialist agent."
    )

    print()
    print("[3] Objective:")
    print("    ", objective)

    # --------------------------------------------------------
    # 4. Master delegates
    # --------------------------------------------------------

    print()
    print("[4] Master dispatching specialist task...")

    result = await master.run(
        objective=objective,
        agent_names=["test_agent"],
        context={
            "phase": "1C",
            "test": True,
        },
    )

    # --------------------------------------------------------
    # 5. Display Master result
    # --------------------------------------------------------

    print()
    print("[5] Master result:")
    print("    Agent:", result.agent_name)
    print("    Status:", result.status)
    print("    Success:", result.success)

    print()
    print("[6] Summary:")
    print("    ", result.summary)

    print()
    print("[7] Combined findings:")

    for finding in result.findings:
        print("    -", finding)

    print()
    print("[8] Orchestration data:")
    print("    ", result.data)

    # --------------------------------------------------------
    # 6. Assertions
    # --------------------------------------------------------

    assert result.agent_name == "master"
    assert result.success
    assert "test_agent" in result.data["agents_consulted"]
    assert "test_agent" in result.data["successful_agents"]
    assert not result.data["failed_agents"]

    print()
    print("=" * 64)
    print("PHASE 1C MASTER TEST: PASSED")
    print("=" * 64)
    print()


if __name__ == "__main__":
    asyncio.run(main())
