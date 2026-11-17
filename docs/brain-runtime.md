# JARVIS Brain Runtime

## Execution path

The live `master_delegate` tool in `main.py` uses `BrainMissionRuntime`:

1. `MasterAgent.create_plan()` calls `GoalPlanner` to create a validated `MissionPlan`.
2. `ManagementManager.accept_mission()` creates the active mission.
3. `MasterAgent.queue_plan()` submits the plan through `BrainManagementBridge`.
4. The bridge translates plan steps into managed tasks and preserves step dependencies.
5. `Scheduler.run(..., task_ids=...)` executes only tasks belonging to this mission.
6. The scheduler calls the registered specialist through `AgentDispatcher`.
7. `TaskManager` owns task state; task events update the stored Brain plan.
8. `MasterAgent.synthesize()` produces the final evidence-grounded report.

A managed `MasterAgent` cannot call its standalone `execute_plan()` path. This prevents two independent executors from running the same plan.

## Authority and approval boundaries

- Planning output is validated against registered specialists.
- Plans do not grant action authority.
- Specialist action requests are collected as data only.
- The Brain runtime does not execute those requests.
- The live host passes requests to `AgentActionExecutor`, which remains subject to the existing approval and permission controls.
- A recovery plan is saved for review. It is not queued or executed automatically.

## Failure and recovery

When a task fails or becomes blocked:

- `MissionMonitor` observes the task events.
- `ReplanningEngine` requests a revised plan using completed, failed, and blocked step context.
- Completed work is supplied as prior evidence and is not scheduled again.
- Exact repeats of completed or failed step objectives are rejected.
- The proposal is stored with status `READY` in `memory/brain_plans.json`.
- The mission is marked failed/needs review; there is no automatic retry.

## State and persistence boundary

`PlanStore` persists Brain plans atomically in `memory/brain_plans.json`.

The current `ManagementState` / `TaskManager` task lifecycle is still in-memory. `BrainManagementBridge.restore_plan()` can reconnect a saved plan to task metadata when the corresponding task state is already loaded, but this is **not yet full process-restart recovery**. Durable task-state storage and a user-approved resume flow remain future work.

## Regression checks

The GitHub Actions workflow compiles the application and Brain modules, runs the focused security/Brain tests, runs Phase 7 mission-management regression scripts, and runs Phase 8D–8L contract scripts.

Run the focused suite locally with:

```powershell
python -m pytest -q tests
```
