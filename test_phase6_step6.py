from core.events.bus import EventBus
from core.events.events import Event
from core.management.decision import DecisionType
from core.management.manager import ManagementManager
from core.management.state import ManagementState
from core.management.base_manager import BaseManager
from core.task_manager import TaskManager
from core.dependency_graph import DependencyGraph


print("=== PHASE 6 STEP 6 BASE MANAGER TEST ===")


# ------------------------------------------------------------------
# 1. Foundation

event_bus = EventBus()
management_state = ManagementState()
task_manager = TaskManager(management_state, event_bus)
dependency_graph = DependencyGraph()

management = ManagementManager(
    management_state,
    event_bus,
    task_manager,
    dependency_graph,
)

manager = BaseManager(
    management,
    event_bus,
    name="Test Manager",
)

print("Construction: PASS")


# 2. Initial status
# ------------------------------------------------------------------

status = manager.status()

assert status["name"] == "Test Manager"
assert status["manager_type"] == "BASE"
assert status["running"] is False
assert status["owned_tasks"] == []

print("Initial status: PASS")


# ------------------------------------------------------------------
# 3. Lifecycle
# ------------------------------------------------------------------

manager.start()

assert manager.status()["running"] is True

manager.start()

assert manager.status()["running"] is True

manager.stop()

assert manager.status()["running"] is False

manager.stop()

assert manager.status()["running"] is False

print("Lifecycle handling: PASS")


# ------------------------------------------------------------------
# 4. Task ownership
# ------------------------------------------------------------------

task_a = task_manager.create_task(
    "Base manager task A",
)

task_b = task_manager.create_task(
    "Base manager task B",
)

manager.register_task(task_a.task_id)
manager.register_tasks([task_b.task_id])

assert manager.owns_task(task_a.task_id)
assert manager.owns_task(task_b.task_id)
assert set(manager.owned_tasks) == {
    task_a.task_id,
    task_b.task_id,
}

print("Task ownership: PASS")


# ------------------------------------------------------------------
# 5. Duplicate ownership is harmless
# ------------------------------------------------------------------

manager.register_task(task_a.task_id)

assert manager.owned_tasks.count(task_a.task_id) == 1

print("Duplicate ownership handling: PASS")


# ------------------------------------------------------------------
# 6. Invalid task ownership
# ------------------------------------------------------------------

try:
    manager.register_task("")
    raise AssertionError("Empty task ID should fail")
except ValueError:
    pass

print("Task validation: PASS")


# ------------------------------------------------------------------
# 7. Event handling
# ------------------------------------------------------------------

manager.start()

event_bus.publish(
    Event(
        event_type="TASK_COMPLETED",
        payload={"task_id": task_a.task_id},
    )
)

event_bus.publish(
    Event(
        event_type="TASK_FAILED",
        payload={"task_id": task_b.task_id},
    )
)

assert task_a.task_id in manager.completed_tasks
assert task_b.task_id in manager.failed_tasks
assert len(manager.recent_events) >= 2

print("Event handling: PASS")


# ------------------------------------------------------------------
# 8. Event isolation
# ------------------------------------------------------------------

unowned = task_manager.create_task(
    "Unowned task",
)

event_bus.publish(
    Event(
        event_type="TASK_COMPLETED",
        payload={"task_id": unowned.task_id},
    )
)

assert unowned.task_id not in manager.completed_tasks

print("Task ownership event isolation: PASS")


# ------------------------------------------------------------------
# 9. Custom event handler
# ------------------------------------------------------------------

received = []

custom_manager = BaseManager(
    management,
    event_bus,
    name="Custom Manager",
    event_handler=lambda event: received.append(event.event_type),
)

custom_manager.start()

event_bus.publish(
    Event(
        event_type="CUSTOM_EVENT",
        payload={"value": 42},
    )
)

assert "CUSTOM_EVENT" in received

print("Custom event handler: PASS")


# ------------------------------------------------------------------
# 10. Management escalation
# ------------------------------------------------------------------

management.accept_mission(
    "Test management mission",
)

clarification = custom_manager.request_clarification(
    "Need additional mission information",
)

assert clarification.decision == DecisionType.CLARIFY

custom_manager.management_manager.clear_clarification()

approval = custom_manager.request_approval(
    "Testing manager escalation",
)

assert approval.decision == DecisionType.APPROVAL

print("Management escalation: PASS")


# ------------------------------------------------------------------
# 11. Decision delegation
# ------------------------------------------------------------------

decision = custom_manager.evaluate()

assert isinstance(decision.decision, DecisionType)

print("Decision delegation: PASS")


# ------------------------------------------------------------------
# 12. No execution bypass
# ------------------------------------------------------------------

assert not hasattr(manager, "execute_task")
assert not hasattr(manager, "dispatch_agent")
assert not hasattr(manager, "run_agent")

print("No execution bypass: PASS")


print()
print("PHASE 6 STEP 6: ALL TESTS PASSED")

