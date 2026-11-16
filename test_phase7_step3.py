from core.mission_context import MissionContext


print("=== PHASE 7B — MISSION CONTEXT TEST ===")


# ------------------------------------------------------------
# Foundation
# ------------------------------------------------------------
context = MissionContext(
    mission_id="mission-7b-test",
    objective="Build a gaming print-on-demand business",
)

assert context.mission_id == "mission-7b-test"
assert context.objective == (
    "Build a gaming print-on-demand business"
)
assert context.constraints == []
assert context.success_criteria == []
assert context.environment == {}
assert context.capabilities == []
assert context.evidence_ids == []

print("Mission context foundation: PASS")


# ------------------------------------------------------------
# Constraints
# ------------------------------------------------------------
context.add_constraint("Budget is $500")
context.add_constraint("Operate in Singapore")
context.add_constraint("Budget is $500")

assert context.constraints == [
    "Budget is $500",
    "Operate in Singapore",
]

print("Constraint management: PASS")


# ------------------------------------------------------------
# Success criteria
# ------------------------------------------------------------
context.add_success_criterion(
    "Create a viable launch plan"
)
context.add_success_criterion(
    "Identify initial products"
)

assert context.success_criteria == [
    "Create a viable launch plan",
    "Identify initial products",
]

print("Success criteria management: PASS")


# ------------------------------------------------------------
# Environment
# ------------------------------------------------------------
context.set_environment(
    "region",
    "Singapore",
)

context.set_environment(
    "currency",
    "SGD",
)

assert context.environment == {
    "region": "Singapore",
    "currency": "SGD",
}

print("Environment context: PASS")


# ------------------------------------------------------------
# Capabilities
# ------------------------------------------------------------
context.add_capability("web_research")
context.add_capability("analytics")
context.add_capability("social_research")
context.add_capability("web_research")

assert context.capabilities == [
    "web_research",
    "analytics",
    "social_research",
]

print("Capability context: PASS")


# ------------------------------------------------------------
# Evidence references
# ------------------------------------------------------------
context.add_evidence_reference("evidence-001")
context.add_evidence_reference("evidence-002")
context.add_evidence_reference("evidence-001")

assert context.evidence_ids == [
    "evidence-001",
    "evidence-002",
]

print("Evidence references: PASS")


# ------------------------------------------------------------
# Additional context
# ------------------------------------------------------------
context.set_context(
    "source",
    "phase7b_test",
)

context.set_context(
    "domain",
    "business",
)

assert context.additional_context == {
    "source": "phase7b_test",
    "domain": "business",
}

print("Additional context: PASS")


# ------------------------------------------------------------
# Serialization
# ------------------------------------------------------------
serialized = context.to_dict()

assert serialized["mission_id"] == "mission-7b-test"
assert serialized["objective"] == (
    "Build a gaming print-on-demand business"
)
assert serialized["constraints"] == [
    "Budget is $500",
    "Operate in Singapore",
]
assert serialized["evidence_ids"] == [
    "evidence-001",
    "evidence-002",
]

print("Serialization: PASS")


# ------------------------------------------------------------
# Restoration
# ------------------------------------------------------------
restored = MissionContext.from_dict(serialized)

assert restored.to_dict() == serialized

print("Serialization round-trip: PASS")


# ------------------------------------------------------------
# Validation
# ------------------------------------------------------------
try:
    MissionContext(
        mission_id="",
        objective="Test",
    )
    raise AssertionError(
        "Empty mission_id should fail"
    )
except ValueError:
    pass

try:
    MissionContext(
        mission_id="test",
        objective="",
    )
    raise AssertionError(
        "Empty objective should fail"
    )
except ValueError:
    pass

try:
    MissionContext(
        mission_id="test",
        objective="Test",
        environment="invalid",
    )
    raise AssertionError(
        "Invalid environment should fail"
    )
except TypeError:
    pass

print("Input validation: PASS")


# ------------------------------------------------------------
# No execution authority
# ------------------------------------------------------------
assert not hasattr(context, "execute")
assert not hasattr(context, "dispatch")
assert not hasattr(context, "run_agent")
assert not hasattr(context, "create_task")

print("No execution authority: PASS")


print()
print("==============================================")
print("PHASE 7B FOUNDATION: ALL TESTS PASSED")
print("MISSION CONTEXT: PASS")
print("==============================================")
