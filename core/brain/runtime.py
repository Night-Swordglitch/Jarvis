"""Run Brain plans through ManagementManager and the dependency-aware Scheduler.

The runtime has one execution path: GoalPlanner creates a plan, the bridge
queues managed tasks, Scheduler dispatches registered specialists, and
TaskManager owns lifecycle state. Specialist action requests are returned as
data for the host's existing approval boundary; this module never executes
them.
"""

from __future__ import annotations

import asyncio
from copy import deepcopy
from typing import Any

from core.agents.result import AgentResult
from core.agents.task import AgentTask
from core.management.manager import ManagementManager
from core.scheduler import Scheduler


class BrainMissionRuntime:
    """Execute a planned mission using the existing managed-task runtime."""

    def __init__(self, master: Any, management: ManagementManager, scheduler: Scheduler):
        if not callable(getattr(master, "create_plan", None)):
            raise TypeError("master must provide create_plan().")
        if not callable(getattr(master, "queue_plan", None)):
            raise TypeError("master must provide queue_plan().")
        if not callable(getattr(master, "synthesize", None)):
            raise TypeError("master must provide synthesize().")
        if not isinstance(management, ManagementManager):
            raise TypeError("management must be a ManagementManager.")
        if not isinstance(scheduler, Scheduler):
            raise TypeError("scheduler must be a Scheduler.")

        self.master = master
        self.management = management
        self.scheduler = scheduler
        self.task_manager = scheduler.task_manager

    async def run(
        self,
        objective: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Plan, queue, and execute one mission without automatic retries."""
        objective = str(objective).strip()
        if not objective:
            raise ValueError("Mission objective cannot be empty.")
        if context is not None and not isinstance(context, dict):
            raise TypeError("context must be a dictionary.")
        base_context = deepcopy(context or {})

        # Plan before accepting the mission so a planning failure cannot leave
        # Management holding an active mission with no executable plan.
        plan = await asyncio.to_thread(
            self.master.create_plan,
            objective,
            base_context,
        )
        mission = self.management.accept_mission(
            objective,
            context=base_context,
        )

        try:
            task_ids = self.master.queue_plan(plan)
        except Exception as exc:
            self.management.fail_mission(
                f"Plan submission failed safely: {exc}"
            )
            raise

        results_by_task: dict[str, AgentResult] = {}

        async def run_specialist(task: Any) -> dict[str, Any]:
            if not task.agent_name:
                raise RuntimeError(
                    f"Managed task '{task.task_id}' has no specialist assignment."
                )

            dependency_results: dict[str, Any] = {}
            for dependency_id in task.dependencies:
                dependency = self.task_manager.get_task(dependency_id)
                if dependency is None or dependency.status != "COMPLETED":
                    raise RuntimeError(
                        f"Dependency '{dependency_id}' is not completed."
                    )
                dependency_results[dependency_id] = dict(dependency.result or {})

            task_context = deepcopy(base_context)
            task_context.update({
                "plan_id": plan.plan_id,
                "plan_step_id": task.metadata.get("brain_step_id"),
                "dependency_results": dependency_results,
            })
            agent_task = AgentTask(
                objective=task.objective,
                context=task_context,
                requested_by="management_scheduler",
                priority=task.priority,
            )
            result = await asyncio.to_thread(
                self.master.dispatcher.dispatch,
                task.agent_name,
                agent_task,
            )
            if not isinstance(result, AgentResult):
                raise TypeError("Specialist dispatcher returned an invalid result.")
            results_by_task[task.task_id] = result
            if not result.success:
                raise RuntimeError(
                    "; ".join(result.errors) or result.summary or "Specialist failed."
                )
            return result.to_dict()

        scheduler_snapshot = await self.scheduler.run(run_specialist)

        ordered_results: list[AgentResult] = []
        for step, task_id in zip(plan.steps, task_ids):
            result = results_by_task.get(task_id)
            if result is not None:
                ordered_results.append(result)
                continue
            task = self.task_manager.get_task(task_id)
            if task is not None and task.status in {"FAILED", "BLOCKED", "CANCELLED"}:
                reason = task.error or f"Managed task ended as {task.status}."
                ordered_results.append(AgentResult(
                    agent_name=step.agent_name,
                    task_id=task_id,
                    status="FAILED",
                    summary=reason,
                    errors=[reason],
                ))

        master_result = await asyncio.to_thread(
            self.master.synthesize,
            objective,
            base_context,
            ordered_results,
        )
        # Keep requested actions as data for the existing host-side approval
        # boundary. The scheduler and runtime do not execute those requests.
        master_result.actions_requested = [
            request
            for item in ordered_results
            for request in item.actions_requested
        ]

        mission_tasks = [self.task_manager.get_task(task_id) for task_id in task_ids]
        if mission_tasks and all(
            task is not None and task.status == "COMPLETED"
            for task in mission_tasks
        ):
            decision = self.management.complete_mission()
            review_decision = decision
        else:
            review_decision = self.management.evaluate()
            if any(
                task is not None and task.status in {"FAILED", "BLOCKED", "CANCELLED"}
                for task in mission_tasks
            ):
                decision = self.management.fail_mission(
                    review_decision.user_update
                    or "The mission could not complete all planned tasks."
                )
            else:
                decision = review_decision

        return {
            "mission_id": mission.mission_id,
            "mission_status": mission.status,
            "plan": plan.to_dict(),
            "task_ids": list(task_ids),
            "scheduler": scheduler_snapshot,
            "management_review": review_decision.to_dict(),
            "management_decision": decision.to_dict(),
            "master_result": master_result.to_dict(),
            "action_requests": list(master_result.actions_requested),
            "actions_executed": 0,
        }
