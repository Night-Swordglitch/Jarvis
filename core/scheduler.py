"""Concurrent dependency-aware scheduler for MARK-L.

The scheduler coordinates execution of already-created management tasks.

It does not:
- create missions
- invent dependencies
- bypass the dependency graph
- make LLM decisions
- execute arbitrary actions

The DependencyGraph determines what may run.
The Scheduler determines when and where it runs.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from core.dependency_graph import DependencyGraph
from core.management.state import TaskState
from core.task_manager import TaskManager


TaskRunner = Callable[[TaskState], Awaitable[Any] | Any]


class Scheduler:
    """Concurrent dependency-aware task scheduler."""

    def __init__(
        self,
        task_manager: TaskManager,
        dependency_graph: DependencyGraph,
        *,
        max_workers: int = 3,
    ) -> None:
        if not isinstance(task_manager, TaskManager):
            raise TypeError("task_manager must be a TaskManager")

        if not isinstance(dependency_graph, DependencyGraph):
            raise TypeError("dependency_graph must be a DependencyGraph")

        if not isinstance(max_workers, int) or max_workers < 1:
            raise ValueError("max_workers must be at least 1")

        self.task_manager = task_manager
        self.dependency_graph = dependency_graph
        self.max_workers = max_workers

        self._cancel_requested = False
        self._running: dict[str, asyncio.Task[Any]] = {}

    # ------------------------------------------------------------------
    # Public state
    # ------------------------------------------------------------------

    @property
    def running_task_ids(self) -> list[str]:
        return sorted(self._running)

    @property
    def running_count(self) -> int:
        return len(self._running)

    @property
    def cancelled(self) -> bool:
        return self._cancel_requested

    # ------------------------------------------------------------------
    # Scheduling
    # ------------------------------------------------------------------

    def ready_tasks(self, task_ids: set[str] | None = None) -> list[str]:
        """Return eligible tasks, optionally restricted to one mission scope."""
        states = self._task_states()
        ready = self.dependency_graph.ready_tasks(states)
        return self._in_scope(ready, task_ids)

    def waiting_tasks(self, task_ids: set[str] | None = None) -> list[str]:
        """Return queued tasks waiting on dependencies."""
        states = self._task_states()
        waiting = self.dependency_graph.waiting_tasks(states)
        return self._in_scope(waiting, task_ids)

    def blocked_tasks(self, task_ids: set[str] | None = None) -> list[str]:
        """Return queued tasks whose dependencies failed."""
        states = self._task_states()
        blocked = self.dependency_graph.blocked_tasks(states)
        return self._in_scope(blocked, task_ids)

    async def run(
        self,
        runner: TaskRunner,
        *,
        task_ids: set[str] | list[str] | tuple[str, ...] | None = None,
    ) -> dict[str, Any]:
        """Run all schedulable tasks until the queue is exhausted.

        Tasks are launched concurrently up to max_workers.

        The runner receives a TaskState and may return either:
        - an ordinary value
        - an awaitable

        A successful runner result completes the task.
        An exception fails the task.

        Dependency failures cause dependent queued tasks to be blocked.
        """
        if not callable(runner):
            raise TypeError("runner must be callable")
        scope = self._normalize_scope(task_ids)

        self._cancel_requested = False

        while True:
            self._block_failed_dependents(scope)

            if self._cancel_requested:
                self._cancel_queued_tasks(scope)

            self._launch_available(runner, scope)

            if not self._running:
                if not self.ready_tasks(scope):
                    break

            if self._running:
                await self._wait_for_progress()
                continue

            # Nothing in this scope is running or ready.
            break

        self._block_failed_dependents(scope)

        return self.snapshot(scope)

    def cancel(self) -> None:
        """Request scheduler cancellation.

        Running tasks are allowed to finish.
        Queued tasks are cancelled by the scheduler loop.
        """
        self._cancel_requested = True

    async def shutdown(self) -> None:
        """Cancel currently running asyncio workers."""
        if not self._running:
            return

        tasks = list(self._running.values())

        for task in tasks:
            task.cancel()

        await asyncio.gather(
            *tasks,
            return_exceptions=True,
        )

        self._running.clear()

    # ------------------------------------------------------------------
    # Worker management
    # ------------------------------------------------------------------

    def _launch_available(
        self,
        runner: TaskRunner,
        task_ids: set[str] | None = None,
    ) -> None:
        if self._cancel_requested:
            return

        capacity = self.max_workers - len(self._running)

        if capacity <= 0:
            return

        for task_id in self.ready_tasks(task_ids):
            if capacity <= 0:
                break

            if task_id in self._running:
                continue

            task = self.task_manager.get_task(task_id)

            if task is None:
                continue

            # The TaskManager remains the lifecycle authority.
            started = self.task_manager.start_task(task_id)

            if started is None:
                continue

            worker = asyncio.create_task(
                self._execute_task(
                    task_id,
                    runner,
                ),
                name=f"markl-task-{task_id}",
            )

            self._running[task_id] = worker
            capacity -= 1

    async def _execute_task(
        self,
        task_id: str,
        runner: TaskRunner,
    ) -> None:
        try:
            task = self.task_manager.get_task(task_id)

            if task is None:
                return

            result = runner(task)

            if asyncio.iscoroutine(result) or isinstance(
                result,
                Awaitable,
            ):
                result = await result

            self.task_manager.complete_task(
                task_id,
                result=result,
            )

        except asyncio.CancelledError:
            # A cancelled worker must not remain RUNNING in durable state.
            # TaskManager owns the transition and emits the lifecycle event.
            task = self.task_manager.get_task(task_id)
            if task is not None and task.status in {"RUNNING", "QUEUED", "BLOCKED"}:
                self.task_manager.cancel_task(task_id)
            raise

        except Exception as exc:
            self.task_manager.fail_task(
                task_id,
                error=str(exc),
            )

        finally:
            self._running.pop(task_id, None)

    async def _wait_for_progress(self) -> None:
        if not self._running:
            await asyncio.sleep(0)
            return

        running = list(self._running.values())

        done, _ = await asyncio.wait(
            running,
            return_when=asyncio.FIRST_COMPLETED,
        )

        # Consume exceptions from completed workers.
        for task in done:
            try:
                task.result()
            except asyncio.CancelledError:
                pass
            except Exception:
                # _execute_task already records ordinary worker failures.
                pass

    # ------------------------------------------------------------------
    # Dependency propagation
    # ------------------------------------------------------------------

    def _block_failed_dependents(
        self,
        task_ids: set[str] | None = None,
    ) -> None:
        states = self._task_states()

        for task_id in self._in_scope(
            self.dependency_graph.blocked_tasks(states),
            task_ids,
        ):
            failed = self.dependency_graph.failed_dependencies(
                task_id,
                states,
            )

            if not failed:
                continue

            reason = (
                "Blocked by failed dependency: "
                + ", ".join(failed)
            )

            self.task_manager.block_task(
                task_id,
                reason=reason,
            )

    def _cancel_queued_tasks(
        self,
        task_ids: set[str] | None = None,
    ) -> None:
        states = self._task_states()

        for task_id, task in states.items():
            if task.status.upper() == "QUEUED" and (
                task_ids is None or task_id in task_ids
            ):
                self.task_manager.cancel_task(task_id)

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------

    def _task_states(self) -> dict[str, TaskState]:
        states: dict[str, TaskState] = {}

        for task_id in self.dependency_graph.tasks():
            task = self.task_manager.get_task(task_id)

            if task is not None:
                states[task_id] = task

        return states

    def snapshot(
        self,
        task_ids: set[str] | None = None,
    ) -> dict[str, Any]:
        states = self._task_states()
        scoped_states = {
            task_id: task
            for task_id, task in states.items()
            if task_ids is None or task_id in task_ids
        }

        return {
            "max_workers": self.max_workers,
            "running": self._in_scope(sorted(self._running), task_ids),
            "ready": self._in_scope(
                self.dependency_graph.ready_tasks(states), task_ids
            ),
            "waiting": self._in_scope(
                self.dependency_graph.waiting_tasks(states), task_ids
            ),
            "blocked": sorted(
                task_id
                for task_id, task in scoped_states.items()
                if task.status.upper() == "BLOCKED"
            ),
            "cancelled": self._cancel_requested,
            "task_states": {
                task_id: task.status
                for task_id, task in sorted(scoped_states.items())
            },
        }

    def _normalize_scope(
        self,
        task_ids: set[str] | list[str] | tuple[str, ...] | None,
    ) -> set[str] | None:
        if task_ids is None:
            return None
        if not isinstance(task_ids, (set, list, tuple)):
            raise TypeError("task_ids must be a set, list, tuple, or None.")
        scope = set(task_ids)
        if any(not isinstance(task_id, str) or not task_id.strip() for task_id in scope):
            raise ValueError("task_ids must contain non-empty strings.")
        unknown = scope - set(self.dependency_graph.tasks())
        if unknown:
            raise KeyError("Unknown scheduler task IDs: " + ", ".join(sorted(unknown)))
        return scope

    @staticmethod
    def _in_scope(
        values: list[str],
        task_ids: set[str] | None,
    ) -> list[str]:
        if task_ids is None:
            return values
        return [value for value in values if value in task_ids]
