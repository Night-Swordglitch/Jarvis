from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


@dataclass
class EvidenceRecord:
    """Immutable-style provenance record for management evidence."""

    mission_id: str
    task_id: str
    agent_name: str
    source: str
    claim: str
    details: dict[str, Any] = field(default_factory=dict)
    status: str = "UNVERIFIED"
    confidence: float | None = None
    evidence_id: str = field(default_factory=lambda: uuid4().hex)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def __post_init__(self) -> None:
        self.mission_id = str(self.mission_id)
        self.task_id = str(self.task_id)
        self.agent_name = str(self.agent_name)
        self.source = str(self.source)
        self.claim = str(self.claim)
        self.status = str(self.status).upper()

        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")

        self.details = dict(self.details)

    def to_dict(self) -> dict[str, Any]:
        """Return a serializable provenance record."""

        return {
            "evidence_id": self.evidence_id,
            "mission_id": self.mission_id,
            "task_id": self.task_id,
            "agent_name": self.agent_name,
            "source": self.source,
            "claim": self.claim,
            "details": dict(self.details),
            "status": self.status,
            "confidence": self.confidence,
            "created_at": self.created_at,
        }


class EvidenceStore:
    """In-memory evidence store with provenance-aware retrieval."""

    def __init__(self) -> None:
        self._records: dict[str, EvidenceRecord] = {}

    def add(self, record: EvidenceRecord) -> EvidenceRecord:
        """Store an evidence record."""

        if not isinstance(record, EvidenceRecord):
            raise TypeError("record must be EvidenceRecord")

        if record.evidence_id in self._records:
            raise ValueError(
                f"Evidence already exists: {record.evidence_id}"
            )

        self._records[record.evidence_id] = record
        return record

    def get(self, evidence_id: str) -> EvidenceRecord | None:
        """Retrieve evidence by ID."""

        return self._records.get(str(evidence_id))

    def for_mission(self, mission_id: str) -> list[EvidenceRecord]:
        """Return evidence associated with a mission."""

        mission_id = str(mission_id)

        return [
            record
            for record in self._records.values()
            if record.mission_id == mission_id
        ]

    def for_task(self, task_id: str) -> list[EvidenceRecord]:
        """Return evidence associated with a task."""

        task_id = str(task_id)

        return [
            record
            for record in self._records.values()
            if record.task_id == task_id
        ]

    def for_agent(self, agent_name: str) -> list[EvidenceRecord]:
        """Return evidence produced by an agent."""

        agent_name = str(agent_name)

        return [
            record
            for record in self._records.values()
            if record.agent_name == agent_name
        ]

    def search(self, query: str) -> list[EvidenceRecord]:
        """Search claims, sources, and details for matching text."""

        query = str(query).strip().lower()

        if not query:
            return []

        results: list[EvidenceRecord] = []

        for record in self._records.values():
            haystack = " ".join(
                [
                    record.claim,
                    record.source,
                    record.agent_name,
                    record.status,
                    str(record.details),
                ]
            ).lower()

            if query in haystack:
                results.append(record)

        return results

    def latest(self) -> EvidenceRecord | None:
        """Return the most recently created evidence record."""

        if not self._records:
            return None

        return max(
            self._records.values(),
            key=lambda record: record.created_at,
        )

    def all(self) -> list[EvidenceRecord]:
        """Return all stored evidence records."""

        return list(self._records.values())

    def __len__(self) -> int:
        return len(self._records)

