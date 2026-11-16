from __future__ import annotations

from typing import Any, Callable

from core.events.bus import EventBus
from core.events.events import Event
from core.management.decision import ManagementDecision
from core.management.manager import ManagementManager


class BaseManager:
    """
    Reusable foundation for specialist managers.

    ManagementManager remains the system-level authority.
    BaseManager provides manager-local ownership, lifecycle,
    event handling, status reporting, and escalation.

    BaseManager does not execute agents, perform actions,
    modify files, or bypass permissions.
    """

    MANAGER_TYPE = "BASE"

    def __init__(
        self,
        management_manager: ManagementManager,
        event_bus: EventBus,
        *,
        name: str | None = None,
        event_handler: Callable[[Event], None] | None = None,
    ) -> None:
        if management_manager is None:
            raise ValueError("management_manager is required")

        if event_bus is None:
            raise ValueError("event_bus is required")

        self.management_manager = management_manager
        self.event_bus = event_bus
        self.name = str(name or self.MANAGER_TYPE).strip()

        if not self.name:
            raise ValueError("Manager name cannot be empty")

        self._running = False
        self._events: list[Event] = []
        self._event_handler = event_handler

        self._owned_tasks: set[str] = set()
        self._completed_tasks: set[str] = set()
        self._failed_tasks: set[str] = set()

        self._subscribed = False
        self._subscribe()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start manager-local event handling."""
        if self._running:
            return

        self._running = True

        self._publish(
            "MANAGER_STARTED",
            {
                "manager": self.name,
                "manager_type": self.MANAGER_TYPE,
            },
        )

    def stop(self) -> None:
        """Stop manager-local event handling."""
        if not self._running:
            return

        self._running = False

        self._publish(
            "MANAGER_STOPPED",
            {
                "manager": self.name,
                "manager_type": self.MANAGER_TYPE,
            },
        )

    # ------------------------------------------------------------------
    # Task ownership
    # ------------------------------------------------------------------

    def register_task(self, task_id: str) -> None:
        """Register a task as owned by this manager."""
        task_id = str(task_id).strip()

        if not task_id:
            raise ValueError("task_id cannot be empty")

        self._owned_tasks.add(task_id)

    def register_tasks(self, task_ids: list[str]) -> None:
        """Register multiple manager-owned tasks."""
        for task_id in task_ids:
            self.register_task(task_id)

    def owns_task(self, task_id: str) -> bool:
        return str(task_id) in self._owned_tasks

    @property
    def owned_tasks(self) -> list[str]:
        return sorted(self._owned_tasks)

    @property
    def completed_tasks(self) -> list[str]:
        return sorted(self._completed_tasks)

    @property
    def failed_tasks(self) -> list[str]:
        return sorted(self._failed_tasks)

    # ------------------------------------------------------------------
    # System coordination
    # ------------------------------------------------------------------

    def evaluate(self) -> ManagementDecision:
        """
        Ask ManagementManager for the current system-level decision.
        """
        return self.management_manager.evaluate()

    def request_clarification(
        self,
        question: str,
    ) -> ManagementDecision:
        """Escalate clarification to ManagementManager."""
        return self.management_manager.request_clarification(question)

    def request_approval(self, reason: str) -> ManagementDecision:
        """Escalate approval to ManagementManager."""
        return self.management_manager.request_approval(reason)

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------

    def _subscribe(self) -> None:
        if self._subscribed:
            return

        self.event_bus.subscribe("*", self._on_event)
        self._subscribed = True

    def _on_event(self, event: Event) -> None:
        if not self._running:
            return

        self._events.append(event)

        task_id = event.payload.get("task_id")

        if task_id and self.owns_task(task_id):
            if event.event_type == "TASK_COMPLETED":
                self._completed_tasks.add(task_id)
                self.on_task_completed(task_id)

            elif event.event_type == "TASK_FAILED":
                self._failed_tasks.add(task_id)
                self.on_task_failed(task_id)

        if self._event_handler is not None:
            self._event_handler(event)

        self.on_event(event)

    def on_event(self, event: Event) -> None:
        """
        Extension hook for specialist managers.
        """
        return None

    def on_task_completed(self, task_id: str) -> None:
        """Extension hook for completed specialist work."""
        return None

    def on_task_failed(self, task_id: str) -> None:
        """Extension hook for failed specialist work."""
        return None

    @property
    def recent_events(self) -> list[Event]:
        return list(self._events)

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def status(self) -> dict[str, Any]:
        """Return manager-local state for monitoring."""
        return {
            "name": self.name,
            "manager_type": self.MANAGER_TYPE,
            "running": self._running,
            "owned_tasks": self.owned_tasks,
            "completed_tasks": self.completed_tasks,
            "failed_tasks": self.failed_tasks,
            "event_count": len(self._events),
        }

    # ------------------------------------------------------------------
    # Event publishing
    # ------------------------------------------------------------------

    def _publish(
        self,
        event_type: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        self.event_bus.publish(
            Event(
                event_type=event_type,
                payload=payload or {},
            )
        )
