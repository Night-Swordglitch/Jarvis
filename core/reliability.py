from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True)
class RetryPolicy:
    """Controls whether a failed task may be retried."""

    max_attempts: int = 1
    retryable_errors: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.max_attempts, int):
            raise TypeError("max_attempts must be an integer")

        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")

        object.__setattr__(
            self,
            "retryable_errors",
            tuple(str(item).lower() for item in self.retryable_errors),
        )

    def can_retry(self, attempt: int, error: str) -> bool:
        """Return whether another attempt is permitted."""

        if attempt < 1:
            return False

        if attempt >= self.max_attempts:
            return False

        if not self.retryable_errors:
            return True

        error_text = str(error).lower()

        return any(
            marker in error_text
            for marker in self.retryable_errors
        )


@dataclass
class ResourcePolicy:
    """Tracks and limits resources available to scheduled work."""

    max_workers: int = 3
    max_cpu: int = 100
    max_memory_mb: int = 16384

    used_workers: int = field(default=0, init=False)
    used_cpu: int = field(default=0, init=False)
    used_memory_mb: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        if self.max_workers < 1:
            raise ValueError("max_workers must be at least 1")

        if self.max_cpu < 0:
            raise ValueError("max_cpu cannot be negative")

        if self.max_memory_mb < 0:
            raise ValueError("max_memory_mb cannot be negative")

    def can_allocate(
        self,
        *,
        workers: int = 0,
        cpu: int = 0,
        memory_mb: int = 0,
    ) -> bool:
        """Return whether the requested resources fit within capacity."""

        self._validate_request(workers, cpu, memory_mb)

        return (
            self.used_workers + workers <= self.max_workers
            and self.used_cpu + cpu <= self.max_cpu
            and self.used_memory_mb + memory_mb <= self.max_memory_mb
        )

    def allocate(
        self,
        *,
        workers: int = 0,
        cpu: int = 0,
        memory_mb: int = 0,
    ) -> None:
        """Reserve resources."""

        if not self.can_allocate(
            workers=workers,
            cpu=cpu,
            memory_mb=memory_mb,
        ):
            raise RuntimeError("Requested resources exceed available capacity")

        self.used_workers += workers
        self.used_cpu += cpu
        self.used_memory_mb += memory_mb

    def release(
        self,
        *,
        workers: int = 0,
        cpu: int = 0,
        memory_mb: int = 0,
    ) -> None:
        """Release previously allocated resources."""

        self._validate_request(workers, cpu, memory_mb)

        if (
            workers > self.used_workers
            or cpu > self.used_cpu
            or memory_mb > self.used_memory_mb
        ):
            raise RuntimeError("Cannot release more resources than allocated")

        self.used_workers -= workers
        self.used_cpu -= cpu
        self.used_memory_mb -= memory_mb

    @staticmethod
    def _validate_request(
        workers: int,
        cpu: int,
        memory_mb: int,
    ) -> None:
        if workers < 0:
            raise ValueError("workers cannot be negative")

        if cpu < 0:
            raise ValueError("cpu cannot be negative")

        if memory_mb < 0:
            raise ValueError("memory_mb cannot be negative")


@dataclass
class ReliabilityState:
    """Runtime reliability information for a task."""

    attempts: int = 0
    last_error: str | None = None
    timed_out: bool = False
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def record_attempt(self) -> None:
        """Record a new execution attempt."""

        self.attempts += 1
        self.timed_out = False
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def record_failure(self, error: str) -> None:
        """Record an execution failure."""

        self.last_error = str(error)
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def record_timeout(self) -> None:
        """Record an execution timeout."""

        self.timed_out = True
        self.last_error = "Task execution timed out."
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def reset_attempt(self) -> None:
        """Reset runtime reliability state."""

        self.attempts = 0
        self.last_error = None
        self.timed_out = False
        self.updated_at = datetime.now(timezone.utc).isoformat()
