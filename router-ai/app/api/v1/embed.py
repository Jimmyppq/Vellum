from fastapi import APIRouter, HTTPException, status
from app.models.request import EmbedRequest
from app.models.response import EmbedResponse, ErrorResponse
from app.core.registry import registry

router = APIRouter()


@router.post("/embed", response_model=EmbedResponse)
async def embed(request: EmbedRequest):
    adapter = registry.get(request.provider)
    if adapter is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=ErrorResponse(
                code="PROVIDER_NOT_FOUND",
                message=f"Proveedor '{request.provider}' no está registrado.",
                provider=request.provider,
            ).model_dump(),
        )
    try:
        return await adapter.embed(request)
    except NotImplementedError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=ErrorResponse(
                code="CAPABILITY_NOT_SUPPORTED",
                message="Este proveedor no soporta embeddings.",
                provider=request.provider,
            ).model_dump(),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=ErrorResponse(
                code="PROVIDER_ERROR",
                message=str(e),
                provider=request.provider,
            ).model_dump(),
        )
