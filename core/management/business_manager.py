from __future__ import annotations

from typing import Any

from core.management.base_manager import BaseManager


class BusinessManager(BaseManager):
    """
    Specialist manager for business-operation missions.

    Business Manager coordinates business-domain work. It does not execute
    specialist agents directly and does not make final system-wide decisions.
    """

    MANAGER_TYPE = "BUSINESS"

    _KEYWORDS = (
        "business",
        "business plan",
        "company",
        "startup",
        "commerce",
        "ecommerce",
        "e-commerce",
        "store",
        "shop",
        "product",
        "sales",
        "marketing",
        "revenue",
        "customer",
        "market",
        "niche",
        "pod",
        "print on demand",
        "print-on-demand",
        "brand",
        "content business",
    )

    def __init__(
        self,
        management_manager,
        event_bus,
        *,
        name: str | None = None,
        event_handler=None,
    ) -> None:
        super().__init__(
            management_manager,
            event_bus,
            name=name or "Business Manager",
            event_handler=event_handler,
        )

    # ------------------------------------------------------------------
    # Domain routing
    # ------------------------------------------------------------------

    def accepts(self, objective: str) -> bool:
        """Return whether this manager can coordinate the objective."""
        text = str(objective).strip().lower()

        return any(
            keyword in text
            for keyword in self._KEYWORDS
        )

    # ------------------------------------------------------------------
    # Deferred specialist task specifications
    # ------------------------------------------------------------------

    def prepare_research_task(
        self,
        objective: str,
        *,
        priority: int = 60,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._prepare_task(
            objective=objective,
            agent_name="research_agent",
            priority=priority,
            context=context,
            role="business_research",
        )

    def prepare_social_task(
        self,
        objective: str,
        *,
        priority: int = 50,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._prepare_task(
            objective=objective,
            agent_name="social_agent",
            priority=priority,
            context=context,
            role="business_social_research",
        )

    def prepare_analytics_task(
        self,
        objective: str,
        *,
        priority: int = 50,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._prepare_task(
            objective=objective,
            agent_name="analytics_agent",
            priority=priority,
            context=context,
            role="business_analytics",
        )

    # ------------------------------------------------------------------
    # Business planning
    # ------------------------------------------------------------------

    def prepare_business_plan(
        self,
        objective: str,
        *,
        context: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Prepare the default business-operation work package.

        Research, social research, and analytics are independent evidence
        gathering tasks. A later synthesis task can depend on all three.

        This method only describes work. It does not execute any agent.
        """
        base_context = dict(context or {})

        return [
            {
                "id": "business_research",
                **self.prepare_research_task(
                    objective,
                    context=base_context,
                ),
            },
            {
                "id": "business_social",
                **self.prepare_social_task(
                    objective,
                    context=base_context,
                ),
            },
            {
                "id": "business_analytics",
                **self.prepare_analytics_task(
                    objective,
                    context=base_context,
                ),
            },
            {
                "id": "business_evaluation",
                "manager": self.name,
                "manager_type": self.MANAGER_TYPE,
                "agent_name": None,
                "objective": (
                    "Evaluate the business evidence collected for: "
                    f"{objective}"
                ),
                "priority": 70,
                "context": base_context,
                "role": "business_evaluation",
                "execution": "DEFERRED",
                "dependencies": [
                    "business_research",
                    "business_social",
                    "business_analytics",
                ],
            },
        ]

    def create_business_tasks(
        self,
        objective: str,
        *,
        context: dict[str, Any] | None = None,
    ) -> list[str]:
        """
        Create the business work package in the real management system.

        ManagementManager remains responsible for creating TaskManager tasks
        and registering dependency relationships.

        No specialist agent is executed here.
        """
        plan = self.prepare_business_plan(
            objective,
            context=context,
        )

        return self.management_manager.create_planned_tasks(plan)

    # ------------------------------------------------------------------
    # Task specifications
    # ------------------------------------------------------------------

    def _prepare_task(
        self,
        *,
        objective: str,
        agent_name: str,
        priority: int,
        context: dict[str, Any] | None,
        role: str,
    ) -> dict[str, Any]:
        return {
            "manager": self.name,
            "manager_type": self.MANAGER_TYPE,
            "agent_name": agent_name,
            "objective": str(objective),
            "priority": int(priority),
            "context": dict(context or {}),
            "role": role,
            "execution": "DEFERRED",
            "dependencies": [],
        }
