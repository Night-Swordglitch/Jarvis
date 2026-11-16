from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class MissionMemoryRecord:
    mission_id: str
    objective: str
    status: str = "UNKNOWN"
    context: dict[str, Any] = field(default_factory=dict)
    tasks: list[dict[str, Any]] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    decisions: list[dict[str, Any]] = field(default_factory=list)
    approvals: list[dict[str, Any]] = field(default_factory=list)
    outcomes: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not isinstance(self.mission_id, str) or not self.mission_id.strip():
            raise ValueError("mission_id must be a non-empty string")
        if not isinstance(self.objective, str) or not self.objective.strip():
            raise ValueError("objective must be a non-empty string")
        if not isinstance(self.status, str):
            raise TypeError("status must be a string")

        for name in ("context", "metadata"):
            if not isinstance(getattr(self, name), dict):
                raise TypeError(f"{name} must be a dict")

        for name in (
            "tasks",
            "evidence_ids",
            "decisions",
            "approvals",
            "outcomes",
        ):
            if not isinstance(getattr(self, name), list):
                raise TypeError(f"{name} must be a list")

        self.mission_id = self.mission_id.strip()
        self.objective = self.objective.strip()
        self.status = self.status.strip()

        cleaned = []
        for evidence_id in self.evidence_ids:
            if not isinstance(evidence_id, str):
                raise TypeError("evidence_ids must contain strings")
            evidence_id = evidence_id.strip()
            if evidence_id and evidence_id not in cleaned:
                cleaned.append(evidence_id)

        self.evidence_ids = cleaned

    def add_task(self, task):
        if not isinstance(task, dict):
            raise TypeError("task must be a dict")
        self.tasks.append(dict(task))

    def add_evidence_reference(self, evidence_id):
        if not isinstance(evidence_id, str) or not evidence_id.strip():
            raise ValueError("evidence_id must be a non-empty string")
        evidence_id = evidence_id.strip()
        if evidence_id not in self.evidence_ids:
            self.evidence_ids.append(evidence_id)

    def add_decision(self, decision):
        if not isinstance(decision, dict):
            raise TypeError("decision must be a dict")
        self.decisions.append(dict(decision))

    def add_approval(self, approval):
        if not isinstance(approval, dict):
            raise TypeError("approval must be a dict")
        self.approvals.append(dict(approval))

    def add_outcome(self, outcome):
        if not isinstance(outcome, dict):
            raise TypeError("outcome must be a dict")
        self.outcomes.append(dict(outcome))

    def to_dict(self):
        return {
            "mission_id": self.mission_id,
            "objective": self.objective,
            "status": self.status,
            "context": dict(self.context),
            "tasks": [dict(x) for x in self.tasks],
            "evidence_ids": list(self.evidence_ids),
            "decisions": [dict(x) for x in self.decisions],
            "approvals": [dict(x) for x in self.approvals],
            "outcomes": [dict(x) for x in self.outcomes],
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict):
            raise TypeError("data must be a dict")

        return cls(
            mission_id=data["mission_id"],
            objective=data["objective"],
            status=data.get("status", "UNKNOWN"),
            context=dict(data.get("context") or {}),
            tasks=[dict(x) for x in data.get("tasks") or []],
            evidence_ids=list(data.get("evidence_ids") or []),
            decisions=[dict(x) for x in data.get("decisions") or []],
            approvals=[dict(x) for x in data.get("approvals") or []],
            outcomes=[dict(x) for x in data.get("outcomes") or []],
            metadata=dict(data.get("metadata") or {}),
        )


class MissionMemory:

    def __init__(self, path):
        self.path = Path(path)

    def save(self, record):
        if not isinstance(record, MissionMemoryRecord):
            raise TypeError("record must be MissionMemoryRecord")

        data = self._read()
        data[record.mission_id] = record.to_dict()
        self._write(data)
        return record

    def get(self, mission_id):
        data = self._read()
        raw = data.get(mission_id)

        if raw is None:
            return None

        return MissionMemoryRecord.from_dict(raw)

    def all(self):
        return [
            MissionMemoryRecord.from_dict(x)
            for x in self._read().values()
        ]

    def latest(self):
        records = self.all()
        return records[-1] if records else None

    def __len__(self):
        return len(self._read())

    def _read(self):
        if not self.path.exists():
            return {}

        with self.path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            raise ValueError("Mission memory must contain a JSON object")

        return data

    def _write(self, data):
        self.path.parent.mkdir(parents=True, exist_ok=True)

        temp = self.path.with_suffix(self.path.suffix + ".tmp")

        with temp.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        temp.replace(self.path)
