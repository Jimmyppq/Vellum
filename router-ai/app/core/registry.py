import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.adapters.base import BaseAdapter

logger = logging.getLogger(__name__)


class ProviderRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, "BaseAdapter"] = {}

    def register(self, name: str, adapter: "BaseAdapter") -> None:
        self._adapters[name.lower()] = adapter
        logger.info("Proveedor registrado: %s", name)

    def get(self, name: str) -> "BaseAdapter | None":
        return self._adapters.get(name.lower())

    def list_providers(self) -> list[str]:
        return list(self._adapters.keys())

    async def startup(self) -> None:
        from app.core.config import settings
        from app.adapters.anthropic import AnthropicAdapter
        from app.adapters.openai import OpenAIAdapter
        from app.adapters.deepseek import DeepSeekAdapter
        from app.adapters.ollama import OllamaAdapter
        from app.adapters.lmstudio import LMStudioAdapter

        if settings.anthropic_api_key:
            self.register("anthropic", AnthropicAdapter(settings.anthropic_api_key.get_secret_value()))

        if settings.openai_api_key:
            self.register("openai", OpenAIAdapter(settings.openai_api_key.get_secret_value()))

        if settings.deepseek_api_key:
            self.register("deepseek", DeepSeekAdapter(
                api_key=settings.deepseek_api_key.get_secret_value(),
                base_url=settings.deepseek_base_url,
            ))

        self.register("ollama", OllamaAdapter(base_url=settings.ollama_base_url))
        self.register("lmstudio", LMStudioAdapter(base_url=settings.lmstudio_base_url))

        if not self._adapters:
            logger.warning("No hay proveedores configurados.")


registry = ProviderRegistry()
