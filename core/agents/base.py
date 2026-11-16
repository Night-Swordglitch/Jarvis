"""Base class for MARK-L specialist agents."""

from __future__ import annotations

from abc import ABC, abstractmethod

from .task import AgentTask
from .result import AgentResult


class BaseAgent(ABC):
    """Common interface every specialist agent must implement."""

    name: str = "unnamed_agent"
    description: str = ""

    @abstractmethod
    def run(self, task: AgentTask) -> AgentResult:
        """Execute the supplied task and return a structured result."""
        raise NotImplementedError

    def can_handle(self, task: AgentTask) -> bool:
        """
        Return whether this agent considers the task relevant.

        The first version intentionally defaults to True.
        The Master will eventually use richer routing logic.
        """
        return True

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r}>"
