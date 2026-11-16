from core.events import EventBus
from core.management.manager import ManagementManager
from core.management.state import ManagementState
from core.management.business_manager import BusinessManager
from core.task_manager import TaskManager
from core.dependency_graph import DependencyGraph


def main() -> None:
    print("=== PHASE 6 STEP 12 BUSINESS TASK ORCHESTRATION TEST ===")

    state = ManagementState()
    events = EventBus()
    task_manager = TaskManager(state, events)
    graph = DependencyGraph()

    management_manager = ManagementManager(
        state,
        events,
        task_manager,
        graph,
    )

    manager = BusinessManager(
        management_manager,
        events,
    )

    # ------------------------------------------------------------
    # Accept a real business mission
    # ------------------------------------------------------------
    mission = management_manager.accept_mission(
        "Build a gaming print-on-demand business",
        context={"region": "Singapore"},
    )

    assert mission.objective == "Build a gaming print-on-demand business"
    assert management_manager.running is True

    print("Business mission acceptance: PASS")

    # ------------------------------------------------------------
    # Build the business plan
    # ------------------------------------------------------------
    plan = manager.prepare_business_plan(
        mission.objective,
        context=mission.context,
    )

    assert len(plan) == 4

    aliases = {
        item["id"]
        for item in plan
    }

    assert aliases == {
        "business_research",
        "business_social",
        "business_analytics",
        "business_evaluation",
    }

    print("Business plan generation: PASS")

    # ------------------------------------------------------------
    # Verify specialist assignments
    # ------------------------------------------------------------
    by_id = {
        item["id"]: item
        for item in plan
    }

    assert by_id["business_research"]["agent_name"] == "research_agent"
    assert by_id["business_social"]["agent_name"] == "social_agent"
    assert by_id["business_analytics"]["agent_name"] == "analytics_agent"

    assert by_id["business_evaluation"]["agent_name"] is None

    print("Specialist task routing: PASS")

    # ------------------------------------------------------------
    # Create REAL management tasks
    # ------------------------------------------------------------
    task_ids = manager.create_business_tasks(
        mission.objective,
        context=mission.context,
    )

    assert len(task_ids) == 4

    print("Management task creation: PASS")

    # ------------------------------------------------------------
    # Every task exists in TaskManager and DependencyGraph
    # ------------------------------------------------------------
    for task_id in task_ids:
        assert task_manager.get_task(task_id) is not None
        assert graph.has_task(task_id)

    print("TaskManager / DependencyGraph integration: PASS")

    # ------------------------------------------------------------
    # Resolve plan aliases to actual task IDs
    # ------------------------------------------------------------
    tasks_by_alias = {}

    for task_id in task_ids:
        task = task_manager.get_task(task_id)
        assert task is not None

        alias = task.metadata.get("plan_alias")
        tasks_by_alias[alias] = task_id

    assert set(tasks_by_alias) == {
        "business_research",
        "business_social",
        "business_analytics",
        "business_evaluation",
    }

    print("Plan alias resolution: PASS")

    # ------------------------------------------------------------
    # Verify dependency structure
    #
    # Research ────────┐
    # Social ──────────┼──> Evaluation
    # Analytics ───────┘
    # ------------------------------------------------------------
    evaluation_id = tasks_by_alias["business_evaluation"]

    dependencies = set(
        graph.dependencies_of(evaluation_id)
    )

    assert dependencies == {
        tasks_by_alias["business_research"],
        tasks_by_alias["business_social"],
        tasks_by_alias["business_analytics"],
    }

    print("Business dependency graph: PASS")

    # ------------------------------------------------------------
    # Evidence gathering tasks should initially be independent
    # ------------------------------------------------------------
    for alias in (
        "business_research",
        "business_social",
        "business_analytics",
    ):
        task_id = tasks_by_alias[alias]

        assert graph.dependencies_of(task_id) == []

    print("Independent evidence branches: PASS")

    # ------------------------------------------------------------
    # Evaluation must wait for all evidence
    # ------------------------------------------------------------
    states = {
        task_id: task_manager.get_task(task_id)
        for task_id in graph.tasks()
    }

    assert graph.is_ready(evaluation_id, states) is False

    ready = set(
        graph.ready_tasks(states)
    )

    assert ready == {
        tasks_by_alias["business_research"],
        tasks_by_alias["business_social"],
        tasks_by_alias["business_analytics"],
    }

    print("Dependency-aware readiness: PASS")

    # ------------------------------------------------------------
    # No direct specialist execution
    # ------------------------------------------------------------
    assert not hasattr(manager, "dispatch")
    assert not hasattr(manager, "run_agent")

    print("No direct specialist execution: PASS")

    # ------------------------------------------------------------
    # Management Manager remains the orchestration authority
    # ------------------------------------------------------------
    assert manager.management_manager is management_manager

    print("Management authority boundary: PASS")

    print()
    print("PHASE 6 STEP 12: ALL TESTS PASSED")


if __name__ == "__main__":
    main()
