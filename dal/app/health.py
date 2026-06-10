from fastapi import APIRouter

from app.database import _provider
from app.schemas.responses import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health():
    db_ok = await _provider.health_check()
    return HealthResponse(status="ok" if db_ok else "degraded", db=db_ok)
