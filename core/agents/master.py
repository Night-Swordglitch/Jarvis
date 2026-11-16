from __future__ import annotations

import asyncio
import json
from typing import Any

from core.llm_client import call_llm_text

from .base import BaseAgent
from .dispatcher import AgentDispatcher
from .registry import AgentRegistry
from .result import AgentResult
from .task import AgentTask


class MasterAgent(BaseAgent):
    """
    Top-level orchestrator for the MARK-L agent system.

    The Master:
      1. Receives an objective.
      2. Uses the local LLM to determine which registered agents are relevant.
      3. Validates the LLM's selections against the real registry.
      4. Dispatches selected agents concurrently.
      5. Uses the local LLM to synthesize their findings.
    """

    name = "master"
    description = "Coordinates specialist agents and synthesizes their results."

    def __init__(
        self,
        registry: AgentRegistry,
        dispatcher: AgentDispatcher | None = None,
    ) -> None:
        self.registry = registry
        self.dispatcher = dispatcher or AgentDispatcher(registry)

    @property
    def available_agents(self) -> list[str]:
        return [
            agent.name
            for agent in self.registry.all()
            if agent.name != self.name
        ]

    def create_task(
        self,
        objective: str,
        context: dict[str, Any] | None = None,
    ) -> AgentTask:
        return AgentTask(
            objective=objective,
            context=context or {},
            requested_by=self.name,
        )

    def choose_agents(
        self,
        objective: str,
        context: dict[str, Any] | None = None,
    ) -> list[str]:
        """Ask the local LLM which registered agents are relevant."""

        available = self.available_agents

        if not available:
            return []

        context = context or {}

        prompt = f"""
You are the planning brain of MARK-L.

Your job is ONLY to select which specialist agents should handle
the user's objective.

OBJECTIVE:
{objective}

CONTEXT:
{json.dumps(context, ensure_ascii=False, default=str)}

AVAILABLE SPECIALIST AGENTS:
{json.dumps(available, ensure_ascii=False)}

Rules:
1. Select only agents from the AVAILABLE SPECIALIST AGENTS list.
2. Select only agents genuinely relevant to the objective.
3. Do not invent agent names.
4. Use as few agents as reasonably necessary.
5. Do not perform the task yourself.
6. Do not execute tools or actions.
7. Return JSON only.

Required JSON format:
{{
  "agents": ["agent_name_1", "agent_name_2"],
  "reason": "brief explanation"
}}
""".strip()

        try:
            response = call_llm_text(
                prompt=prompt,
                system=(
                    "You are the MARK-L Master Agent planner. "
                    "Return valid JSON only."
                ),
                timeout=60,
            )

            parsed = self._parse_json(response)

            if not isinstance(parsed, dict):
                return []

            selected = parsed.get("agents", [])

            if not isinstance(selected, list):
                return []

            valid = set(available)
            chosen: list[str] = []

            for name in selected:
                if not isinstance(name, str):
                    continue

                name = name.strip()

                if name in valid and name not in chosen:
                    chosen.append(name)

            return chosen

        except Exception:
            return []

    @staticmethod
    def _parse_json(response: str) -> Any:
        """Parse normal or fenced JSON returned by the LLM."""

        text = (response or "").strip()

        if text.startswith("```"):
            lines = text.splitlines()

            if lines and lines[0].strip().startswith("```"):
                lines = lines[1:]

            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]

            text = "\n".join(lines).strip()

        return json.loads(text)

    async def delegate(
        self,
        agent_name: str,
        task: AgentTask,
    ) -> AgentResult:
        """
        Run blocking specialist work in a worker thread.

        This allows multiple specialists to execute concurrently without
        blocking the asyncio event loop.
        """

        return await asyncio.to_thread(
            self.dispatcher.dispatch,
            agent_name,
            task,
        )

    async def _run_agent(
        self,
        agent_name: str,
        objective: str,
        context: dict[str, Any],
    ) -> AgentResult:
        """Create and dispatch one specialist task."""

        task = self.create_task(
            objective=objective,
            context=context,
        )

        print(f"[Master] Dispatching specialist: {agent_name}")

        result = await self.delegate(
            agent_name=agent_name,
            task=task,
        )

        print(
            f"[Master] Specialist completed: "
            f"{agent_name} -> {result.status}"
        )

        return result

    @staticmethod
    def _validate_synthesis(
        synthesis: str,
        objective: str,
        results: list[AgentResult],
    ) -> str:
        """
        Deterministic post-synthesis evidence guard.

        The local LLM can produce a polished report that still promotes
        specialist interpretation into an unsupported business conclusion.
        This final guard removes that class of leakage without attempting
        to rewrite the entire report.
        """

        report = (synthesis or "").strip()

        if not report:
            return (
                "EXECUTIVE SUMMARY\n\n"
                "Commercial viability cannot be determined from the available "
                "evidence."
            )

        objective_lower = (objective or "").lower()

        business_terms = (
            "business",
            "commercial",
            "viability",
            "viable",
            "opportunity",
            "profitable",
            "profitability",
            "demand",
            "revenue",
            "sales",
            "market",
        )

        if not any(term in objective_lower for term in business_terms):
            return report

        # Collect only evidence from specialists that actually returned a
        # usable result. Failed specialists contribute no evidence.
        evidence_parts: list[str] = []

        for result in results:
            if not result.success:
                continue

            if result.summary:
                evidence_parts.append(result.summary)

            evidence_parts.extend(result.findings or [])

            if isinstance(result.data, dict) and result.data:
                evidence_parts.append(
                    json.dumps(
                        result.data,
                        ensure_ascii=False,
                        default=str,
                    )
                )

        evidence_text = " ".join(evidence_parts).lower()

        # Direct business evidence must be concrete. Generic popularity,
        # activity, growth, or social engagement does not qualify.
        direct_business_evidence_terms = (
            "revenue",
            "profit",
            "sales",
            "conversion",
            "customer purchase",
            "customers purchased",
            "willingness to pay",
            "paid orders",
            "units sold",
            "average order value",
            "gross margin",
            "net margin",
            "actual demand",
        )

        has_direct_business_evidence = any(
            term in evidence_text
            for term in direct_business_evidence_terms
        )

        if has_direct_business_evidence:
            return report

        # HARD EVIDENCE MODE
        #
        # If the supplied specialists contain no direct business evidence,
        # do not allow the LLM's synthesized prose to survive. The LLM may
        # repeatedly rephrase an unsupported conclusion even after individual
        # phrases are filtered. Instead, construct a deterministic report from
        # specialist execution status only.
        #
        # This prevents:
        #   "has potential"
        #   "suggests potential"
        #   "there may be a market"
        #   "encouraging"
        #   "promising"
        #   and similar rewordings from escaping the evidence boundary.

        status_lines: list[str] = []

        for result in results:
            status = (result.status or "UNKNOWN").upper()

            if status == "FAILED":
                status_lines.append(
                    f"- {result.agent_name}: FAILED ? evidence unavailable."
                )
            elif status == "PARTIAL":
                status_lines.append(
                    f"- {result.agent_name}: PARTIAL ? only partial evidence "
                    f"was available."
                )
            elif status == "SUCCESS":
                status_lines.append(
                    f"- {result.agent_name}: COMPLETED ? however, the supplied "
                    f"result did not contain direct business evidence."
                )
            else:
                status_lines.append(
                    f"- {result.agent_name}: {status}."
                )

        limitation = (
            "Commercial viability cannot be determined from the available "
            "evidence."
        )

        deterministic_report = (
            "EXECUTIVE SUMMARY\n\n"
            f"{limitation}\n\n"
            "The available specialist results do not establish product "
            "demand, willingness to pay, conversion, revenue, profit, or "
            "commercial viability.\n\n"
            "KEY FINDINGS\n\n"
            "No direct business outcome evidence was supplied. General "
            "topic activity, audience activity, or social-platform activity "
            "cannot by itself establish commercial viability.\n\n"
            "CROSS-AGENT INSIGHTS\n\n"
            "The available evidence does not provide cross-agent support "
            "for a commercial viability conclusion.\n\n"
            "RISKS OR GAPS\n\n"
            + "\n".join(status_lines)
            + "\n\n"
            "NEXT STEPS\n\n"
            "Additional direct business evidence would be required, such as "
            "actual sales, revenue, conversion, paid orders, willingness "
            "to pay, units sold, margins, or other directly supplied "
            "business-performance data."
        )

        return deterministic_report

        # Unsupported positive interpretations that should not survive as
        # conclusions about the specific business.
        import re

        unsupported_positive_patterns = (
            r"\bhas potential\b",
            r"\bhave potential\b",
            r"\bshows potential\b",
            r"\bshow potential\b",
            r"\bhigh potential\b",
            r"\bstrong potential\b",
            r"\bpromising opportunity\b",
            r"\bstrong opportunity\b",
            r"\bgood opportunity\b",
            r"\bgreat opportunity\b",
            r"\bviable business\b",
            r"\bcommercially viable\b",
            r"\bfinancially viable\b",
            r"\bprofitable business\b",
            r"\blikely to succeed\b",
            r"\bwill succeed\b",
            r"\bcustomers will buy\b",
            r"\bstrong demand\b",
            r"\bhigh demand\b",
            r"\bencouraging\b",
            r"\bpromising\b",
            r"\bfavorable\b",
            r"\bfavourable\b",
            r"\bpositive sign\b",
            r"\bpositive indicator\b",
            r"\bsuggests an opportunity\b",
            r"\bsuggests opportunity\b",
        )

        sanitized = report

        # Remove entire sentences containing unsupported business
        # conclusions rather than replacing each match independently.
        for pattern in unsupported_positive_patterns:
            sentence_pattern = re.compile(
                r"[^.?!\n]*(?:" + pattern + r")[^.?!\n]*[.?!]?",
                re.IGNORECASE,
            )
            sanitized = sentence_pattern.sub("", sanitized)

        # Remove repeated evidence-limit sentences generated by either the
        # LLM or an earlier validator pass.
        limitation_sentence = (
            "Commercial viability cannot be determined from the available "
            "evidence."
        )

        sanitized = re.sub(
            r"(?:\s*" + re.escape(limitation_sentence) + r"){2,}",
            " " + limitation_sentence,
            sanitized,
            flags=re.IGNORECASE,
        )

        # Clean whitespace created by sentence removal.
        sanitized = re.sub(r"[ \t]+", " ", sanitized)
        sanitized = re.sub(r"\n[ \t]+\n", "\n\n", sanitized)
        sanitized = re.sub(r"\n{3,}", "\n\n", sanitized)
        sanitized = sanitized.strip()

        # Guarantee one clear evidence limitation for a business-viability
        # question when no direct business evidence exists.
        if limitation_sentence.lower() not in sanitized.lower():
            sanitized = (
                "EXECUTIVE SUMMARY\n\n"
                + limitation_sentence
                + "\n\n"
                + sanitized
            )

        # Prevent the validator from producing an empty or useless report if
        # all unsupported conclusion sentences were removed.
        if len(sanitized.strip()) < 80:
            sanitized = (
                "EXECUTIVE SUMMARY\n\n"
                + limitation_sentence
                + "\n\n"
                "The available specialist evidence does not establish "
                "product demand, willingness to pay, conversion, revenue, "
                "profit, or commercial viability."
            )

        return sanitized.strip()

    def synthesize(
        self,
        objective: str,
        context: dict[str, Any],
        results: list[AgentResult],
    ) -> AgentResult:
        """
        Use the local LLM to synthesize all successful specialist findings.

        The LLM receives specialist results as evidence and is explicitly
        instructed not to invent information that is absent from them.
        """

        successful = [result for result in results if result.success]
        failed = [result for result in results if not result.success]

        if not successful:
            return AgentResult(
                agent_name=self.name,
                task_id="master-synthesis",
                status="FAILED",
                summary=(
                    f"Master could not complete orchestration for: "
                    f"{objective}"
                ),
                data={
                    "objective": objective,
                    "agents_consulted": [r.agent_name for r in results],
                    "successful_agents": [],
                    "failed_agents": [r.agent_name for r in failed],
                    "results": [r.to_dict() for r in results],
                },
                errors=[
                    error
                    for result in failed
                    for error in result.errors
                ],
            )

        evidence = []
        evidence_status = []

        for result in results:
            evidence_status.append(
                {
                    "agent": result.agent_name,
                    "status": result.status,
                    "summary": result.summary,
                    "successful_searches": result.data.get("successful_searches")
                    if isinstance(result.data, dict)
                    else None,
                }
            )

            if result.success:
                evidence.append(
                    {
                        "agent": result.agent_name,
                        "status": result.status,
                        "summary": result.summary,
                        "findings": result.findings,
                        "data": result.data,
                    }
                )

        evidence_quality = {
            "agents": evidence_status,
            "successful_or_partial_agents": [
                r.agent_name for r in results if r.success
            ],
            "failed_agents": [
                r.agent_name for r in results if not r.success
            ],
        }

        synthesis_prompt = f"""
You are the MARK-L Master Agent.

You have received findings from multiple specialist agents.

Your job is to synthesize their findings into ONE clear, useful report
for the user.

OBJECTIVE:
{objective}

CONTEXT:
{json.dumps(context, ensure_ascii=False, default=str)}

SPECIALIST EVIDENCE:
{json.dumps(evidence, ensure_ascii=False, indent=2, default=str)}

EVIDENCE QUALITY:
{json.dumps(evidence_quality, ensure_ascii=False, indent=2, default=str)}

Rules:
0. Evidence quality takes precedence over plausible, useful-sounding, or
   commercially attractive conclusions.

1. EVIDENCE BOUNDARY
   Use ONLY information contained in SPECIALIST EVIDENCE.
   Do not use general knowledge, model knowledge, assumptions, intuition,
   or unstated background information.

2. FAILED SPECIALISTS
   A specialist with status FAILED provides ZERO usable evidence.
   Never quote, paraphrase, reconstruct, or infer what a FAILED specialist
   might have discovered.
   A FAILED specialist may only be mentioned as an evidence gap.

3. PARTIAL SPECIALISTS
   A specialist with status PARTIAL provides incomplete evidence.
   Every conclusion relying on PARTIAL evidence must preserve that limitation.
   Never present PARTIAL evidence as complete, representative, current,
   comprehensive, or independently validated unless the supplied evidence
   explicitly establishes that fact.

4. ATTRIBUTION
   Every substantive factual claim must be attributable to at least one
   supplied specialist.
   When presenting an important finding, identify the supporting specialist
   explicitly, for example:
   "[Research Agent] reported ..."
   "[Social Agent, PARTIAL] found ..."
   "[Analytics Agent] reported ..."

   A specialist's own conclusion, recommendation, interpretation, or claim
   is NOT automatically established fact. Treat it as a specialist
   interpretation unless the underlying supplied evidence directly supports
   the statement.

   Do not promote statements such as "this has potential", "this is viable",
   "this is profitable", "customers will buy", "this strategy will work",
   or similar conclusions into factual claims unless the supplied evidence
   directly establishes them.

   When useful, distinguish:
   - EVIDENCE: what the supplied sources/data actually establish
   - SPECIALIST INTERPRETATION: what the specialist concluded from that evidence
   - MASTER CONCLUSION: what can legitimately be concluded after applying the
     evidence limitations

   Do not merge separate specialist findings into one apparently independent
   fact unless the supplied evidence actually supports the combination.

5. SOURCE BOUNDARY
   Do not invent, extend, reinterpret, or strengthen sources, statistics,
   dates, trends, events, companies, audiences, market conditions,
   customer behavior, revenue figures, benchmarks, or business outcomes.
   If a specialist supplied a source, preserve the source as reported.
   Do not imply that a source proves more than the supplied evidence says.

6. UNSUPPORTED CONCLUSIONS
   If the available evidence does not support a conclusion, say:
   "Cannot be determined from the available evidence."
   Do not replace insufficient evidence with a plausible-sounding conclusion.

7. OPPORTUNITY CLAIMS
   Do NOT conclude that a business, product, market, niche, channel, or
   strategy is an "opportunity", "promising", "high potential", "viable",
   "successful", "strong", "growing", "profitable", or similar unless the
   supplied evidence directly supports that characterization.
   Evidence that a topic is popular, discussed, viewed, or active does NOT
   by itself establish commercial opportunity, demand, profitability,
   market viability, or likely business success.

8. BUSINESS ANALYSIS
   Do not infer revenue, profit, demand, conversion, customer willingness
   to pay, market size, margins, competition, or financial viability unless
   those facts are explicitly supplied by the specialist evidence.

   Evidence that a broader industry, audience, platform, or topic is growing,
   popular, active, or widely discussed does NOT establish that the user's
   specific business idea will succeed.

   Evidence about social media activity does NOT by itself establish product
   demand, willingness to pay, conversion, revenue, profit, or viability.

   If financial/business evidence is absent, state that the business
   conclusion cannot be determined from the available evidence.

9. METRICS
   Do not call a metric high, low, strong, weak, good, bad, successful,
   unsuccessful, abnormal, or significant unless the supplied evidence
   contains a relevant comparison, benchmark, or explicit characterization.

10. TRENDS
    Do not call something a current trend unless multiple observations,
    time points, or an explicit comparison support that characterization.
    Historical evidence must be identified as historical when relevant.
    Do not silently treat older evidence as current evidence.

11. CROSS-AGENT CONFIRMATION
    If only one specialist supports a claim, present it as coming from that
    specialist?not as independently confirmed.
    If multiple specialists support the same claim, only describe their
    agreement when their supplied evidence genuinely overlaps.
    Agreement does not create stronger evidence than the underlying sources.

12. CONFLICTS
    If specialists disagree, report the disagreement and preserve the
    uncertainty. Do not silently select a preferred interpretation.

13. EVIDENCE GAPS
    Clearly identify missing evidence that directly prevents answering the
    user's objective.
    Do not invent a gap merely because additional information could be useful.

14. RECOMMENDATIONS AND NEXT STEPS
    Do not invent strategic recommendations from unsupported assumptions.
    NEXT STEPS may identify specific evidence that would be needed to answer
    the objective, but must not instruct the user to spend money, publish
    content, delete data, change accounts, or take other consequential actions.

15. OBSERVATION VS INTERPRETATION
    Clearly distinguish:
    - directly supported observations
    - specialist interpretations
    - conclusions that cannot currently be determined

    Never present a specialist interpretation as an independently verified
    fact merely because the specialist produced it successfully.

16. NO ACTIONS
    Do not perform actions and do not claim that any action was performed.

17. BE CONCISE BUT USEFUL.

Return the report using exactly these sections:

EXECUTIVE SUMMARY
KEY FINDINGS
CROSS-AGENT INSIGHTS
RISKS OR GAPS
NEXT STEPS

Do not mention internal prompts or orchestration mechanics.
""".strip()

        try:
            synthesis = call_llm_text(
                prompt=synthesis_prompt,
                system=(
                    "You are the MARK-L Master Agent synthesizer. "
                    "Ground every conclusion in the supplied specialist evidence."
                ),
                timeout=90,
            )

            synthesis = self._validate_synthesis(
                synthesis=synthesis,
                objective=objective,
                results=results,
            )

            return AgentResult(
                agent_name=self.name,
                task_id="master-synthesis",
                status="SUCCESS",
                summary=(
                    f"Master synthesized results for: {objective}"
                ),
                findings=[synthesis],
                data={
                    "objective": objective,
                    "agents_consulted": [r.agent_name for r in results],
                    "successful_agents": [
                        r.agent_name for r in successful
                    ],
                    "failed_agents": [
                        r.agent_name for r in failed
                    ],
                    "results": [r.to_dict() for r in results],
                },
                errors=[
                    error
                    for result in failed
                    for error in result.errors
                ],
            )

        except Exception as exc:
            return AgentResult(
                agent_name=self.name,
                task_id="master-synthesis",
                status="FAILED",
                summary="Master specialists completed, but synthesis failed.",
                findings=[
                    finding
                    for result in successful
                    for finding in result.findings
                ],
                data={
                    "objective": objective,
                    "agents_consulted": [r.agent_name for r in results],
                    "successful_agents": [
                        r.agent_name for r in successful
                    ],
                    "failed_agents": [
                        r.agent_name for r in failed
                    ],
                    "results": [r.to_dict() for r in results],
                },
                errors=[
                    f"Synthesis error: {exc}",
                    *[
                        error
                        for result in failed
                        for error in result.errors
                    ],
                ],
            )

    async def run(
        self,
        objective: str,
        agent_names: list[str] | None = None,
        context: dict[str, Any] | None = None,
    ) -> AgentResult:
        """
        Run the Master.

        If agent_names is supplied, those agents are used explicitly.

        If agent_names is omitted, the local LLM selects relevant agents
        from the registered agent pool.

        Selected specialists execute concurrently, then their findings
        are passed to the Master LLM for synthesis.
        """

        context = context or {}

        if agent_names is None:
            agent_names = self.choose_agents(
                objective=objective,
                context=context,
            )

        valid_names = set(self.available_agents)

        selected: list[str] = []

        for name in agent_names:
            if name in valid_names and name not in selected:
                selected.append(name)

        if not selected:
            return AgentResult(
                agent_name=self.name,
                task_id="master-no-agents",
                status="FAILED",
                summary="No suitable specialist agents were selected.",
                data={
                    "objective": objective,
                    "available_agents": self.available_agents,
                    "agents_consulted": [],
                },
                errors=[
                    "No valid specialist agents were selected for this objective."
                ],
            )

        print(
            f"[Master] Running {len(selected)} specialist(s) concurrently: "
            f"{selected}"
        )

        gathered = await asyncio.gather(
            *[
                self._run_agent(
                    agent_name=agent_name,
                    objective=objective,
                    context=context,
                )
                for agent_name in selected
            ],
            return_exceptions=True,
        )

        results: list[AgentResult] = []

        for agent_name, result in zip(selected, gathered):
            if isinstance(result, AgentResult):
                results.append(result)
                continue

            results.append(
                AgentResult(
                    agent_name=agent_name,
                    task_id="master-dispatch-error",
                    status="FAILED",
                    summary=(
                        f"Master could not collect the result from "
                        f"'{agent_name}'."
                    ),
                    errors=[str(result)],
                )
            )

        print(
            f"[Master] Synthesizing {len(results)} specialist result(s)..."
        )

        return self.synthesize(
            objective=objective,
            context=context,
            results=results,
        )
