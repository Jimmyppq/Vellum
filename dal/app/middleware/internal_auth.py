import logging

from fastapi import Request
from fastapi.responses import JSONResponse

from app.config import get_settings

logger = logging.getLogger(__name__)

_settings = get_settings()

EXEMPT_PATHS = {"/health"}


class InternalAuthMiddleware:
    """Token-based internal auth for dev environments (MTLS_ENABLED=false)."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path in EXEMPT_PATHS or _settings.MTLS_ENABLED:
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        token = request.headers.get("X-Internal-Service-Token", "")

        if not _settings.INTERNAL_SERVICE_TOKEN:
            # No token configured — pass through with warning (logged at startup)
            await self.app(scope, receive, send)
            return

        if not token:
            response = JSONResponse(
                status_code=401,
                content={"error": {
                    "code": "MISSING_SERVICE_TOKEN",
                    "message": "X-Internal-Service-Token header is required",
                    "trace_id": getattr(request.state, "trace_id", ""),
                }},
            )
            await response(scope, receive, send)
            return

        if token != _settings.INTERNAL_SERVICE_TOKEN:
            response = JSONResponse(
                status_code=401,
                content={"error": {
                    "code": "INVALID_SERVICE_TOKEN",
                    "message": "Invalid X-Internal-Service-Token",
                    "trace_id": getattr(request.state, "trace_id", ""),
                }},
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)


def warn_if_token_missing() -> None:
    if not _settings.MTLS_ENABLED and not _settings.INTERNAL_SERVICE_TOKEN:
        logger.warning(
            "INTERNAL_SERVICE_TOKEN is not configured. All internal requests will be accepted without authentication.",
            extra={"action": "startup.auth_check", "status": "warning"},
        )
