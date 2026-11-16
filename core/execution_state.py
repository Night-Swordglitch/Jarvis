"""Phase 8K - Persistent execution state.

This module persists ActionExecution state across process restarts.

It does not execute actions, enforce permissions, request approval,
perform verification, retry actions, or replan missions.
"""

from __future__ import annotations

import json
from pathlib import Path

from core.action_execution import ActionExecution


class ExecutionStateStore:
    """JSON-backed persistence for ActionExecution records."""

    def __init__(self, path: str | Path) -> None:
        if not isinstance(path, (str, Path)):
            raise TypeError("path must be a string or Path.")

        self.path = Path(path)

    def save(self, execution: ActionExecution) -> ActionExecution:
        if not isinstance(execution, ActionExecution):
            raise TypeError(
                "execution must be an ActionExecution."
            )

        data = self._read()
        data[execution.execution_id] = execution.to_dict()
        self._write(data)

        return execution

    def get(self, execution_id: str) -> ActionExecution | None:
        if not isinstance(execution_id, str):
            raise TypeError("execution_id must be a string.")

        execution_id = execution_id.strip()

        if not execution_id:
            raise ValueError(
                "execution_id must be a non-empty string."
            )

        data = self._read()
        raw = data.get(execution_id)

        if raw is None:
            return None

        return ActionExecution.from_dict(raw)

    def all(self) -> list[ActionExecution]:
        return [
            ActionExecution.from_dict(raw)
            for raw in self._read().values()
        ]

    def remove(self, execution_id: str) -> bool:
        if not isinstance(execution_id, str):
            raise TypeError("execution_id must be a string.")

        execution_id = execution_id.strip()

        if not execution_id:
            raise ValueError(
                "execution_id must be a non-empty string."
            )

        data = self._read()

        if execution_id not in data:
            return False

        del data[execution_id]
        self._write(data)
        return True

    def __len__(self) -> int:
        return len(self._read())

    def _read(self) -> dict:
        if not self.path.exists():
            return {}

        with self.path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            raise ValueError(
                "Execution state must contain a JSON object."
            )

        return data

    def _write(self, data: dict) -> None:
        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temp = self.path.with_suffix(
            self.path.suffix + ".tmp"
        )

        with temp.open("w", encoding="utf-8") as f:
            json.dump(
                data,
                f,
                indent=2,
                ensure_ascii=False,
            )

        temp.replace(self.path)
