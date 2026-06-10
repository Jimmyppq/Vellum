from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import configure_logging, get_settings
from app.database import verify_schema_version
from app.middleware.internal_auth import InternalAuthMiddleware, warn_if_token_missing
from app.middleware.trace_id import TraceIdMiddleware

settings = get_settings()
configure_logging(settings.LOG_LEVEL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    warn_if_token_missing()
    # The service never runs DDL in any environment: migrations are applied
    # exclusively by the dal-migrate ephemeral container (alembic upgrade head).
    # Startup aborts if the schema is not at the Alembic head.
    await verify_schema_version()
    yield


app = FastAPI(title="Vellum DAL", version="1.0.0", lifespan=lifespan)

# Middleware — order matters: trace_id must run first so auth can read it
app.add_middleware(InternalAuthMiddleware)
app.add_middleware(TraceIdMiddleware)


# HTTPExceptions raised by routers carry detail={"code": ..., "message": ...};
# wrap them in the standard error envelope with the request trace_id
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    trace_id = getattr(request.state, "trace_id", "")
    if isinstance(exc.detail, dict):
        code = exc.detail.get("code", "ERROR")
        message = exc.detail.get("message", "")
    else:
        code = "ERROR"
        message = str(exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": code, "message": message, "trace_id": trace_id}},
        headers=exc.headers,
    )


# Standard error handler for HTTPException details
@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception):
    trace_id = getattr(request.state, "trace_id", "")
    return JSONResponse(
        status_code=500,
        content={"error": {
            "code": "INTERNAL_SERVER_ERROR",
            "message": "An unexpected error occurred",
            "trace_id": trace_id,
        }},
    )


# Routers
from app.health import router as health_router  # noqa: E402
from app.routers.config import router as config_router  # noqa: E402
from app.routers.connectors import router as connectors_router  # noqa: E402
from app.routers.executions import router as executions_router  # noqa: E402
from app.routers.prompts import router as prompts_router  # noqa: E402
from app.routers.transcripts import router as transcripts_router  # noqa: E402
from app.routers.users import router as users_router  # noqa: E402

app.include_router(health_router)
app.include_router(prompts_router)
app.include_router(executions_router)
app.include_router(users_router)
app.include_router(transcripts_router)
app.include_router(connectors_router)
app.include_router(config_router)
