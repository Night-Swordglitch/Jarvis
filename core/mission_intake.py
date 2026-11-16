from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MissionIntakeResult:
    """Structured interpretation of a user's mission request."""

    objective: str
    constraints: list[str] = field(default_factory=list)
    success_criteria: list[str] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    clarification_questions: list[str] = field(default_factory=list)

    @property
    def ready(self) -> bool:
        """Whether the mission contains enough information to proceed."""
        return bool(
            self.objective.strip()
            and not self.clarification_questions
        )

    def to_context(self) -> dict[str, Any]:
        """Convert intake information into ManagementManager context."""
        return {
            "constraints": list(self.constraints),
            "success_criteria": list(self.success_criteria),
            **dict(self.context),
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize the intake result."""
        return {
            "objective": self.objective,
            "constraints": list(self.constraints),
            "success_criteria": list(self.success_criteria),
            "context": dict(self.context),
            "clarification_questions": list(
                self.clarification_questions
            ),
            "ready": self.ready,
        }


class MissionIntake:
    """
    Phase 7A mission-intake boundary.

    MissionIntake interprets and validates structured mission information.
    It does not execute actions, create tasks, invoke agents, or bypass
    ManagementManager / PermissionManager.
    """

    def __init__(self, *, default_context: dict[str, Any] | None = None):
        if default_context is not None and not isinstance(
            default_context,
            dict,
        ):
            raise TypeError("default_context must be a dictionary")

        self.default_context = dict(default_context or {})

    def intake(
        self,
        objective: str,
        *,
        constraints: list[str] | None = None,
        success_criteria: list[str] | None = None,
        context: dict[str, Any] | None = None,
    ) -> MissionIntakeResult:
        """Create a validated mission-intake result."""
        if not isinstance(objective, str):
            raise TypeError("objective must be a string")

        objective = objective.strip()

        if not objective:
            raise ValueError("Mission objective cannot be empty")

        if constraints is not None and not isinstance(constraints, list):
            raise TypeError("constraints must be a list")

        if success_criteria is not None and not isinstance(
            success_criteria,
            list,
        ):
            raise TypeError("success_criteria must be a list")

        if context is not None and not isinstance(context, dict):
            raise TypeError("context must be a dictionary")

        clean_constraints = self._clean_list(
            constraints,
            "constraints",
        )
        clean_success = self._clean_list(
            success_criteria,
            "success_criteria",
        )

        merged_context = dict(self.default_context)
        if context:
            merged_context.update(context)

        merged_context["mission_intake"] = {
            "constraints": list(clean_constraints),
            "success_criteria": list(clean_success),
        }

        return MissionIntakeResult(
            objective=objective,
            constraints=clean_constraints,
            success_criteria=clean_success,
            context=merged_context,
        )

    def require_clarification(
        self,
        objective: str,
        question: str,
        *,
        constraints: list[str] | None = None,
        success_criteria: list[str] | None = None,
        context: dict[str, Any] | None = None,
    ) -> MissionIntakeResult:
        """
        Build an intake result that explicitly requires clarification.

        This does not ask the user directly; it records the question so the
        existing ManagementManager clarification lifecycle can handle it.
        """
        result = self.intake(
            objective,
            constraints=constraints,
            success_criteria=success_criteria,
            context=context,
        )

        question = str(question).strip()

        if not question:
            raise ValueError("Clarification question cannot be empty")

        result.clarification_questions.append(question)
        return result

    @staticmethod
    def _clean_list(
        values: list[str] | None,
        field_name: str,
    ) -> list[str]:
        if values is None:
            return []

        cleaned: list[str] = []

        for value in values:
            if not isinstance(value, str):
                raise TypeError(
                    f"{field_name} entries must be strings"
                )

            value = value.strip()

            if value:
                cleaned.append(value)

        return cleaned
