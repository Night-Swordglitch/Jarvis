"""Management state for MARK-L's operational control layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TaskState:
    """Current state of one managed task."""

    task_id: str
    objective: str
    status: str = "QUEUED"
    priority: int = 50
    agent_name: str | None = None
    dependencies: list[str] = field(default_factory=list)
    result: dict[str, Any] | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskState":
        if not isinstance(data, dict):
            raise TypeError("Task data must be a dictionary.")
        result = data.get("result")
        if result is not None and not isinstance(result, dict):
            raise TypeError("Task result must be a dictionary or None.")
        return cls(
            task_id=str(data["task_id"]),
            objective=str(data["objective"]),
            status=str(data.get("status", "QUEUED")).upper(),
            priority=int(data.get("priority", 50)),
            agent_name=data.get("agent_name"),
            dependencies=list(data.get("dependencies", [])),
            result=dict(result) if result is not None else None,
            error=data.get("error"),
            metadata=dict(data.get("metadata", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "objective": self.objective,
            "status": self.status,
            "priority": self.priority,
            "agent_name": self.agent_name,
            "dependencies": list(self.dependencies),
            "result": self.result,
            "error": self.error,
            "metadata": dict(self.metadata),
        }


@dataclass
class ManagementState:
    """Single source of truth for Management's operational state."""

    mission_id: str | None = None
    objective: str = ""
    status: str = "IDLE"

    active_tasks: dict[str, TaskState] = field(default_factory=dict)
    queued_tasks: dict[str, TaskState] = field(default_factory=dict)
    blocked_tasks: dict[str, TaskState] = field(default_factory=dict)
    completed_tasks: dict[str, TaskState] = field(default_factory=dict)
    failed_tasks: dict[str, TaskState] = field(default_factory=dict)

    current_plan: list[dict[str, Any]] = field(default_factory=list)

    recent_events: list[dict[str, Any]] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    pending_approvals: list[dict[str, Any]] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)

    metadata: dict[str, Any] = field(default_factory=dict)

    def set_mission(self, mission_id: str, objective: str) -> None:
        """Attach a mission to this management state."""
        if not mission_id:
            raise ValueError("mission_id must not be empty.")

        if not objective or not objective.strip():
            raise ValueError("objective must not be empty.")

        self.mission_id = mission_id
        self.objective = objective.strip()
        self.status = "PLANNING"

    def add_event(self, event: dict[str, Any], max_events: int = 100) -> None:
        """Record a recent event while bounding memory usage."""
        if not isinstance(event, dict):
            raise TypeError("event must be a dictionary.")

        self.recent_events.append(dict(event))

        if max_events > 0 and len(self.recent_events) > max_events:
            del self.recent_events[:-max_events]

    def task_count(self) -> int:
        """Return the total number of tracked tasks."""
        return sum(
            len(group)
            for group in (
                self.active_tasks,
                self.queued_tasks,
                self.blocked_tasks,
                self.completed_tasks,
                self.failed_tasks,
            )
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ManagementState":
        """Restore management state from its serialized representation."""
        if not isinstance(data, dict):
            raise TypeError("Management state data must be a dictionary.")

        state = cls(
            mission_id=data.get("mission_id"),
            objective=str(data.get("objective", "")),
            status=str(data.get("status", "IDLE")),
            current_plan=[
                dict(item) if isinstance(item, dict) else item
                for item in data.get("current_plan", [])
            ],
            recent_events=[
                dict(item) for item in data.get("recent_events", [])
            ],
            open_questions=list(data.get("open_questions", [])),
            pending_approvals=list(data.get("pending_approvals", [])),
            next_actions=list(data.get("next_actions", [])),
            metadata=dict(data.get("metadata", {})),
        )

        for group_name in (
            "active_tasks",
            "queued_tasks",
            "blocked_tasks",
            "completed_tasks",
            "failed_tasks",
        ):
            raw_group = data.get(group_name, {})
            if not isinstance(raw_group, dict):
                raise TypeError(f"{group_name} must be a dictionary.")
            group = getattr(state, group_name)
            for task_id, raw_task in raw_group.items():
                task = TaskState.from_dict(raw_task)
                if task.task_id != task_id:
                    raise ValueError(
                        f"Task key mismatch in {group_name}: {task_id}"
                    )
                group[task_id] = task

        return state

    def to_dict(self) -> dict[str, Any]:
        """Serialize the complete management state."""
        return {
            "mission_id": self.mission_id,
            "objective": self.objective,
            "status": self.status,
            "active_tasks": {
                key: value.to_dict()
                for key, value in self.active_tasks.items()
            },
            "queued_tasks": {
                key: value.to_dict()
                for key, value in self.queued_tasks.items()
            },
            "blocked_tasks": {
                key: value.to_dict()
                for key, value in self.blocked_tasks.items()
            },
            "completed_tasks": {
                key: value.to_dict()
                for key, value in self.completed_tasks.items()
            },
            "failed_tasks": {
                key: value.to_dict()
                for key, value in self.failed_tasks.items()
            },
            "current_plan": [
                dict(item) if isinstance(item, dict) else item
                for item in self.current_plan
            ],
            "recent_events": list(self.recent_events),
            "open_questions": list(self.open_questions),
            "pending_approvals": list(self.pending_approvals),
            "next_actions": list(self.next_actions),
            "metadata": dict(self.metadata),
        }
