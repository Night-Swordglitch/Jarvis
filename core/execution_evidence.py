from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.action_execution import ActionExecution, ActionExecutionStatus
from core.management.evidence import EvidenceRecord, EvidenceStore


@dataclass
class ExecutionEvidence:
    """Evidence contract connecting an action execution to management evidence."""

    execution_id: str
    mission_id: str
    task_id: str
    action: str
    status: str
    result: str
    source: str = "execution_engine"
    agent_name: str = "execution_engine"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.execution_id = str(self.execution_id)
        self.mission_id = str(self.mission_id)
        self.task_id = str(self.task_id)
        self.action = str(self.action)
        self.status = str(self.status).upper()
        self.result = str(self.result)
        self.source = str(self.source)
        self.agent_name = str(self.agent_name)
        self.metadata = dict(self.metadata)

        if not self.execution_id.strip():
            raise ValueError("execution_id must be a non-empty string.")

        if not self.mission_id.strip():
            raise ValueError("mission_id must be a non-empty string.")

        if not self.task_id.strip():
            raise ValueError("task_id must be a non-empty string.")

        if not self.action.strip():
            raise ValueError("action must be a non-empty string.")

    @classmethod
    def from_execution(
        cls,
        execution: ActionExecution,
        *,
        source: str = "execution_engine",
        agent_name: str = "execution_engine",
        metadata: dict[str, Any] | None = None,
    ) -> "ExecutionEvidence":
        """Create evidence from a completed action execution."""

        if not isinstance(execution, ActionExecution):
            raise TypeError("execution must be an ActionExecution.")

        if execution.status not in {
            ActionExecutionStatus.SUCCEEDED,
            ActionExecutionStatus.FAILED,
            ActionExecutionStatus.TIMED_OUT,
        }:
            raise ValueError(
                "Execution evidence requires a terminal execution state."
            )

        return cls(
            execution_id=execution.execution_id,
            mission_id=execution.mission_id,
            task_id=execution.task_id,
            action=execution.action,
            status=execution.status.value,
            result=str(execution.result or ""),
            source=source,
            agent_name=agent_name,
            metadata=metadata or {},
        )

    def to_record(self) -> EvidenceRecord:
        """Convert the execution contract into the existing evidence model."""

        details = {
            "execution_id": self.execution_id,
            "action": self.action,
            "execution_status": self.status,
            "result": self.result,
            **self.metadata,
        }

        return EvidenceRecord(
            mission_id=self.mission_id,
            task_id=self.task_id,
            agent_name=self.agent_name,
            source=self.source,
            claim=f"Action '{self.action}' completed with status {self.status}.",
            details=details,
            status="UNVERIFIED",
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a serializable execution evidence contract."""

        return {
            "execution_id": self.execution_id,
            "mission_id": self.mission_id,
            "task_id": self.task_id,
            "action": self.action,
            "status": self.status,
            "result": self.result,
            "source": self.source,
            "agent_name": self.agent_name,
            "metadata": dict(self.metadata),
        }


class ExecutionEvidenceRecorder:
    """Thin adapter from execution evidence to the existing EvidenceStore."""

    def __init__(self, evidence_store: EvidenceStore) -> None:
        if not isinstance(evidence_store, EvidenceStore):
            raise TypeError("evidence_store must be an EvidenceStore.")

        self._evidence = evidence_store

    def record(
        self,
        evidence: ExecutionEvidence,
    ) -> EvidenceRecord:
        if not isinstance(evidence, ExecutionEvidence):
            raise TypeError("evidence must be ExecutionEvidence.")

        record = evidence.to_record()
        return self._evidence.add(record)

    def store(self) -> EvidenceStore:
        return self._evidence

