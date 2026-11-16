"""Structured capability requests for MARK-L agents."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class CapabilityRequest:
    """A request by an agent to perform a capability-gated action."""

    capability: str
    action: str
    reason: str = ""
    context: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate and normalize the request contract."""
        if not isinstance(self.capability, str) or not self.capability.strip():
            raise ValueError("capability must be a non-empty string")

        if not isinstance(self.action, str) or not self.action.strip():
            raise ValueError("action must be a non-empty string")

        if not isinstance(self.reason, str):
            raise TypeError("reason must be a string")

        if not isinstance(self.context, dict):
            raise TypeError("context must be a dictionary")

        object.__setattr__(
            self,
            "capability",
            self.capability.strip().upper(),
        )

        object.__setattr__(
            self,
            "action",
            self.action.strip(),
        )

    @property
    def normalized_capability(self) -> str:
        """Return the normalized capability name."""
        return self.capability

    @property
    def normalized_action(self) -> str:
        """Return the normalized action name."""
        return self.action

    def to_dict(self) -> dict[str, Any]:
        """Return a serializable representation."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CapabilityRequest":
        """Create a request from an existing actions_requested entry."""
        if not isinstance(data, dict):
            raise TypeError("Capability request must be a dictionary")

        return cls(
            capability=data.get("capability", ""),
            action=data.get("action", ""),
            reason=data.get("reason", ""),
            context=data.get("context", {}),
        )
