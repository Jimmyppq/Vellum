from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import configure_logging, get_settings
from app.database import init_db
from app.middleware.internal_auth import InternalAuthMiddleware, warn_if_token_missing
from app.middleware.trace_id import TraceIdMiddleware

settings = get_settings()
configure_logging(settings.LOG_LEVEL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    warn_if_token_missing()
    if settings.ENV == "dev":
        # In dev, auto-create tables for convenience.
        # In staging/prod schema changes go through Alembic migrations only —
        # never through the application on startup.
        await init_db()
    yield


app = FastAPI(title="Vellum DAL", version="1.0.0", lifespan=lifespan)

# Middleware — order matters: trace_id must run first so auth can read it
app.add_middleware(InternalAuthMiddleware)
app.add_middleware(TraceIdMiddleware)


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
