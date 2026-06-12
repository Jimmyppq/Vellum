import json
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from app.core.rate_limiter import RateLimiter

_limiter: RateLimiter | None = None
_store_status: str = "memory"


def get_limiter() -> RateLimiter | None:
    return _limiter


def set_limiter(limiter: RateLimiter) -> None:
    global _limiter
    _limiter = limiter


def get_store_status() -> str:
    """Tipo de store decidido en el arranque ('memory', 'redis' o
    'memory (degraded)'); lo reporta /health sin tocar Redis."""
    return _store_status


def set_store_status(status: str) -> None:
    global _store_status
    _store_status = status


class RateLimitMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next) -> Response:
        limiter = get_limiter()
        if limiter is None:
            return await call_next(request)

        provider = None
        if request.method == "POST" and request.url.path in ("/v1/message", "/v1/stream", "/v1/embed"):
            try:
                body = await request.json()
                provider = body.get("provider")
            except Exception:
                pass

        if provider:
            result = await limiter.check_request(provider)
            if not result.allowed:
                body = json.dumps({
                    "code": "RATE_LIMIT_EXCEEDED",
                    "limit_type": result.limit_type,
                    "provider": provider,
                    "retry_after_seconds": result.retry_after_seconds,
                })
                return Response(
                    content=body,
                    status_code=429,
                    media_type="application/json",
                    headers={"Retry-After": str(result.retry_after_seconds)},
                )

        response = await call_next(request)

        if provider and result.allowed:
            await limiter.record_request(provider)
            remaining_rpm = result.remaining_rpm
            remaining_tpm = result.remaining_tpm
            if remaining_rpm is not None:
                response.headers["X-RateLimit-Remaining-RPM"] = str(max(0, remaining_rpm - 1))
            if remaining_tpm is not None:
                response.headers["X-RateLimit-Remaining-TPM"] = str(remaining_tpm)

        return response
