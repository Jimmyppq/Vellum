import logging
import time
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("router-ai.audit")


class AuditLogMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = str(uuid.uuid4())
        trace_id = request.headers.get("X-Trace-Id") or str(uuid.uuid4())
        request.state.request_id = request_id
        request.state.trace_id = trace_id
        start = time.monotonic()

        response = await call_next(request)

        duration_ms = round((time.monotonic() - start) * 1000, 2)
        status_code = response.status_code
        log_level = logging.WARNING if status_code >= 400 else logging.INFO

        logger.log(
            log_level,
            "%s %s",
            request.method,
            request.url.path,
            extra={
                "request_id": request_id,
                "trace_id": trace_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": status_code,
                "duration_ms": duration_ms,
            },
        )

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Trace-Id"] = trace_id
        return response
