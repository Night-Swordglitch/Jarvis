"""Management dashboard API integration for the existing MARK-L dashboard server."""

from __future__ import annotations

from typing import Any, Callable

from fastapi import Request
from core.management.dashboard import DashboardProjector


class ManagementDashboardAPI:
    """Attach read-only management state endpoints to DashboardServer."""

    def __init__(
        self,
        server: Any,
        projector: DashboardProjector,
    ) -> None:
        if server is None:
            raise TypeError("server must not be None")

        if not isinstance(projector, DashboardProjector):
            raise TypeError("projector must be DashboardProjector")

        self.server = server
        self.projector = projector
        self._installed = False

    def install(self) -> None:
        """Install the authenticated management-state endpoint once."""

        if self._installed:
            return

        app = getattr(self.server, "app", None)

        if app is None:
            raise TypeError("server must expose a FastAPI app")

        from fastapi.responses import JSONResponse

        def _auth(req: Request) -> bool:
            tok = (
                req.headers
                .get("authorization", "")
                .removeprefix("Bearer ")
                .strip()
            )

            tokens = getattr(self.server, "_tokens", set())

            return bool(tok) and tok in tokens

        @app.get("/api/management/state")
        async def management_state(req: Request):
            if not _auth(req):
                return JSONResponse(
                    {"error": "Unauthorized"},
                    status_code=401,
                )

            snapshot = self.projector.snapshot()

            return JSONResponse(snapshot.to_dict())

        self._installed = True

    @property
    def installed(self) -> bool:
        return self._installed

    def snapshot(self) -> dict[str, Any]:
        """Return the same read-only projection exposed by the API."""
        return self.projector.snapshot().to_dict()

