import json
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from app.core.auth import verify_api_key

EXCLUDED_PATHS = {"/v1/health"}


class APIKeyMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in EXCLUDED_PATHS:
            return await call_next(request)

        if not verify_api_key(request):
            missing = "X-API-Key" not in request.headers
            msg = "Header X-API-Key requerido" if missing else "API key inválida"
            body = json.dumps({"code": "UNAUTHORIZED", "message": msg})
            return Response(content=body, status_code=401, media_type="application/json")

        return await call_next(request)
