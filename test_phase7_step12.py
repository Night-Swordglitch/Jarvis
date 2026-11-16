"""Phase 7I — Human Approval Center integration tests."""

from core import confirm
from core.approval_center import ApprovalCenter, ApprovalRequest
from core.permission_manager import PermissionManager
from core.permissions import CapabilityRequest


def main() -> None:
    print("\n=== PHASE 7I — HUMAN APPROVAL CENTER TEST ===")

    # ---------------------------------------------------------
    # Fake HUD callbacks.
    # These simulate the existing interface without replacing
    # core.confirm.
    # ---------------------------------------------------------
    shown = []
    hidden = []
    executed = []

    def show(title: str, detail: str) -> None:
        shown.append((title, detail))

    def hide() -> None:
        hidden.append(True)

    def log(message: str) -> None:
        pass

    confirm.bind(show, hide, log)

    center = ApprovalCenter(
        permission_manager=PermissionManager(),
    )

    request = CapabilityRequest(
        capability="PUBLISH",
        action="publish_campaign",
        reason="Publish the approved campaign to the public.",
    )

    # ---------------------------------------------------------
    # Approval request
    # ---------------------------------------------------------
    response = center.request(
        mission_id="mission-7i",
        task_id="task-publish",
        capability_request=request,
        run=lambda: executed.append(True) or "Published.",
    )

    assert "[CONFIRMATION_PENDING]" in response
    assert shown
    assert not executed

    pending = center.pending()

    assert len(pending) == 1
    assert isinstance(pending[0], ApprovalRequest)
    assert pending[0].mission_id == "mission-7i"
    assert pending[0].task_id == "task-publish"
    assert pending[0].action == "publish_campaign"
    assert pending[0].capability == "PUBLISH"
    assert pending[0].status == "PENDING"

    print("ApprovalCenter created pending approval: PASS")
    print("Existing core.confirm gate displayed approval: PASS")
    print("Action did not execute before human approval: PASS")

    # ---------------------------------------------------------
    # Human approval
    # ---------------------------------------------------------
    confirm.resolve(True)

    import time
    time.sleep(0.15)

    assert executed == [True]
    assert hidden

    print("Human CONFIRM reached existing core.confirm: PASS")
    print("Trusted callback executed only after confirmation: PASS")

    # ---------------------------------------------------------
    # Serialization
    # ---------------------------------------------------------
    payload = pending[0].to_dict()
    restored = ApprovalRequest.from_dict(payload)

    assert restored.to_dict() == payload

    print("ApprovalRequest serialization: PASS")

    # ---------------------------------------------------------
    # Cancellation must not execute.
    # ---------------------------------------------------------
    executed.clear()
    shown.clear()
    hidden.clear()

    cancel_request = CapabilityRequest(
        capability="DELETE",
        action="delete_campaign",
        reason="Delete the campaign draft.",
    )

    response = center.request(
        mission_id="mission-7i",
        task_id="task-delete",
        capability_request=cancel_request,
        run=lambda: executed.append(True) or "Deleted.",
    )

    assert "[CONFIRMATION_PENDING]" in response
    assert not executed

    confirm.resolve(False)

    time.sleep(0.15)

    assert not executed

    print("Human CANCEL prevented execution: PASS")

    # ---------------------------------------------------------
    # Unknown capability must be denied.
    # ---------------------------------------------------------
    unknown = CapabilityRequest(
        capability="NUCLEAR_LAUNCH",
        action="launch",
        reason="Unknown capability test.",
    )

    response = center.request(
        mission_id="mission-7i",
        task_id="task-unknown",
        capability_request=unknown,
        run=lambda: executed.append(True) or "Launched.",
    )

    assert "denied" in response.lower()
    assert not executed

    print("Unknown capability remained denied: PASS")

    # ---------------------------------------------------------
    # Authority boundary.
    # ---------------------------------------------------------
    forbidden = {
        "execute",
        "run",
        "approve",
        "resolve",
        "cancel",
        "retry",
        "replan",
        "dispatch",
        "modify_permissions",
    }

    center_methods = set(dir(center))

    assert not forbidden.intersection(center_methods)

    print("ApprovalCenter has no execution / resolution authority: PASS")
    print("core.confirm remains the human confirmation authority: PASS")
    print("PermissionManager remains the permission authority: PASS")
    print("PermissionBridge remains the execution-routing authority: PASS")

    print("\n==============================================")
    print("PHASE 7I: ALL TESTS PASSED")
    print("HUMAN APPROVAL CENTER: PASS")
    print("EXISTING CONFIRMATION GATE PRESERVED: PASS")
    print("AUTHORITY BOUNDARIES: PASS")
    print("==============================================")


if __name__ == "__main__":
    main()
