import logging
from typing import TYPE_CHECKING
from app.core.circuit_breaker import CircuitBreaker

if TYPE_CHECKING:
    from app.adapters.base import BaseAdapter

logger = logging.getLogger(__name__)


class ProviderRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, "BaseAdapter"] = {}
        self._breakers: dict[str, CircuitBreaker] = {}

    def register(self, name: str, adapter: "BaseAdapter") -> None:
        key = name.lower()
        self._adapters[key] = adapter
        self._breakers[key] = CircuitBreaker(provider=key)
        logger.info("Proveedor registrado: %s", name)

    def get(self, name: str) -> "BaseAdapter | None":
        key = name.lower()
        breaker = self._breakers.get(key)
        if breaker and not breaker.is_available():
            logger.warning("Circuit breaker abierto para '%s'", key)
            return None
        return self._adapters.get(key)

    def record_success(self, name: str) -> None:
        breaker = self._breakers.get(name.lower())
        if breaker:
            breaker.record_success()

    def record_failure(self, name: str) -> None:
        breaker = self._breakers.get(name.lower())
        if breaker:
            breaker.record_failure()

    def list_providers(self) -> list[str]:
        return list(self._adapters.keys())

    def get_circuit_state(self, name: str) -> str | None:
        breaker = self._breakers.get(name.lower())
        return breaker.state if breaker else None

    async def startup(self) -> None:
        from app.core.config import settings
        from app.adapters.anthropic import AnthropicAdapter
        from app.adapters.openai import OpenAIAdapter
        from app.adapters.deepseek import DeepSeekAdapter
        from app.adapters.ollama import OllamaAdapter
        from app.adapters.lmstudio import LMStudioAdapter
        from app.adapters.google import GoogleAdapter

        if settings.anthropic_api_key:
            self.register("anthropic", AnthropicAdapter(settings.anthropic_api_key.get_secret_value()))
        if settings.openai_api_key:
            self.register("openai", OpenAIAdapter(settings.openai_api_key.get_secret_value()))
        if settings.deepseek_api_key:
            self.register("deepseek", DeepSeekAdapter(
                api_key=settings.deepseek_api_key.get_secret_value(),
                base_url=settings.deepseek_base_url,
            ))
        if settings.google_api_key:
            self.register("google", GoogleAdapter(settings.google_api_key.get_secret_value()))
        if settings.ollama_base_url:
            self.register("ollama", OllamaAdapter(base_url=settings.ollama_base_url))
        if settings.lmstudio_base_url:
            self.register("lmstudio", LMStudioAdapter(base_url=settings.lmstudio_base_url))

        if not self._adapters:
            logger.warning("No hay proveedores configurados.")


registry = ProviderRegistry()
