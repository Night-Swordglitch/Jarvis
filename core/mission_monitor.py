from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from core.events import Event, EventBus


@dataclass
class MissionHealth:
    mission_id: str
    status: str = "UNKNOWN"
    healthy: bool = True
    alerts: list[str] = field(default_factory=list)
    observed_tasks: dict[str, str] = field(default_factory=dict)
    last_event_type: str | None = None
    updated_at: float = field(default_factory=time.monotonic)


class MissionMonitor:
    """
    Read-only observer for an active mission.

    This layer observes execution but does not:
      - execute tasks
      - cancel tasks
      - retry tasks
      - approve actions
      - resolve confirmations
      - replan missions
    """

    TERMINAL = {
        "COMPLETED",
        "FAILED",
        "BLOCKED",
        "CANCELLED",
    }

    FAILURE_STATES = {
        "FAILED",
        "BLOCKED",
    }

    TASK_EVENT_STATUS = {
        "TASK_CREATED": "QUEUED",
        "TASK_QUEUED": "QUEUED",
        "TASK_STARTED": "RUNNING",
        "TASK_COMPLETED": "COMPLETED",
        "TASK_FAILED": "FAILED",
        "TASK_BLOCKED": "BLOCKED",
        "TASK_CANCELLED": "CANCELLED",
    }

    def __init__(
        self,
        mission_id: str,
        *,
        stale_after: float = 300.0,
    ) -> None:
        if not isinstance(mission_id, str) or not mission_id.strip():
            raise ValueError("mission_id must be a non-empty string")

        if not isinstance(stale_after, (int, float)):
            raise TypeError("stale_after must be numeric")

        if stale_after <= 0:
            raise ValueError("stale_after must be greater than zero")

        self.mission_id = mission_id.strip()
        self.stale_after = float(stale_after)

        self._health = MissionHealth(
            mission_id=self.mission_id,
        )

        self._task_started_at: dict[str, float] = {}
        self._tracked_tasks: set[str] = set()
        self._event_bus: EventBus | None = None

    # ------------------------------------------------------------------
    # Mission task ownership
    # ------------------------------------------------------------------

    def track_task(self, task_id: str) -> None:
        """Register a task as belonging to this mission."""
        if not isinstance(task_id, str) or not task_id.strip():
            raise ValueError("task_id must be a non-empty string")

        task_id = task_id.strip()
        self._tracked_tasks.add(task_id)

        # A newly registered task is assumed to be queued until
        # a later lifecycle event reports a different state.
        if task_id not in self._health.observed_tasks:
            self.observe_task(task_id, "QUEUED")

    def tracked_tasks(self) -> list[str]:
        """Return tracked task IDs in deterministic order."""
        return sorted(self._tracked_tasks)

    # ------------------------------------------------------------------
    # EventBus integration
    # ------------------------------------------------------------------

    def bind_event_bus(self, event_bus: EventBus) -> None:
        """
        Subscribe to the existing EventBus.

        This only observes events. It does not execute or mutate tasks.
        """
        if not isinstance(event_bus, EventBus):
            raise TypeError("event_bus must be an EventBus")

        if self._event_bus is event_bus:
            return

        if self._event_bus is not None:
            self.unbind_event_bus()

        self._event_bus = event_bus
        event_bus.subscribe("*", self._on_event)

    def unbind_event_bus(self) -> None:
        """Remove this monitor from its EventBus."""
        if self._event_bus is None:
            return

        self._event_bus.unsubscribe("*", self._on_event)
        self._event_bus = None

    def _on_event(self, event: Event) -> None:
        """Observe task lifecycle events belonging to this mission."""
        if not isinstance(event, Event):
            return

        status = self.TASK_EVENT_STATUS.get(event.event_type)

        if status is None:
            return

        payload = event.payload

        if not isinstance(payload, dict):
            return

        task_id = payload.get("task_id")

        if not isinstance(task_id, str) or not task_id.strip():
            return

        task_id = task_id.strip()

        # Ignore tasks that do not belong to this mission.
        if task_id not in self._tracked_tasks:
            return

        self._health.last_event_type = event.event_type

        self.observe_task(
            task_id,
            status,
        )

    # ------------------------------------------------------------------
    # Direct observation
    # ------------------------------------------------------------------

    def observe_task(
        self,
        task_id: str,
        status: str,
        *,
        observed_at: float | None = None,
    ) -> None:
        if not isinstance(task_id, str) or not task_id.strip():
            raise ValueError("task_id must be a non-empty string")

        if not isinstance(status, str) or not status.strip():
            raise ValueError("status must be a non-empty string")

        task_id = task_id.strip()
        status = status.strip().upper()
        now = time.monotonic() if observed_at is None else float(observed_at)

        self._health.observed_tasks[task_id] = status
        self._health.updated_at = now

        if status == "RUNNING":
            self._task_started_at.setdefault(task_id, now)

        elif status in self.TERMINAL:
            self._task_started_at.pop(task_id, None)

        if status in self.FAILURE_STATES:
            alert = f"Task {task_id} entered {status} state."

            if alert not in self._health.alerts:
                self._health.alerts.append(alert)

        self._recalculate_health()

    def observe_event(
        self,
        event_type: str,
        *,
        task_id: str | None = None,
        status: str | None = None,
    ) -> None:
        if not isinstance(event_type, str) or not event_type.strip():
            raise ValueError("event_type must be a non-empty string")

        self._health.last_event_type = event_type.strip().upper()
        self._health.updated_at = time.monotonic()

        if task_id is not None:
            if status is None:
                raise ValueError(
                    "status is required when task_id is provided"
                )

            self.observe_task(
                task_id,
                status,
            )

        self._recalculate_health()

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def stale_tasks(
        self,
        *,
        now: float | None = None,
    ) -> list[str]:
        current = time.monotonic() if now is None else float(now)

        stale = []

        for task_id, started_at in self._task_started_at.items():
            if current - started_at >= self.stale_after:
                stale.append(task_id)

        return sorted(stale)

    def snapshot(
        self,
        *,
        now: float | None = None,
    ) -> dict[str, Any]:
        stale = self.stale_tasks(now=now)

        return {
            "mission_id": self.mission_id,
            "status": self._health.status,
            "healthy": self._health.healthy,
            "alerts": list(self._health.alerts),
            "tracked_tasks": self.tracked_tasks(),
            "observed_tasks": dict(self._health.observed_tasks),
            "stale_tasks": stale,
            "last_event_type": self._health.last_event_type,
            "event_bus_bound": self._event_bus is not None,
        }

    @property
    def healthy(self) -> bool:
        return self._health.healthy

    @property
    def alerts(self) -> list[str]:
        return list(self._health.alerts)

    def _recalculate_health(self) -> None:
        statuses = set(self._health.observed_tasks.values())

        if not statuses:
            self._health.status = "UNKNOWN"
            self._health.healthy = True
            return

        if statuses & self.FAILURE_STATES:
            self._health.status = "DEGRADED"
            self._health.healthy = False
            return

        if "RUNNING" in statuses or "QUEUED" in statuses:
            self._health.status = "ACTIVE"
            self._health.healthy = True
            return

        if statuses and statuses <= {"COMPLETED"}:
            self._health.status = "HEALTHY"
            self._health.healthy = True
            return

        self._health.status = "OBSERVING"
        self._health.healthy = True
