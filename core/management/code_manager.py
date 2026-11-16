from __future__ import annotations

from typing import Any

from .base_manager import BaseManager


class CodeManager(BaseManager):
    """Manager responsible for coordinating coding-related work."""

    MANAGER_TYPE = "CODE"

    def __init__(self, management_manager, event_bus, *, name=None, event_handler=None):
        super().__init__(
            management_manager,
            event_bus,
            name=name or "Code Manager",
            event_handler=event_handler,
        )

    def accepts(self, objective: str) -> bool:
        """Return whether an objective belongs to the coding domain."""

        text = str(objective).lower()

        keywords = (
            "code",
            "coding",
            "bug",
            "debug",
            "repository",
            "repo",
            "software",
            "program",
            "python",
            "javascript",
            "typescript",
            "implement",
            "refactor",
            "fix",
        )

        return any(keyword in text for keyword in keywords)

    def prepare_task(
        self,
        objective: str,
        *,
        repository: str | None = None,
        priority: int = 50,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Prepare a structured coding task for the Code Agent.

        This method does not execute the task.
        """

        context: dict[str, Any] = {}

        if repository:
            context["repository"] = repository

        if metadata:
            context.update(metadata)

        return {
            "manager": self.name,
            "manager_type": self.MANAGER_TYPE,
            "objective": str(objective),
            "priority": int(priority),
            "context": context,
            "execution": "DEFERRED",
        }

    def on_task_completed(self, task_id: str) -> None:
        """Hook for completed coding tasks."""

        return None

    def on_task_failed(self, task_id: str) -> None:
        """Hook for failed coding tasks."""

        return None
