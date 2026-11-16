from core.mission_monitor import MissionMonitor


print("=== PHASE 7G — AUTONOMOUS MONITORING TEST ===")


# ----------------------------------------------------------
# 1. Foundation
# ----------------------------------------------------------

monitor = MissionMonitor(
    "mission-7g-001",
    stale_after=10,
)

assert monitor.healthy is True

print("Mission monitor foundation: PASS")


# ----------------------------------------------------------
# 2. Observe running task
# ----------------------------------------------------------

monitor.observe_task(
    "task-001",
    "RUNNING",
    observed_at=100.0,
)

snapshot = monitor.snapshot(now=105.0)

assert snapshot["observed_tasks"]["task-001"] == "RUNNING"
assert snapshot["status"] == "ACTIVE"
assert snapshot["healthy"] is True

print("Running task observation: PASS")


# ----------------------------------------------------------
# 3. Detect stale task
# ----------------------------------------------------------

snapshot = monitor.snapshot(now=111.0)

assert snapshot["stale_tasks"] == ["task-001"]

print("Stale task detection: PASS")


# ----------------------------------------------------------
# 4. Completed task clears stale tracking
# ----------------------------------------------------------

monitor.observe_task(
    "task-001",
    "COMPLETED",
    observed_at=112.0,
)

snapshot = monitor.snapshot(now=120.0)

assert snapshot["stale_tasks"] == []
assert snapshot["status"] == "HEALTHY"
assert snapshot["healthy"] is True

print("Completed task observation: PASS")


# ----------------------------------------------------------
# 5. Failure creates a health alert
# ----------------------------------------------------------

monitor.observe_task(
    "task-002",
    "FAILED",
    observed_at=125.0,
)

snapshot = monitor.snapshot(now=126.0)

assert snapshot["healthy"] is False
assert snapshot["status"] == "DEGRADED"
assert "task-002" in snapshot["alerts"][0]

print("Failure detection and health alert: PASS")


# ----------------------------------------------------------
# 6. Event observation
# ----------------------------------------------------------

monitor.observe_event(
    "TASK_STARTED",
    task_id="task-003",
    status="RUNNING",
)

snapshot = monitor.snapshot()

assert snapshot["last_event_type"] == "TASK_STARTED"
assert snapshot["observed_tasks"]["task-003"] == "RUNNING"

print("EventBus-compatible observation: PASS")


# ----------------------------------------------------------
# 7. Terminal states are tracked
# ----------------------------------------------------------

monitor.observe_task("task-004", "BLOCKED")
monitor.observe_task("task-005", "CANCELLED")

snapshot = monitor.snapshot()

assert snapshot["observed_tasks"]["task-004"] == "BLOCKED"
assert snapshot["observed_tasks"]["task-005"] == "CANCELLED"

print("Blocked/cancelled observation: PASS")


# ----------------------------------------------------------
# 8. Monitoring remains read-only
# ----------------------------------------------------------

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


# ----------------------------------------------------------
# 9. Snapshot is serializable
# ----------------------------------------------------------

import json

json.dumps(snapshot)

print("Monitoring snapshot serialization: PASS")


print()
print("==============================================")
print("PHASE 7G FOUNDATION: ALL TESTS PASSED")
print("AUTONOMOUS MISSION MONITORING: PASS")
print("==============================================")
