from core.dependency_graph import DependencyGraph
from core.events.bus import EventBus
from core.management.evidence import EvidenceRecord, EvidenceStore
from core.management.manager import ManagementManager
from core.management.state import ManagementState
from core.mission_context import MissionContext
from core.mission_intake import MissionIntake
from core.task_manager import TaskManager


print("=== PHASE 7B — CONTEXT INTEGRATION TEST ===")


# ------------------------------------------------------------
# Existing Phase 6 management stack
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

print("Phase 6 management stack: PASS")


# ------------------------------------------------------------
# 7A — Mission intake
# ------------------------------------------------------------
intake = MissionIntake()

intake_result = intake.intake(
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
        "domain": "business",
    },
)

assert intake_result.ready

print("7A mission intake: PASS")


# ------------------------------------------------------------
# Accept mission through existing ManagementManager
# ------------------------------------------------------------
mission = manager.accept_mission(
    intake_result.objective,
    context=intake_result.to_context(),
)

assert mission.mission_id
assert mission.objective == (
    "Build a gaming print-on-demand business"
)

print("Mission accepted: PASS")


# ------------------------------------------------------------
# 7B — Build structured mission context
# ------------------------------------------------------------
mission_context = MissionContext(
    mission_id=mission.mission_id,
    objective=mission.objective,
    constraints=intake_result.constraints,
    success_criteria=intake_result.success_criteria,
    environment={
        "region": "Singapore",
        "currency": "SGD",
    },
    capabilities=[
        "web_research",
        "analytics",
        "social_research",
    ],
)

assert mission_context.mission_id == mission.mission_id
assert mission_context.objective == mission.objective

print("MissionContext attached to mission: PASS")


# ------------------------------------------------------------
# EvidenceStore remains authoritative
# ------------------------------------------------------------
evidence = EvidenceStore()

record = EvidenceRecord(
    mission_id=mission.mission_id,
    task_id="research-task",
    agent_name="ResearchAgent",
    source="test-source",
    claim="Gaming merchandise demand exists.",
    details={
        "test": True,
    },
    status="UNVERIFIED",
    confidence=0.75,
)

evidence.add(record)

mission_context.add_evidence_reference(
    record.evidence_id
)

assert record.evidence_id in mission_context.evidence_ids
assert evidence.get(record.evidence_id) is record

print("Evidence reference → EvidenceStore: PASS")


# ------------------------------------------------------------
# Verify evidence ownership is not duplicated
# ------------------------------------------------------------
assert len(evidence) == 1
assert len(mission_context.evidence_ids) == 1

print("Evidence ownership remains centralized: PASS")


# ------------------------------------------------------------
# Serialize and restore context
# ------------------------------------------------------------
serialized = mission_context.to_dict()

restored = MissionContext.from_dict(
    serialized
)

assert restored.to_dict() == serialized
assert restored.mission_id == mission.mission_id

print("MissionContext round-trip: PASS")


# ------------------------------------------------------------
# Verify mission itself remains valid
# ------------------------------------------------------------
assert manager.mission is mission
assert state.mission_id == mission.mission_id
assert state.objective == mission.objective

print("Management state remains synchronized: PASS")


# ------------------------------------------------------------
# No task execution
# ------------------------------------------------------------
assert state.active_tasks == {}
assert state.queued_tasks == {}
assert state.completed_tasks == {}

print("No automatic task execution: PASS")


# ------------------------------------------------------------
# No execution authority in MissionContext
# ------------------------------------------------------------
assert not hasattr(mission_context, "execute")
assert not hasattr(mission_context, "dispatch")
assert not hasattr(mission_context, "run_agent")
assert not hasattr(mission_context, "create_task")

print("MissionContext remains non-executing: PASS")


print()
print("==============================================")
print("PHASE 7B INTEGRATION: ALL TESTS PASSED")
print("MISSION → CONTEXT → EVIDENCE → MANAGEMENT: PASS")
print("==============================================")
