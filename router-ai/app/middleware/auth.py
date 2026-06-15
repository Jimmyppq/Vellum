import json
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from app.core.auth import verify_api_key
from app.core.config import settings

DOC_PATHS = {"/docs", "/openapi.json", "/redoc"}


def excluded_paths(env: str) -> set[str]:
    """Paths exentos de API key. La documentación solo queda abierta en dev;
    /v1/health siempre (probes y load balancers)."""
    paths = {"/v1/health"}
    if env == "dev":
        paths |= DOC_PATHS
    return paths


class APIKeyMiddleware(BaseHTTPMiddleware):

    def __init__(self, app, env: str | None = None):
        super().__init__(app)
        self._excluded = excluded_paths(env if env is not None else settings.env)

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in self._excluded:
            return await call_next(request)

        if not verify_api_key(request):
            missing = "X-API-Key" not in request.headers
            msg = "Header X-API-Key requerido" if missing else "API key inválida"
            body = json.dumps({"code": "UNAUTHORIZED", "message": msg})
            return Response(content=body, status_code=401, media_type="application/json")

        return await call_next(request)
