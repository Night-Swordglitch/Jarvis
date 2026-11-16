from pathlib import Path
from tempfile import TemporaryDirectory

from core.agents.code_agent import CodeAgent
from core.agents.task import AgentTask
from core.events.bus import EventBus
from core.management.code_manager import CodeManager
from core.dependency_graph import DependencyGraph
from core.management.manager import ManagementManager
from core.management.state import ManagementState
from core.task_manager import TaskManager


print("=== PHASE 6 STEP 7 CODE AGENT + CODE MANAGER TEST ===")


# ------------------------------------------------------------------
# 1. Foundation
# ------------------------------------------------------------------

event_bus = EventBus()
management_state = ManagementState()

task_manager = TaskManager(
    management_state,
    event_bus,
)

dependency_graph = DependencyGraph()

management = ManagementManager(
    management_state,
    event_bus,
    task_manager,
    dependency_graph,
)

code_manager = CodeManager(
    management,
    event_bus,
)

code_agent = CodeAgent()

print("Foundation: PASS")


# ------------------------------------------------------------------
# 2. Manager identity
# ------------------------------------------------------------------

assert code_manager.MANAGER_TYPE == "CODE"
assert code_manager.name == "Code Manager"

print("Manager identity: PASS")


# ------------------------------------------------------------------
# 3. Domain routing
# ------------------------------------------------------------------

assert code_manager.accepts("Fix the Python bug") is True
assert code_manager.accepts("Analyze the repository") is True
assert code_manager.accepts("Plan my vacation") is False

assert code_agent.can_handle(
    AgentTask(objective="Debug the Python application")
) is True

assert code_agent.can_handle(
    AgentTask(objective="Plan my vacation")
) is False

print("Domain routing: PASS")


# ------------------------------------------------------------------
# 4. Task preparation
# ------------------------------------------------------------------

prepared = code_manager.prepare_task(
    "Inspect the repository for bugs",
    repository="/tmp/example",
    priority=80,
    metadata={"source": "6G test"},
)

assert prepared["manager"] == "Code Manager"
assert prepared["manager_type"] == "CODE"
assert prepared["objective"] == "Inspect the repository for bugs"
assert prepared["priority"] == 80
assert prepared["context"]["repository"] == "/tmp/example"
assert prepared["context"]["source"] == "6G test"
assert prepared["execution"] == "DEFERRED"

print("Task preparation: PASS")


# ------------------------------------------------------------------
# 5. Repository inspection
# ------------------------------------------------------------------

with TemporaryDirectory() as temp_dir:
    root = Path(temp_dir)

    (root / "main.py").write_text(
        "print('hello')",
        encoding="utf-8",
    )

    (root / "README.md").write_text(
        "# Test",
        encoding="utf-8",
    )

    (root / "ignored.txt").write_text(
        "still inspectable",
        encoding="utf-8",
    )

    (root / ".git").mkdir()

    (root / ".git" / "config").write_text(
        "ignored",
        encoding="utf-8",
    )

    task = AgentTask(
        objective="Inspect repository",
        context={"repository": str(root)},
    )

    result = code_agent.run(task)

    assert result.agent_name == "code_agent"
    assert result.task_id == task.task_id
    assert result.status == "SUCCESS"
    assert result.success is True
    assert result.data["repository"] == str(root.resolve())
    assert result.data["file_count"] == 3
    assert "main.py" in result.data["files"]
    assert "README.md" in result.data["files"]
    assert ".git/config" not in result.data["files"]

print("Repository inspection: PASS")


# ------------------------------------------------------------------
# 6. Invalid repository handling
# ------------------------------------------------------------------

invalid_task = AgentTask(
    objective="Inspect repository",
    context={"repository": "Z:\\definitely\\not\\a\\real\\repository"},
)

invalid_result = code_agent.run(invalid_task)

assert invalid_result.status == "FAILED"
assert invalid_result.success is False
assert invalid_result.errors

print("Invalid repository handling: PASS")


# ------------------------------------------------------------------
# 7. No direct execution
# ------------------------------------------------------------------

assert not hasattr(code_agent, "write_file")
assert not hasattr(code_agent, "modify_file")
assert not hasattr(code_agent, "execute_command")
assert not hasattr(code_agent, "apply_patch")

assert not hasattr(code_manager, "execute_agent")
assert not hasattr(code_manager, "dispatch_agent")
assert not hasattr(code_manager, "run_agent")

print("No direct execution: PASS")


# ------------------------------------------------------------------
# 8. Manager lifecycle
# ------------------------------------------------------------------

code_manager.start()

assert code_manager.status()["running"] is True

code_manager.stop()

assert code_manager.status()["running"] is False

print("Manager lifecycle: PASS")


# ------------------------------------------------------------------
# Final
# ------------------------------------------------------------------

print()
print("PHASE 6 STEP 7: ALL TESTS PASSED")
