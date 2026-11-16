from __future__ import annotations

from typing import Any

from core.plugin_loader import PluginRegistry


class ExternalIntegrationContract:
    """Thin boundary around MARK-L's existing external PluginRegistry."""

    def __init__(self, registry: PluginRegistry) -> None:
        if not isinstance(registry, PluginRegistry):
            raise TypeError("registry must be a PluginRegistry.")

        self._registry = registry

    def has(self, name: str) -> bool:
        """Check whether an external integration is registered."""
        return self._registry.has(str(name).strip())

    def run(
        self,
        name: str,
        parameters: dict[str, Any],
        *,
        player: Any = None,
        session_memory: Any = None,
    ) -> str:
        """Delegate execution to the existing PluginRegistry."""
        if not isinstance(parameters, dict):
            raise TypeError("parameters must be a dictionary.")

        return self._registry.run(
            str(name).strip(),
            parameters,
            player=player,
            session_memory=session_memory,
        )

    def scheduling(self, name: str) -> str | None:
        """Return the existing integration scheduling policy."""
        return self._registry.scheduling(str(name).strip())

    def declarations(self) -> list[dict[str, Any]]:
        """Return the existing external tool declarations."""
        return self._registry.get_tool_declarations()

    def registry(self) -> PluginRegistry:
        """Expose the existing registry without replacing it."""
        return self._registry
