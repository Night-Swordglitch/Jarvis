from core.events import EventBus
from core.management.state import ManagementState
from core.mission_monitor import MissionMonitor
from core.task_manager import TaskManager


print("=== PHASE 7G — EVENTBUS INTEGRATION TEST ===")


# ------------------------------------------------------------
# Real Phase 6 infrastructure
# ------------------------------------------------------------

state = ManagementState()
event_bus = EventBus()
task_manager = TaskManager(
    state,
    event_bus,
)

print("Real EventBus constructed: PASS")
print("Real TaskManager constructed: PASS")


# ------------------------------------------------------------
# Real MissionMonitor
# ------------------------------------------------------------

monitor = MissionMonitor(
    "mission-7g-integration",
    stale_after=10,
)

monitor.bind_event_bus(event_bus)

assert event_bus.subscriber_count("*") >= 1
print("MissionMonitor bound to real EventBus: PASS")


# ------------------------------------------------------------
# Create a real task
# ------------------------------------------------------------

task = task_manager.create_task(
    "Perform monitored mission work.",
)

monitor.track_task(task.task_id)

assert task.task_id in monitor.tracked_tasks()
print("Mission task registered with monitor: PASS")


# ------------------------------------------------------------
# TASK_CREATED / TASK_QUEUED
# ------------------------------------------------------------

snapshot = monitor.snapshot()

assert snapshot["observed_tasks"][task.task_id] == "QUEUED"
assert snapshot["last_event_type"] is None

print("Initial mission task state registered as QUEUED: PASS")


# ------------------------------------------------------------
# TASK_STARTED
# ------------------------------------------------------------

task_manager.start_task(task.task_id)

snapshot = monitor.snapshot()

assert snapshot["observed_tasks"][task.task_id] == "RUNNING"
assert snapshot["last_event_type"] == "TASK_STARTED"
assert snapshot["status"] == "ACTIVE"

print("Real TASK_STARTED observed automatically: PASS")


# ------------------------------------------------------------
# TASK_COMPLETED
# ------------------------------------------------------------

task_manager.complete_task(
    task.task_id,
    result={"ok": True},
)

snapshot = monitor.snapshot()

assert snapshot["observed_tasks"][task.task_id] == "COMPLETED"
assert snapshot["last_event_type"] == "TASK_COMPLETED"
assert snapshot["status"] == "HEALTHY"
assert snapshot["healthy"] is True

print("Real TASK_COMPLETED observed automatically: PASS")


# ------------------------------------------------------------
# Failed task
# ------------------------------------------------------------

failed_task = task_manager.create_task(
    "Perform a task that will fail.",
)

monitor.track_task(failed_task.task_id)

task_manager.start_task(failed_task.task_id)

task_manager.fail_task(
    failed_task.task_id,
    "Simulated mission failure.",
)

snapshot = monitor.snapshot()

assert snapshot["observed_tasks"][failed_task.task_id] == "FAILED"
assert snapshot["last_event_type"] == "TASK_FAILED"
assert snapshot["status"] == "DEGRADED"
assert snapshot["healthy"] is False
assert failed_task.task_id in snapshot["alerts"][0]

print("Real TASK_FAILED observed automatically: PASS")
print("Mission health degraded automatically: PASS")


# ------------------------------------------------------------
# Untracked task isolation
# ------------------------------------------------------------

untracked = task_manager.create_task(
    "This task does not belong to the monitored mission.",
)

before = monitor.snapshot()["observed_tasks"].copy()

task_manager.start_task(untracked.task_id)

after = monitor.snapshot()["observed_tasks"].copy()

assert untracked.task_id not in after
assert after == before

print("Untracked task isolation: PASS")


# ------------------------------------------------------------
# Serialization
# ------------------------------------------------------------

import json

json.dumps(monitor.snapshot())

print("Integrated monitoring snapshot serialization: PASS")


# ------------------------------------------------------------
# Authority boundary
# ------------------------------------------------------------

forbidden = {
    "run",
    "execute",
    "cancel",
    "retry",
    "approve",
    "resolve",
    "replan",
    "dispatch",
}

assert not forbidden.intersection(dir(MissionMonitor))

print("No execution / retry / approval / replanning authority: PASS")


# ------------------------------------------------------------
# Cleanup
# ------------------------------------------------------------

monitor.unbind_event_bus()

assert event_bus.subscriber_count("*") == 0

print("EventBus unbinding: PASS")


print()
print("==============================================")
print("PHASE 7G INTEGRATION: ALL TESTS PASSED")
print("REAL EVENTBUS MONITORING: PASS")
print("==============================================")

