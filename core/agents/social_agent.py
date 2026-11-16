"""MARK-L Social Media specialist agent."""

from __future__ import annotations

import json

from .base import BaseAgent
from .task import AgentTask
from .result import AgentResult
from core.llm_client import call_llm_text
from actions.web_search import web_search


class SocialAgent(BaseAgent):
    """Researches social-media evidence and reports supported findings."""

    name = "social_agent"

    description = (
        "Analyzes social-media trends, gaming audiences, competitor content, "
        "and content opportunities using supplied live web evidence."
    )

    @staticmethod
    def _validate_analysis(analysis: str) -> str:
        """
        Deterministic evidence guard.

        Prevents unsupported commercial/POD conclusions from being
        passed through when the supplied evidence only establishes
        general gaming or social-media behavior.
        """
        if not analysis:
            return analysis

        import re

        commercial_patterns = [
            r"gaming[- ]themed\\s+print[- ]on[- ]demand.*(?:opportunit|viable|profit|demand|sales|revenue|customer|cater)",
            r"print[- ]on[- ]demand.*(?:can|could|will|would|is|are).*(?:cater|opportunit|viable|demand|profit|sales|revenue)",
            r"(?:content|clips|influencers|audience).*?(?:can|could|will|would|is|are).*?(?:viable opportunity|commercial opportunity|business opportunity).*?(?:print[- ]on[- ]demand|pod)",
            r"(?:gaming|gaming-themed).*?(?:viable opportunity|commercial opportunity|business opportunity).*?(?:print[- ]on[- ]demand|pod)",
            r"\\bviable opportunity\\b",
            r"\\bcommercial opportunity\\b",
            r"\\bbusiness opportunity\\b",
        ]

        if any(
            re.search(pattern, analysis, re.IGNORECASE | re.DOTALL)
            for pattern in commercial_patterns
        ):
            guard_message = (
                "\\n\\nEVIDENCE GUARD:\\n"
                "The available evidence does not establish a commercial "
                "opportunity, product demand, customer demand, profitability, "
                "or viability for a gaming-themed print-on-demand business. "
                "General gaming audience activity, social-media engagement, "
                "influencer activity, or content popularity cannot by itself "
                "establish those business outcomes."
            )

            if "EVIDENCE GUARD:" not in analysis:
                return analysis + guard_message

        return analysis

    def run(self, task: AgentTask) -> AgentResult:
        """Research social opportunities and return an evidence-bounded brief."""

        context = task.context or {}

        try:
            # --------------------------------------------------------------
            # STEP 1 — Generate focused search queries.
            # --------------------------------------------------------------
            query_prompt = f"""
You are the MARK-L Social Media Agent.

Create up to 3 focused web-search queries for the social-media objective below.

OBJECTIVE:
{task.objective}

CONTEXT:
{context}

Focus on:
- current social-media trends
- gaming audience behavior
- TikTok, Instagram, and YouTube Shorts
- competitor content strategies
- content opportunities

Return ONLY valid JSON:

{{
  "queries": [
    "query 1",
    "query 2",
    "query 3"
  ]
}}

Do not explain your choices.
""".strip()

            queries = []

            try:
                query_response = call_llm_text(
                    prompt=query_prompt,
                    system=(
                        "You are the MARK-L Social Media research planner. "
                        "Return valid JSON only."
                    ),
                    timeout=45,
                )

                try:
                    query_data = json.loads(query_response)
                except json.JSONDecodeError:
                    query_data = {}

                raw_queries = query_data.get("queries", [])

                if isinstance(raw_queries, list):
                    queries = [
                        str(q).strip()
                        for q in raw_queries
                        if str(q).strip()
                    ][:3]

            except Exception as exc:
                print(
                    "[SocialAgent] Query planner unavailable; "
                    f"using objective fallback. ({exc})"
                )

            # Query-planner failure must not prevent research.
            if not queries:
                queries = [task.objective]

            query_label = "query" if len(queries) == 1 else "queries"

            print(
                f"[SocialAgent] Using {len(queries)} research {query_label}."
            )

            # --------------------------------------------------------------
            # STEP 2 — Live web research.
            # --------------------------------------------------------------
            research_results = []

            for query in queries:
                print(f"[SocialAgent] Web research: {query}")

                try:
                    result = web_search(
                        parameters={
                            "query": query,
                            "mode": "research",
                        }
                    )
                except Exception as exc:
                    result = f"Web search failed: {exc}"

                research_results.append(
                    {
                        "query": query,
                        "result": result,
                    }
                )

            # --------------------------------------------------------------
            # STEP 3 — Determine usable evidence.
            # --------------------------------------------------------------
            def _is_successful_result(result) -> bool:
                text = str(result or "").strip()

                if not text:
                    return False

                failure_prefixes = (
                    "No results found",
                    "No news found",
                    "No search results found",
                    "Search failed",
                    "Web search failed",
                )

                return not text.startswith(failure_prefixes)

            source_count = sum(
                1
                for item in research_results
                if _is_successful_result(item.get("result"))
            )

            if source_count == 0:
                return AgentResult(
                    agent_name=self.name,
                    task_id=task.task_id,
                    status="FAILED",
                    summary=(
                        "Social Agent could not obtain usable live web "
                        "research."
                    ),
                    findings=[],
                    data={
                        "objective": task.objective,
                        "context": context,
                        "queries": queries,
                        "research_results": research_results,
                        "successful_searches": 0,
                    },
                    errors=[
                        "All social-media searches returned no usable evidence."
                    ],
                )

            # --------------------------------------------------------------
            # STEP 4 — Supply ONLY successful evidence to the analyzer.
            # --------------------------------------------------------------
            evidence = "\n\n".join(
                f"=== SOCIAL SEARCH {i} ===\n"
                f"QUERY: {item['query']}\n"
                f"{item['result']}"
                for i, item in enumerate(research_results, 1)
                if _is_successful_result(item.get("result"))
            )

            # --------------------------------------------------------------
            # STEP 5 — Evidence-bounded analysis.
            # --------------------------------------------------------------
            analysis_prompt = f"""
You are the MARK-L Social Media Agent.

You are an evidence analyst, NOT a business strategist.

Analyze ONLY the supplied live web-search evidence.

OBJECTIVE:
{task.objective}

CONTEXT:
{context}

LIVE WEB RESEARCH:
{evidence}

NON-NEGOTIABLE EVIDENCE RULES:

1. SOURCE-BOUND CLAIMS
- Every factual claim must be directly supported by the supplied evidence.
- Attribute important factual claims to the relevant search result/source.
- Do not silently combine unrelated sources into a stronger claim.
- Do not strengthen, generalize, or reinterpret what a source actually says.

2. NO INFERENCE FROM RELATED TOPICS
Do NOT infer:
- gaming popularity -> gaming merchandise demand
- gaming audience size -> willingness to pay
- social-media activity -> product demand
- social engagement -> sales or conversion
- gaming trends -> print-on-demand opportunity
- platform activity -> platform effectiveness
- industry growth -> profitability
- audience interest -> customer intent to purchase

These relationships require direct evidence.

3. BUSINESS CLAIMS REQUIRE DIRECT BUSINESS EVIDENCE
Do NOT claim that a gaming-themed POD business, product, niche, platform, or strategy is:
- an opportunity
- promising
- viable
- profitable
- successful
- in demand
- commercially attractive
- high potential
- likely to succeed

unless the supplied evidence directly establishes that specific claim.

If the evidence does not establish a requested business conclusion, write:
"The available evidence does not establish this."

4. STATISTICS
- Preserve statistics exactly as supported by the evidence.
- Keep projections clearly identified as projections.
- Keep historical data clearly identified as historical.
- Never turn a projected market size into current sales or current demand.
- Never turn a CAGR into proof of commercial success for the user's specific business.

5. TRENDS
Only describe something as a trend when the supplied evidence explicitly establishes a trend or provides sufficient time-based evidence.
A single article, prediction, statistic, or snapshot does not automatically establish a trend.

6. PLATFORM CLAIMS
Do not rank TikTok, Instagram, YouTube, or any other platform unless the supplied evidence directly compares them.
Mentioning a platform in a source does NOT prove that it is effective, dominant, best, or suitable for the user's business.

7. COMPETITOR CLAIMS
Do not claim that competitors are successful, profitable, growing, or effective unless the supplied evidence directly establishes that.
Do not infer competition from the mere existence of businesses, products, accounts, or creators.

8. OBSERVATION VS INTERPRETATION
Clearly distinguish:
- what the supplied source directly reports
- what a source predicts or interprets
- what cannot be established from the evidence

A source's interpretation is not automatically an independently verified fact.

9. INSUFFICIENT EVIDENCE
When evidence is insufficient, say so directly.
Do not fill evidence gaps using general knowledge, intuition, assumptions, or plausible-sounding business reasoning.

10. RECOMMENDATIONS
Do not convert weak evidence into strategic recommendations.
You may identify what additional evidence would be useful.
Do not recommend spending money, launching products, choosing a platform, or changing strategy based only on general gaming or social activity.

11. SOURCE SCOPE
The supplied evidence may contain outdated, speculative, promotional, projected, or incomplete information.
Preserve those limitations.
Do not present predictions as facts.

12. FINAL CLAIM CHECK
Before producing each finding, ask:
"Can this exact claim be supported directly by the supplied evidence?"
If NO, remove it or state:
"The available evidence does not establish this."

Produce a concise social-media evidence report using exactly these sections:

SUMMARY:
A short summary of what the supplied evidence directly supports. Do not make a business-opportunity conclusion unless directly established.

KEY FINDINGS:
- List only findings supported by the supplied evidence.
- Attribute important factual claims to the relevant search result/source.
- Keep projections, predictions, and historical information explicitly labelled.

CONTENT OPPORTUNITIES:
- Only identify content opportunities when the evidence directly supports them.
- Gaming activity or popularity alone does NOT establish a POD opportunity.
- If unsupported, state: "The available evidence does not establish this."

PLATFORM STRATEGY:
- Report only platform-specific evidence actually present in the supplied research.
- Do not rank or recommend platforms without direct comparative evidence.
- If unsupported, state: "The available evidence does not establish this."

IMPORTANT CONSIDERATIONS:
- State important evidence limitations, missing data, conflicts, outdated information, or uncertainty.

NEXT STEPS:
- Only identify additional evidence that would reduce uncertainty.
- Do not turn unsupported assumptions into business recommendations.

Do not invent statistics, sources, trends, customer behavior, product demand, revenue, sales, conversion, profitability, market size, or commercial viability.

Return ONLY the report.
""".strip()

            try:
                analysis = call_llm_text(
                    prompt=analysis_prompt,
                    system=(
                        "You are the MARK-L Social Media Agent. "
                        "Produce evidence-bounded analysis only. "
                        "Never invent or strengthen evidence. "
                        "Attribute factual claims to supplied sources. "
                        "Explicitly state when evidence is insufficient."
                    ),
                    timeout=180,
                )

                analysis = self._validate_analysis(analysis)

            except Exception as exc:
                return AgentResult(
                    agent_name=self.name,
                    task_id=task.task_id,
                    status="PARTIAL",
                    summary=(
                        "Social Agent obtained live web evidence, but "
                        "local analysis could not be completed."
                    ),
                    findings=[
                        "Live social-media evidence was collected, "
                        "but the local LLM analysis step failed."
                    ],
                    data={
                        "objective": task.objective,
                        "context": context,
                        "queries": queries,
                        "research_results": research_results,
                        "successful_searches": source_count,
                        "analysis_error": str(exc),
                    },
                    errors=[
                        f"Local Social Agent analysis failed: {exc}"
                    ],
                )

            status = "SUCCESS"

            if source_count < len(queries):
                status = "PARTIAL"

            return AgentResult(
                agent_name=self.name,
                task_id=task.task_id,
                status=status,
                summary=(
                    "Social Agent completed live social-media research."
                    if status == "SUCCESS"
                    else "Social Agent completed with partial live web evidence."
                ),
                findings=[analysis],
                data={
                    "objective": task.objective,
                    "context": context,
                    "queries": queries,
                    "research_results": research_results,
                    "successful_searches": source_count,
                },
            )

        except Exception as exc:
            return AgentResult(
                agent_name=self.name,
                task_id=task.task_id,
                status="FAILED",
                summary="Social Agent failed to complete social-media research.",
                errors=[str(exc)],
            )
