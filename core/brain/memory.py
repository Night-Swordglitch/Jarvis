"""Project-scoped long-term memory retrieval for the MARK-L Brain."""

from __future__ import annotations

import re
from typing import Any, Callable

from memory.memory_manager import load_memory


class BrainMemory:
    """Recall relevant project facts without exposing unrelated personal memory."""

    def __init__(self, loader: Callable[[], dict[str, Any]] | None = None) -> None:
        self._loader = loader or load_memory

    def recall_project_context(self, objective: str, *, limit: int = 6) -> list[dict[str, str]]:
        if not isinstance(objective, str) or not objective.strip():
            raise ValueError("objective must be a non-empty string.")
        if not isinstance(limit, int) or not 1 <= limit <= 20:
            raise ValueError("limit must be between 1 and 20.")

        memory = self._loader()
        if not isinstance(memory, dict):
            return []

        words = {
            word for word in re.findall(r"[a-z0-9_]+", objective.lower())
            if len(word) > 2
        }
        projects = memory.get("projects", {})
        if not isinstance(projects, dict):
            return []

        matches: list[tuple[int, str, str, str]] = []
        for key, entry in projects.items():
            if isinstance(entry, dict):
                value = entry.get("value", "")
            else:
                value = entry
            if not isinstance(value, str) or not value.strip():
                continue
            searchable = f"{key} {value}".lower()
            score = sum(1 for word in words if word in searchable)
            if score:
                matches.append((score, str(key), value.strip(), str(entry.get("updated", "") if isinstance(entry, dict) else "")))

        matches.sort(key=lambda item: (-item[0], item[1]))
        return [
            {"category": "projects", "key": key, "value": value, "updated": updated}
            for _score, key, value, updated in matches[:limit]
        ]
