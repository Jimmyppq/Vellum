import json
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from app.models.request import MessageRequest
from app.models.response import ErrorResponse
from app.core.registry import registry

router = APIRouter()

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
    "Connection": "keep-alive",
}


@router.post("/stream")
async def stream(request: MessageRequest):
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

    async def event_generator():
        try:
            async for chunk in adapter.stream(request):
                yield f"data: {chunk.model_dump_json()}\n\n"
        except Exception as e:
            error = ErrorResponse(code="STREAM_ERROR", message=str(e), provider=request.provider)
            yield f"data: {json.dumps({'error': True, **error.model_dump()})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )
