"""Resolución compartida de adapters para los endpoints v1.

Centraliza la traducción de las excepciones tipadas del registry al contrato
HTTP, de modo que /v1/message, /v1/stream y /v1/embed no puedan divergir:
  - ProviderNotFound    → 422 PROVIDER_NOT_FOUND   (permanente: no reintentar)
  - ProviderUnavailable → 503 PROVIDER_UNAVAILABLE (temporal: Retry-After)
"""
from fastapi import HTTPException, status

from app.core.errors import ProviderNotFound, ProviderUnavailable
from app.core.registry import registry
from app.models.response import ErrorResponse


def resolve_adapter(provider: str, trace_id: str | None = None):
    try:
        return registry.get(provider)
    except ProviderNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=ErrorResponse(
                code="PROVIDER_NOT_FOUND",
                message=str(exc),
                trace_id=trace_id,
                provider=provider,
            ).model_dump(),
        )
    except ProviderUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=ErrorResponse(
                code="PROVIDER_UNAVAILABLE",
                message=str(exc),
                trace_id=trace_id,
                provider=provider,
                retry_after_seconds=exc.retry_after_seconds,
            ).model_dump(),
            headers={"Retry-After": str(exc.retry_after_seconds)},
        )
