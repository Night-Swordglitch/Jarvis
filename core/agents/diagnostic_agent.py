"""Built-in diagnostic specialist used to verify the MARK-L agent pipeline."""

from __future__ import annotations

from .base import BaseAgent
from .task import AgentTask
from .result import AgentResult


class DiagnosticAgent(BaseAgent):
    """Simple built-in agent for validating Master orchestration."""

    name = "diagnostic_agent"
    description = "Verifies that the Master can successfully dispatch and collect an agent."

    def run(self, task: AgentTask) -> AgentResult:
        return AgentResult(
            agent_name=self.name,
            task_id=task.task_id,
            status="SUCCESS",
            summary="Diagnostic agent completed successfully.",
            findings=[
                f"Received objective: {task.objective}",
                "AgentTask was received correctly.",
                "Diagnostic agent executed successfully.",
                "AgentResult was returned correctly.",
            ],
            data={
                "objective": task.objective,
                "context": task.context,
            },
        )
