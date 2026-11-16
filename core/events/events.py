"""Event definitions for MARK-L's operational nervous system."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class Event:
    """Immutable event emitted by MARK-L subsystems."""

    event_type: str
    payload: dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: str = field(default_factory=_now)

    def __post_init__(self) -> None:
        if not isinstance(self.event_type, str) or not self.event_type.strip():
            raise ValueError("event_type must be a non-empty string.")

        if not isinstance(self.payload, dict):
            raise TypeError("payload must be a dictionary.")

        object.__setattr__(
            self,
            "event_type",
            self.event_type.strip().upper(),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "payload": dict(self.payload),
        }
