"""Atomic local persistence for ManagementState and task lifecycle records."""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

from core.dependency_graph import DependencyGraph
from core.events import Event, EventBus
from core.management.state import ManagementState, TaskState


class ManagementStateStore:
    """Persist management state while keeping interrupted work non-executable."""

    SENSITIVE_KEY_PARTS = (
        "password",
        "secret",
        "token",
        "api_key",
        "apikey",
        "authorization",
        "credential",
        "private_key",
    )

    INTERRUPTED_REASON = (
        "JARVIS restarted before this task completed. "
        "The task was not resumed automatically and requires review."
    )

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = threading.RLock()
        self._state: ManagementState | None = None
        self._event_bus: EventBus | None = None
        self.last_error: str | None = None

    def load(self) -> ManagementState:
        """Load state, safely terminalizing work interrupted by a restart."""
        with self._lock:
            if not self.path.exists():
                state = ManagementState()
                self._state = state
                return state

            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
                state = ManagementState.from_dict(raw)
            except Exception as exc:
                raise RuntimeError(
                    f"Could not restore management state from {self.path}: {exc}"
                ) from exc

            interrupted_active = list(state.active_tasks.values())
            for task in interrupted_active:
                state.active_tasks.pop(task.task_id, None)
                task.status = "FAILED"
                task.error = self.INTERRUPTED_REASON
                state.failed_tasks[task.task_id] = task

            interrupted_queued = [
                task
                for task in state.queued_tasks.values()
                if task.metadata.get("mission_id") == state.mission_id
            ]
            for task in interrupted_queued:
                state.queued_tasks.pop(task.task_id, None)
                task.status = "BLOCKED"
                task.error = self.INTERRUPTED_REASON
                state.blocked_tasks[task.task_id] = task

            mission_data = state.metadata.get("mission")
            mission_is_active = (
                isinstance(mission_data, dict)
                and str(mission_data.get("status", "")).upper()
                not in {"COMPLETED", "FAILED", "CANCELLED"}
            )
            interrupted_mission = bool(
                mission_is_active
                and state.status.upper() in {"PLANNING", "RUNNING"}
            )

            if interrupted_active or interrupted_queued or interrupted_mission:
                state.status = "FAILED"
                state.metadata["restart_recovery"] = {
                    "requires_review": True,
                    "reason": self.INTERRUPTED_REASON,
                    "interrupted_active_task_ids": [
                        task.task_id for task in interrupted_active
                    ],
                    "blocked_queued_task_ids": [
                        task.task_id for task in interrupted_queued
                    ],
                }
                if isinstance(mission_data, dict):
                    mission_data = dict(mission_data)
                    mission_data["status"] = "FAILED"
                    state.metadata["mission"] = mission_data
                self.save(state)

            self._state = state
            return state

    def save(self, state: ManagementState) -> None:
        """Write a redacted snapshot using an atomic replace."""
        if not isinstance(state, ManagementState):
            raise TypeError("state must be a ManagementState.")

        with self._lock:
            payload = self._redact(state.to_dict())
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(self.path.suffix + ".tmp")
            with temporary.open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
            self._state = state
            self.last_error = None

    def bind(self, state: ManagementState, event_bus: EventBus) -> None:
        """Persist state after each event once lifecycle owners have updated it."""
        if not isinstance(state, ManagementState):
            raise TypeError("state must be a ManagementState.")
        if not isinstance(event_bus, EventBus):
            raise TypeError("event_bus must be an EventBus.")
        self.close()
        self._state = state
        self._event_bus = event_bus
        event_bus.subscribe("*", self._on_event)
        self.save(state)

    def restore_dependency_graph(
        self,
        state: ManagementState,
        graph: DependencyGraph,
    ) -> None:
        """Rebuild dependency edges from the persisted TaskState records."""
        if not isinstance(state, ManagementState):
            raise TypeError("state must be a ManagementState.")
        if not isinstance(graph, DependencyGraph):
            raise TypeError("graph must be a DependencyGraph.")

        groups = (
            state.active_tasks,
            state.queued_tasks,
            state.blocked_tasks,
            state.completed_tasks,
            state.failed_tasks,
        )
        tasks = [
            task
            for group in groups
            for task in group.values()
        ]

        for task in tasks:
            graph.add_task(task.task_id)

        for task in tasks:
            for dependency_id in task.dependencies:
                if not graph.has_task(dependency_id):
                    if task.status == "QUEUED":
                        state.queued_tasks.pop(task.task_id, None)
                        task.status = "BLOCKED"
                        task.error = (
                            f"Missing persisted dependency: {dependency_id}"
                        )
                        state.blocked_tasks[task.task_id] = task
                    continue
                graph.add_dependency(task.task_id, dependency_id)

    def close(self) -> None:
        """Unsubscribe from lifecycle events and flush the latest state."""
        if self._event_bus is not None:
            self._event_bus.unsubscribe("*", self._on_event)
            self._event_bus = None
        if self._state is not None:
            self.save(self._state)

    def _on_event(self, event: Event) -> None:
        if self._state is None:
            return
        try:
            self.save(self._state)
        except Exception as exc:
            self.last_error = str(exc)

    @classmethod
    def _redact(cls, value: Any) -> Any:
        if isinstance(value, dict):
            redacted = {}
            for key, item in value.items():
                key_text = str(key).lower().replace("-", "_")
                if any(part in key_text for part in cls.SENSITIVE_KEY_PARTS):
                    redacted[key] = "[REDACTED]"
                else:
                    redacted[key] = cls._redact(item)
            return redacted
        if isinstance(value, list):
            return [cls._redact(item) for item in value]
        if isinstance(value, tuple):
            return [cls._redact(item) for item in value]
        return value
