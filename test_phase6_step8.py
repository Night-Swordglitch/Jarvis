from core.dependency_graph import DependencyGraph
from core.events.bus import EventBus
from core.management.manager import ManagementManager
from core.management.state import ManagementState
from core.task_manager import TaskManager


print("=== PHASE 6 STEP 8 REPLANNING + CLARIFICATION TEST ===")

event_bus = EventBus()
state = ManagementState()
task_manager = TaskManager(state, event_bus)
dependency_graph = DependencyGraph()

manager = ManagementManager(
    state,
    event_bus,
    task_manager,
    dependency_graph,
)

# ------------------------------------------------------------
# 1. Foundation
# ------------------------------------------------------------

mission = manager.accept_mission(
    "Build and test a coding feature"
)

assert mission.objective == "Build and test a coding feature"
assert manager.running is True

print("Foundation: PASS")


# ------------------------------------------------------------
# 2. Clarification request
# ------------------------------------------------------------

decision = manager.request_clarification(
    "Which repository should I modify?"
)

assert decision.decision.value == "CLARIFY"
assert decision.clarification_question == "Which repository should I modify?"
assert "Which repository should I modify?" in state.open_questions

print("Clarification request: PASS")


# ------------------------------------------------------------
# 3. Clarification blocks continuation
# ------------------------------------------------------------

decision = manager.evaluate()

assert decision.decision.value == "CLARIFY"
assert decision.clarification_question == "Which repository should I modify?"

print("Clarification lifecycle: PASS")


# ------------------------------------------------------------
# 4. Resolve clarification
# ------------------------------------------------------------

manager.clear_clarification(
    "Which repository should I modify?"
)

assert not state.open_questions

print("Clarification resolution: PASS")


# ------------------------------------------------------------
# 5. Initial plan
# ------------------------------------------------------------

plan = manager.create_plan(
    planner_output='''
    {
        "tasks": [
            {
                "id": "inspect",
                "objective": "Inspect the repository",
                "priority": 80
            },
            {
                "id": "implement",
                "objective": "Implement the feature",
                "priority": 70,
                "dependencies": ["inspect"]
            }
        ]
    }
    '''
)

assert len(plan) == 2
assert plan[0]["objective"] == "Inspect the repository"

task_ids = manager.create_planned_tasks(plan)

assert len(task_ids) == 2

print("Initial planning: PASS")


# ------------------------------------------------------------
# 6. Failed work triggers REPLAN
# ------------------------------------------------------------

failed_task = task_ids[0]

task_manager.start_task(failed_task)
task_manager.fail_task(
    failed_task,
    "Repository structure changed."
)

manager._synchronize_state()

decision = manager.evaluate()

assert decision.decision.value == "REPLAN"
assert failed_task in decision.metadata["failed_tasks"]

print("Failure detection: PASS")
print("Replan decision: PASS")


# ------------------------------------------------------------
# 7. Revised plan
# ------------------------------------------------------------

revised_plan = manager.create_plan(
    planner_output='''
    {
        "tasks": [
            {
                "id": "rediscover",
                "objective": "Rediscover the repository structure",
                "priority": 90
            },
            {
                "id": "implement_v2",
                "objective": "Implement the feature using the updated structure",
                "priority": 80,
                "dependencies": ["rediscover"]
            }
        ]
    }
    '''
)

assert len(revised_plan) == 2
assert revised_plan[0]["id"] == "rediscover"

replanned_task_ids = manager.create_planned_tasks(revised_plan)

assert len(replanned_task_ids) == 2

print("Revised planning: PASS")


# ------------------------------------------------------------
# 8. Replan does not erase mission identity
# ------------------------------------------------------------

assert manager.mission is not None
assert manager.mission.mission_id == state.mission_id
assert manager.mission.objective == "Build and test a coding feature"

print("Mission preservation: PASS")


print()
print("PHASE 6 STEP 8: ALL TESTS PASSED")
