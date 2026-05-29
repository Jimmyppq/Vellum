import time
from abc import ABC, abstractmethod
from collections import defaultdict, deque

WINDOW = 60


class RateLimitStore(ABC):

    @abstractmethod
    def increment(self, key: str, window_seconds: int) -> int:
        ...

    @abstractmethod
    def get_count(self, key: str, window_seconds: int = WINDOW) -> int:
        ...

    @abstractmethod
    def oldest_timestamp(self, key: str) -> float | None:
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

    def get_count(self, key: str, window_seconds: int = WINDOW) -> int:
        self._evict(key, window_seconds)
        return len(self._windows.get(key, deque()))

    def oldest_timestamp(self, key: str) -> float | None:
        q = self._windows.get(key)
        return q[0] if q else None
