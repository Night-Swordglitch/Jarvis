from core.dependency_graph import DependencyGraph
from core.events.bus import EventBus
from core.management.manager import ManagementManager
from core.management.state import ManagementState
from core.mission_intake import MissionIntake
from core.task_manager import TaskManager


print("=== PHASE 7A — MANAGEMENT INTEGRATION TEST ===")


# ------------------------------------------------------------
# Build the existing Phase 6 management stack
# ------------------------------------------------------------
state = ManagementState()
event_bus = EventBus()
task_manager = TaskManager(state, event_bus)
dependency_graph = DependencyGraph()

manager = ManagementManager(
    state,
    event_bus,
    task_manager,
    dependency_graph,
)


# ------------------------------------------------------------
# MissionIntake creates structured mission input
# ------------------------------------------------------------
intake = MissionIntake()

result = intake.intake(
    "Build a gaming print-on-demand business",
    constraints=[
        "Budget is $500",
        "Operate in Singapore",
    ],
    success_criteria=[
        "Create a viable launch plan",
        "Identify initial products",
    ],
    context={
        "source": "phase7a",
        "domain": "business",
    },
)

assert result.ready
print("Structured mission created: PASS")


# ------------------------------------------------------------
# Hand structured mission to existing ManagementManager
# ------------------------------------------------------------
mission = manager.accept_mission(
    result.objective,
    context=result.to_context(),
)

assert mission.objective == (
    "Build a gaming print-on-demand business"
)

assert state.mission_id == mission.mission_id
assert state.objective == (
    "Build a gaming print-on-demand business"
)

print("ManagementManager accepted mission: PASS")


# ------------------------------------------------------------
# Verify context survived the boundary
# ------------------------------------------------------------
assert mission.context["constraints"] == [
    "Budget is $500",
    "Operate in Singapore",
]

assert mission.context["success_criteria"] == [
    "Create a viable launch plan",
    "Identify initial products",
]

assert mission.context["source"] == "phase7a"
assert mission.context["domain"] == "business"

print("Mission context preserved: PASS")


# ------------------------------------------------------------
# Verify MissionIntake does not replace ManagementManager
# ------------------------------------------------------------
assert manager.mission is mission
assert manager.running

print("Existing ManagementManager remains authoritative: PASS")


# ------------------------------------------------------------
# Clarification case
# ------------------------------------------------------------
clarified = intake.require_clarification(
    "Build a gaming print-on-demand business",
    "What is the maximum launch budget?",
)

assert not clarified.ready
assert clarified.clarification_questions == [
    "What is the maximum launch budget?"
]

print("Clarification boundary preserved: PASS")


# ------------------------------------------------------------
# No automatic execution
# ------------------------------------------------------------
assert state.active_tasks == {}
assert state.queued_tasks == {}
assert state.completed_tasks == {}

print("No automatic task execution: PASS")


print()
print("==============================================")
print("PHASE 7A INTEGRATION: ALL TESTS PASSED")
print("MISSION INTAKE → MANAGEMENT MANAGER: PASS")
print("==============================================")
