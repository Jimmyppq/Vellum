import json
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.models.request import MessageRequest
from app.models.response import ErrorResponse
from app.api.v1.deps import resolve_adapter

router = APIRouter()

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
    "Connection": "keep-alive",
}


@router.post("/stream")
async def stream(request: MessageRequest):
    # El breaker se comprueba antes de abrir el SSE: el 503 sale como JSON normal
    adapter = resolve_adapter(request.provider)

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
