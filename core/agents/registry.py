"""Registry for specialist agents."""

from __future__ import annotations

from .base import BaseAgent


class AgentRegistry:
    """Stores and discovers the specialist agents available to MARK-L."""

    def __init__(self) -> None:
        self._agents: dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent) -> None:
        """Register an agent by its unique name."""
        name = str(agent.name).strip()

        if not name:
            raise ValueError("Agent name cannot be empty.")

        if name in self._agents:
            raise ValueError(f"Agent '{name}' is already registered.")

        self._agents[name] = agent

    def unregister(self, name: str) -> None:
        """Remove an agent from the registry."""
        self._agents.pop(name, None)

    def get(self, name: str) -> BaseAgent:
        """Retrieve a registered agent."""
        try:
            return self._agents[name]
        except KeyError:
            raise KeyError(f"Agent '{name}' is not registered.")

    def has(self, name: str) -> bool:
        """Return whether an agent exists."""
        return name in self._agents

    def names(self) -> list[str]:
        """Return registered agent names."""
        return sorted(self._agents)

    def all(self) -> list[BaseAgent]:
        """Return all registered agents."""
        return list(self._agents.values())

    def describe(self) -> list[dict[str, str]]:
        """Return agent metadata for the Master."""
        return [
            {
                "name": agent.name,
                "description": agent.description,
            }
            for agent in self._agents.values()
        ]
