from core.external_integration import ExternalIntegrationContract
from core.plugin_loader import PluginRecord, PluginRegistry


calls = []


def plugin_run(parameters, **kwargs):
    calls.append({
        "parameters": dict(parameters),
        "kwargs": dict(kwargs),
    })
    return "external integration completed"


registry = PluginRegistry(
    {
        "test_external": PluginRecord(
            name="test_external",
            description="Test external integration",
            parameters={
                "type": "OBJECT",
                "properties": {},
            },
            run=plugin_run,
            file="test_external.py",
            valid=True,
        )
    },
    logger=lambda _message: None,
)

contract = ExternalIntegrationContract(registry)


def check(label, condition):
    print(f"{label}: {'PASS' if condition else 'FAIL'}")
    if not condition:
        raise AssertionError(label)


print("=== PHASE 8I - EXTERNAL INTEGRATION CONTRACT TEST ===")

check(
    "Existing PluginRegistry accepted",
    contract.registry() is registry,
)

check(
    "External integration discovered",
    contract.has("test_external"),
)

result = contract.run(
    "test_external",
    {"query": "MARK-L"},
)

check(
    "External integration executes through existing registry",
    result == "external integration completed",
)

check(
    "Existing plugin handler executed",
    len(calls) == 1,
)

check(
    "Parameters preserved",
    calls[0]["parameters"]["query"] == "MARK-L",
)

check(
    "Tool declarations exposed",
    len(contract.declarations()) == 1
    and contract.declarations()[0]["name"] == "test_external",
)

check(
    "Scheduling delegates to registry",
    contract.scheduling("test_external") is None,
)

check(
    "Unknown integration does not execute",
    contract.run("missing_external", {}) ==
    "Plugin 'missing_external' is not available.",
)

check(
    "Contract exposes no permission authority",
    not hasattr(contract, "approve")
    and not hasattr(contract, "check_permission"),
)

check(
    "Contract exposes no capability classifier",
    not hasattr(contract, "classify")
    and not hasattr(contract, "capability_for_action"),
)

check(
    "Contract does not replace PluginRegistry",
    contract.registry() is registry,
)

print()
print("PHASE 8I: EXTERNAL INTEGRATION CONTRACT - PASS")
