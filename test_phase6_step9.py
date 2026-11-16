from core.management.evidence import EvidenceRecord, EvidenceStore


print("=== PHASE 6 STEP 9 MEMORY + EVIDENCE / PROVENANCE TEST ===")


# ------------------------------------------------------------
# 1. Evidence record
# ------------------------------------------------------------

record = EvidenceRecord(
    mission_id="mission-001",
    task_id="task-001",
    agent_name="code_agent",
    source="repository_inspection",
    claim="The repository contains a Python entry point.",
    details={"file": "main.py"},
    status="CONFIRMED",
    confidence=0.95,
)

assert record.mission_id == "mission-001"
assert record.task_id == "task-001"
assert record.agent_name == "code_agent"
assert record.source == "repository_inspection"
assert record.claim == "The repository contains a Python entry point."
assert record.confidence == 0.95

print("Evidence record: PASS")


# ------------------------------------------------------------
# 2. Serialization
# ------------------------------------------------------------

data = record.to_dict()

assert data["evidence_id"] == record.evidence_id
assert data["mission_id"] == "mission-001"
assert data["task_id"] == "task-001"
assert data["agent_name"] == "code_agent"
assert data["source"] == "repository_inspection"
assert data["claim"] == "The repository contains a Python entry point."

print("Evidence serialization: PASS")


# ------------------------------------------------------------
# 3. Store
# ------------------------------------------------------------

store = EvidenceStore()

stored = store.add(record)

assert stored.evidence_id == record.evidence_id
assert store.get(record.evidence_id) is record

print("Evidence storage: PASS")


# ------------------------------------------------------------
# 4. Mission lookup
# ------------------------------------------------------------

mission_records = store.for_mission("mission-001")

assert len(mission_records) == 1
assert mission_records[0].evidence_id == record.evidence_id

print("Mission lookup: PASS")


# ------------------------------------------------------------
# 5. Task lookup
# ------------------------------------------------------------

task_records = store.for_task("task-001")

assert len(task_records) == 1
assert task_records[0].task_id == "task-001"

print("Task lookup: PASS")


# ------------------------------------------------------------
# 6. Agent lookup
# ------------------------------------------------------------

agent_records = store.for_agent("code_agent")

assert len(agent_records) == 1
assert agent_records[0].agent_name == "code_agent"

print("Agent lookup: PASS")


# ------------------------------------------------------------
# 7. Multiple evidence records
# ------------------------------------------------------------

second = EvidenceRecord(
    mission_id="mission-001",
    task_id="task-002",
    agent_name="research_agent",
    source="web_search",
    claim="The required API documentation exists.",
    details={"url": "documentation"},
    status="CONFIRMED",
    confidence=0.88,
)

store.add(second)

assert len(store.for_mission("mission-001")) == 2
assert len(store.for_agent("research_agent")) == 1

print("Multi-source evidence: PASS")


# ------------------------------------------------------------
# 8. Search
# ------------------------------------------------------------

results = store.search("API documentation")

assert len(results) == 1
assert results[0].evidence_id == second.evidence_id

print("Evidence search: PASS")


# ------------------------------------------------------------
# 9. Latest evidence
# ------------------------------------------------------------

latest = store.latest()

assert latest is not None

print("Latest evidence: PASS")


# ------------------------------------------------------------
# 10. Provenance integrity
# ------------------------------------------------------------

assert record.evidence_id != second.evidence_id
assert record.created_at
assert second.created_at

print("Provenance integrity: PASS")


print()
print("PHASE 6 STEP 9: ALL TESTS PASSED")
