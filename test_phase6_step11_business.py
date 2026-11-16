from core.events import EventBus
from core.management.manager import ManagementManager
from core.management.state import ManagementState
from core.task_manager import TaskManager
from core.dependency_graph import DependencyGraph
from core.management.business_manager import BusinessManager


def main() -> None:
    print("=== PHASE 6 STEP 11 BUSINESS OPERATIONS TEST ===")

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
    # Identity
    # ------------------------------------------------------------
    assert manager.name == "Business Manager"
    assert manager.MANAGER_TYPE == "BUSINESS"

    print("Business manager identity: PASS")

    # ------------------------------------------------------------
    # Domain routing
    # ------------------------------------------------------------
    assert manager.accepts("Build a print-on-demand business") is True
    assert manager.accepts("Analyze sales for my online store") is True
    assert manager.accepts("Fix my Python repository") is False

    print("Business domain routing: PASS")

    # ------------------------------------------------------------
    # Research task preparation
    # ------------------------------------------------------------
    research = manager.prepare_research_task(
        "Research the market for a gaming print-on-demand business",
        context={"market": "gaming"},
    )

    assert research["manager_type"] == "BUSINESS"
    assert research["agent_name"] == "research_agent"
    assert research["role"] == "business_research"
    assert research["execution"] == "DEFERRED"
    assert research["context"]["market"] == "gaming"

    print("Research task preparation: PASS")

    # ------------------------------------------------------------
    # Social task preparation
    # ------------------------------------------------------------
    social = manager.prepare_social_task(
        "Research social-media evidence for a gaming business"
    )

    assert social["agent_name"] == "social_agent"
    assert social["role"] == "business_social_research"
    assert social["execution"] == "DEFERRED"

    print("Social task preparation: PASS")

    # ------------------------------------------------------------
    # Analytics task preparation
    # ------------------------------------------------------------
    analytics = manager.prepare_analytics_task(
        "Analyze supplied store sales metrics",
        context={"analytics_data": {"orders": 10}},
    )

    assert analytics["agent_name"] == "analytics_agent"
    assert analytics["role"] == "business_analytics"
    assert analytics["execution"] == "DEFERRED"
    assert analytics["context"]["analytics_data"]["orders"] == 10

    print("Analytics task preparation: PASS")

    # ------------------------------------------------------------
    # Full business work package
    # ------------------------------------------------------------
    plan = manager.prepare_business_plan(
        "Build a gaming print-on-demand business",
        context={"region": "Singapore"},
    )

    assert len(plan) == 4

    agent_names = {
        item["agent_name"]
        for item in plan
    }

    assert agent_names == {
        "research_agent",
        "social_agent",
        "analytics_agent",
        None,
    }

    evaluation = next(
        item
        for item in plan
        if item["agent_name"] is None
    )

    assert evaluation["manager_type"] == "BUSINESS"
    assert evaluation["role"] == "business_evaluation"
    assert evaluation["execution"] == "DEFERRED"

    assert all(
        item["manager_type"] == "BUSINESS"
        and item["execution"] == "DEFERRED"
        for item in plan
    )

    print("Business work package: PASS")

    # ------------------------------------------------------------
    # No direct execution
    # ------------------------------------------------------------
    assert not hasattr(manager, "dispatch")
    assert not hasattr(manager, "run_agent")

    print("No direct agent execution: PASS")

    # ------------------------------------------------------------
    # Management authority remains above Business Manager
    # ------------------------------------------------------------
    assert manager.management_manager is management_manager

    print("Management authority boundary: PASS")

    print()
    print("PHASE 6 STEP 11: ALL TESTS PASSED")


if __name__ == "__main__":
    main()

