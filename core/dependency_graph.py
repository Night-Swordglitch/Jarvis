"""Deterministic dependency graph for MARK-L management tasks.

The dependency graph describes task relationships but never executes tasks.
It answers which tasks are ready, waiting, blocked, or involved in cycles.

Execution remains the responsibility of the future Scheduler.
"""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Iterable

from core.management.state import TaskState


TERMINAL_SUCCESS = {"COMPLETED"}
TERMINAL_FAILURE = {"FAILED", "BLOCKED", "CANCELLED"}
ACTIVE_STATES = {"QUEUED", "RUNNING"}


class DependencyGraph:
    """Directed acyclic dependency graph for management tasks.

    An edge:

        A -> B

    means:

        B depends on A.

    Therefore A must complete before B becomes ready.
    """

    def __init__(self) -> None:
        # dependency -> dependents
        self._dependents: dict[str, set[str]] = defaultdict(set)

        # dependent -> dependencies
        self._dependencies: dict[str, set[str]] = defaultdict(set)

        # Known task IDs.
        self._nodes: set[str] = set()

    # ------------------------------------------------------------------
    # Node management
    # ------------------------------------------------------------------

    def add_task(self, task_id: str) -> None:
        """Register a task node."""
        self._validate_task_id(task_id)
        self._nodes.add(task_id)

        # Force both adjacency entries to exist.
        self._dependencies.setdefault(task_id, set())
        self._dependents.setdefault(task_id, set())

    def remove_task(self, task_id: str) -> None:
        """Remove a task and every dependency relationship involving it."""
        self._validate_task_id(task_id)

        if task_id not in self._nodes:
            raise KeyError(f"Unknown task: {task_id}")

        for dependency in list(self._dependencies[task_id]):
            self._dependents[dependency].discard(task_id)

        for dependent in list(self._dependents[task_id]):
            self._dependencies[dependent].discard(task_id)

        self._dependencies.pop(task_id, None)
        self._dependents.pop(task_id, None)
        self._nodes.discard(task_id)

    # ------------------------------------------------------------------
    # Dependency management
    # ------------------------------------------------------------------

    def add_dependency(
        self,
        task_id: str,
        depends_on: str,
    ) -> None:
        """Make task_id depend on depends_on.

        Example:

            add_dependency("synthesis", "research")

        means:

            research -> synthesis
        """
        self._validate_task_id(task_id)
        self._validate_task_id(depends_on)

        if task_id not in self._nodes:
            raise KeyError(f"Unknown task: {task_id}")

        if depends_on not in self._nodes:
            raise KeyError(f"Unknown dependency: {depends_on}")

        if task_id == depends_on:
            raise ValueError(
                f"Dependency cycle detected: {task_id} cannot depend on itself."
            )

        if depends_on in self._dependencies[task_id]:
            return

        # Temporarily add the edge.
        self._dependencies[task_id].add(depends_on)
        self._dependents[depends_on].add(task_id)

        # Reject cycles atomically.
        if self.has_cycle():
            self._dependencies[task_id].remove(depends_on)
            self._dependents[depends_on].remove(task_id)

            raise ValueError(
                f"Dependency cycle detected when adding "
                f"{depends_on} -> {task_id}."
            )

    def remove_dependency(
        self,
        task_id: str,
        depends_on: str,
    ) -> None:
        """Remove a dependency relationship."""
        self._validate_task_id(task_id)
        self._validate_task_id(depends_on)

        if task_id not in self._nodes:
            raise KeyError(f"Unknown task: {task_id}")

        if depends_on not in self._nodes:
            raise KeyError(f"Unknown dependency: {depends_on}")

        self._dependencies[task_id].discard(depends_on)
        self._dependents[depends_on].discard(task_id)

    # ------------------------------------------------------------------
    # Graph inspection
    # ------------------------------------------------------------------

    def has_task(self, task_id: str) -> bool:
        return task_id in self._nodes

    def tasks(self) -> list[str]:
        return sorted(self._nodes)

    def dependencies_of(self, task_id: str) -> list[str]:
        """Return tasks that task_id depends on."""
        self._require_task(task_id)
        return sorted(self._dependencies[task_id])

    def dependents_of(self, task_id: str) -> list[str]:
        """Return tasks that depend on task_id."""
        self._require_task(task_id)
        return sorted(self._dependents[task_id])

    def dependency_count(self, task_id: str) -> int:
        self._require_task(task_id)
        return len(self._dependencies[task_id])

    def dependent_count(self, task_id: str) -> int:
        self._require_task(task_id)
        return len(self._dependents[task_id])

    # ------------------------------------------------------------------
    # State evaluation
    # ------------------------------------------------------------------

    def unresolved_dependencies(
        self,
        task_id: str,
        task_states: dict[str, TaskState],
    ) -> list[str]:
        """Return dependencies that have not completed successfully."""
        self._require_task(task_id)

        unresolved: list[str] = []

        for dependency in sorted(self._dependencies[task_id]):
            state = task_states.get(dependency)

            if state is None:
                unresolved.append(dependency)
                continue

            if state.status.upper() not in TERMINAL_SUCCESS:
                unresolved.append(dependency)

        return unresolved

    def failed_dependencies(
        self,
        task_id: str,
        task_states: dict[str, TaskState],
    ) -> list[str]:
        """Return dependencies that can never satisfy this task."""
        self._require_task(task_id)

        failed: list[str] = []

        for dependency in sorted(self._dependencies[task_id]):
            state = task_states.get(dependency)

            if state is None:
                continue

            if state.status.upper() in TERMINAL_FAILURE:
                failed.append(dependency)

        return failed

    def is_ready(
        self,
        task_id: str,
        task_states: dict[str, TaskState],
    ) -> bool:
        """Return True when every dependency has COMPLETED."""
        self._require_task(task_id)

        state = task_states.get(task_id)

        if state is None:
            return False

        if state.status.upper() != "QUEUED":
            return False

        return not self.unresolved_dependencies(
            task_id,
            task_states,
        )

    def ready_tasks(
        self,
        task_states: dict[str, TaskState],
    ) -> list[str]:
        """Return all currently runnable queued tasks."""
        return sorted(
            task_id
            for task_id in self._nodes
            if self.is_ready(task_id, task_states)
        )

    def waiting_tasks(
        self,
        task_states: dict[str, TaskState],
    ) -> list[str]:
        """Return queued tasks whose dependencies are incomplete."""
        return sorted(
            task_id
            for task_id in self._nodes
            if (
                task_states.get(task_id) is not None
                and task_states[task_id].status.upper() == "QUEUED"
                and not self.is_ready(task_id, task_states)
                and not self.failed_dependencies(task_id, task_states)
            )
        )

    def blocked_tasks(
        self,
        task_states: dict[str, TaskState],
    ) -> list[str]:
        """Return queued tasks whose dependencies have failed/blocked."""
        return sorted(
            task_id
            for task_id in self._nodes
            if (
                task_states.get(task_id) is not None
                and task_states[task_id].status.upper() == "QUEUED"
                and bool(self.failed_dependencies(task_id, task_states))
            )
        )

    # ------------------------------------------------------------------
    # Graph algorithms
    # ------------------------------------------------------------------

    def has_cycle(self) -> bool:
        """Return True if the dependency graph contains a cycle."""
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node: str) -> bool:
            if node in visiting:
                return True

            if node in visited:
                return False

            visiting.add(node)

            for dependency in self._dependencies[node]:
                if visit(dependency):
                    return True

            visiting.remove(node)
            visited.add(node)

            return False

        return any(
            visit(node)
            for node in self._nodes
            if node not in visited
        )

    def topological_order(self) -> list[str]:
        """Return a deterministic dependency-safe ordering.

        Raises:
            ValueError: if a cycle exists.
        """
        if self.has_cycle():
            raise ValueError(
                "Cannot produce topological order: dependency cycle detected."
            )

        indegree = {
            node: len(self._dependencies[node])
            for node in self._nodes
        }

        queue = deque(
            sorted(
                node
                for node, degree in indegree.items()
                if degree == 0
            )
        )

        result: list[str] = []

        while queue:
            node = queue.popleft()
            result.append(node)

            for dependent in sorted(self._dependents[node]):
                indegree[dependent] -= 1

                if indegree[dependent] == 0:
                    queue.append(dependent)

        if len(result) != len(self._nodes):
            raise ValueError(
                "Cannot produce topological order: dependency cycle detected."
            )

        return result

    def independent_tasks(self) -> list[str]:
        """Return tasks with no dependencies."""
        return sorted(
            task_id
            for task_id in self._nodes
            if not self._dependencies[task_id]
        )

    # ------------------------------------------------------------------
    # Internal validation
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_task_id(task_id: str) -> None:
        if not isinstance(task_id, str) or not task_id.strip():
            raise TypeError("task_id must be a non-empty string")

    def _require_task(self, task_id: str) -> None:
        self._validate_task_id(task_id)

        if task_id not in self._nodes:
            raise KeyError(f"Unknown task: {task_id}")
