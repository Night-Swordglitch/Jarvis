from core.reliability import (
    RetryPolicy,
    ResourcePolicy,
    ReliabilityState,
)


print("=== PHASE 6 STEP 10 RELIABILITY + RESOURCE TEST ===")


# ------------------------------------------------------------
# 1. Retry policy
# ------------------------------------------------------------

retry = RetryPolicy(
    max_attempts=3,
    retryable_errors=("temporary", "timeout"),
)

assert retry.max_attempts == 3
assert retry.can_retry(1, "temporary failure") is True
assert retry.can_retry(2, "timeout occurred") is True
assert retry.can_retry(3, "temporary failure") is False
assert retry.can_retry(1, "permanent failure") is False

print("Retry policy: PASS")


# ------------------------------------------------------------
# 2. Invalid retry policy
# ------------------------------------------------------------

try:
    RetryPolicy(max_attempts=0)
    raise AssertionError("Expected invalid max_attempts to fail")
except ValueError:
    pass

print("Retry validation: PASS")


# ------------------------------------------------------------
# 3. Resource policy
# ------------------------------------------------------------

resources = ResourcePolicy(
    max_workers=3,
    max_cpu=8,
    max_memory_mb=16384,
)

assert resources.max_workers == 3
assert resources.max_cpu == 8
assert resources.max_memory_mb == 16384

assert resources.can_allocate(
    workers=1,
    cpu=2,
    memory_mb=4096,
) is True

assert resources.can_allocate(
    workers=4,
    cpu=2,
    memory_mb=4096,
) is False

assert resources.can_allocate(
    workers=1,
    cpu=9,
    memory_mb=4096,
) is False

assert resources.can_allocate(
    workers=1,
    cpu=2,
    memory_mb=20000,
) is False

print("Resource policy: PASS")


# ------------------------------------------------------------
# 4. Resource allocation
# ------------------------------------------------------------

resources.allocate(
    workers=1,
    cpu=2,
    memory_mb=4096,
)

assert resources.used_workers == 1
assert resources.used_cpu == 2
assert resources.used_memory_mb == 4096

print("Resource allocation: PASS")


# ------------------------------------------------------------
# 5. Resource release
# ------------------------------------------------------------

resources.release(
    workers=1,
    cpu=2,
    memory_mb=4096,
)

assert resources.used_workers == 0
assert resources.used_cpu == 0
assert resources.used_memory_mb == 0

print("Resource release: PASS")


# ------------------------------------------------------------
# 6. Reliability state
# ------------------------------------------------------------

state = ReliabilityState()

assert state.attempts == 0
assert state.last_error is None
assert state.timed_out is False

state.record_attempt()

assert state.attempts == 1

state.record_failure("temporary failure")

assert state.last_error == "temporary failure"

state.record_attempt()

assert state.attempts == 2

print("Reliability state: PASS")


# ------------------------------------------------------------
# 7. Timeout state
# ------------------------------------------------------------

state.record_timeout()

assert state.timed_out is True
assert state.last_error == "Task execution timed out."

print("Timeout tracking: PASS")


# ------------------------------------------------------------
# 8. Retry decision
# ------------------------------------------------------------

state.reset_attempt()

assert state.attempts == 0
assert state.last_error is None
assert state.timed_out is False

assert retry.can_retry(1, "temporary failure") is True
assert retry.can_retry(3, "temporary failure") is False

print("Retry decision: PASS")


# ------------------------------------------------------------
# 9. Resource policy validation
# ------------------------------------------------------------

try:
    ResourcePolicy(max_workers=0)
    raise AssertionError("Expected invalid max_workers to fail")
except ValueError:
    pass

try:
    ResourcePolicy(max_cpu=-1)
    raise AssertionError("Expected invalid max_cpu to fail")
except ValueError:
    pass

try:
    ResourcePolicy(max_memory_mb=-1)
    raise AssertionError("Expected invalid memory limit to fail")
except ValueError:
    pass

print("Resource validation: PASS")


print()
print("PHASE 6 STEP 10: ALL TESTS PASSED")
