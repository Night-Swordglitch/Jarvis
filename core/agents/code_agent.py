from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import BaseAgent
from .task import AgentTask
from .result import AgentResult


class CodeAgent(BaseAgent):
    """Specialist agent for repository inspection and code analysis."""

    name = "code_agent"
    description = (
        "Inspects repositories, analyzes source code, identifies issues, "
        "and proposes controlled engineering changes."
    )

    def run(self, task: AgentTask) -> AgentResult:
        """Analyze a coding task without directly modifying files."""

        try:
            repository = self._resolve_repository(task)
            if repository is None:
                return AgentResult(
                    agent_name=self.name,
                    task_id=task.task_id,
                    status="FAILED",
                    summary="No valid repository was provided.",
                    errors=["A valid repository path is required."],
                )

            findings: list[str] = []
            data: dict[str, Any] = {
                "repository": str(repository),
                "operation": "inspect",
            }

            files = self._collect_files(repository)
            data["file_count"] = len(files)
            data["files"] = [str(path.relative_to(repository)) for path in files[:200]]

            findings.append(
                f"Repository contains {len(files)} inspectable source/config files."
            )

            return AgentResult(
                agent_name=self.name,
                task_id=task.task_id,
                status="SUCCESS",
                summary=f"Inspected repository: {repository}",
                findings=findings,
                data=data,
            )

        except Exception as exc:
            return AgentResult(
                agent_name=self.name,
                task_id=task.task_id,
                status="FAILED",
                summary="Code inspection failed.",
                errors=[f"{type(exc).__name__}: {exc}"],
            )

    def _resolve_repository(self, task: AgentTask) -> Path | None:
        """Resolve the repository path from task context."""

        raw = (
            task.context.get("repository")
            or task.context.get("repo")
            or task.context.get("path")
        )

        if not raw:
            return None

        path = Path(str(raw)).expanduser().resolve()

        if not path.exists() or not path.is_dir():
            return None

        return path

    def _collect_files(self, repository: Path) -> list[Path]:
        """Collect relevant source/config files without modifying anything."""

        ignored_dirs = {
            ".git",
            ".venv",
            "venv",
            "__pycache__",
            "node_modules",
            ".pytest_cache",
            ".mypy_cache",
            ".ruff_cache",
            "dist",
            "build",
        }

        allowed_suffixes = {
            ".py",
            ".js",
            ".jsx",
            ".ts",
            ".tsx",
            ".html",
            ".css",
            ".json",
            ".toml",
            ".yaml",
            ".yml",
            ".md",
            ".txt",
        }

        files: list[Path] = []

        for path in repository.rglob("*"):
            if not path.is_file():
                continue

            if any(part in ignored_dirs for part in path.parts):
                continue

            if path.suffix.lower() in allowed_suffixes:
                files.append(path)

        return sorted(files, key=lambda item: str(item).lower())

    def can_handle(self, task: AgentTask) -> bool:
        """Return whether the task appears to be a coding task."""

        text = task.objective.lower()

        keywords = (
            "code",
            "coding",
            "bug",
            "debug",
            "repository",
            "repo",
            "file",
            "python",
            "javascript",
            "typescript",
            "program",
            "software",
            "implement",
            "refactor",
            "fix",
        )

        return any(keyword in text for keyword in keywords)
