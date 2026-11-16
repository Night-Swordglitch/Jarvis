"""Agent task dispatcher."""

from __future__ import annotations

from .task import AgentTask
from .result import AgentResult
from .registry import AgentRegistry


class AgentDispatcher:
    """Dispatches tasks to registered specialist agents."""

    def __init__(self, registry: AgentRegistry) -> None:
        self.registry = registry

    def dispatch(self, agent_name: str, task: AgentTask) -> AgentResult:
        """Send one task to one named agent."""
        agent = self.registry.get(agent_name)

        if not agent.can_handle(task):
            return AgentResult(
                agent_name=agent.name,
                task_id=task.task_id,
                status="REJECTED",
                summary=f"Agent '{agent.name}' cannot handle this task.",
            )

        try:
            result = agent.run(task)

            if not isinstance(result, AgentResult):
                raise TypeError(
                    f"Agent '{agent.name}' returned "
                    f"{type(result).__name__}; expected AgentResult."
                )

            return result

        except Exception as exc:
            return AgentResult(
                agent_name=agent.name,
                task_id=task.task_id,
                status="FAILED",
                summary=f"Agent '{agent.name}' failed.",
                errors=[str(exc)],
            )
