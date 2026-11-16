"""MARK-L Analytics Agent."""

from __future__ import annotations

import json

from .base import BaseAgent
from .task import AgentTask
from .result import AgentResult
from ..llm_client import call_llm_text


class AnalyticsAgent(BaseAgent):
    """Analyzes supplied business metrics and identifies patterns."""

    name = "analytics_agent"

    description = (
        "Analyzes business metrics, sales, traffic, conversion data, "
        "product performance, trends, and anomalies."
    )

    def run(self, task: AgentTask) -> AgentResult:
        data = task.context.get("analytics_data", task.context)

        prompt = f"""
You are the MARK-L Analytics Agent.

Analyze ONLY the supplied business data.

OBJECTIVE:
{task.objective}

DATA:
{json.dumps(data, ensure_ascii=False, indent=2, default=str)}

EVIDENCE RULES:
- Use only information explicitly present in DATA.
- Do not invent, estimate, assume, or fill in missing numbers.
- Do not introduce outside facts, benchmarks, market averages, or
  industry assumptions.
- Do not call a metric high, low, good, bad, strong, weak, abnormal,
  successful, or unsuccessful unless the supplied data contains a
  clear benchmark or comparison that supports that description.
- A single snapshot is NOT a trend.
- Only describe a trend when multiple time points or another explicit
  comparison in DATA supports it.
- Only identify an anomaly when the supplied data provides enough
  evidence to establish that it differs meaningfully from an expected
  or comparison value.
- Do not create correlations or causal explanations unless DATA directly
  supports them.
- If evidence is insufficient, explicitly state that the evidence is
  insufficient.
- Distinguish observed facts from interpretations.
- Do not turn missing data into a problem unless its absence directly
  prevents the requested analysis.
- Do not invent opportunities, risks, problems, or recommendations that
  are not supported by the supplied data.

Return concise analysis with exactly these sections:

SUMMARY
KEY METRICS
TRENDS
ANOMALIES
AREAS NEEDING ATTENTION
NEXT STEPS

For each section, stay grounded in DATA.
If a section cannot be supported by the supplied data, say:
"Insufficient data to determine."

Do not perform or recommend purchases, publishing, deletion,
account changes, financial transactions, or other consequential actions.
"""
        analysis = call_llm_text(prompt)

        return AgentResult(
            agent_name=self.name,
            task_id=task.task_id,
            status="SUCCESS",
            summary="Analytics Agent completed business analysis.",
            findings=[analysis],
            data={
                "analytics_data": data,
            },
        )
