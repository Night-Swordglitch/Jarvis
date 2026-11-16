"""Security regression tests for agent-requested action classification."""

from core.agent_action_executor import AgentActionExecutor
from core.permissions import CapabilityRequest


class RecordingPermissionBridge:
    def __init__(self):
        self.request = None
        self.run = None

    def submit(self, request, run):
        self.request = request
        self.run = run
        return "submitted"


def test_unknown_action_fails_closed():
    bridge = RecordingPermissionBridge()
    calls = []
    executor = AgentActionExecutor(
        lambda action, context: calls.append((action, context)) or "ran",
        permission_bridge=bridge,
    )

    result = executor.submit({"action": "unregistered_action"})

    assert "denied" in result.lower()
    assert bridge.request is None
    assert calls == []


def test_operation_capability_is_host_classified():
    bridge = RecordingPermissionBridge()
    executor = AgentActionExecutor(
        lambda _action, _context: "ran",
        permission_bridge=bridge,
    )

    result = executor.submit({
        "action": "file_controller",
        "reason": "Remove an obsolete file",
        "context": {"action": "delete", "path": "example.txt"},
        "capability": "READ",
    })

    assert result == "submitted"
    assert isinstance(bridge.request, CapabilityRequest)
    assert bridge.request.capability == "DELETE"
    assert bridge.request.action == "file_controller"


def test_unknown_operation_fails_closed():
    bridge = RecordingPermissionBridge()
    executor = AgentActionExecutor(
        lambda _action, _context: "ran",
        permission_bridge=bridge,
    )

    result = executor.submit({
        "action": "file_controller",
        "context": {"action": "wipe_everything"},
    })

    assert "denied" in result.lower()
    assert bridge.request is None


def test_context_is_deep_copied_before_submission():
    bridge = RecordingPermissionBridge()
    original = {"action": "read", "options": {"include_hidden": False}}
    executor = AgentActionExecutor(
        lambda _action, _context: "ran",
        permission_bridge=bridge,
    )

    assert executor.submit({
        "action": "file_controller",
        "context": original,
    }) == "submitted"

    original["options"]["include_hidden"] = True
    assert bridge.request.context["options"]["include_hidden"] is False


def test_invalid_request_fields_are_rejected():
    bridge = RecordingPermissionBridge()
    executor = AgentActionExecutor(
        lambda _action, _context: "ran",
        permission_bridge=bridge,
    )

    assert "invalid action" in executor.submit({"action": 42}).lower()
    assert "reason must be text" in executor.submit({
        "action": "web_search",
        "reason": ["not", "text"],
    }).lower()
    assert bridge.request is None
