import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logging import setup_logging
from app.core.registry import registry
from app.core.rate_limiter import RateLimiter
from app.core.rate_limit_store import (
    InMemoryRateLimitStore,
    RateLimitStore,
    RedisRateLimitStore,
)
from app.middleware.auth import APIKeyMiddleware
from app.middleware.logging import AuditLogMiddleware
from app.middleware.rate_limit import RateLimitMiddleware, set_limiter, set_store_status
from app.api.v1.router import router as v1_router
from app.models.response import ErrorResponse

logger = logging.getLogger(__name__)


async def _build_rate_limit_store() -> tuple[RateLimitStore, str]:
    """Selecciona el store según RATE_LIMIT_STORE. Con redis inaccesible
    arranca degradado a memoria (fail-open) — la URL no se loggea porque
    puede contener credenciales."""
    if settings.rate_limit_store.lower() != "redis":
        return InMemoryRateLimitStore(), "memory"

    import redis.asyncio as aioredis

    client = aioredis.from_url(settings.redis_url)
    try:
        await client.ping()
        logger.info("Rate limiting con RedisRateLimitStore (compartido entre réplicas)")
        return RedisRateLimitStore(client), "redis"
    except Exception:
        logger.error(
            "RATE_LIMIT_STORE=redis pero Redis es inaccesible; "
            "degradado a InMemoryRateLimitStore (los límites no se comparten entre réplicas)"
        )
        try:
            await client.aclose()
        except Exception:
            pass
        return InMemoryRateLimitStore(), "memory (degraded)"


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(settings.log_level, settings.log_dir)
    logger.info("Iniciando router-ai")

    store, store_status = await _build_rate_limit_store()
    set_store_status(store_status)
    limiter = RateLimiter(settings.rate_limits_config, store=store)
    set_limiter(limiter)

    await registry.startup()
    logger.info("Proveedores disponibles: %s", registry.list_providers())

    yield

    logger.info("Apagando router-ai")


app = FastAPI(
    title="router-ai",
    description="Microservicio de enrutamiento unificado para múltiples proveedores LLM",
    version="0.1.0",
    lifespan=lifespan,
)

# Orden de middlewares: auth → rate_limit → audit_log
# Starlette los ejecuta en orden inverso al de add_middleware,
# por lo que el último añadido se ejecuta primero.
app.add_middleware(AuditLogMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(APIKeyMiddleware, env=settings.env)

app.include_router(v1_router)


def _custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
    schema.setdefault("components", {})["securitySchemes"] = {
        "ApiKeyHeader": {"type": "apiKey", "in": "header", "name": "X-API-Key"}
    }
    schema["security"] = [{"ApiKeyHeader": []}]
    app.openapi_schema = schema
    return schema


app.openapi = _custom_openapi  # type: ignore[method-assign]


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Error no controlado en %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            code="INTERNAL_ERROR",
            message="Error interno del servidor.",
        ).model_dump(),
    )

