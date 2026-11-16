"""Authoritative capability registry for MARK-L.

The registry connects executable actions to trusted capabilities.

Capabilities describe what class of operation an action represents.
They are not executable themselves.

Agents may request actions, but they never choose the capability.
The host-side registry remains the source of truth.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from core.action_capabilities import ACTION_CAPABILITIES
from core.permission_manager import PermissionDecision, PermissionManager


@dataclass(frozen=True)
class CapabilityDefinition:
    """Immutable definition of a MARK-L capability."""

    name: str
    description: str = ""
    actions: frozenset[str] = field(default_factory=frozenset)
    permission: PermissionDecision = PermissionDecision.DENY

    def to_dict(self) -> dict:
        """Return a serializable representation."""
        return {
            "name": self.name,
            "description": self.description,
            "actions": sorted(self.actions),
            "permission": self.permission.value,
        }


class CapabilityRegistry:
    """Authoritative registry of MARK-L capabilities and action mappings."""

    _DESCRIPTIONS = {
        "READ": "Read or retrieve information without modifying external state.",
        "ANALYZE": "Inspect or analyze information.",
        "DRAFT": "Prepare content without externally committing it.",
        "PUBLISH": "Commit prepared content to an external destination.",
        "DELETE": "Remove data or external resources.",
        "SPEND": "Perform an action involving expenditure.",
        "FINANCIAL": "Perform a financially consequential operation.",
    }

    def __init__(
        self,
        action_capabilities: dict[str, str] | None = None,
        permission_manager: PermissionManager | None = None,
    ) -> None:
        self._permissions = permission_manager or PermissionManager()
        self._action_capabilities = dict(
            action_capabilities
            if action_capabilities is not None
            else ACTION_CAPABILITIES
        )

        self._definitions: dict[str, CapabilityDefinition] = {}
        self._build()

    def _build(self) -> None:
        """Build the canonical capability definitions."""
        capabilities = set(self._action_capabilities.values())
        capabilities.update(PermissionManager._AUTO_ALLOW)
        capabilities.update(PermissionManager._REQUIRES_APPROVAL)

        for capability in sorted(capabilities):
            normalized = self.normalize(capability)
            actions = frozenset(
                action
                for action, mapped in self._action_capabilities.items()
                if self.normalize(mapped) == normalized
            )

            permission = self._permissions.check(normalized).decision

            self._definitions[normalized] = CapabilityDefinition(
                name=normalized,
                description=self._DESCRIPTIONS.get(normalized, ""),
                actions=actions,
                permission=permission,
            )

    @staticmethod
    def normalize(capability: str) -> str:
        """Normalize a capability name."""
        if not isinstance(capability, str):
            return ""

        return capability.strip().upper()

    def has(self, capability: str) -> bool:
        """Return whether the capability is registered."""
        return self.normalize(capability) in self._definitions

    def get(self, capability: str) -> CapabilityDefinition | None:
        """Return a capability definition, or None if unknown."""
        return self._definitions.get(self.normalize(capability))

    def all(self) -> list[CapabilityDefinition]:
        """Return all registered capabilities in deterministic order."""
        return [
            self._definitions[name]
            for name in sorted(self._definitions)
        ]

    def actions_for(self, capability: str) -> set[str]:
        """Return the actions registered under a capability."""
        definition = self.get(capability)
        if definition is None:
            return set()

        return set(definition.actions)

    def capability_for_operation(self, action: str, parameters: dict | None = None) -> str | None:
        """Resolve capability using the action and its operation parameters."""
        from core.action_capabilities import capability_for_operation
        return capability_for_operation(action, parameters)
    def capability_for_action(self, action: str) -> str | None:
        """Return the trusted capability for an action."""
        if not isinstance(action, str):
            return None

        action = action.strip()
        capability = self._action_capabilities.get(action)

        if capability is None:
            return None

        normalized = self.normalize(capability)

        if normalized not in self._definitions:
            return None

        return normalized

    def permission_for(self, capability: str) -> PermissionDecision:
        """Return the current deterministic permission classification."""
        definition = self.get(capability)

        if definition is None:
            return PermissionDecision.DENY

        return definition.permission

    def validate_action(self, action: str) -> bool:
        """Return whether an action has a trusted registered capability."""
        return self.capability_for_action(action) is not None

    def to_dict(self) -> dict[str, dict]:
        """Return the complete registry as serializable data."""
        return {
            definition.name: definition.to_dict()
            for definition in self.all()
        }

