from core.events.bus import EventBus
from core.events.events import Event
from core.management.dashboard_events import DashboardEventBridge


print("=== PHASE 6 STEP 15 DASHBOARD EVENTBUS TEST ===")

event_bus = EventBus()
received = []


def on_dashboard_event(event):
    received.append(event)


bridge = DashboardEventBridge(
    event_bus,
    on_event=on_dashboard_event,
)

assert bridge.started is False
assert bridge.event_count == 0
assert bridge.last_event is None
print("Bridge initialization: PASS")


bridge.start()

assert bridge.started is True
print("EventBus subscription: PASS")


event_1 = Event(
    "TASK_STARTED",
    {
        "task_id": "task-001",
        "agent_name": "research_agent",
    },
)

called = event_bus.publish(event_1)

assert called == 1
assert bridge.event_count == 1
assert bridge.last_event is event_1
assert received == [event_1]
print("Event reception: PASS")


event_2 = Event(
    "TASK_COMPLETED",
    {
        "task_id": "task-001",
        "status": "COMPLETED",
    },
)

called = event_bus.publish(event_2)

assert called == 1
assert bridge.event_count == 2
assert bridge.last_event is event_2
assert received == [event_1, event_2]
print("Multiple event reception: PASS")


status = bridge.status()

assert status["started"] is True
assert status["event_count"] == 2
assert status["last_event"]["event_type"] == "TASK_COMPLETED"
assert status["last_event"]["payload"]["task_id"] == "task-001"
print("Bridge status projection: PASS")


bridge.stop()

assert bridge.started is False
print("Bridge stop: PASS")


event_3 = Event(
    "TASK_FAILED",
    {
        "task_id": "task-001",
        "error": "test failure",
    },
)

called = event_bus.publish(event_3)

assert called == 1
assert bridge.event_count == 2
assert bridge.last_event is event_2
assert received == [event_1, event_2]
print("Stopped bridge ignores events: PASS")


bridge.start()

event_4 = Event(
    "MISSION_COMPLETED",
    {
        "mission_id": "mission-001",
    },
)

called = event_bus.publish(event_4)

assert called == 1
assert bridge.event_count == 3
assert bridge.last_event is event_4
assert received == [event_1, event_2, event_4]
print("Bridge restart: PASS")


print("EventBus source state: PASS")
print("Read-only event observation: PASS")
print("PHASE 6 STEP 15: ALL TESTS PASSED")
