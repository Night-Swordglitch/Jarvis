"""
MARK-L Agent System

The agent layer sits above MARK-L's existing action/plugin system.
"""

from .task import AgentTask
from .result import AgentResult
from .base import BaseAgent
from .registry import AgentRegistry
from .dispatcher import AgentDispatcher
from .master import MasterAgent
from .diagnostic_agent import DiagnosticAgent
from .research_agent import ResearchAgent
from .social_agent import SocialAgent
from .analytics_agent import AnalyticsAgent

__all__ = [
    "AgentTask",
    "AgentResult",
    "BaseAgent",
    "AgentRegistry",
    "AgentDispatcher",
    "MasterAgent",
    "DiagnosticAgent",
    "ResearchAgent",
    "SocialAgent",
    "AnalyticsAgent",
]
