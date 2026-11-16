"""JSON persistence for validated MARK-L mission plans."""

from __future__ import annotations

import json
from pathlib import Path
from threading import RLock

from .models import MissionPlan


class PlanStore:
    """Persist plan definitions and progress without granting execution authority."""

    def __init__(self, path: str | Path) -> None:
        if not isinstance(path, (str, Path)):
            raise TypeError("path must be a string or Path.")
        self.path = Path(path)
        self._lock = RLock()

    def save(self, plan: MissionPlan) -> MissionPlan:
        if not isinstance(plan, MissionPlan):
            raise TypeError("plan must be a MissionPlan.")
        with self._lock:
            data = self._read()
            data[plan.plan_id] = plan.to_dict()
            self._write(data)
        return plan

    def get(self, plan_id: str) -> MissionPlan | None:
        if not isinstance(plan_id, str) or not plan_id.strip():
            raise ValueError("plan_id must be a non-empty string.")
        with self._lock:
            raw = self._read().get(plan_id.strip())
        return MissionPlan.from_dict(raw) if raw is not None else None

    def all(self) -> list[MissionPlan]:
        with self._lock:
            values = list(self._read().values())
        return [MissionPlan.from_dict(item) for item in values]

    def remove(self, plan_id: str) -> bool:
        if not isinstance(plan_id, str) or not plan_id.strip():
            raise ValueError("plan_id must be a non-empty string.")
        with self._lock:
            data = self._read()
            if plan_id.strip() not in data:
                return False
            del data[plan_id.strip()]
            self._write(data)
            return True

    def _read(self) -> dict:
        if not self.path.exists():
            return {}
        with self.path.open("r", encoding="utf-8") as stream:
            data = json.load(stream)
        if not isinstance(data, dict):
            raise ValueError("Plan store must contain a JSON object.")
        return data

    def _write(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump(data, stream, indent=2, ensure_ascii=False)
        temporary.replace(self.path)

    def __len__(self) -> int:
        with self._lock:
            return len(self._read())
