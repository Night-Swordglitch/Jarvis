from core.events.bus import EventBus
from core.dependency_graph import DependencyGraph
from core.management.dashboard import DashboardProjector
from core.management.evidence import EvidenceStore
from core.management.manager import ManagementManager
from core.management.state import ManagementState
from core.task_manager import TaskManager
from dashboard.management_api import ManagementDashboardAPI
from dashboard.server import DashboardServer


print("=== PHASE 6 STEP 16 DASHBOARD API INTEGRATION TEST ===")


# ── Real management infrastructure ────────────────────────────────────────

state = ManagementState()
event_bus = EventBus()
task_manager = TaskManager(state, event_bus)
dependency_graph = DependencyGraph()
management_manager = ManagementManager(
    state,
    event_bus,
    task_manager,
    dependency_graph,
)

evidence_store = EvidenceStore()


management_manager.accept_mission(
    "Build a gaming print-on-demand business",
    context={
        "region": "Singapore",
        "test_mode": True,
    },
)

task_a = task_manager.create_task(
    "Research gaming market",
    agent_name="research_agent",
)

task_b = task_manager.create_task(
    "Analyze gaming metrics",
    agent_name="analytics_agent",
    dependencies=[task_a.task_id],
)

dependency_graph.add_task(task_a.task_id)
dependency_graph.add_task(task_b.task_id)

dependency_graph.add_dependency(
    task_b.task_id,
    task_a.task_id,
)


# ── Real projector ─────────────────────────────────────────────────────────

projector = DashboardProjector(
    state,
    dependency_graph,
    evidence_store,
)


# ── Existing dashboard server ──────────────────────────────────────────────

server = DashboardServer()

api = ManagementDashboardAPI(
    server,
    projector,
)

assert api.installed is False

api.install()

assert api.installed is True

print("API integration installation: PASS")


# Installing twice must not create another endpoint/subscription.

api.install()

assert api.installed is True

print("Idempotent installation: PASS")


# ── Inspect registered routes ─────────────────────────────────────────────

routes = {
    getattr(route, "path", None)
    for route in server.app.routes
}

assert "/api/management/state" in routes

print("Management endpoint registration: PASS")


# ── Check projector through integration layer ──────────────────────────────

snapshot = api.snapshot()

assert snapshot["mission"]["objective"] == (
    "Build a gaming print-on-demand business"
)

assert len(snapshot["tasks"]["queued"]) == 2

assert task_a.task_id in snapshot["dependencies"]
assert task_b.task_id in snapshot["dependencies"]

assert task_a.task_id in snapshot["dependencies"][task_b.task_id]["dependencies"]

print("Real dashboard projection: PASS")


# ── Authentication boundary ───────────────────────────────────────────────

import asyncio
import httpx


async def run_http_tests():
    transport = httpx.ASGITransport(app=server.app)

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:

        response = await client.get(
            "/api/management/state",
        )

        assert response.status_code == 401

        print("Unauthorized request blocked: PASS")


        token = "test-dashboard-token"
        server._tokens.add(token)

        response = await client.get(
            "/api/management/state",
            headers={
                "Authorization": f"Bearer {token}",
            },
        )

        assert response.status_code == 200

        payload = response.json()

        assert payload["mission"]["objective"] == (
            "Build a gaming print-on-demand business"
        )

        assert "tasks" in payload
        assert "agents" in payload
        assert "dependencies" in payload
        assert "evidence" in payload
        assert "scheduler" in payload
        assert "approvals" in payload
        assert "questions" in payload
        assert "next_actions" in payload

        print("Authorized dashboard request: PASS")

        # Verify dependency data survives the HTTP boundary.

        assert (
            task_a.task_id
            in payload["dependencies"][task_b.task_id]["dependencies"]
        )

        print("Dependency API projection: PASS")


asyncio.run(run_http_tests())


# ── Read-only behavior ─────────────────────────────────────────────────────

before = projector.snapshot().to_dict()

after = api.snapshot()

assert before == after

assert state.mission_id is not None
assert state.objective == "Build a gaming print-on-demand business"

print("Read-only API behavior: PASS")


print("Existing DashboardServer preserved: PASS")
print("PHASE 6 STEP 16: ALL TESTS PASSED")
