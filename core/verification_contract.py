from __future__ import annotations

from typing import Any

from core.management.state import ManagementState
from core.mission_context import MissionContext
from core.mission_verifier import MissionVerifier, VerificationResult


class VerificationContract:
    """Thin execution-layer boundary around the existing MissionVerifier."""

    def __init__(self, verifier: MissionVerifier) -> None:
        if not isinstance(verifier, MissionVerifier):
            raise TypeError("verifier must be a MissionVerifier.")

        self._verifier = verifier

    def verify(
        self,
        *,
        context: MissionContext,
        state: ManagementState,
    ) -> VerificationResult:
        """Delegate verification to the existing read-only verifier."""

        if not isinstance(context, MissionContext):
            raise TypeError("context must be a MissionContext.")

        if not isinstance(state, ManagementState):
            raise TypeError("state must be a ManagementState.")

        return self._verifier.verify(
            context=context,
            state=state,
        )

    @staticmethod
    def serialize(result: VerificationResult) -> dict[str, Any]:
        """Return the existing verification result as serializable data."""

        if not isinstance(result, VerificationResult):
            raise TypeError("result must be a VerificationResult.")

        return result.to_dict()

    def verifier(self) -> MissionVerifier:
        """Return the existing verifier without replacing it."""

        return self._verifier
