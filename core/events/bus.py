"""Synchronous event bus for MARK-L."""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Callable
from typing import Any

from .events import Event


EventHandler = Callable[[Event], Any]


class EventBus:
    """Small, dependency-free publish/subscribe event bus.

    Handlers are isolated: one broken subscriber must not prevent
    other subscribers from receiving an event.
    """

    def __init__(
        self,
        logger: Callable[[str], Any] | None = None,
    ) -> None:
        self._subscribers: dict[str, list[EventHandler]] = defaultdict(list)
        self._logger = logger or logging.getLogger(__name__).info

    def subscribe(
        self,
        event_type: str,
        handler: EventHandler,
    ) -> None:
        """Subscribe a handler to one event type."""
        if not isinstance(event_type, str) or not event_type.strip():
            raise ValueError("event_type must be a non-empty string.")

        if not callable(handler):
            raise TypeError("handler must be callable.")

        normalized = event_type.strip().upper()

        if handler not in self._subscribers[normalized]:
            self._subscribers[normalized].append(handler)

    def unsubscribe(
        self,
        event_type: str,
        handler: EventHandler,
    ) -> bool:
        """Remove a handler. Returns whether it was subscribed."""
        normalized = event_type.strip().upper()
        handlers = self._subscribers.get(normalized, [])

        if handler in handlers:
            handlers.remove(handler)

            if not handlers:
                self._subscribers.pop(normalized, None)

            return True

        return False

    def publish(self, event: Event) -> int:
        """Publish an event and return the number of handlers called."""
        if not isinstance(event, Event):
            raise TypeError("publish expects an Event instance.")

        handlers = list(
            self._subscribers.get(event.event_type, [])
        )

        # Wildcard subscribers receive every event.
        handlers.extend(
            self._subscribers.get("*", [])
        )

        called = 0

        for handler in handlers:
            try:
                handler(event)
                called += 1
            except Exception as exc:
                self._logger(
                    "[EventBus] Handler failed for "
                    f"{event.event_type}: {exc}"
                )

        return called

    def subscriber_count(self, event_type: str | None = None) -> int:
        """Return subscriber count."""
        if event_type is None:
            return sum(
                len(handlers)
                for handlers in self._subscribers.values()
            )

        return len(
            self._subscribers.get(
                event_type.strip().upper(),
                [],
            )
        )

    def clear(self) -> None:
        """Remove all subscribers."""
        self._subscribers.clear()
