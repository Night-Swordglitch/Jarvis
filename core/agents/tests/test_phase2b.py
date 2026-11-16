import asyncio

from core.agents import AgentRegistry, AgentDispatcher, MasterAgent
from core.agents.tests.test_agent import TestAgent


async def main():
    print()
    print("=" * 64)
    print("MARK-L PHASE 2B — LLM AGENT SELECTION TEST")
    print("=" * 64)

    registry = AgentRegistry()
    registry.register(TestAgent())

    dispatcher = AgentDispatcher(registry)
    master = MasterAgent(
        registry=registry,
        dispatcher=dispatcher,
    )

    objective = (
        "Verify that the Master can coordinate "
        "a specialist agent."
    )

    print()
    print("[1] Objective:")
    print("   ", objective)

    print()
    print("[2] Available agents:")
    for agent in registry.all():
        print(f"    - {agent.name}")

    print()
    print("[3] Asking local LLM to select agents...")

    selected = master.choose_agents(
        objective=objective,
        context={
            "phase": "2B",
            "test": True,
        },
    )

    print()
    print("[4] LLM selected:")
    print("   ", selected)

    assert isinstance(selected, list)

    if "test_agent" not in selected:
        raise AssertionError(
            "LLM did not select the available test_agent."
        )

    print()
    print("[5] Running Master WITHOUT manually supplying agent_names...")

    result = await master.run(
        objective=objective,
        context={
            "phase": "2B",
            "test": True,
        },
    )

    print()
    print("[6] Master result:")
    print("    Agent:", result.agent_name)
    print("    Status:", result.status)
    print("    Success:", result.success)

    print()
    print("[7] Agents actually consulted:")
    print("   ", result.data.get("agents_consulted"))

    print()
    print("[8] Findings:")

    for finding in result.findings:
        print("    -", finding)

    assert result.success
    assert "test_agent" in result.data["agents_consulted"]

    print()
    print("=" * 64)
    print("PHASE 2B LLM AGENT SELECTION: PASSED")
    print("=" * 64)
    print()


if __name__ == "__main__":
    asyncio.run(main())
