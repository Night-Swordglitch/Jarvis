from core.management.manager import ManagementManager
from core.management.state import ManagementState
from core.events.bus import EventBus
from core.dependency_graph import DependencyGraph
from core.task_manager import TaskManager


def build_manager():
    state = ManagementState(
        mission_id="test-mission",
        objective="Test MARK-L management",
    )

    bus = EventBus()
    tasks = TaskManager(state, bus)
    graph = DependencyGraph()

    manager = ManagementManager(
        state,
        bus,
        tasks,
        graph,
    )

    return manager, state, tasks, graph


print("=== PHASE 6 STEP 5 MANAGEMENT MANAGER TEST ===")


# ------------------------------------------------------------
# 1. Mission acceptance
# ------------------------------------------------------------

manager, state, tasks, graph = build_manager()

mission = manager.accept_mission(
    "Research a potential new product"
)

assert manager.mission is mission
assert state.mission_id == mission.mission_id
assert state.objective == "Research a potential new product"
assert manager.running is True

print("Mission acceptance: PASS")


# ------------------------------------------------------------
# 2. Planning
# ------------------------------------------------------------

plan = manager.create_plan(
    planner_output="""
    {
        "tasks": [
            {
                "id": "research",
                "objective": "Research the product market",
                "priority": 80,
                "agent_name": "research_agent"
            },
            {
                "id": "analysis",
                "objective": "Analyze the research",
                "priority": 70,
                "agent_name": "analytics_agent",
                "dependencies": ["research"]
            }
        ]
    }
    """
)

assert len(plan) == 2
assert state.status == "RUNNING"

print("Planning: PASS")


# ------------------------------------------------------------
# 3. Task creation
# ------------------------------------------------------------

task_ids = manager.create_planned_tasks(plan)

assert len(task_ids) == 2

for task_id in task_ids:
    assert tasks.get_task(task_id) is not None
    assert task_id in graph.tasks()

print("Task creation: PASS")


# ------------------------------------------------------------
# 4. Dependency integration
# ------------------------------------------------------------

research_id = task_ids[0]
analysis_id = task_ids[1]

assert set(graph.dependencies_of(analysis_id)) == {research_id}
assert graph.is_ready(research_id, {task.task_id: task for task in [tasks.get_task(research_id), tasks.get_task(analysis_id)] if task is not None}) is True
assert graph.is_ready(analysis_id, {task.task_id: task for task in [tasks.get_task(research_id), tasks.get_task(analysis_id)] if task is not None}) is False

print("Dependency integration: PASS")


# ------------------------------------------------------------
# 5. Continue decision
# ------------------------------------------------------------

decision = manager.evaluate()

assert decision.decision == "CONTINUE"

print("Continue decision: PASS")


# ------------------------------------------------------------
# 6. Clarification
# ------------------------------------------------------------

manager.request_clarification(
    "Which market should be researched?"
)

decision = manager.evaluate()

assert decision.decision == "CLARIFY"
assert decision.clarification_question == (
    "Which market should be researched?"
)

print("Clarification handling: PASS")

manager.clear_clarification()


# ------------------------------------------------------------
# 7. Approval
# ------------------------------------------------------------

manager.request_approval(
    "Publishing the final product listing"
)

decision = manager.evaluate()

assert decision.decision == "APPROVAL"

print("Approval handling: PASS")

manager.clear_approval()


# ------------------------------------------------------------
# 8. Failure -> replan
# ------------------------------------------------------------

tasks.start_task(research_id)

tasks.fail_task(
    research_id,
    "Research provider unavailable",
)

manager._synchronize_state()

decision = manager.evaluate()

assert decision.decision == "REPLAN"

print("Failure / replan decision: PASS")


# ------------------------------------------------------------
# 9. Mission completion
# ------------------------------------------------------------

# Build a fresh manager for clean completion testing.
manager2, state2, tasks2, graph2 = build_manager()

manager2.accept_mission(
    "Complete a simple test mission"
)

plan2 = manager2.create_plan(
    planner_output="""
    {
        "tasks": [
            {
                "id": "finish",
                "objective": "Perform the final test"
            }
        ]
    }
    """
)

ids2 = manager2.create_planned_tasks(plan2)

tasks2.start_task(ids2[0])
tasks2.complete_task(
    ids2[0],
    {"result": "done"},
)

manager2._synchronize_state()

decision = manager2.evaluate()

assert decision.decision == "COMPLETE"

print("Completion detection: PASS")


# ------------------------------------------------------------
# 10. Explicit completion
# ------------------------------------------------------------

result = manager2.complete_mission()

assert result.decision == "COMPLETE"
assert state2.status == "COMPLETED"
assert manager2.running is False

print("Mission completion: PASS")


# ------------------------------------------------------------
# 11. No execution bypass
# ------------------------------------------------------------

# Management Manager must only manipulate management/task state.
# It does not possess an action runner or confirmation resolver.

assert not hasattr(manager, "_action_runner")
assert not hasattr(manager, "_execute_action")

print("No execution bypass: PASS")


print()
print("PHASE 6 STEP 5: ALL TESTS PASSED")










