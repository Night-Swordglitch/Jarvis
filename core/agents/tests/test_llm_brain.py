"""Phase 2A — isolated local LLM brain test."""

from core.llm_client import call_llm_text


def main() -> None:
    print()
    print("=" * 60)
    print("MARK-L LOCAL LLM BRAIN TEST")
    print("=" * 60)

    system = """
You are the planning brain of a hierarchical multi-agent system.

You are NOT executing actions.
You are NOT controlling the computer.
You are NOT browsing the internet.

Your only job is to identify which specialist agents would be
useful for a given objective.

Available specialists:

- research: investigates information and trends
- analytics: analyzes metrics and performance
- product: evaluates products and product opportunities
- social: analyzes social-media activity and content performance
- finance: analyzes business financial information
- content: develops content concepts and drafts
- store: analyzes ecommerce/store information

For this test, return ONLY a comma-separated list of the
specialist names you would use.

Do not explain your answer.
"""

    objective = (
        "Analyze why an online store's sales have dropped "
        "and determine what parts of the business need investigation."
    )

    print()
    print("[1] Objective:")
    print("    ", objective)

    print()
    print("[2] Asking local LLM for specialist selection...")
    print()

    response = call_llm_text(
        prompt=objective,
        system=system,
        timeout=60,
    )

    if not isinstance(response, str):
        raise TypeError(
            f"Expected string response, got {type(response).__name__}"
        )

    response = response.strip()

    if not response:
        raise RuntimeError("LLM returned an empty response.")

    print("[3] Raw LLM response:")
    print("    ", response)

    # Basic validation only.
    # We are NOT trusting the model to execute anything.
    available = {
        "research",
        "analytics",
        "product",
        "social",
        "finance",
        "content",
        "store",
    }

    selected = [
        item.strip().lower()
        for item in response.split(",")
        if item.strip()
    ]

    recognized = [
        item for item in selected
        if item in available
    ]

    print()
    print("[4] Recognized specialists:")
    print("    ", recognized)

    if not recognized:
        raise RuntimeError(
            "The LLM response contained no recognized specialist names."
        )

    print()
    print("=" * 60)
    print("PHASE 2A LLM BRAIN TEST: PASSED")
    print("=" * 60)
    print()


if __name__ == "__main__":
    main()
