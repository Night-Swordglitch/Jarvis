from core.dependency_graph import DependencyGraph
from core.management.state import TaskState


def state(task_id: str, status: str) -> TaskState:
    return TaskState(
        task_id=task_id,
        objective=f"Task {task_id}",
        status=status,
    )


print("=== PHASE 6 STEP 3 DEPENDENCY GRAPH TEST ===")

graph = DependencyGraph()

# ------------------------------------------------------------
# Basic nodes
# ------------------------------------------------------------

for task_id in ["T1", "T2", "T3", "T4"]:
    graph.add_task(task_id)

assert set(graph.tasks()) == {"T1", "T2", "T3", "T4"}

print("Task nodes: PASS")

# ------------------------------------------------------------
# Dependencies
#
# T1 ──┐
#      ├──> T4
# T2 ──┘
#
# T3 is independent.
# ------------------------------------------------------------

graph.add_dependency("T4", "T1")
graph.add_dependency("T4", "T2")

assert graph.dependencies_of("T4") == ["T1", "T2"]
assert graph.dependents_of("T1") == ["T4"]

print("Dependency relationships: PASS")

# ------------------------------------------------------------
# Initial state
# ------------------------------------------------------------

states = {
    "T1": state("T1", "QUEUED"),
    "T2": state("T2", "QUEUED"),
    "T3": state("T3", "QUEUED"),
    "T4": state("T4", "QUEUED"),
}

ready = graph.ready_tasks(states)

assert ready == ["T1", "T2", "T3"]

print("Initial ready tasks: PASS")

waiting = graph.waiting_tasks(states)

assert waiting == ["T4"]

print("Waiting tasks: PASS")

# ------------------------------------------------------------
# Complete T1
# ------------------------------------------------------------

states["T1"] = state("T1", "COMPLETED")

ready = graph.ready_tasks(states)

assert ready == ["T2", "T3"]

print("Partial dependency completion: PASS")

assert graph.unresolved_dependencies("T4", states) == ["T2"]

print("Unresolved dependency detection: PASS")

# ------------------------------------------------------------
# Complete T2
# ------------------------------------------------------------

states["T2"] = state("T2", "COMPLETED")

ready = graph.ready_tasks(states)

assert ready == ["T3", "T4"]

print("Dependency unlock: PASS")

# ------------------------------------------------------------
# Failed dependency
# ------------------------------------------------------------

states["T4"] = state("T4", "QUEUED")
states["T2"] = state("T2", "FAILED")

assert graph.failed_dependencies("T4", states) == ["T2"]

print("Failed dependency detection: PASS")

assert "T4" in graph.blocked_tasks(states)

print("Blocked task detection: PASS")

# ------------------------------------------------------------
# Independent task
# ------------------------------------------------------------

assert graph.independent_tasks() == ["T1", "T2", "T3"]

print("Independent task detection: PASS")

# ------------------------------------------------------------
# Cycle detection
# ------------------------------------------------------------

cycle_graph = DependencyGraph()

for task_id in ["A", "B", "C"]:
    cycle_graph.add_task(task_id)

cycle_graph.add_dependency("B", "A")
cycle_graph.add_dependency("C", "B")

try:
    cycle_graph.add_dependency("A", "C")
except ValueError:
    pass
else:
    raise AssertionError("Cycle was not rejected")

assert not cycle_graph.has_cycle()

print("Cycle prevention: PASS")

# ------------------------------------------------------------
# Missing dependency
# ------------------------------------------------------------

try:
    graph.add_dependency("T4", "MISSING")
except KeyError:
    pass
else:
    raise AssertionError("Missing dependency was not rejected")

print("Missing dependency validation: PASS")

# ------------------------------------------------------------
# Topological order
# ------------------------------------------------------------

order_graph = DependencyGraph()

for task_id in ["A", "B", "C", "D"]:
    order_graph.add_task(task_id)

order_graph.add_dependency("C", "A")
order_graph.add_dependency("C", "B")
order_graph.add_dependency("D", "C")

order = order_graph.topological_order()

assert order.index("A") < order.index("C")
assert order.index("B") < order.index("C")
assert order.index("C") < order.index("D")

print("Topological ordering: PASS")

# ------------------------------------------------------------
# Final
# ------------------------------------------------------------

print()
print("PHASE 6 STEP 3: ALL TESTS PASSED")
