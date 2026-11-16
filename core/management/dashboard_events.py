"""Live EventBus integration for the MARK-L operations dashboard."""

from __future__ import annotations

from typing import Any, Callable

from core.events.bus import EventBus
from core.events.events import Event


class DashboardEventBridge:
    """Connect MARK-L EventBus activity to dashboard refresh notifications.

    The bridge is intentionally read-only with respect to management state.
    It observes events and notifies dashboard consumers that a new projection
    should be requested.
    """

    def __init__(
        self,
        event_bus: EventBus,
        *,
        on_event: Callable[[Event], None] | None = None,
    ) -> None:
        if not isinstance(event_bus, EventBus):
            raise TypeError("event_bus must be EventBus")

        if on_event is not None and not callable(on_event):
            raise TypeError("on_event must be callable or None")

        self.event_bus = event_bus
        self.on_event = on_event
        self._started = False
        self._event_count = 0
        self._last_event: Event | None = None

    def start(self) -> None:
        """Subscribe to all EventBus events."""
        if self._started:
            return

        self.event_bus.subscribe("*", self._handle_event)
        self._started = True

    def stop(self) -> None:
        """Stop receiving dashboard event notifications.

        EventBus currently exposes subscription only, not unsubscribe.
        Therefore stopping disables bridge processing without mutating the
        EventBus subscriber registry.
        """
        self._started = False

    def _handle_event(self, event: Event) -> None:
        if not self._started:
            return

        self._event_count += 1
        self._last_event = event

        if self.on_event is not None:
            self.on_event(event)

    @property
    def started(self) -> bool:
        return self._started

    @property
    def event_count(self) -> int:
        return self._event_count

    @property
    def last_event(self) -> Event | None:
        return self._last_event

    def status(self) -> dict[str, Any]:
        """Return read-only bridge status."""
        return {
            "started": self._started,
            "event_count": self._event_count,
            "last_event": (
                self._last_event.to_dict()
                if self._last_event is not None
                else None
            ),
        }
