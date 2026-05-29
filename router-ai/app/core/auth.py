import secrets
from fastapi import Request
from app.core.config import settings


def verify_api_key(request: Request) -> bool:
    provided = request.headers.get("X-API-Key", "")
    expected = settings.router_ai_api_key.get_secret_value()
    return secrets.compare_digest(provided, expected)
