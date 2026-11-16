"""Validated, serializable goal plans for the MARK-L reasoning layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


STEP_STATUSES = {"PENDING", "RUNNING", "COMPLETED", "FAILED", "BLOCKED"}


@dataclass
class PlanStep:
    """One specialist assignment inside a mission plan."""

    step_id: str
    objective: str
    agent_name: str
    depends_on: list[str] = field(default_factory=list)
    success_criteria: list[str] = field(default_factory=list)
    priority: int = 50
    status: str = "PENDING"
    result: dict[str, Any] | None = None
    error: str | None = None

    def __post_init__(self) -> None:
        for name in ("step_id", "objective", "agent_name"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string.")
            setattr(self, name, value.strip())

        if not self.step_id.replace("-", "").replace("_", "").isalnum():
            raise ValueError("step_id may contain only letters, numbers, '_' and '-'.")
        if len(self.objective) > 1200:
            raise ValueError("Step objective exceeds 1200 characters.")
        if not isinstance(self.depends_on, list) or not all(
            isinstance(item, str) and item.strip() for item in self.depends_on
        ):
            raise TypeError("depends_on must be a list of non-empty strings.")
        if not isinstance(self.success_criteria, list) or not all(
            isinstance(item, str) and item.strip() for item in self.success_criteria
        ):
            raise TypeError("success_criteria must be a list of non-empty strings.")
        self.depends_on = list(dict.fromkeys(item.strip() for item in self.depends_on))
        self.success_criteria = [item.strip() for item in self.success_criteria]
        if not isinstance(self.priority, int) or not 0 <= self.priority <= 100:
            raise ValueError("priority must be an integer between 0 and 100.")
        self.status = str(self.status).upper()
        if self.status not in STEP_STATUSES:
            raise ValueError(f"Invalid plan step status: {self.status}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "objective": self.objective,
            "agent_name": self.agent_name,
            "depends_on": list(self.depends_on),
            "success_criteria": list(self.success_criteria),
            "priority": self.priority,
            "status": self.status,
            "result": self.result,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PlanStep":
        if not isinstance(data, dict):
            raise TypeError("Plan step must be a dictionary.")
        return cls(
            step_id=data["step_id"],
            objective=data["objective"],
            agent_name=data["agent_name"],
            depends_on=list(data.get("depends_on", [])),
            success_criteria=list(data.get("success_criteria", [])),
            priority=data.get("priority", 50),
            status=data.get("status", "PENDING"),
            result=data.get("result"),
            error=data.get("error"),
        )


@dataclass
class MissionPlan:
    """A bounded plan; it describes specialist work but grants no action authority."""

    objective: str
    steps: list[PlanStep]
    summary: str = ""
    plan_id: str = field(default_factory=lambda: uuid4().hex)
    status: str = "READY"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self) -> None:
        if not isinstance(self.objective, str) or not self.objective.strip():
            raise ValueError("Plan objective must be a non-empty string.")
        self.objective = self.objective.strip()
        if not isinstance(self.steps, list) or not self.steps:
            raise ValueError("A mission plan must contain at least one step.")
        if len(self.steps) > 20:
            raise ValueError("A mission plan cannot contain more than 20 steps.")
        if not all(isinstance(step, PlanStep) for step in self.steps):
            raise TypeError("steps must contain PlanStep objects.")
        if not isinstance(self.summary, str):
            raise TypeError("summary must be a string.")
        if not isinstance(self.plan_id, str) or not self.plan_id.strip():
            raise ValueError("plan_id must be a non-empty string.")
        self.status = str(self.status).upper()
        if self.status not in {"READY", "RUNNING", "COMPLETED", "PARTIAL", "FAILED"}:
            raise ValueError(f"Invalid plan status: {self.status}")
        self.validate_graph()

    def validate_graph(self) -> None:
        by_id = {step.step_id: step for step in self.steps}
        if len(by_id) != len(self.steps):
            raise ValueError("Plan step IDs must be unique.")
        for step in self.steps:
            unknown = set(step.depends_on) - set(by_id)
            if unknown:
                raise ValueError(
                    f"Step '{step.step_id}' has unknown dependencies: {sorted(unknown)}"
                )
            if step.step_id in step.depends_on:
                raise ValueError(f"Step '{step.step_id}' cannot depend on itself.")

        remaining = {step.step_id: set(step.depends_on) for step in self.steps}
        completed: set[str] = set()
        while remaining:
            ready = [
                step_id for step_id, deps in remaining.items()
                if deps.issubset(completed)
            ]
            if not ready:
                raise ValueError("Plan dependencies contain a cycle.")
            for step_id in ready:
                completed.add(step_id)
                remaining.pop(step_id)

    def validate_agents(self, available_agents: set[str]) -> None:
        if not isinstance(available_agents, set):
            raise TypeError("available_agents must be a set.")
        for step in self.steps:
            if step.agent_name not in available_agents:
                raise ValueError(
                    f"Step '{step.step_id}' references unregistered agent "
                    f"'{step.agent_name}'."
                )

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "objective": self.objective,
            "summary": self.summary,
            "status": self.status,
            "created_at": self.created_at,
            "steps": [step.to_dict() for step in self.steps],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MissionPlan":
        if not isinstance(data, dict):
            raise TypeError("Mission plan must be a dictionary.")
        return cls(
            plan_id=data.get("plan_id", uuid4().hex),
            objective=data["objective"],
            summary=data.get("summary", ""),
            status=data.get("status", "READY"),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            steps=[PlanStep.from_dict(item) for item in data["steps"]],
        )
