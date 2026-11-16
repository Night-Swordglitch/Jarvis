import asyncio

from core.agents import AgentRegistry, AgentDispatcher, MasterAgent
from core.agents.tests.test_agent import TestAgent


async def main():
    registry = AgentRegistry()
    registry.register(TestAgent())

    dispatcher = AgentDispatcher(registry)
    master = MasterAgent(registry, dispatcher)

    print()
    print("=" * 64)
    print("MARK-L INTERACTIVE MASTER TEST")
    print("=" * 64)
    print()
    print("Available agents:")

    for agent in registry.all():
        print(f"  - {agent.name}")

    print()
    print("Type an objective.")
    print("Type 'exit' to quit.")
    print()

    while True:
        objective = input("You > ").strip()

        if objective.lower() in {"exit", "quit"}:
            break

        if not objective:
            continue

        print()
        print("[MASTER] Asking local LLM which agents are needed...")

        selected = master.choose_agents(
            objective=objective,
            context={"interactive_test": True},
        )

        print(f"[MASTER] Selected agents: {selected}")

        if not selected:
            print("[MASTER] No suitable agents selected.")
            print()
            continue

        print("[MASTER] Dispatching...")
        
        result = await master.run(
            objective=objective,
            context={"interactive_test": True},
        )

        print()
        print("[MASTER] Result:")
        print(f"  Status: {result.status}")
        print(f"  Agents: {result.data.get('agents_consulted')}")

        for finding in result.findings:
            print(f"  - {finding}")

        print()


if __name__ == "__main__":
    asyncio.run(main())
