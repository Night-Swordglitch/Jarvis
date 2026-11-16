from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MissionContext:
    """
    Structured execution context for one MARK-L mission.

    MissionContext describes what is known about a mission.
    It does not execute actions, invoke agents, create tasks, or
    make management decisions.
    """

    mission_id: str
    objective: str

    constraints: list[str] = field(default_factory=list)
    success_criteria: list[str] = field(default_factory=list)

    environment: dict[str, Any] = field(default_factory=dict)
    capabilities: list[str] = field(default_factory=list)

    evidence_ids: list[str] = field(default_factory=list)

    additional_context: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.mission_id = str(self.mission_id).strip()
        self.objective = str(self.objective).strip()

        if not self.mission_id:
            raise ValueError("mission_id cannot be empty.")

        if not self.objective:
            raise ValueError("objective cannot be empty.")

        self.constraints = self._clean_list(
            self.constraints,
            "constraints",
        )

        self.success_criteria = self._clean_list(
            self.success_criteria,
            "success_criteria",
        )

        self.capabilities = self._clean_list(
            self.capabilities,
            "capabilities",
        )

        if not isinstance(self.environment, dict):
            raise TypeError("environment must be a dictionary.")

        if not isinstance(self.additional_context, dict):
            raise TypeError(
                "additional_context must be a dictionary."
            )

        self.environment = dict(self.environment)
        self.additional_context = dict(self.additional_context)

        self.evidence_ids = self._clean_list(
            self.evidence_ids,
            "evidence_ids",
        )

    def add_constraint(self, constraint: str) -> None:
        """Add one unique mission constraint."""
        constraint = str(constraint).strip()

        if not constraint:
            raise ValueError("constraint cannot be empty.")

        if constraint not in self.constraints:
            self.constraints.append(constraint)

    def add_success_criterion(self, criterion: str) -> None:
        """Add one unique mission success criterion."""
        criterion = str(criterion).strip()

        if not criterion:
            raise ValueError(
                "success criterion cannot be empty."
            )

        if criterion not in self.success_criteria:
            self.success_criteria.append(criterion)

    def add_capability(self, capability: str) -> None:
        """Record one capability relevant to the mission."""
        capability = str(capability).strip()

        if not capability:
            raise ValueError("capability cannot be empty.")

        if capability not in self.capabilities:
            self.capabilities.append(capability)

    def add_evidence_reference(self, evidence_id: str) -> None:
        """
        Attach an evidence reference.

        The complete EvidenceRecord remains owned by EvidenceStore.
        """
        evidence_id = str(evidence_id).strip()

        if not evidence_id:
            raise ValueError("evidence_id cannot be empty.")

        if evidence_id not in self.evidence_ids:
            self.evidence_ids.append(evidence_id)

    def set_environment(
        self,
        key: str,
        value: Any,
    ) -> None:
        """Set one environmental context value."""
        key = str(key).strip()

        if not key:
            raise ValueError("environment key cannot be empty.")

        self.environment[key] = value

    def set_context(
        self,
        key: str,
        value: Any,
    ) -> None:
        """Set one additional context value."""
        key = str(key).strip()

        if not key:
            raise ValueError("context key cannot be empty.")

        self.additional_context[key] = value

    def to_dict(self) -> dict[str, Any]:
        """Serialize the complete mission context."""
        return {
            "mission_id": self.mission_id,
            "objective": self.objective,
            "constraints": list(self.constraints),
            "success_criteria": list(self.success_criteria),
            "environment": dict(self.environment),
            "capabilities": list(self.capabilities),
            "evidence_ids": list(self.evidence_ids),
            "additional_context": dict(self.additional_context),
        }

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
    ) -> "MissionContext":
        """Restore MissionContext from serialized data."""
        if not isinstance(data, dict):
            raise TypeError(
                "Mission context data must be a dictionary."
            )

        return cls(
            mission_id=data["mission_id"],
            objective=data["objective"],
            constraints=list(data.get("constraints", [])),
            success_criteria=list(
                data.get("success_criteria", [])
            ),
            environment=dict(data.get("environment", {})),
            capabilities=list(data.get("capabilities", [])),
            evidence_ids=list(data.get("evidence_ids", [])),
            additional_context=dict(
                data.get("additional_context", {})
            ),
        )

    @staticmethod
    def _clean_list(
        values: list[str],
        field_name: str,
    ) -> list[str]:
        if not isinstance(values, list):
            raise TypeError(f"{field_name} must be a list.")

        cleaned: list[str] = []

        for value in values:
            value = str(value).strip()

            if value and value not in cleaned:
                cleaned.append(value)

        return cleaned
