import asyncio
from fastapi import APIRouter
from app.models.response import HealthResponse, ProviderStatus
from app.core.registry import registry
from app.middleware.rate_limit import get_store_status

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health():
    providers = registry.list_providers()
    store_status = get_store_status()
    if not providers:
        return HealthResponse(status="degraded", providers={}, rate_limit_store=store_status)

    # get_unchecked: el health consulta el adapter aunque su breaker esté
    # abierto (registry.get lanzaría ProviderUnavailable y rompería el check)
    results = await asyncio.gather(
        *[registry.get_unchecked(p).health() for p in providers],
        return_exceptions=True,
    )

    provider_statuses: dict[str, str] = {}
    overall = "ok"
    for name, result in zip(providers, results):
        if isinstance(result, Exception):
            provider_statuses[name] = f"error: {result}"
            overall = "degraded"
        elif result.get("status") != "ok":
            provider_statuses[name] = f"error: {result.get('detail', 'desconocido')}"
            overall = "degraded"
        else:
            provider_statuses[name] = "ok"

    return HealthResponse(status=overall, providers=provider_statuses, rate_limit_store=store_status)


@router.get("/providers", response_model=list[ProviderStatus])
async def providers():
    names = registry.list_providers()
    results = await asyncio.gather(
        *[registry.get_unchecked(p).health() for p in names],
        return_exceptions=True,
    )
    return [
        ProviderStatus(
            name=name,
            status="ok" if not isinstance(r, Exception) and r.get("status") == "ok" else "error",
            detail=None if not isinstance(r, Exception) and r.get("status") == "ok" else str(r),
            circuit=registry.get_circuit_state(name),
        )
        for name, r in zip(names, results)
    ]
