from app.core.registry import ProviderRegistry
from unittest.mock import MagicMock


def test_register_and_get():
    reg = ProviderRegistry()
    adapter = MagicMock()
    reg.register("Anthropic", adapter)
    assert reg.get("anthropic") is adapter
    assert reg.get("ANTHROPIC") is adapter


def test_get_unknown_returns_none():
    reg = ProviderRegistry()
    assert reg.get("proveedor-desconocido") is None


def test_list_providers():
    reg = ProviderRegistry()
    reg.register("openai", MagicMock())
    reg.register("anthropic", MagicMock())
    providers = reg.list_providers()
    assert set(providers) == {"openai", "anthropic"}
