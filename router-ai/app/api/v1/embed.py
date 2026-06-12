import uuid
from fastapi import APIRouter, HTTPException, Request, status
from app.models.request import EmbedRequest
from app.models.response import ApiResponse, Meta, EmbedResponse, ErrorResponse
from app.core.registry import registry
from app.api.v1.deps import resolve_adapter

router = APIRouter()


@router.post("/embed", response_model=ApiResponse)
async def embed(request: EmbedRequest, http_request: Request):
    request_id = getattr(http_request.state, "request_id", str(uuid.uuid4()))
    trace_id = getattr(http_request.state, "trace_id", None)

    adapter = resolve_adapter(request.provider, trace_id)
    try:
        result: EmbedResponse = await adapter.embed(request)
        registry.record_success(request.provider)
        return ApiResponse(data=result.model_dump(), meta=Meta(request_id=request_id))
    except NotImplementedError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=ErrorResponse(
                code="CAPABILITY_NOT_SUPPORTED",
                message="Este proveedor no soporta embeddings.",
                trace_id=trace_id,
                provider=request.provider,
            ).model_dump(),
        )
    except Exception as e:
        registry.record_failure(request.provider)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=ErrorResponse(
                code="PROVIDER_ERROR",
                message=str(e),
                trace_id=trace_id,
                provider=request.provider,
            ).model_dump(),
        )
