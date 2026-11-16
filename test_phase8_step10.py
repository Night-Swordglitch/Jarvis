from core.action_execution import ActionExecution, ActionExecutionStatus
from core.retry_policy import RetryPolicy


def check(label, condition):
    print(f"{label}: {'PASS' if condition else 'FAIL'}")
    if not condition:
        raise AssertionError(label)


print("=== PHASE 8J - FAILURE / RETRY POLICY TEST ===")

policy = RetryPolicy(max_attempts=3)

failed = ActionExecution(
    action="test_action",
    capability="READ",
    mission_id="mission-8j",
    task_id="task-8j",
)

failed.transition(ActionExecutionStatus.POLICY_CHECK)
failed.transition(ActionExecutionStatus.AUTHORIZED)
failed.transition(ActionExecutionStatus.EXECUTING)
failed.transition(ActionExecutionStatus.FAILED)

decision = policy.decide(failed, attempt=1)

check("Failed execution is retryable", decision.allowed is True)
check("Retry decision records attempt", decision.attempt == 1)
check("Retry decision records maximum attempts", decision.max_attempts == 3)
check("Retry decision serializes", isinstance(decision.to_dict(), dict))

final_attempt = policy.decide(failed, attempt=3)

check("Maximum attempts prevent retry", final_attempt.allowed is False)

succeeded = ActionExecution(
    action="test_action",
    capability="READ",
    mission_id="mission-8j",
    task_id="task-success",
)

succeeded.transition(ActionExecutionStatus.POLICY_CHECK)
succeeded.transition(ActionExecutionStatus.AUTHORIZED)
succeeded.transition(ActionExecutionStatus.EXECUTING)
succeeded.transition(ActionExecutionStatus.SUCCEEDED)

check(
    "Succeeded execution is not retryable",
    policy.is_retryable(succeeded) is False,
)

blocked = ActionExecution(
    action="test_action",
    capability="READ",
    mission_id="mission-8j",
    task_id="task-blocked",
)

blocked.transition(ActionExecutionStatus.POLICY_CHECK)
blocked.transition(ActionExecutionStatus.BLOCKED)

check(
    "Blocked execution is not retryable",
    policy.is_retryable(blocked) is False,
)

timed_out = ActionExecution(
    action="test_action",
    capability="READ",
    mission_id="mission-8j",
    task_id="task-timeout",
)

timed_out.transition(ActionExecutionStatus.POLICY_CHECK)
timed_out.transition(ActionExecutionStatus.AUTHORIZED)
timed_out.transition(ActionExecutionStatus.EXECUTING)
timed_out.transition(ActionExecutionStatus.TIMED_OUT)

check(
    "Timed-out execution is retryable",
    policy.is_retryable(timed_out) is True,
)

check(
    "Retry policy exposes no execution runner",
    not hasattr(policy, "_action_runner")
    and not hasattr(policy, "execute"),
)

check(
    "Retry policy exposes no permission authority",
    not hasattr(policy, "check_permission")
    and not hasattr(policy, "approve"),
)

check(
    "Retry policy exposes no replanning authority",
    not hasattr(policy, "replan")
    and not hasattr(policy, "propose"),
)

print()
print("PHASE 8J: FAILURE / RETRY POLICY - PASS")
