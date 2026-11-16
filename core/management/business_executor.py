"""Business task execution bridge for MARK-L."""

from __future__ import annotations

from typing import Any

from core.agents.dispatcher import AgentDispatcher
from core.agents.result import AgentResult
from core.agents.task import AgentTask
from core.management.evidence import EvidenceRecord, EvidenceStore
from core.management.state import TaskState


class BusinessTaskExecutor:
    """Execute business specialist tasks through AgentDispatcher."""

    def __init__(
        self,
        dispatcher: AgentDispatcher,
        evidence_store: EvidenceStore,
        *,
        mission_id: str,
    ) -> None:
        if not isinstance(dispatcher, AgentDispatcher):
            raise TypeError("dispatcher must be AgentDispatcher")

        if not isinstance(evidence_store, EvidenceStore):
            raise TypeError("evidence_store must be EvidenceStore")

        mission_id = str(mission_id).strip()

        if not mission_id:
            raise ValueError("mission_id cannot be empty")

        self.dispatcher = dispatcher
        self.evidence_store = evidence_store
        self.mission_id = mission_id

    def run(self, task: TaskState) -> AgentResult | dict[str, Any]:
        """Execute one management task through AgentDispatcher."""

        if not isinstance(task, TaskState):
            raise TypeError("task must be TaskState")

        if not task.agent_name:
            return {
                "status": "MANAGEMENT_ONLY",
                "task_id": task.task_id,
                "objective": task.objective,
            }

        context = dict(task.metadata.get("context") or {})

        agent_task = AgentTask(
            objective=task.objective,
            context=context,
            requested_by="business_manager",
            priority=task.priority,
            task_id=task.task_id,
        )

        result = self.dispatcher.dispatch(
            task.agent_name,
            agent_task,
        )

        if not isinstance(result, AgentResult):
            raise TypeError(
                "AgentDispatcher returned an invalid result"
            )

        self._record_evidence(task, result)

        return result.to_dict()

    def _record_evidence(
        self,
        task: TaskState,
        result: AgentResult,
    ) -> None:
        """Record successful/partial specialist output."""

        if not result.success:
            return

        source = f"agent:{result.agent_name}"

        claims: list[tuple[str, dict[str, Any]]] = []

        if result.summary:
            claims.append(
                (
                    result.summary,
                    {
                        "result_status": result.status,
                        "result": result.to_dict(),
                    },
                )
            )

        for finding in result.findings:
            if str(finding).strip():
                claims.append(
                    (
                        str(finding),
                        {
                            "result_status": result.status,
                            "result": result.to_dict(),
                        },
                    )
                )

        for claim, details in claims:
            self.evidence_store.add(
                EvidenceRecord(
                    mission_id=self.mission_id,
                    task_id=task.task_id,
                    agent_name=result.agent_name,
                    source=source,
                    claim=claim,
                    details=details,
                    status="UNVERIFIED",
                )
            )

