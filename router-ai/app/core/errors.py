class RouterError(Exception):
    """Base class for typed router-ai errors."""


class ProviderNotFound(RouterError):
    """El proveedor no está registrado — error permanente, no reintentar."""

    def __init__(self, provider: str) -> None:
        self.provider = provider
        super().__init__(f"Proveedor '{provider}' no está registrado.")


class ProviderUnavailable(RouterError):
    """El proveedor existe pero su circuit breaker está abierto — temporal."""

    def __init__(self, provider: str, retry_after_seconds: int) -> None:
        self.provider = provider
        self.retry_after_seconds = retry_after_seconds
        super().__init__(
            f"Proveedor '{provider}' temporalmente no disponible "
            f"(circuit breaker abierto); reintentar en {retry_after_seconds}s."
        )
