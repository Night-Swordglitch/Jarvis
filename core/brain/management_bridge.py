"""Connect validated Brain plans to the existing mission/task lifecycle.

The bridge queues work only. ManagementManager and TaskManager remain the
single owners of mission coordination, task dependencies, and task status.
It never dispatches agents or executes requested actions.
"""

from __future__ import annotations

from typing import Any

from core.brain.models import MissionPlan
from core.brain.store import PlanStore
from core.events.events import Event
from core.management.manager import ManagementManager


class BrainManagementBridge:
    """Queue a Brain plan through ManagementManager and mirror task events."""

    _EVENT_STATUS = {
        "TASK_STARTED": "RUNNING",
        "TASK_COMPLETED": "COMPLETED",
        "TASK_FAILED": "FAILED",
        "TASK_BLOCKED": "BLOCKED",
        "TASK_CANCELLED": "BLOCKED",
    }

    def __init__(
        self,
        management: ManagementManager,
        store: PlanStore | None = None,
    ) -> None:
        if not isinstance(management, ManagementManager):
            raise TypeError("management must be a ManagementManager.")
        if store is not None and not isinstance(store, PlanStore):
            raise TypeError("store must be a PlanStore or None.")

        self.management = management
        self.store = store
        self._plans: dict[str, MissionPlan] = {}
        self._task_to_step: dict[str, tuple[str, str]] = {}

        for event_type in self._EVENT_STATUS:
            self.management.event_bus.subscribe(event_type, self._on_task_event)

    def submit(self, plan: MissionPlan) -> list[str]:
        """Queue every plan step as a managed task; do not execute it."""
        if not isinstance(plan, MissionPlan):
            raise TypeError("plan must be a MissionPlan.")
        if plan.status != "READY" or any(
            step.status != "PENDING" for step in plan.steps
        ):
            raise ValueError("Only a fresh READY plan can be submitted.")

        mission = self.management.mission
        if mission is None or not self.management.running:
            raise RuntimeError("An active ManagementManager mission is required.")
        if mission.objective != plan.objective:
            raise ValueError("Plan objective must match the active mission objective.")

        specs = [
            {
                "id": step.step_id,
                "objective": step.objective,
                "priority": step.priority,
                "agent_name": step.agent_name,
                "dependencies": list(step.depends_on),
            }
            for step in plan.steps
        ]

        # ManagementManager translates step aliases into TaskManager task IDs
        # and installs the dependency gates before tasks can be started.
        task_ids = self.management.create_planned_tasks(specs)
        if len(task_ids) != len(plan.steps):
            raise RuntimeError("ManagementManager did not create every planned task.")

        self._plans[plan.plan_id] = plan
        for step, task_id in zip(plan.steps, task_ids):
            task = self.management.task_manager.get_task(task_id)
            if task is None:
                raise RuntimeError(f"Managed task '{task_id}' could not be retrieved.")
            task.metadata.update({
                "brain_plan_id": plan.plan_id,
                "brain_step_id": step.step_id,
            })
            self._task_to_step[task_id] = (plan.plan_id, step.step_id)

        plan.status = "RUNNING"
        if self.store is not None:
            self.store.save(plan)
        return task_ids

    def _on_task_event(self, event: Event) -> None:
        task_id = event.payload.get("task_id")
        if not isinstance(task_id, str):
            return

        link = self._task_to_step.get(task_id)
        if link is None:
            return

        plan_id, step_id = link
        plan = self._plans.get(plan_id)
        if plan is None:
            return

        step = next(
            (item for item in plan.steps if item.step_id == step_id),
            None,
        )
        if step is None:
            return

        step.status = self._EVENT_STATUS[event.event_type]
        task = self.management.task_manager.get_task(task_id)
        if task is not None:
            if task.result is not None:
                step.result = dict(task.result)
            if task.error:
                step.error = task.error

        statuses = [item.status for item in plan.steps]
        if all(status == "COMPLETED" for status in statuses):
            plan.status = "COMPLETED"
        elif any(status in {"FAILED", "BLOCKED"} for status in statuses):
            plan.status = (
                "PARTIAL"
                if any(status == "COMPLETED" for status in statuses)
                else "FAILED"
            )
        else:
            plan.status = "RUNNING"

        if self.store is not None:
            self.store.save(plan)

    def close(self) -> None:
        """Unsubscribe this bridge from task lifecycle events."""
        for event_type in self._EVENT_STATUS:
            self.management.event_bus.unsubscribe(event_type, self._on_task_event)
