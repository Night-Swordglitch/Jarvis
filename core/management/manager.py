from __future__ import annotations

import json
import re
from typing import Any, Callable

from core.dependency_graph import DependencyGraph
from core.events.bus import EventBus
from core.events.events import Event
from core.management.decision import ManagementDecision, DecisionType
from core.management.mission import Mission
from core.management.state import ManagementState
from core.task_manager import TaskManager


class ManagementManager:
    """
    Top-level operational manager for MARK-L.

    Responsibilities:
    - accept missions
    - maintain management state
    - create and coordinate tasks
    - maintain dependency relationships
    - inspect task/event results
    - decide whether to continue, replan, clarify, wait,
      request approval, block, or complete

    The Management Manager does NOT:
    - execute arbitrary actions
    - bypass PermissionManager
    - resolve human confirmations
    - directly modify files
    - directly invoke specialist agents
    - invent task dependencies
    """

    VALID_DECISIONS = {
        "CONTINUE",
        "REPLAN",
        "CLARIFY",
        "WAIT",
        "APPROVAL",
        "BLOCKED",
        "COMPLETE",
    }

    def __init__(
        self,
        state: ManagementState,
        event_bus: EventBus,
        task_manager: TaskManager,
        dependency_graph: DependencyGraph,
        *,
        planner: Callable[[str], str] | None = None,
    ):
        if not isinstance(state, ManagementState):
            raise TypeError("state must be ManagementState")

        if not isinstance(event_bus, EventBus):
            raise TypeError("event_bus must be EventBus")

        self.state = state
        self.event_bus = event_bus
        self.task_manager = task_manager
        self.dependency_graph = dependency_graph
        self._planner = planner

        self._mission: Mission | None = None
        self._running = False

        self.event_bus.subscribe("*", self._on_event)

    # ------------------------------------------------------------------
    # Mission lifecycle
    # ------------------------------------------------------------------

    def accept_mission(
        self,
        objective: str,
        *,
        context: dict[str, Any] | None = None,
    ) -> Mission:
        objective = str(objective).strip()

        if not objective:
            raise ValueError("Mission objective cannot be empty")

        if self._mission is not None and self._mission.status not in {
            "COMPLETED",
            "FAILED",
            "CANCELLED",
        }:
            raise RuntimeError("A mission is already active")

        self._mission = Mission(
            objective=objective,
            context=context or {},
        )

        self.state.mission_id = self._mission.mission_id
        self.state.objective = objective
        self.state.status = "PLANNING"
        self.state.current_plan = []
        self.state.open_questions = []
        self.state.pending_approvals = []
        self.state.next_actions = []

        self._running = True

        self._publish(
            "MISSION_ACCEPTED",
            {
                "mission_id": self._mission.mission_id,
                "objective": objective,
            },
        )

        return self._mission

    # ------------------------------------------------------------------
    # Planning
    # ------------------------------------------------------------------

    def create_plan(
        self,
        *,
        planner_output: str | None = None,
    ) -> list[dict[str, Any]]:
        if self._mission is None:
            raise RuntimeError("No active mission")

        objective = self._mission.objective

        if planner_output is None and self._planner is not None:
            planner_output = self._planner(objective)

        if planner_output:
            plan = self._parse_plan(planner_output)
        else:
            plan = [
                {
                    "objective": objective,
                    "priority": 50,
                    "agent_name": None,
                    "dependencies": [],
                }
            ]

        if not plan:
            raise RuntimeError("Planner produced no usable tasks")

        self.state.current_plan = plan
        self.state.status = "RUNNING"

        self._publish(
            "PLAN_CREATED",
            {
                "mission_id": self._mission.mission_id,
                "task_count": len(plan),
            },
        )

        return plan

    def create_planned_tasks(
        self,
        plan: list[dict[str, Any]] | None = None,
    ) -> list[str]:
        if plan is None:
            plan = self.state.current_plan

        created: list[str] = []
        aliases: dict[str, str] = {}
        normalized_items: list[tuple[str, dict[str, Any]]] = []

        # Validate every alias and dependency before creating any tasks.
        for index, item in enumerate(plan):
            objective = str(item.get("objective", "")).strip()
            if not objective:
                continue

            alias = str(
                item.get("id")
                or item.get("name")
                or f"task_{index + 1}"
            ).strip()
            if not alias:
                raise ValueError("Every planned task must have a non-empty alias.")
            if alias in aliases:
                raise ValueError(f"Duplicate planned task alias: {alias}")

            aliases[alias] = ""
            normalized_items.append((alias, item))

        for alias, item in normalized_items:
            dependencies = item.get("dependencies", []) or []
            if not isinstance(dependencies, list):
                raise TypeError(f"Dependencies for task '{alias}' must be a list.")
            unknown = [
                str(dep).strip()
                for dep in dependencies
                if str(dep).strip() not in aliases
            ]
            if unknown:
                raise ValueError(
                    f"Task '{alias}' references unknown dependencies: {unknown}"
                )
            if alias in [str(dep).strip() for dep in dependencies]:
                raise ValueError(f"Task '{alias}' cannot depend on itself.")

        # Create all tasks first so every dependency ID can be resolved.
        for alias, item in normalized_items:
            task = self.task_manager.create_task(
                objective=str(item["objective"]).strip(),
                priority=self._priority(item.get("priority", 50)),
                agent_name=item.get("agent_name"),
                metadata={
                    "management_manager": True,
                    "plan_alias": alias,
                    "mission_id": (
                        self._mission.mission_id
                        if self._mission is not None
                        else self.state.mission_id
                    ),
                },
            )
            self.dependency_graph.add_task(task.task_id)
            aliases[alias] = task.task_id
            created.append(task.task_id)

        # Keep TaskManager's execution gate and DependencyGraph in sync.
        # TaskManager checks TaskState.dependencies when starting a task.
        for alias, item in normalized_items:
            task_id = aliases[alias]
            dependency_ids = [
                aliases[str(dep).strip()]
                for dep in (item.get("dependencies", []) or [])
            ]
            task = self.task_manager.get_task(task_id)
            if task is None:
                raise RuntimeError(f"Created task '{task_id}' could not be retrieved.")

            task.dependencies = list(dependency_ids)
            for dependency_id in dependency_ids:
                self.dependency_graph.add_dependency(task_id, dependency_id)

            if dependency_ids:
                self._publish(
                    "TASK_DEPENDENCIES_LINKED",
                    {
                        "mission_id": self._mission.mission_id
                        if self._mission
                        else self.state.mission_id,
                        "task_id": task_id,
                        "dependencies": list(dependency_ids),
                    },
                )

        self.state.next_actions = list(created)

        self._publish(
            "PLAN_TASKS_CREATED",
            {
                "mission_id": self._mission.mission_id
                if self._mission
                else self.state.mission_id,
                "task_ids": created,
            },
        )

        return created

    # ------------------------------------------------------------------
    # Management decisions
    # ------------------------------------------------------------------

    def evaluate(self) -> ManagementDecision:
        """
        Deterministic high-level evaluation.

        The manager may later use an LLM for richer planning, but
        fundamental lifecycle decisions remain deterministic.
        """

        if self._mission is None:
            return self._decision(
                "BLOCKED",
                user_update="No active mission is available.",
            )

        if self.state.open_questions:
            return self._decision(
                "CLARIFY",
                clarification_question=self.state.open_questions[0],
                user_update="I need clarification before continuing.",
            )

        if self.state.pending_approvals:
            return self._decision(
                "APPROVAL",
                user_update="A human approval is required before continuing.",
            )

        mission_id = self._mission.mission_id

        def mission_tasks(group: dict[str, Any]) -> list[Any]:
            return [
                task for task in group.values()
                if task.metadata.get("mission_id") == mission_id
            ]

        failed = mission_tasks(self.state.failed_tasks)
        if failed:
            return self._decision(
                "REPLAN",
                user_update="A task failed. I am evaluating a revised plan.",
                metadata={
                    "failed_tasks": [task.task_id for task in failed]
                },
            )

        active = mission_tasks(self.state.active_tasks)
        queued = mission_tasks(self.state.queued_tasks)
        blocked = mission_tasks(self.state.blocked_tasks)

        if active or queued:
            return self._decision(
                "CONTINUE",
                user_update="The mission is progressing.",
            )

        if blocked:
            return self._decision(
                "BLOCKED",
                user_update="The mission is blocked by unresolved tasks.",
            )

        completed = list(self.state.completed_tasks)

        if completed:
            return self._decision(
                "COMPLETE",
                user_update="The mission has completed its planned work.",
            )

        return self._decision(
            "WAIT",
            user_update="The mission is waiting for the next event.",
        )

    # ------------------------------------------------------------------
    # Event monitoring
    # ------------------------------------------------------------------

    def _on_event(self, event: Event) -> None:
        if not self._running:
            return

        if event.event_type in {
            "TASK_COMPLETED",
            "TASK_FAILED",
            "TASK_BLOCKED",
            "TASK_CANCELLED",
        }:
            self._synchronize_state()

            self._publish(
                "MANAGEMENT_REVIEW_REQUIRED",
                {
                    "trigger_event": event.event_type,
                    "task_id": event.payload.get("task_id"),
                },
            )

    def _synchronize_state(self) -> None:
        """
        Reconcile management state with TaskManager.

        TaskManager remains the authoritative lifecycle owner.

        The task buckets are shared state structures and must remain
        dictionaries keyed by task ID. Converting them to lists would
        break TaskManager lifecycle operations.
        """

        groups = {
            "queued_tasks": dict(self.task_manager.state.queued_tasks),
            "active_tasks": dict(self.task_manager.state.active_tasks),
            "completed_tasks": dict(self.task_manager.state.completed_tasks),
            "failed_tasks": dict(self.task_manager.state.failed_tasks),
            "blocked_tasks": dict(self.task_manager.state.blocked_tasks),
        }

        for key, value in groups.items():
            setattr(self.state, key, value)
    def request_clarification(self, question: str) -> ManagementDecision:
        question = str(question).strip()

        if not question:
            raise ValueError("Clarification question cannot be empty")

        if question not in self.state.open_questions:
            self.state.open_questions.append(question)

        return self._decision(
            "CLARIFY",
            clarification_question=question,
            user_update=question,
        )

    def request_approval(self, reason: str) -> ManagementDecision:
        reason = str(reason).strip()

        if not reason:
            raise ValueError("Approval reason cannot be empty")

        if reason not in self.state.pending_approvals:
            self.state.pending_approvals.append(reason)

        return self._decision(
            "APPROVAL",
            user_update="Human approval is required.",
            metadata={"reason": reason},
        )

    def clear_clarification(self, question: str | None = None) -> None:
        if question is None:
            self.state.open_questions.clear()
            return

        self.state.open_questions = [
            item
            for item in self.state.open_questions
            if item != question
        ]

    def clear_approval(self, reason: str | None = None) -> None:
        if reason is None:
            self.state.pending_approvals.clear()
            return

        self.state.pending_approvals = [
            item
            for item in self.state.pending_approvals
            if item != reason
        ]

    # ------------------------------------------------------------------
    # Mission completion
    # ------------------------------------------------------------------

    def complete_mission(self) -> ManagementDecision:
        if self._mission is None:
            return self._decision(
                "BLOCKED",
                user_update="Cannot complete a mission that does not exist.",
            )

        self._mission.update_status("COMPLETED")
        self.state.status = "COMPLETED"
        self._running = False

        self._publish(
            "MISSION_COMPLETED",
            {
                "mission_id": self._mission.mission_id,
            },
        )

        return self._decision(
            "COMPLETE",
            user_update="Mission completed.",
        )

    def fail_mission(self, reason: str) -> ManagementDecision:
        """Mark the active mission failed without retrying or executing work."""
        reason = str(reason).strip()
        if not reason:
            raise ValueError("Failure reason cannot be empty.")
        if self._mission is None:
            return self._decision(
                "BLOCKED",
                user_update="Cannot fail a mission that does not exist.",
            )

        self._mission.update_status("FAILED")
        self.state.status = "FAILED"
        self._running = False
        self._publish(
            "MISSION_FAILED",
            {
                "mission_id": self._mission.mission_id,
                "reason": reason,
            },
        )
        return self._decision(
            "BLOCKED",
            user_update=reason,
            metadata={"mission_id": self._mission.mission_id},
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _decision(
        self,
        decision_type: str,
        *,
        clarification_question: str | None = None,
        user_update: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ManagementDecision:
        decision_type = decision_type.upper().strip()

        if decision_type not in self.VALID_DECISIONS:
            raise ValueError(
                f"Invalid management decision: {decision_type}"
            )

        return ManagementDecision(
            decision=DecisionType(decision_type),
            clarification_question=clarification_question,
            user_update=user_update,
            metadata=metadata or {},
        )

    def _publish(
        self,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        self.event_bus.publish(
            Event(
                event_type=event_type,
                payload=payload,
            )
        )

    @staticmethod
    def _priority(value: Any) -> int:
        try:
            value = int(value)
        except (TypeError, ValueError):
            value = 50

        return max(0, min(100, value))

    @staticmethod
    def _parse_plan(raw: str) -> list[dict[str, Any]]:
        """
        Parse planner JSON conservatively.

        Accepted formats:
        {"tasks": [...]}
        [...]
        """

        text = str(raw).strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}|\[.*\]", text, re.DOTALL)

            if not match:
                return []

            try:
                data = json.loads(match.group(0))
            except json.JSONDecodeError:
                return []

        if isinstance(data, dict):
            tasks = data.get("tasks", [])
        elif isinstance(data, list):
            tasks = data
        else:
            return []

        if not isinstance(tasks, list):
            return []

        cleaned: list[dict[str, Any]] = []

        for item in tasks:
            if not isinstance(item, dict):
                continue

            objective = str(item.get("objective", "")).strip()

            if not objective:
                continue

            dependencies = item.get("dependencies", [])

            if not isinstance(dependencies, list):
                dependencies = []

            cleaned.append(
                {
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "objective": objective,
                    "priority": item.get("priority", 50),
                    "agent_name": item.get("agent_name"),
                    "dependencies": dependencies,
                }
            )

        return cleaned

    @property
    def mission(self) -> Mission | None:
        return self._mission

    @property
    def running(self) -> bool:
        return self._running




