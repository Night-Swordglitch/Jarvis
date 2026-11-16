from pathlib import Path
from tempfile import TemporaryDirectory

from core.mission_memory import MissionMemory, MissionMemoryRecord


print("=== PHASE 7F — PERSISTENT MISSION MEMORY TEST ===")

with TemporaryDirectory() as temp:
    path = Path(temp) / "missions.json"

    memory = MissionMemory(path)

    assert len(memory) == 0
    print("Mission memory foundation: PASS")

    record = MissionMemoryRecord(
        mission_id="mission-7f-001",
        objective="Launch a new POD product.",
        status="COMPLETED",
        context={
            "constraints": ["budget limited"],
            "success_criteria": ["validated product"],
        },
    )

    print("Mission memory record: PASS")

    record.add_task({
        "task_id": "task-001",
        "objective": "Research product demand.",
        "status": "COMPLETED",
    })

    print("Mission context persistence model: PASS")

    record.add_evidence_reference("evidence-001")
    record.add_evidence_reference("evidence-001")

    assert record.evidence_ids == ["evidence-001"]

    print("Evidence references remain deduplicated: PASS")

    record.add_decision({
        "decision": "Proceed with product validation.",
        "source": "management",
    })

    record.add_approval({
        "action": "publish_result",
        "status": "APPROVED",
    })

    record.add_outcome({
        "result": "Validation completed.",
    })

    print("Mission decisions and outcomes: PASS")

    memory.save(record)

    assert path.exists()
    assert len(memory) == 1

    print("Mission persisted to disk: PASS")

    restarted = MissionMemory(path)
    loaded = restarted.get("mission-7f-001")

    assert loaded is not None
    assert loaded.mission_id == record.mission_id
    assert loaded.objective == record.objective
    assert loaded.status == "COMPLETED"
    assert loaded.context == record.context
    assert loaded.tasks == record.tasks
    assert loaded.evidence_ids == ["evidence-001"]
    assert loaded.decisions == record.decisions
    assert loaded.approvals == record.approvals
    assert loaded.outcomes == record.outcomes

    print("Mission survives simulated process restart: PASS")

    second = MissionMemoryRecord(
        mission_id="mission-7f-002",
        objective="Research another product.",
        status="PLANNING",
    )

    restarted.save(second)

    assert len(restarted) == 2
    assert restarted.get("mission-7f-001").objective == (
        "Launch a new POD product."
    )
    assert restarted.get("mission-7f-002").objective == (
        "Research another product."
    )

    print("Multiple missions remain independent: PASS")

    latest = restarted.latest()

    assert latest is not None
    assert latest.mission_id == "mission-7f-002"

    print("Latest mission retrieval: PASS")

    restored = MissionMemoryRecord.from_dict(
        loaded.to_dict()
    )

    assert restored.to_dict() == loaded.to_dict()

    print("Mission memory serialization round-trip: PASS")

    forbidden = {
        "run",
        "execute",
        "approve",
        "resolve",
        "dispatch",
    }

    assert not forbidden.intersection(dir(MissionMemory))
    assert not forbidden.intersection(dir(MissionMemoryRecord))

    print("No execution / approval authority: PASS")


print()
print("==============================================")
print("PHASE 7F FOUNDATION: ALL TESTS PASSED")
print("PERSISTENT MISSION MEMORY: PASS")
print("==============================================")
