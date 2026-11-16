"""Phase 7H — Autonomous mission replanning proposal engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable
import json


@dataclass
class ReplanProposal:
    """A proposed revised mission plan.

    This object contains intent only. It has no execution authority.
    """

    mission_id: str
    reason: str
    failed_task_ids: list[str] = field(default_factory=list)
    plan: list[dict[str, Any]] = field(default_factory=list)
    source: str = "REPLANNING_ENGINE"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.mission_id, str) or not self.mission_id.strip():
            raise ValueError("mission_id must be a non-empty string.")

        if not isinstance(self.reason, str):
            raise TypeError("reason must be a string.")

        if not isinstance(self.failed_task_ids, list):
            raise TypeError("failed_task_ids must be a list.")

        if not isinstance(self.plan, list):
            raise TypeError("plan must be a list.")

        if not isinstance(self.metadata, dict):
            raise TypeError("metadata must be a dictionary.")

        self.mission_id = self.mission_id.strip()

        self.failed_task_ids = [
            str(task_id)
            for task_id in self.failed_task_ids
            if str(task_id).strip()
        ]

        cleaned_plan: list[dict[str, Any]] = []

        for item in self.plan:
            if not isinstance(item, dict):
                raise TypeError("Each plan item must be a dictionary.")

            objective = item.get("objective")

            if not isinstance(objective, str) or not objective.strip():
                raise ValueError(
                    "Every replanned task must have a non-empty objective."
                )

            cleaned_plan.append(
                {
                    "objective": objective.strip(),
                    "priority": int(item.get("priority", 50)),
                    "agent_name": item.get("agent_name"),
                    "dependencies": list(item.get("dependencies", [])),
                }
            )

        self.plan = cleaned_plan

    @property
    def ready(self) -> bool:
        """Whether the proposal contains an actionable plan."""
        return bool(self.plan)

    def to_planner_output(self) -> str:
        """Convert the structured proposal into ManagementManager planner input."""
        return json.dumps(self.plan)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the proposal."""
        return {
            "mission_id": self.mission_id,
            "reason": self.reason,
            "failed_task_ids": list(self.failed_task_ids),
            "plan": [dict(item) for item in self.plan],
            "source": self.source,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReplanProposal":
        """Restore a proposal from serialized data."""
        if not isinstance(data, dict):
            raise TypeError("Proposal data must be a dictionary.")

        return cls(
            mission_id=data["mission_id"],
            reason=data.get("reason", ""),
            failed_task_ids=list(data.get("failed_task_ids", [])),
            plan=list(data.get("plan", [])),
            source=data.get("source", "REPLANNING_ENGINE"),
            metadata=dict(data.get("metadata", {})),
        )


class ReplanningEngine:
    """Read-only engine that proposes revised mission plans.

    The engine does NOT:
    - execute tasks
    - mutate ManagementState
    - cancel tasks
    - retry tasks
    - approve actions
    - resolve confirmations
    - modify permissions
    - install the plan

    ManagementManager remains the authoritative plan owner.
    """

    def __init__(
        self,
        *,
        planner: Callable[
            [str, dict[str, Any]],
            list[dict[str, Any]],
        ]
        | None = None,
    ) -> None:
        if planner is not None and not callable(planner):
            raise TypeError("planner must be callable or None.")

        self._planner = planner

    def propose(
        self,
        *,
        mission_id: str,
        objective: str,
        monitor_snapshot: dict[str, Any],
        current_plan: list[dict[str, Any]] | None = None,
    ) -> ReplanProposal | None:
        """Create a revised plan proposal from degraded mission state."""

        if not isinstance(mission_id, str) or not mission_id.strip():
            raise ValueError("mission_id must be a non-empty string.")

        if not isinstance(objective, str) or not objective.strip():
            raise ValueError("objective must be a non-empty string.")

        if not isinstance(monitor_snapshot, dict):
            raise TypeError("monitor_snapshot must be a dictionary.")

        mission_id = mission_id.strip()
        objective = objective.strip()

        healthy = bool(monitor_snapshot.get("healthy", True))
        status = str(monitor_snapshot.get("status", "UNKNOWN"))

        failed_task_ids = [
            task_id
            for task_id, task_status in dict(
                monitor_snapshot.get("observed_tasks", {})
            ).items()
            if task_status in {"FAILED", "BLOCKED"}
        ]

        if healthy and not failed_task_ids:
            return None

        reason = (
            "Mission degraded; failed or blocked tasks require a revised plan."
            if failed_task_ids
            else f"Mission requires replanning because monitor status is {status}."
        )

        context = {
            "mission_id": mission_id,
            "objective": objective,
            "reason": reason,
            "failed_task_ids": list(failed_task_ids),
            "monitor_snapshot": dict(monitor_snapshot),
            "current_plan": list(current_plan or []),
        }

        if self._planner is not None:
            plan = self._planner(objective, context)
        else:
            plan = self._default_plan(
                objective=objective,
                failed_task_ids=failed_task_ids,
            )

        return ReplanProposal(
            mission_id=mission_id,
            reason=reason,
            failed_task_ids=failed_task_ids,
            plan=plan,
            metadata={
                "monitor_status": status,
                "planner_source": (
                    "CUSTOM"
                    if self._planner is not None
                    else "DETERMINISTIC_FALLBACK"
                ),
            },
        )

    @staticmethod
    def _default_plan(
        *,
        objective: str,
        failed_task_ids: list[str],
    ) -> list[dict[str, Any]]:
        """Produce a safe deterministic recovery proposal."""

        if failed_task_ids:
            return [
                {
                    "objective": (
                        f"Recover from failed mission tasks "
                        f"{', '.join(failed_task_ids)} and continue toward: "
                        f"{objective}"
                    ),
                    "priority": 80,
                    "agent_name": None,
                    "dependencies": [],
                }
            ]

        return [
            {
                "objective": objective,
                "priority": 60,
                "agent_name": None,
                "dependencies": [],
            }
        ]
