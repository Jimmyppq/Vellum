from fastapi import APIRouter, HTTPException, status
from app.models.request import MessageRequest
from app.models.response import MessageResponse, ErrorResponse
from app.core.registry import registry

router = APIRouter()


@router.post("/message", response_model=MessageResponse)
async def message(request: MessageRequest):
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
        return await adapter.message(request)
    except NotImplementedError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=ErrorResponse(
                code="CAPABILITY_NOT_SUPPORTED",
                message="Este proveedor no soporta esta operación.",
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
