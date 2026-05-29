from fastapi import APIRouter
from app.api.v1 import chat, stream, embed, health

router = APIRouter(prefix="/v1")
router.include_router(chat.router)
router.include_router(stream.router)
router.include_router(embed.router)
router.include_router(health.router)
