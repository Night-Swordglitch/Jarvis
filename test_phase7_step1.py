from core.mission_intake import MissionIntake, MissionIntakeResult


print("=== PHASE 7A — MISSION INTAKE TEST ===")


# ------------------------------------------------------------
# Foundation
# ------------------------------------------------------------
intake = MissionIntake()

result = intake.intake(
    "Build a gaming print-on-demand business",
)

assert isinstance(result, MissionIntakeResult)
assert result.objective == (
    "Build a gaming print-on-demand business"
)
assert result.ready
print("Mission intake foundation: PASS")


# ------------------------------------------------------------
# Constraint extraction
# ------------------------------------------------------------
result = intake.intake(
    "Build a gaming print-on-demand business",
    constraints=[
        "Budget is $500",
        "Operate in Singapore",
        "",
        "   ",
    ],
)

assert result.constraints == [
    "Budget is $500",
    "Operate in Singapore",
]
assert result.ready
print("Constraint handling: PASS")


# ------------------------------------------------------------
# Success criteria
# ------------------------------------------------------------
result = intake.intake(
    "Build a gaming print-on-demand business",
    success_criteria=[
        "Produce a viable launch plan",
        "Identify initial products",
    ],
)

assert result.success_criteria == [
    "Produce a viable launch plan",
    "Identify initial products",
]
assert result.ready
print("Success criteria handling: PASS")


# ------------------------------------------------------------
# Context merging
# ------------------------------------------------------------
intake = MissionIntake(
    default_context={
        "source": "phase7a_test",
        "region": "Singapore",
    }
)

result = intake.intake(
    "Build a gaming print-on-demand business",
    context={
        "budget": 500,
    },
)

assert result.context["source"] == "phase7a_test"
assert result.context["region"] == "Singapore"
assert result.context["budget"] == 500
print("Context merging: PASS")


# ------------------------------------------------------------
# Structured management context
# ------------------------------------------------------------
result = intake.intake(
    "Build a gaming print-on-demand business",
    constraints=["Budget is $500"],
    success_criteria=["Create launch plan"],
)

management_context = result.to_context()

assert management_context["constraints"] == [
    "Budget is $500"
]
assert management_context["success_criteria"] == [
    "Create launch plan"
]
assert "mission_intake" in management_context
print("Management context generation: PASS")


# ------------------------------------------------------------
# Clarification boundary
# ------------------------------------------------------------
result = intake.require_clarification(
    "Build a gaming print-on-demand business",
    "What is the maximum launch budget?",
)

assert not result.ready
assert result.clarification_questions == [
    "What is the maximum launch budget?"
]
print("Clarification detection: PASS")


# ------------------------------------------------------------
# Validation
# ------------------------------------------------------------
try:
    intake.intake("")
    raise AssertionError("Empty objective should fail")
except ValueError:
    pass

try:
    intake.intake("Test", constraints="invalid")
    raise AssertionError("Invalid constraints should fail")
except TypeError:
    pass

try:
    intake.intake("Test", success_criteria="invalid")
    raise AssertionError("Invalid success criteria should fail")
except TypeError:
    pass

try:
    intake.intake("Test", context="invalid")
    raise AssertionError("Invalid context should fail")
except TypeError:
    pass

print("Input validation: PASS")


# ------------------------------------------------------------
# No execution authority
# ------------------------------------------------------------
assert not hasattr(intake, "dispatch")
assert not hasattr(intake, "run_agent")
assert not hasattr(intake, "execute")
assert not hasattr(intake, "create_task")
print("No execution authority: PASS")


# ------------------------------------------------------------
# Serialization
# ------------------------------------------------------------
serialized = result.to_dict()

assert serialized["objective"] == (
    "Build a gaming print-on-demand business"
)
assert serialized["ready"] is False
assert serialized["clarification_questions"]

print("Serialization: PASS")


print()
print("==============================================")
print("PHASE 7A: ALL TESTS PASSED")
print("MISSION INTAKE: PASS")
print("==============================================")


