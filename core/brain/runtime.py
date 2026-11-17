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
from core.mission_monitor import MissionMonitor
from core.mission_replanner import ReplanningEngine


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
        """Plan and execute one mission; failures yield reviewable recovery proposals."""
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

        monitor = MissionMonitor(mission.mission_id)
        monitor.bind_event_bus(self.management.event_bus)
        for task_id in task_ids:
            monitor.track_task(task_id)

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

        try:
            scheduler_snapshot = await self.scheduler.run(
                run_specialist,
                task_ids=set(task_ids),
            )
            monitor_snapshot = monitor.snapshot()
        finally:
            monitor.unbind_event_bus()

        # A failure produces a persisted proposal only. It is not queued,
        # retried, or executed automatically. Completed work is supplied as
        # immutable context so the planner can focus on recovery gaps.
        replan_proposal: dict[str, Any] | None = None
        replan_error: str | None = None
        if not monitor_snapshot["healthy"]:
            completed_steps: list[dict[str, Any]] = []
            failed_steps: list[dict[str, Any]] = []
            blocked_steps: list[dict[str, Any]] = []
            for step, task_id in zip(plan.steps, task_ids):
                task = self.task_manager.get_task(task_id)
                if task is None:
                    continue
                record = {
                    "step_id": step.step_id,
                    "objective": step.objective,
                    "agent_name": step.agent_name,
                    "task_id": task_id,
                }
                if task.status == "COMPLETED":
                    record["result"] = dict(task.result or {})
                    completed_steps.append(record)
                elif task.status == "FAILED":
                    record["error"] = task.error
                    failed_steps.append(record)
                elif task.status in {"BLOCKED", "CANCELLED"}:
                    record["error"] = task.error
                    blocked_steps.append(record)

            generated: dict[str, Any] = {}

            def create_recovery_plan(
                recovery_objective: str,
                replanning_context: dict[str, Any],
            ) -> list[dict[str, Any]]:
                recovery_context = deepcopy(base_context)
                recovery_context["recovery_context"] = {
                    "mission_id": mission.mission_id,
                    "completed_steps": completed_steps,
                    "failed_steps": failed_steps,
                    "blocked_steps": blocked_steps,
                    "do_not_repeat_completed_work": True,
                    "avoid_repeating_failed_steps_verbatim": True,
                }
                recovery_context["replanning_context"] = replanning_context
                recovery_plan = self.master.create_plan(
                    recovery_objective,
                    recovery_context,
                )
                completed_objectives = {
                    item["objective"].strip().casefold()
                    for item in completed_steps
                }
                failed_objectives = {
                    item["objective"].strip().casefold()
                    for item in failed_steps
                }
                repeated = [
                    step.objective
                    for step in recovery_plan.steps
                    if step.objective.strip().casefold() in (
                        completed_objectives | failed_objectives
                    )
                ]
                if repeated:
                    raise ValueError(
                        "Recovery plan repeated completed or failed work: "
                        + ", ".join(repeated)
                    )
                generated["plan"] = recovery_plan
                return [
                    {
                        "objective": step.objective,
                        "priority": step.priority,
                        "agent_name": step.agent_name,
                        "dependencies": list(step.depends_on),
                    }
                    for step in recovery_plan.steps
                ]

            try:
                engine = ReplanningEngine(planner=create_recovery_plan)
                proposal = engine.propose(
                    mission_id=mission.mission_id,
                    objective=objective,
                    monitor_snapshot=monitor_snapshot,
                    current_plan=[
                        {
                            "step_id": step.step_id,
                            "objective": step.objective,
                            "agent_name": step.agent_name,
                        }
                        for step in plan.steps
                    ],
                )
                recovery_plan = generated.get("plan")
                if proposal is not None and recovery_plan is not None:
                    proposal.metadata["brain_plan_id"] = recovery_plan.plan_id
                    proposal.metadata["brain_plan_summary"] = recovery_plan.summary
                    proposal.metadata["preserved_completed_steps"] = [
                        item["step_id"] for item in completed_steps
                    ]
                    self.master.plan_store.save(recovery_plan)
                    replan_proposal = proposal.to_dict()
            except Exception as exc:
                replan_error = str(exc)

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
        tasks_completed = bool(mission_tasks) and all(
            task is not None and task.status == "COMPLETED"
            for task in mission_tasks
        )
        if tasks_completed and master_result.success:
            decision = self.management.complete_mission()
            review_decision = decision
        else:
            review_decision = self.management.evaluate()
            task_failure = any(
                task is not None and task.status in {"FAILED", "BLOCKED", "CANCELLED"}
                for task in mission_tasks
            )
            if task_failure or not master_result.success:
                failure_reason = (
                    review_decision.user_update
                    or master_result.summary
                    or "The mission could not produce a verified synthesis."
                )
                decision = self.management.fail_mission(failure_reason)
            else:
                decision = review_decision

        return {
            "mission_id": mission.mission_id,
            "mission_status": mission.status,
            "plan": plan.to_dict(),
            "task_ids": list(task_ids),
            "scheduler": scheduler_snapshot,
            "monitor": monitor_snapshot,
            "replan_proposal": replan_proposal,
            "replan_error": replan_error,
            "management_review": review_decision.to_dict(),
            "management_decision": decision.to_dict(),
            "master_result": master_result.to_dict(),
            "master_result_object": master_result,
            "action_requests": list(master_result.actions_requested),
            "actions_executed": 0,
        }
