"""Trusted capability classification for agent-requested actions.

The host, not the agent, decides what capability an action requires.
Unknown actions and unknown sub-actions are denied by default.
"""

from __future__ import annotations


ACTION_CAPABILITIES: dict[str, str] = {
    "web_search": "READ",
    "recall_memory": "READ",
    "file_processor": "ANALYZE",

    # Inline live actions are classified by the trusted host.
    "system_status": "READ",
    "close_camera": "PUBLISH",
    "shutdown_jarvis": "PUBLISH",
}


ACTION_OPERATION_CAPABILITIES: dict[str, dict[str, str]] = {
    "manage_monitor": {
        "list": "READ",
        "add": "PUBLISH",
        "remove": "PUBLISH",
    },

    "file_controller": {
        "list": "READ",
        "read": "READ",
        "find": "READ",
        "largest": "READ",
        "disk_usage": "READ",
        "info": "READ",

        "create_file": "PUBLISH",
        "create_folder": "PUBLISH",
        "create_directory": "PUBLISH",
        "write": "PUBLISH",
        "copy": "PUBLISH",
        "move": "PUBLISH",
        "rename": "PUBLISH",
        "organize_desktop": "PUBLISH",

        "delete": "DELETE",
    },
}


def capability_for_action(action: str) -> str | None:
    """Return the trusted capability for an action."""
    if not isinstance(action, str):
        return None

    return ACTION_CAPABILITIES.get(action.strip())


def capability_for_operation(
    action: str,
    parameters: dict | None = None,
) -> str | None:
    """Return the host-trusted capability for a concrete operation."""
    if not isinstance(action, str):
        return None

    normalized_action = action.strip()

    direct_capability = capability_for_action(normalized_action)
    if direct_capability is not None:
        return direct_capability

    operations = ACTION_OPERATION_CAPABILITIES.get(normalized_action)
    if operations is None or not isinstance(parameters, dict):
        return None

    operation = parameters.get("action")
    if not isinstance(operation, str):
        return None

    return operations.get(operation.strip().lower())

