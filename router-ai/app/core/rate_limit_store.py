import time
from abc import ABC, abstractmethod
from collections import defaultdict, deque


class RateLimitStore(ABC):

    @abstractmethod
    def increment(self, key: str, window_seconds: int) -> int:
        """Añade la marca de tiempo actual y retorna el conteo en la ventana."""
        ...

    @abstractmethod
    def get_count(self, key: str) -> int:
        """Retorna el conteo actual sin modificar el store."""
        ...

    @abstractmethod
    def oldest_timestamp(self, key: str) -> float | None:
        """Retorna el timestamp más antiguo en la ventana, o None si está vacío."""
        ...


class InMemoryRateLimitStore(RateLimitStore):

    def __init__(self) -> None:
        self._windows: dict[str, deque[float]] = defaultdict(deque)

    def _evict(self, key: str, window_seconds: int) -> None:
        cutoff = time.monotonic() - window_seconds
        q = self._windows[key]
        while q and q[0] < cutoff:
            q.popleft()

    def increment(self, key: str, window_seconds: int) -> int:
        self._evict(key, window_seconds)
        self._windows[key].append(time.monotonic())
        return len(self._windows[key])

    def get_count(self, key: str) -> int:
        return len(self._windows.get(key, deque()))

    def oldest_timestamp(self, key: str) -> float | None:
        q = self._windows.get(key)
        return q[0] if q else None
