"""Read-only operations dashboard state projection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.dependency_graph import DependencyGraph
from core.management.evidence import EvidenceStore
from core.management.state import ManagementState
from core.scheduler import Scheduler


@dataclass(frozen=True)
class DashboardSnapshot:
    """Immutable dashboard view of current management state."""

    mission: dict[str, Any]
    decision: dict[str, Any]
    tasks: dict[str, list[dict[str, Any]]]
    agents: dict[str, dict[str, Any]]
    dependencies: dict[str, dict[str, list[str]]]
    evidence: dict[str, Any]
    scheduler: dict[str, Any]
    approvals: list[dict[str, Any]]
    questions: list[str]
    next_actions: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe dashboard snapshot."""
        return {
            "mission": dict(self.mission),
            "decision": dict(self.decision),
            "tasks": {
                key: [dict(item) for item in value]
                for key, value in self.tasks.items()
            },
            "agents": {
                key: dict(value)
                for key, value in self.agents.items()
            },
            "dependencies": {
                key: {
                    "dependencies": list(value.get("dependencies", [])),
                    "dependents": list(value.get("dependents", [])),
                }
                for key, value in self.dependencies.items()
            },
            "evidence": dict(self.evidence),
            "scheduler": dict(self.scheduler),
            "approvals": list(self.approvals),
            "questions": list(self.questions),
            "next_actions": list(self.next_actions),
        }


class DashboardProjector:
    """Project real MARK-L management state into a read-only dashboard view."""

    def __init__(
        self,
        state: ManagementState,
        dependency_graph: DependencyGraph,
        evidence_store: EvidenceStore | None = None,
        scheduler: Scheduler | None = None,
    ) -> None:
        if not isinstance(state, ManagementState):
            raise TypeError("state must be ManagementState")

        if not isinstance(dependency_graph, DependencyGraph):
            raise TypeError("dependency_graph must be DependencyGraph")

        if evidence_store is not None and not isinstance(
            evidence_store, EvidenceStore
        ):
            raise TypeError("evidence_store must be EvidenceStore or None")

        if scheduler is not None and not isinstance(scheduler, Scheduler):
            raise TypeError("scheduler must be Scheduler or None")

        self.state = state
        self.dependency_graph = dependency_graph
        self.evidence_store = evidence_store
        self.scheduler = scheduler

    def snapshot(self) -> DashboardSnapshot:
        """Build a read-only snapshot from current system state."""
        task_groups = {
            "queued": self.state.queued_tasks,
            "active": self.state.active_tasks,
            "completed": self.state.completed_tasks,
            "failed": self.state.failed_tasks,
            "blocked": self.state.blocked_tasks,
        }

        tasks: dict[str, list[dict[str, Any]]] = {}

        for group_name, group in task_groups.items():
            tasks[group_name] = [
                self._task_to_dict(task)
                for task in group.values()
            ]

        agents: dict[str, dict[str, Any]] = {}

        for group in task_groups.values():
            for task in group.values():
                if task.agent_name:
                    entry = agents.setdefault(
                        task.agent_name,
                        {
                            "name": task.agent_name,
                            "queued": 0,
                            "active": 0,
                            "completed": 0,
                            "failed": 0,
                            "blocked": 0,
                            "task_ids": [],
                        },
                    )

                    status_group = {
                        "QUEUED": "queued",
                        "RUNNING": "active",
                        "COMPLETED": "completed",
                        "FAILED": "failed",
                        "BLOCKED": "blocked",
                    }.get(task.status)

                    if status_group:
                        entry[status_group] += 1

                    entry["task_ids"].append(task.task_id)

        dependencies: dict[str, dict[str, list[str]]] = {}

        for task_id in self.dependency_graph.tasks():
            dependencies[task_id] = {
                "dependencies": list(
                    self.dependency_graph.dependencies_of(task_id)
                ),
                "dependents": list(
                    self.dependency_graph.dependents_of(task_id)
                ),
            }

        evidence = self._evidence_summary()

        scheduler_state = (
            self.scheduler.snapshot()
            if self.scheduler is not None
            else {}
        )

        return DashboardSnapshot(
            mission={
                "mission_id": self.state.mission_id,
                "objective": self.state.objective,
                "status": self.state.status,
                "metadata": dict(self.state.metadata),
            },
            decision={
                "current_plan": self._copy_plan(self.state.current_plan),
                "recent_events": list(self.state.recent_events),
            },
            tasks=tasks,
            agents=agents,
            dependencies=dependencies,
            evidence=evidence,
            scheduler=dict(scheduler_state),
            approvals=list(self.state.pending_approvals),
            questions=list(self.state.open_questions),
            next_actions=list(self.state.next_actions),
        )

    @staticmethod
    def _copy_plan(plan: Any) -> Any:
        """Return a JSON-safe copy of the current management plan."""
        if isinstance(plan, dict):
            return {
                key: (
                    dict(value)
                    if isinstance(value, dict)
                    else list(value)
                    if isinstance(value, list)
                    else value
                )
                for key, value in plan.items()
            }

        if isinstance(plan, list):
            return [
                dict(item) if isinstance(item, dict) else item
                for item in plan
            ]

        return plan

    @staticmethod
    def _task_to_dict(task: Any) -> dict[str, Any]:
        return {
            "task_id": task.task_id,
            "objective": task.objective,
            "status": task.status,
            "priority": task.priority,
            "agent_name": task.agent_name,
            "dependencies": list(task.dependencies),
            "result": dict(task.result or {}),
            "error": task.error,
            "metadata": dict(task.metadata),
        }

    def _evidence_summary(self) -> dict[str, Any]:
        if self.evidence_store is None:
            return {
                "available": False,
                "count": 0,
                "records": [],
            }

        records = self.evidence_store.all()

        return {
            "available": True,
            "count": len(records),
            "records": [
                record.to_dict()
                for record in records
            ],
        }


