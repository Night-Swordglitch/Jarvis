import threading
import time

from core import confirm
from core.permission_bridge import PermissionBridge
from core.permission_manager import PermissionDecision
from core.permissions import CapabilityRequest


print("=== PHASE 7E — HUMAN APPROVAL GATE TEST ===")


# --------------------------------------------------------------
# Test-controlled HUD callbacks
# --------------------------------------------------------------

shown = []
hidden = []
executed = []
logs = []


def show(title, detail):
    shown.append(
        {
            "title": title,
            "detail": detail,
        }
    )


def hide():
    hidden.append(True)


def log(message):
    logs.append(message)


# Save existing callbacks/state indirectly by binding our test HUD.
confirm.bind(
    show=show,
    hide=hide,
    log=log,
)

print("Test HUD callbacks bound: PASS")


# --------------------------------------------------------------
# Trusted host-side action
# --------------------------------------------------------------

def trusted_action():
    executed.append("ACTION_EXECUTED")
    return "trusted action complete"


bridge = PermissionBridge()


# --------------------------------------------------------------
# 1. Approval-required capability must NOT execute immediately
# --------------------------------------------------------------

request = CapabilityRequest(
    capability="PUBLISH",
    action="publish_result",
    reason="Publish the completed mission result.",
    context={
        "mission_id": "phase7e-test",
    },
)

result = bridge.submit(
    request,
    trusted_action,
)

assert "CONFIRMATION_PENDING" in result
assert len(executed) == 0

print("APPROVAL_REQUIRED does not execute immediately: PASS")


# --------------------------------------------------------------
# 2. Confirmation must appear on the host UI
# --------------------------------------------------------------

assert len(shown) == 1
assert shown[0]["title"] == "Approve publish_result"

assert confirm.pending_title() == "Approve publish_result"

print("Human confirmation requested through HUD: PASS")
print("Pending confirmation state: PASS")


# --------------------------------------------------------------
# 3. Agent cannot execute by simply requesting the action
# --------------------------------------------------------------

assert len(executed) == 0

print("Agent request cannot bypass human approval: PASS")


# --------------------------------------------------------------
# 4. Simulate human pressing CANCEL
# --------------------------------------------------------------

confirm.resolve(False)

time.sleep(0.05)

assert len(executed) == 0
assert confirm.pending_title() == ""

print("Human CANCEL prevents execution: PASS")


# --------------------------------------------------------------
# 5. Submit a second approval-required action
# --------------------------------------------------------------

shown.clear()
hidden.clear()

result = bridge.submit(
    request,
    trusted_action,
)

assert "CONFIRMATION_PENDING" in result
assert len(executed) == 0
assert confirm.pending_title() == "Approve publish_result"

print("Second approval request queued: PASS")


# --------------------------------------------------------------
# 6. Simulate human pressing CONFIRM
# --------------------------------------------------------------

confirm.resolve(True)

# Confirmation runs the callback on a worker thread.
deadline = time.time() + 2.0

while time.time() < deadline:
    if executed:
        break
    time.sleep(0.01)

assert executed == ["ACTION_EXECUTED"]
assert confirm.pending_title() == ""

print("Human CONFIRM executes trusted action: PASS")


# --------------------------------------------------------------
# 7. Verify the confirmation result came from the UI boundary
# --------------------------------------------------------------

assert len(logs) > 0
assert any(
    "Awaiting confirmation" in message
    for message in logs
)

assert any(
    "Confirmed" in message
    for message in logs
)

print("Confirmation lifecycle logged: PASS")


# --------------------------------------------------------------
# 8. Verify an already-pending confirmation blocks stacking
# --------------------------------------------------------------

shown.clear()

result = bridge.submit(
    request,
    trusted_action,
)

assert "CONFIRMATION_PENDING" in result
assert confirm.pending_title() == "Approve publish_result"

second_result = bridge.submit(
    CapabilityRequest(
        capability="PUBLISH",
        action="another_publish",
        reason="Second approval test.",
        context={},
    ),
    trusted_action,
)

assert "already a confirmation waiting" in second_result.lower()
assert len(executed) == 1

print("Confirmation stacking prevented: PASS")


# Clean up the pending test confirmation.
confirm.resolve(False)

print()
print("==============================================")
print("PHASE 7E FOUNDATION: ALL TESTS PASSED")
print("AGENT → PERMISSION → HUMAN CONFIRMATION → ACTION: PASS")
print("==============================================")
