import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logging import setup_logging
from app.core.registry import registry
from app.core.rate_limiter import RateLimiter
from app.middleware.auth import APIKeyMiddleware
from app.middleware.logging import AuditLogMiddleware
from app.middleware.rate_limit import RateLimitMiddleware, set_limiter
from app.api.v1.router import router as v1_router
from app.models.response import ErrorResponse

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(settings.log_level, settings.log_dir)
    logger.info("Iniciando router-ai")

    limiter = RateLimiter(settings.rate_limits_config)
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
app.add_middleware(APIKeyMiddleware)

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

