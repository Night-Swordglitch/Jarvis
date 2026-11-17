from core.agent_action_executor import AgentActionExecutor
from core.permission_manager import PermissionDecision, PermissionManager
from core.permission_bridge import PermissionBridge
from core.permissions import CapabilityRequest


print("=== PHASE 7D — CAPABILITY EXECUTOR TEST ===")


# --------------------------------------------------------------
# Trusted host-side action runner
# --------------------------------------------------------------

executed_actions = []


def action_runner(action, context):
    executed_actions.append(
        {
            "action": action,
            "context": dict(context),
        }
    )

    return f"Executed trusted action: {action}"


executor = AgentActionExecutor(
    action_runner=action_runner,
)

print("AgentActionExecutor constructed: PASS")


# --------------------------------------------------------------
# 1. READ capability should execute automatically
# --------------------------------------------------------------

result = executor.submit(
    {
        "action": "web_search",
        "reason": "Research information required by the mission.",
        "context": {
            "query": "MARK-L capability execution test",
        },
    }
)

assert "Executed trusted action: web_search" in result

assert len(executed_actions) == 1
assert executed_actions[0]["action"] == "web_search"

print("READ capability auto-execution: PASS")


# --------------------------------------------------------------
# 2. ANALYZE capability should execute automatically
# --------------------------------------------------------------

result = executor.submit(
    {
        "action": "file_processor",
        "reason": "Analyze a trusted file supplied to the mission.",
        "context": {
            "file": "test-input.txt",
        },
    }
)

assert "Executed trusted action: file_processor" in result

assert len(executed_actions) == 2
assert executed_actions[1]["action"] == "file_processor"

print("ANALYZE capability auto-execution: PASS")


# --------------------------------------------------------------
# 3. Unknown action must be denied
# --------------------------------------------------------------

before = len(executed_actions)

result = executor.submit(
    {
        "action": "delete_everything",
        "reason": "Malicious test action.",
        "context": {},
    }
)

assert "denied" in result.lower()
assert len(executed_actions) == before

print("Unknown action denied: PASS")
print("Denied action never reached executable callback: PASS")


# --------------------------------------------------------------
# 4. Agent cannot choose its own capability
# --------------------------------------------------------------

before = len(executed_actions)

result = executor.submit(
    {
        "action": "web_search",
        "capability": "DELETE",
        "reason": (
            "The agent falsely claims this requires DELETE."
        ),
        "context": {
            "query": "capability spoof test",
        },
    }
)

assert "Executed trusted action: web_search" in result

assert len(executed_actions) == before + 1
assert executed_actions[-1]["action"] == "web_search"

print("Agent-supplied capability ignored: PASS")
print("Host-side capability classification remains authoritative: PASS")


# --------------------------------------------------------------
# 5. Verify deterministic permission policy
# --------------------------------------------------------------

permissions = PermissionManager()

read_result = permissions.check("READ")
analyze_result = permissions.check("ANALYZE")
publish_result = permissions.check("PUBLISH")
unknown_result = permissions.check("SOMETHING_UNKNOWN")

assert read_result.decision == PermissionDecision.ALLOW
assert analyze_result.decision == PermissionDecision.ALLOW
assert publish_result.decision == PermissionDecision.APPROVAL_REQUIRED
assert unknown_result.decision == PermissionDecision.DENY

print("READ permission policy: PASS")
print("ANALYZE permission policy: PASS")
print("PUBLISH approval boundary: PASS")
print("Unknown capability denial: PASS")


# --------------------------------------------------------------
# 6. Verify CapabilityRequest remains structured
# --------------------------------------------------------------

request = CapabilityRequest(
    capability="read",
    action="web_search",
    reason="Structured capability test.",
    context={
        "query": "test",
    },
)

assert request.capability == "READ"
assert request.action == "web_search"
assert request.normalized_capability == "READ"
assert request.normalized_action == "web_search"

print("CapabilityRequest contract: PASS")


# --------------------------------------------------------------
# 7. Verify the executable callback belongs to the host
# --------------------------------------------------------------

bridge = PermissionBridge()

trusted_request = CapabilityRequest(
    capability="READ",
    action="web_search",
    reason="Trusted callback test.",
    context={},
)

trusted_result = bridge.submit(
    trusted_request,
    lambda: "trusted-host-execution",
)

assert trusted_result == "trusted-host-execution"

print("PermissionBridge → trusted callback: PASS")


print()
print("==============================================")
print("PHASE 7D FOUNDATION: ALL TESTS PASSED")
print("AGENT INTENT → HOST CAPABILITY → PERMISSION → EXECUTION: PASS")
print("==============================================")
