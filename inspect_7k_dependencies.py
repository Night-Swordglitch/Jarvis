from core.events.bus import EventBus
from core.management.state import ManagementState
from core.task_manager import TaskManager
from core.dependency_graph import DependencyGraph
from core.management.manager import ManagementManager
from core.management.business_manager import BusinessManager

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

mission = manager.accept_mission(
    "Evaluate a gaming-themed print-on-demand business using evidence.",
    context={}
)

business = BusinessManager(manager, event_bus)

business.create_business_tasks(
    "Evaluate a gaming-themed print-on-demand business using evidence.",
    context={}
)

print("`TASK OBJECTS`")
print("=" * 60)

for task in list(state.queued_tasks.values()):
    print()
    print("TASK ID:", task.task_id)
    print("ALIAS:", task.metadata.get("plan_alias"))
    print("AGENT:", task.agent_name)
    print("DEPENDENCIES ATTRIBUTE:", repr(task.dependencies))
    print("METADATA:")
    print(task.metadata)

print()
print("`DEPENDENCY GRAPH`")
print("=" * 60)

print("Graph tasks:", dependency_graph.tasks())

for task_id in dependency_graph.tasks():
    print()
    print("GRAPH TASK:", task_id)
    try:
        print("READY:", dependency_graph.is_ready(task_id, {
            **state.queued_tasks,
            **state.active_tasks,
            **state.completed_tasks,
            **state.failed_tasks,
            **state.blocked_tasks,
        }))
    except Exception as e:
        print("READY ERROR:", repr(e))

print()
print("`RAW DEPENDENCY GRAPH OBJECT`")
print("=" * 60)
print(dependency_graph.__dict__)
