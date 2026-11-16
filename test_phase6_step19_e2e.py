from core.events.bus import EventBus
from core.events.events import Event
from core.management.state import ManagementState
from core.task_manager import TaskManager
from core.dependency_graph import DependencyGraph
from core.scheduler import Scheduler
from core.management.manager import ManagementManager
from core.management.evidence import EvidenceStore
from core.management.dashboard import DashboardProjector
from core.management.dashboard_events import DashboardEventBridge
from dashboard.server import DashboardServer
from dashboard.management_api import ManagementDashboardAPI

print("=== PHASE 6 STEP 19 — 6M-5 END-TO-END TEST ===")

state = ManagementState()
bus = EventBus()
tasks = TaskManager(state, bus)
graph = DependencyGraph()
scheduler = Scheduler(tasks, graph, max_workers=3)
evidence = EvidenceStore()
manager = ManagementManager(state, bus, tasks, graph)
projector = DashboardProjector(
    state,
    graph,
    evidence,
    scheduler,
)

print("Management runtime construction: PASS")

manager.accept_mission(
    "Run an end-to-end MARK-L dashboard integration test."
)

plan = manager.create_plan()
created = manager.create_planned_tasks(plan)

assert created
assert len(state.queued_tasks) == 1

print("Mission -> management task: PASS")

task_id = next(iter(state.queued_tasks))

assert graph.has_task(task_id)

snapshot = projector.snapshot().to_dict()

assert snapshot["mission"]["mission_id"] == state.mission_id

queued_ids = {
    task["task_id"]
    for task in snapshot["tasks"]["queued"]
}

assert task_id in queued_ids
assert task_id in snapshot["dependencies"]

print("Real state -> dashboard projection: PASS")

received = []

bridge = DashboardEventBridge(
    bus,
    on_event=lambda event: received.append(event),
)

bridge.start()

bus.publish(
    Event(
        event_type="DASHBOARD_E2E_TEST",
        payload={
            "mission_id": state.mission_id,
            "task_id": task_id,
        },
    )
)

assert bridge.event_count == 1
assert bridge.last_event is not None
assert len(received) == 1
assert received[0].payload["task_id"] == task_id

print("EventBus -> dashboard bridge: PASS")

server = DashboardServer()

api = ManagementDashboardAPI(
    server,
    projector,
)

api.install()

assert api.installed

print("Existing DashboardServer + management API: PASS")

api_snapshot = api.snapshot()

assert api_snapshot["mission"]["mission_id"] == state.mission_id
assert api_snapshot["mission"]["objective"] == state.objective

api_task_ids = {
    task["task_id"]
    for group in api_snapshot["tasks"].values()
    for task in group
}

assert task_id in api_task_ids

print("Management API -> real state: PASS")

tasks.start_task(task_id)

running_snapshot = projector.snapshot().to_dict()

running_ids = {
    task["task_id"]
    for task in running_snapshot["tasks"]["active"]
}

assert task_id in running_ids

tasks.complete_task(
    task_id,
    {
        "status": "E2E_PASS",
        "source": "phase6_step19",
    },
)

completed_snapshot = projector.snapshot().to_dict()

completed_ids = {
    task["task_id"]
    for task in completed_snapshot["tasks"]["completed"]
}

assert task_id in completed_ids

completed_task = next(
    task
    for task in completed_snapshot["tasks"]["completed"]
    if task["task_id"] == task_id
)

assert completed_task["result"]["status"] == "E2E_PASS"

print("Task lifecycle -> live dashboard projection: PASS")

scheduler_snapshot = projector.snapshot().to_dict()["scheduler"]

assert scheduler_snapshot["max_workers"] == 3
assert isinstance(scheduler_snapshot["task_states"], dict)

print("Scheduler -> dashboard projection: PASS")

before = projector.snapshot().to_dict()
after = projector.snapshot().to_dict()

assert before == after

print("Dashboard read-only projection: PASS")

print()
print("PHASE 6 STEP 19: ALL TESTS PASSED")
print("6M-5 END-TO-END DASHBOARD INTEGRATION: PASS")
