import time
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"       # operación normal
    OPEN = "open"           # proveedor en fallo, rechazar llamadas
    HALF_OPEN = "half_open" # probar si el proveedor se ha recuperado


@dataclass
class CircuitBreaker:
    provider: str
    failure_threshold: int = 5      # fallos consecutivos para abrir
    recovery_timeout: float = 60.0  # segundos antes de intentar half-open
    success_threshold: int = 2      # éxitos en half-open para cerrar

    _state: CircuitState = field(default=CircuitState.CLOSED, init=False, repr=False)
    _failure_count: int = field(default=0, init=False, repr=False)
    _success_count: int = field(default=0, init=False, repr=False)
    _opened_at: Optional[float] = field(default=None, init=False, repr=False)

    def is_available(self) -> bool:
        if self._state == CircuitState.CLOSED:
            return True
        if self._state == CircuitState.OPEN:
            if self._opened_at and (time.monotonic() - self._opened_at) >= self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                self._success_count = 0
                logger.info("Circuit breaker '%s': OPEN → HALF_OPEN", self.provider)
                return True
            return False
        return True  # HALF_OPEN: permitir una llamada de prueba

    def record_success(self) -> None:
        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self.success_threshold:
                self._state = CircuitState.CLOSED
                self._failure_count = 0
                logger.info("Circuit breaker '%s': HALF_OPEN → CLOSED", self.provider)
        elif self._state == CircuitState.CLOSED:
            self._failure_count = 0

    def record_failure(self) -> None:
        self._failure_count += 1
        if self._state == CircuitState.HALF_OPEN or self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN
            self._opened_at = time.monotonic()
            logger.warning(
                "Circuit breaker '%s': ABIERTO tras %d fallos",
                self.provider, self._failure_count,
            )

    @property
    def state(self) -> str:
        return self._state.value
