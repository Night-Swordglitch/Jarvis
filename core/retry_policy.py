"""Phase 8J - Failure and retry policy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.action_execution import ActionExecution, ActionExecutionStatus


RETRYABLE_STATUSES = frozenset({
    ActionExecutionStatus.FAILED,
    ActionExecutionStatus.TIMED_OUT,
})


@dataclass(frozen=True)
class RetryDecision:
    allowed: bool
    reason: str
    attempt: int
    max_attempts: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "attempt": self.attempt,
            "max_attempts": self.max_attempts,
        }


class RetryPolicy:
    """Decides whether a failed execution may be retried."""

    def __init__(self, *, max_attempts: int = 3) -> None:
        if not isinstance(max_attempts, int):
            raise TypeError("max_attempts must be an integer.")
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1.")
        self.max_attempts = max_attempts

    def decide(
        self,
        execution: ActionExecution,
        *,
        attempt: int = 1,
    ) -> RetryDecision:
        if not isinstance(execution, ActionExecution):
            raise TypeError("execution must be an ActionExecution.")
        if not isinstance(attempt, int):
            raise TypeError("attempt must be an integer.")
        if attempt < 1:
            raise ValueError("attempt must be at least 1.")

        if execution.status not in RETRYABLE_STATUSES:
            return RetryDecision(
                False,
                "Execution is not in a retryable terminal state.",
                attempt,
                self.max_attempts,
            )

        if attempt >= self.max_attempts:
            return RetryDecision(
                False,
                "Maximum retry attempts have been reached.",
                attempt,
                self.max_attempts,
            )

        return RetryDecision(
            True,
            "Execution may be retried.",
            attempt,
            self.max_attempts,
        )

    def is_retryable(self, execution: ActionExecution) -> bool:
        if not isinstance(execution, ActionExecution):
            raise TypeError("execution must be an ActionExecution.")
        return execution.status in RETRYABLE_STATUSES
