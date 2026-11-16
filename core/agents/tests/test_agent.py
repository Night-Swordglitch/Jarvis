"""Simple test specialist for the MARK-L agent framework."""

from core.agents.base import BaseAgent
from core.agents.task import AgentTask
from core.agents.result import AgentResult


class TestAgent(BaseAgent):
    name = "test_agent"
    description = "A harmless internal agent used to verify agent orchestration."

    def run(self, task: AgentTask) -> AgentResult:
        return AgentResult(
            agent_name=self.name,
            task_id=task.task_id,
            status="SUCCESS",
            summary="Test agent completed successfully.",
            findings=[
                f"Received objective: {task.objective}",
                "AgentTask was received correctly.",
                "Dispatcher successfully executed the agent.",
                "AgentResult was returned correctly.",
            ],
            data={
                "echo": task.objective,
                "context_received": task.context,
            },
        )
