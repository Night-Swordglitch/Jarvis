import asyncio

from core import confirm
from core.permission_manager import PermissionDecision, PermissionManager
from core.permission_bridge import PermissionBridge
from core.permissions import CapabilityRequest


def main() -> None:
    print("=== PHASE 6 STEP 11 PERMISSION INTEGRATION TEST ===")

    permissions = PermissionManager()

    # ------------------------------------------------------------
    # Automatic allow
    # ------------------------------------------------------------
    read_request = CapabilityRequest(
        capability="READ",
        action="inspect_repository",
        reason="Management Manager needs repository information.",
    )

    read_result = permissions.evaluate(read_request)

    assert read_result.decision == PermissionDecision.ALLOW
    assert read_result.allowed is True
    assert read_result.requires_approval is False
    assert read_result.action == "inspect_repository"

    print("Automatic allow: PASS")

    # ------------------------------------------------------------
    # Approval boundary
    # ------------------------------------------------------------
    publish_request = CapabilityRequest(
        capability="PUBLISH",
        action="publish_result",
        reason="Management Manager wants to publish the completed result.",
    )

    publish_result = permissions.evaluate(publish_request)

    assert publish_result.decision == PermissionDecision.APPROVAL_REQUIRED
    assert publish_result.allowed is True
    assert publish_result.requires_approval is True

    print("Approval boundary: PASS")

    # ------------------------------------------------------------
    # Unknown capability must remain denied
    # ------------------------------------------------------------
    unknown_request = CapabilityRequest(
        capability="SUPERUSER",
        action="do_unrestricted_thing",
        reason="Attempted unrestricted management action.",
    )

    unknown_result = permissions.evaluate(unknown_request)

    assert unknown_result.decision == PermissionDecision.DENY
    assert unknown_result.allowed is False
    assert unknown_result.requires_approval is False

    print("Unknown capability denial: PASS")

    # ------------------------------------------------------------
    # Bridge ALLOW path
    # ------------------------------------------------------------
    bridge = PermissionBridge(permissions)

    executed = []

    allow_result = bridge.submit(
        read_request,
        lambda: executed.append("read") or "READ EXECUTED",
    )

    assert allow_result == "READ EXECUTED"
    assert executed == ["read"]

    print("Bridge allow execution: PASS")

    # ------------------------------------------------------------
    # Bridge DENY path
    # ------------------------------------------------------------
    executed.clear()

    deny_result = bridge.submit(
        unknown_request,
        lambda: executed.append("dangerous"),
    )

    assert "denied" in deny_result.lower()
    assert executed == []

    print("Bridge deny enforcement: PASS")

    # ------------------------------------------------------------
    # Approval path must NOT execute immediately
    # ------------------------------------------------------------
    executed.clear()

    # The confirmation system may not be bound in this isolated test.
    # We replace the request function temporarily so we can verify that
    # the bridge reaches the approval boundary without resolving it.
    original_request = confirm.request

    captured = {}

    def fake_request(*, key, title, detail, run):
        captured["key"] = key
        captured["title"] = title
        captured["detail"] = detail
        captured["run"] = run
        return "APPROVAL_REQUIRED"

    confirm.request = fake_request

    try:
        approval_result = bridge.submit(
            publish_request,
            lambda: executed.append("published") or "PUBLISHED",
        )
    finally:
        confirm.request = original_request

    assert approval_result == "APPROVAL_REQUIRED"
    assert executed == []
    assert captured["key"] == "permission-publish_result"
    assert captured["run"] is not None

    print("Human approval boundary: PASS")

    # ------------------------------------------------------------
    # Confirmation callback remains host-controlled
    # ------------------------------------------------------------
    captured["run"]()

    assert executed == ["published"]

    print("Approved callback execution: PASS")

    # ------------------------------------------------------------
    # Capability request cannot grant itself permission
    # ------------------------------------------------------------
    forged_request = CapabilityRequest(
        capability="ALLOW",
        action="delete_everything",
        reason="Forged capability supplied by management layer.",
    )

    forged_result = permissions.evaluate(forged_request)

    assert forged_result.decision == PermissionDecision.DENY

    print("Self-granted permission rejection: PASS")

    print()
    print("PHASE 6 STEP 11: ALL TESTS PASSED")


if __name__ == "__main__":
    main()
