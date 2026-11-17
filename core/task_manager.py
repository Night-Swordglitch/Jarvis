"""MARK-L Task Manager.

The Task Manager owns the lifecycle of managed tasks.
It does not execute agents or actions.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from core.events import Event, EventBus
from core.management import ManagementState, TaskState


class TaskManager:
    """Create and manage the lifecycle of MARK-L tasks."""

    VALID_STATUSES = {
        "QUEUED",
        "RUNNING",
        "COMPLETED",
        "FAILED",
        "BLOCKED",
        "CANCELLED",
    }

    def __init__(
        self,
        state: ManagementState,
        event_bus: EventBus,
    ) -> None:
        if not isinstance(state, ManagementState):
            raise TypeError("state must be a ManagementState.")

        if not isinstance(event_bus, EventBus):
            raise TypeError("event_bus must be an EventBus.")

        self._state = state
        self._events = event_bus

    @property
    def state(self) -> ManagementState:
        """Return the managed state."""
        return self._state

    def create_task(
        self,
        objective: str,
        *,
        priority: int = 50,
        agent_name: str | None = None,
        dependencies: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TaskState:
        """Create and queue a new task."""

        if not isinstance(objective, str) or not objective.strip():
            raise ValueError(
                "Task objective must be a non-empty string."
            )

        if not isinstance(priority, int):
            raise TypeError("priority must be an integer.")

        if priority < 0 or priority > 100:
            raise ValueError(
                "priority must be between 0 and 100."
            )

        if agent_name is not None and not isinstance(
            agent_name,
            str,
        ):
            raise TypeError(
                "agent_name must be a string or None."
            )

        dependencies = list(dependencies or [])
        metadata = dict(metadata or {})

        task_id = str(uuid4())

        task = TaskState(
            task_id=task_id,
            objective=objective.strip(),
            status="QUEUED",
            priority=priority,
            agent_name=agent_name,
            dependencies=dependencies,
            metadata=metadata,
        )

        self._state.queued_tasks[task_id] = task

        self._emit(
            "TASK_CREATED",
            {
                "task_id": task_id,
                "objective": task.objective,
                "priority": task.priority,
                "agent_name": task.agent_name,
                "dependencies": list(task.dependencies),
            },
        )

        self._emit(
            "TASK_QUEUED",
            {
                "task_id": task_id,
                "priority": task.priority,
            },
        )

        return task

    def start_task(self, task_id: str) -> TaskState:
        """Move a queued task into the running state."""

        task = self._find_task(task_id)

        if task.status != "QUEUED":
            raise ValueError(
                f"Task '{task_id}' cannot start from "
                f"status '{task.status}'."
            )

        if not self.dependencies_satisfied(task):
            raise ValueError(
                f"Task '{task_id}' has unresolved dependencies."
            )

        self._remove_from_all_groups(task_id)

        task.status = "RUNNING"

        self._state.active_tasks[task_id] = task

        self._emit(
            "TASK_STARTED",
            {
                "task_id": task_id,
                "objective": task.objective,
                "agent_name": task.agent_name,
            },
        )

        return task

    def complete_task(
        self,
        task_id: str,
        result: dict[str, Any] | None = None,
    ) -> TaskState:
        """Mark a running task as completed."""

        task = self._find_task(task_id)

        if task.status != "RUNNING":
            raise ValueError(
                f"Task '{task_id}' cannot complete from "
                f"status '{task.status}'."
            )

        self._remove_from_all_groups(task_id)

        task.status = "COMPLETED"
        task.result = dict(result or {})
        task.error = None

        self._state.completed_tasks[task_id] = task

        self._emit(
            "TASK_COMPLETED",
            {
                "task_id": task_id,
                "result": dict(task.result),
            },
        )

        return task

    def fail_task(
        self,
        task_id: str,
        error: str,
    ) -> TaskState:
        """Mark a running task as failed."""

        if not isinstance(error, str) or not error.strip():
            raise ValueError(
                "error must be a non-empty string."
            )

        task = self._find_task(task_id)

        if task.status != "RUNNING":
            raise ValueError(
                f"Task '{task_id}' cannot fail from "
                f"status '{task.status}'."
            )

        self._remove_from_all_groups(task_id)

        task.status = "FAILED"
        task.error = error.strip()

        self._state.failed_tasks[task_id] = task

        self._emit(
            "TASK_FAILED",
            {
                "task_id": task_id,
                "error": task.error,
            },
        )

        return task

    def block_task(
        self,
        task_id: str,
        reason: str,
    ) -> TaskState:
        """Move a task into the blocked state."""

        if not isinstance(reason, str) or not reason.strip():
            raise ValueError(
                "reason must be a non-empty string."
            )

        task = self._find_task(task_id)

        if task.status not in {"QUEUED", "RUNNING"}:
            raise ValueError(
                f"Task '{task_id}' cannot be blocked from "
                f"status '{task.status}'."
            )

        self._remove_from_all_groups(task_id)

        task.status = "BLOCKED"
        task.error = reason.strip()

        self._state.blocked_tasks[task_id] = task

        self._emit(
            "TASK_BLOCKED",
            {
                "task_id": task_id,
                "reason": task.error,
            },
        )

        return task

    def cancel_task(self, task_id: str) -> TaskState:
        """Cancel a queued or running task."""

        task = self._find_task(task_id)

        if task.status not in {"QUEUED", "RUNNING", "BLOCKED"}:
            raise ValueError(
                f"Task '{task_id}' cannot be cancelled from "
                f"status '{task.status}'."
            )

        previous_status = task.status
        self._remove_from_all_groups(task_id)

        task.status = "CANCELLED"

        self._state.failed_tasks[task_id] = task

        self._emit(
            "TASK_CANCELLED",
            {
                "task_id": task_id,
                "previous_status": previous_status,
            },
        )

        return task

    def get_task(self, task_id: str) -> TaskState | None:
        """Return a task if it exists."""
        if not isinstance(task_id, str):
            return None

        groups = (
            self._state.active_tasks,
            self._state.queued_tasks,
            self._state.blocked_tasks,
            self._state.completed_tasks,
            self._state.failed_tasks,
        )

        for group in groups:
            task = group.get(task_id)

            if task is not None:
                return task

        return None

    def dependencies_satisfied(
        self,
        task: TaskState,
    ) -> bool:
        """Return whether every dependency completed successfully."""

        for dependency_id in task.dependencies:
            dependency = self.get_task(dependency_id)

            if dependency is None:
                return False

            if dependency.status != "COMPLETED":
                return False

        return True

    def queued_tasks(self) -> list[TaskState]:
        """Return queued tasks sorted by priority."""
        return sorted(
            self._state.queued_tasks.values(),
            key=lambda task: (-task.priority, task.task_id),
        )

    def _find_task(self, task_id: str) -> TaskState:
        """Find a task or raise a clear error."""

        task = self.get_task(task_id)

        if task is None:
            raise KeyError(
                f"Task '{task_id}' does not exist."
            )

        return task

    def _remove_from_all_groups(self, task_id: str) -> None:
        """Ensure one task exists in only one lifecycle bucket."""

        for group in (
            self._state.active_tasks,
            self._state.queued_tasks,
            self._state.blocked_tasks,
            self._state.completed_tasks,
            self._state.failed_tasks,
        ):
            group.pop(task_id, None)

    def _emit(
        self,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        """Publish a task lifecycle event."""
        event = Event(
            event_type=event_type,
            payload=payload,
        )

        self._state.add_event(event.to_dict())
        self._events.publish(event)
