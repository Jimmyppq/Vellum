import logging
import time
from abc import ABC, abstractmethod
from collections import defaultdict, deque

logger = logging.getLogger(__name__)

WINDOW = 60


class RateLimitStore(ABC):
    """Contadores de ventana deslizante compartibles entre réplicas.

    La interfaz no expone timestamps crudos: el reloj de un proceso no es
    comparable entre réplicas, así que el tiempo restante de la ventana lo
    calcula cada implementación con su propio reloj.
    """

    @abstractmethod
    async def increment(self, key: str, window_seconds: int, amount: int = 1) -> int:
        ...

    @abstractmethod
    async def get_count(self, key: str, window_seconds: int = WINDOW) -> int:
        ...

    @abstractmethod
    async def seconds_until_oldest_expires(self, key: str, window_seconds: int = WINDOW) -> int:
        ...


class InMemoryRateLimitStore(RateLimitStore):
    """Default para dev y tests. Los contadores son locales al proceso."""

    def __init__(self) -> None:
        # (timestamp, amount) por entrada; un solo append por increment
        self._windows: dict[str, deque[tuple[float, int]]] = defaultdict(deque)

    def _evict(self, key: str, window_seconds: int) -> None:
        cutoff = time.time() - window_seconds
        q = self._windows[key]
        while q and q[0][0] < cutoff:
            q.popleft()

    async def increment(self, key: str, window_seconds: int, amount: int = 1) -> int:
        self._evict(key, window_seconds)
        self._windows[key].append((time.time(), amount))
        return sum(a for _, a in self._windows[key])

    async def get_count(self, key: str, window_seconds: int = WINDOW) -> int:
        self._evict(key, window_seconds)
        return sum(a for _, a in self._windows.get(key, deque()))

    async def seconds_until_oldest_expires(self, key: str, window_seconds: int = WINDOW) -> int:
        self._evict(key, window_seconds)
        q = self._windows.get(key)
        if not q:
            return window_seconds
        return max(1, int(window_seconds - (time.time() - q[0][0])))


class RedisRateLimitStore(RateLimitStore):
    """Ventana deslizante por buckets de 1 segundo sobre Redis.

    Una clave por segundo (`{key}:{epoch_second}`) con INCRBY + EXPIRE en
    pipeline; el conteo de la ventana es la suma (MGET) de los últimos
    `window_seconds` buckets. Atómico entre réplicas sin Lua ni sorted sets.

    Fail-open: cualquier error de Redis se loggea y la operación devuelve un
    valor que no bloquea la solicitud (el rate limiter protege cuota de
    proveedor, no es una frontera de seguridad).
    """

    def __init__(self, redis_client) -> None:
        self._redis = redis_client

    @staticmethod
    def _bucket(key: str, second: int) -> str:
        return f"rl:{key}:{second}"

    async def increment(self, key: str, window_seconds: int, amount: int = 1) -> int:
        now = int(time.time())
        try:
            async with self._redis.pipeline(transaction=False) as pipe:
                pipe.incrby(self._bucket(key, now), amount)
                pipe.expire(self._bucket(key, now), window_seconds + 1)
                await pipe.execute()
            return await self.get_count(key, window_seconds)
        except Exception:
            logger.exception("Redis increment falló para '%s'; fail-open", key)
            return 0

    async def get_count(self, key: str, window_seconds: int = WINDOW) -> int:
        now = int(time.time())
        buckets = [self._bucket(key, s) for s in range(now - window_seconds + 1, now + 1)]
        try:
            values = await self._redis.mget(buckets)
            return sum(int(v) for v in values if v is not None)
        except Exception:
            logger.exception("Redis get_count falló para '%s'; fail-open", key)
            return 0

    async def seconds_until_oldest_expires(self, key: str, window_seconds: int = WINDOW) -> int:
        now = int(time.time())
        seconds = list(range(now - window_seconds + 1, now + 1))
        buckets = [self._bucket(key, s) for s in seconds]
        try:
            values = await self._redis.mget(buckets)
        except Exception:
            logger.exception("Redis seconds_until_oldest_expires falló para '%s'", key)
            return 1
        for second, value in zip(seconds, values):
            if value is not None and int(value) > 0:
                return max(1, window_seconds - (now - second))
        return window_seconds
