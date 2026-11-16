"""Phase 7J — Mission Verification.

Read-only verification of mission success criteria against management state
and mission evidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from core.management.evidence import EvidenceRecord, EvidenceStore
from core.management.state import ManagementState
from core.mission_context import MissionContext


@dataclass
class CriterionResult:
    """Verification result for one mission success criterion."""

    criterion: str
    satisfied: bool
    reason: str = ""
    evidence_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "criterion": self.criterion,
            "satisfied": self.satisfied,
            "reason": self.reason,
            "evidence_ids": list(self.evidence_ids),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CriterionResult":
        if not isinstance(data, dict):
            raise TypeError("Criterion data must be a dictionary.")

        return cls(
            criterion=str(data["criterion"]),
            satisfied=bool(data["satisfied"]),
            reason=str(data.get("reason", "")),
            evidence_ids=list(data.get("evidence_ids", [])),
        )


@dataclass
class VerificationResult:
    """Complete read-only mission verification result."""

    mission_id: str
    objective: str
    status: str
    verified: bool
    complete: bool
    criteria: list[CriterionResult] = field(default_factory=list)
    completed_task_ids: list[str] = field(default_factory=list)
    failed_task_ids: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.mission_id, str) or not self.mission_id.strip():
            raise ValueError("mission_id must be a non-empty string.")

        if not isinstance(self.objective, str):
            raise TypeError("objective must be a string.")

        if self.status not in {
            "VERIFIED",
            "FAILED",
            "INCOMPLETE",
        }:
            raise ValueError(f"Unknown verification status: {self.status}")

        if not isinstance(self.criteria, list):
            raise TypeError("criteria must be a list.")

        self.mission_id = self.mission_id.strip()

    def to_dict(self) -> dict[str, Any]:
        return {
            "mission_id": self.mission_id,
            "objective": self.objective,
            "status": self.status,
            "verified": self.verified,
            "complete": self.complete,
            "criteria": [
                criterion.to_dict()
                for criterion in self.criteria
            ],
            "completed_task_ids": list(self.completed_task_ids),
            "failed_task_ids": list(self.failed_task_ids),
            "evidence_ids": list(self.evidence_ids),
            "reason": self.reason,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VerificationResult":
        if not isinstance(data, dict):
            raise TypeError("Verification data must be a dictionary.")

        return cls(
            mission_id=data["mission_id"],
            objective=data.get("objective", ""),
            status=data["status"],
            verified=bool(data.get("verified", False)),
            complete=bool(data.get("complete", False)),
            criteria=[
                CriterionResult.from_dict(item)
                for item in data.get("criteria", [])
            ],
            completed_task_ids=list(
                data.get("completed_task_ids", [])
            ),
            failed_task_ids=list(
                data.get("failed_task_ids", [])
            ),
            evidence_ids=list(data.get("evidence_ids", [])),
            reason=data.get("reason", ""),
            metadata=dict(data.get("metadata", {})),
        )


CriterionEvaluator = Callable[
    [str, MissionContext, ManagementState, list[EvidenceRecord]],
    CriterionResult,
]


class MissionVerifier:
    """Read-only mission verification engine."""

    def __init__(
        self,
        evidence_store: EvidenceStore | None = None,
        evaluator: CriterionEvaluator | None = None,
    ) -> None:
        if evidence_store is not None and not isinstance(
            evidence_store,
            EvidenceStore,
        ):
            raise TypeError("evidence_store must be an EvidenceStore.")

        if evaluator is not None and not callable(evaluator):
            raise TypeError("evaluator must be callable or None.")

        self._evidence = evidence_store or EvidenceStore()
        self._evaluator = evaluator

    def verify(
        self,
        *,
        context: MissionContext,
        state: ManagementState,
    ) -> VerificationResult:
        """Evaluate mission completion without changing system state."""

        if not isinstance(context, MissionContext):
            raise TypeError("context must be a MissionContext.")

        if not isinstance(state, ManagementState):
            raise TypeError("state must be a ManagementState.")

        if state.mission_id != context.mission_id:
            return VerificationResult(
                mission_id=context.mission_id,
                objective=context.objective,
                status="FAILED",
                verified=False,
                complete=False,
                reason="Management state belongs to a different mission.",
            )

        completed = list(state.completed_tasks.keys())
        failed = list(state.failed_tasks.keys())
        blocked = list(state.blocked_tasks.keys())

        evidence = self._evidence.for_mission(context.mission_id)

        if failed or blocked:
            return VerificationResult(
                mission_id=context.mission_id,
                objective=context.objective,
                status="FAILED",
                verified=False,
                complete=False,
                completed_task_ids=completed,
                failed_task_ids=failed + blocked,
                evidence_ids=[
                    record.evidence_id
                    for record in evidence
                ],
                reason="Mission contains failed or blocked tasks.",
                metadata={
                    "blocked_task_ids": blocked,
                },
            )

        if state.active_tasks or state.queued_tasks:
            return VerificationResult(
                mission_id=context.mission_id,
                objective=context.objective,
                status="INCOMPLETE",
                verified=False,
                complete=False,
                completed_task_ids=completed,
                evidence_ids=[
                    record.evidence_id
                    for record in evidence
                ],
                reason="Mission still has active or queued tasks.",
            )

        if not context.success_criteria:
            return VerificationResult(
                mission_id=context.mission_id,
                objective=context.objective,
                status="INCOMPLETE",
                verified=False,
                complete=False,
                completed_task_ids=completed,
                evidence_ids=[
                    record.evidence_id
                    for record in evidence
                ],
                reason="Mission has no success criteria to verify.",
            )

        criteria: list[CriterionResult] = []

        for criterion in context.success_criteria:
            if self._evaluator is not None:
                result = self._evaluator(
                    criterion,
                    context,
                    state,
                    evidence,
                )

                if not isinstance(result, CriterionResult):
                    raise TypeError(
                        "Criterion evaluator must return CriterionResult."
                    )

                criteria.append(result)
            else:
                criteria.append(
                    self._default_evaluate(
                        criterion,
                        evidence,
                    )
                )

        verified = bool(criteria) and all(
            result.satisfied
            for result in criteria
        )

        return VerificationResult(
            mission_id=context.mission_id,
            objective=context.objective,
            status="VERIFIED" if verified else "FAILED",
            verified=verified,
            complete=True,
            criteria=criteria,
            completed_task_ids=completed,
            evidence_ids=[
                record.evidence_id
                for record in evidence
            ],
            reason=(
                "All mission success criteria were verified."
                if verified
                else "One or more mission success criteria were not verified."
            ),
        )

    @staticmethod
    def _default_evaluate(
        criterion: str,
        evidence: list[EvidenceRecord],
    ) -> CriterionResult:
        """Conservative evidence-based fallback."""

        target = criterion.strip().lower()
        matching_ids: list[str] = []

        for record in evidence:
            haystack = " ".join(
                [
                    record.claim,
                    record.source,
                    str(record.details),
                ]
            ).lower()

            if target and target in haystack:
                matching_ids.append(record.evidence_id)

        if matching_ids:
            return CriterionResult(
                criterion=criterion,
                satisfied=True,
                reason="Criterion matched mission evidence.",
                evidence_ids=matching_ids,
            )

        return CriterionResult(
            criterion=criterion,
            satisfied=False,
            reason="No mission evidence explicitly supports this criterion.",
        )
