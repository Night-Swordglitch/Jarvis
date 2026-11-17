from core.management import (
    Mission,
    ManagementState,
    TaskState,
    ManagementDecision,
    DecisionType,
)

from core.events import Event, EventBus


print("=== PHASE 6 STEP 1 FOUNDATION TEST ===")

# ---------------------------------------------------------
# Mission
# ---------------------------------------------------------

mission = Mission(
    objective="Test MARK-L multi-agent orchestration",
    context={"source": "phase_6_test"},
)

assert mission.status == "CREATED"
assert mission.objective == "Test MARK-L multi-agent orchestration"

print("Mission model: PASS")


# ---------------------------------------------------------
# Management State
# ---------------------------------------------------------

state = ManagementState()

state.set_mission(
    mission.mission_id,
    mission.objective,
)

task = TaskState(
    task_id="task-test-001",
    objective="Test event-driven task",
    priority=80,
)

state.queued_tasks[task.task_id] = task

assert state.mission_id == mission.mission_id
assert state.task_count() == 1

print("Management state: PASS")


# ---------------------------------------------------------
# Management Decision
# ---------------------------------------------------------

decision = ManagementDecision(
    decision=DecisionType.CONTINUE,
    reason="Test decision",
    tasks_to_start=["task-test-001"],
    user_update="Continuing the mission.",
)

serialized = decision.to_dict()

assert serialized["decision"] == "CONTINUE"

restored = ManagementDecision.from_dict(serialized)

assert restored.decision == DecisionType.CONTINUE

print("Management decision: PASS")


# ---------------------------------------------------------
# Event Bus
# ---------------------------------------------------------

bus = EventBus()

received = []


def handler(event):
    received.append(event)


bus.subscribe("TASK_STARTED", handler)

event = Event(
    event_type="TASK_STARTED",
    payload={
        "task_id": "task-test-001",
        "agent": "research_agent",
    },
)

called = bus.publish(event)

assert called == 1
assert len(received) == 1
assert received[0].event_type == "TASK_STARTED"

print("Event bus: PASS")


# ---------------------------------------------------------
# Wildcard Events
# ---------------------------------------------------------

wildcard_events = []

bus.subscribe(
    "*",
    lambda event: wildcard_events.append(event),
)

bus.publish(
    Event(
        event_type="TASK_COMPLETED",
        payload={
            "task_id": "task-test-001",
        },
    )
)

assert len(wildcard_events) == 1

print("Wildcard events: PASS")


# ---------------------------------------------------------
# Event Handler Isolation
# ---------------------------------------------------------

bus.subscribe(
    "TASK_FAILED",
    lambda event: (_ for _ in ()).throw(
        RuntimeError("intentional test failure")
    ),
)

safe_received = []

bus.subscribe(
    "TASK_FAILED",
    lambda event: safe_received.append(event),
)

bus.publish(
    Event(
        event_type="TASK_FAILED",
        payload={
            "task_id": "task-test-001",
        },
    )
)

assert len(safe_received) == 1

print("Event handler isolation: PASS")


print("")
print("PHASE 6 STEP 1: ALL TESTS PASSED")
