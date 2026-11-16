"""MARK-L Phase 4B research specialist agent."""

from __future__ import annotations

import json

from .base import BaseAgent
from .task import AgentTask
from .result import AgentResult
from core.llm_client import call_llm_text
from actions.web_search import web_search


class ResearchAgent(BaseAgent):
    """Researches topics using MARK-L's existing web-search system."""

    name = "research_agent"

    description = (
        "Researches a topic using MARK-L's live web-search capability, "
        "then analyzes and structures the findings for the Master Agent."
    )

    def run(self, task: AgentTask) -> AgentResult:
        """Execute live research and return a structured AgentResult."""

        context = task.context or {}

        try:
            query_prompt = f"""
You are the MARK-L Research Agent.

Create up to 3 focused research queries for the objective below.

OBJECTIVE:
{task.objective}

CONTEXT:
{context}

Return ONLY valid JSON:

{{
  "queries": [
    "query 1",
    "query 2",
    "query 3"
  ]
}}

Make the queries specific enough to retrieve useful current information.
Do not explain your choices.
""".strip()

            query_response = call_llm_text(
                prompt=query_prompt,
                system=(
                    "You are the MARK-L research-query planner. "
                    "Return valid JSON only."
                ),
                timeout=60,
            )

            try:
                query_data = json.loads(query_response)
            except json.JSONDecodeError:
                query_data = {"queries": [task.objective]}

            queries = query_data.get("queries", [])

            if not isinstance(queries, list):
                queries = []

            queries = [
                str(q).strip()
                for q in queries
                if str(q).strip()
            ][:3]

            if not queries:
                queries = [task.objective]

            research_results = []

            for query in queries:
                print(f"[ResearchAgent] Web research: {query}")

                result = web_search(
                    parameters={
                        "query": query,
                        "mode": "research",
                    }
                )

                research_results.append(
                    {
                        "query": query,
                        "result": result,
                    }
                )

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

            # If no live search produced usable evidence, do not ask the
            # language model to manufacture a research brief from nothing.
            if source_count == 0:
                return AgentResult(
                    agent_name=self.name,
                    task_id=task.task_id,
                    status="FAILED",
                    summary=(
                        "Research Agent could not obtain usable live web "
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
                        "All research searches returned no usable evidence."
                    ],
                )

            evidence = "\n\n".join(
                f"=== SEARCH {i} ===\n"
                f"QUERY: {item['query']}\n"
                f"{item['result']}"
                for i, item in enumerate(research_results, 1)
                if _is_successful_result(item.get("result"))
            )

            analysis_prompt = f"""
You are the MARK-L Research Agent.

Analyze ONLY the supplied live web-search evidence.

OBJECTIVE:
{task.objective}

CONTEXT:
{context}

LIVE WEB RESEARCH:
{evidence}

Produce a concise research brief using exactly these sections:

SUMMARY:
A short evidence-based overview.

KEY FINDINGS:
- Finding 1
- Finding 2
- Finding 3

SOURCES:
- List important source titles or URLs explicitly present in the research.

IMPORTANT CONSIDERATIONS:
- Mention uncertainty, conflicting information, limitations, or missing data.

NEXT STEPS:
- Give practical next steps based only on the available evidence.

EVIDENCE RULES:
- Use only the supplied research as evidence.
- Do not invent sources.
- Do not invent statistics, dates, companies, events, or market figures.
- Do not use outside knowledge to fill gaps.
- Distinguish directly observed evidence from inference.
- Do not treat one source as universal evidence.
- Do not call something a trend unless the supplied evidence supports a trend.
- Do not claim consensus unless multiple supplied sources support it.
- If evidence is insufficient, explicitly say so.
- If sources conflict, report the conflict instead of choosing a side without evidence.
- Do not claim to have performed actions.
- Do not purchase, publish, delete, message, or modify anything.
""".strip()

            analysis = call_llm_text(
                prompt=analysis_prompt,
                system=(
                    "You are the MARK-L Research Agent. "
                    "Analyze supplied live web research carefully. "
                    "Never invent sources or unsupported facts. "
                    "When evidence is insufficient, say so explicitly."
                ),
                timeout=60,
            )

            status = "SUCCESS"

            if source_count < len(queries):
                status = "PARTIAL"

            return AgentResult(
                agent_name=self.name,
                task_id=task.task_id,
                status=status,
                summary=(
                    "Research Agent completed live web research."
                    if status == "SUCCESS"
                    else "Research Agent completed with partial live web evidence."
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
                summary="Research Agent failed to complete live web research.",
                errors=[str(exc)],
            )
