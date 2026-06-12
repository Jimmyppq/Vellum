import logging
import os
from dataclasses import dataclass
from typing import Optional

import yaml

from app.core.rate_limit_store import RateLimitStore, InMemoryRateLimitStore

logger = logging.getLogger(__name__)

WINDOW = 60  # segundos


@dataclass
class ProviderLimits:
    requests_per_minute: Optional[int]
    tokens_per_minute: Optional[int]


@dataclass
class CheckResult:
    allowed: bool
    limit_type: Optional[str] = None
    retry_after_seconds: int = 0
    remaining_rpm: Optional[int] = None
    remaining_tpm: Optional[int] = None


class RateLimiter:

    def __init__(self, config_path: str, store: RateLimitStore | None = None) -> None:
        self._config_path = config_path
        self._store = store or InMemoryRateLimitStore()
        self._limits: dict[str, ProviderLimits] = {}
        self._load_config()

    def _load_config(self) -> None:
        if not os.path.exists(self._config_path):
            logger.warning(
                "rate_limits.yaml no encontrado en '%s'. Sin rate limiting.", self._config_path
            )
            return
        with open(self._config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        for provider, cfg in (data.get("providers") or {}).items():
            self._limits[provider.lower()] = ProviderLimits(
                requests_per_minute=cfg.get("requests_per_minute"),
                tokens_per_minute=cfg.get("tokens_per_minute"),
            )
        logger.info("Rate limits cargados para: %s", list(self._limits.keys()))

    async def check_request(self, provider: str, estimated_tokens: int = 0) -> CheckResult:
        limits = self._limits.get(provider.lower())
        if limits is None:
            return CheckResult(allowed=True)

        rpm_key = f"{provider.lower()}:rpm"
        tpm_key = f"{provider.lower()}:tpm"

        # Verificar RPM
        if limits.requests_per_minute is not None:
            current_rpm = await self._store.get_count(rpm_key)
            if current_rpm >= limits.requests_per_minute:
                retry_after = await self._store.seconds_until_oldest_expires(rpm_key, WINDOW)
                return CheckResult(
                    allowed=False,
                    limit_type="requests_per_minute",
                    retry_after_seconds=retry_after,
                    remaining_rpm=0,
                )

        # Verificar TPM
        if limits.tokens_per_minute is not None and estimated_tokens > 0:
            current_tpm = await self._store.get_count(tpm_key)
            if current_tpm + estimated_tokens > limits.tokens_per_minute:
                retry_after = await self._store.seconds_until_oldest_expires(tpm_key, WINDOW)
                return CheckResult(
                    allowed=False,
                    limit_type="tokens_per_minute",
                    retry_after_seconds=retry_after,
                    remaining_tpm=0,
                )

        remaining_rpm = None
        if limits.requests_per_minute is not None:
            remaining_rpm = limits.requests_per_minute - await self._store.get_count(rpm_key)

        remaining_tpm = None
        if limits.tokens_per_minute is not None:
            remaining_tpm = limits.tokens_per_minute - await self._store.get_count(tpm_key)

        return CheckResult(allowed=True, remaining_rpm=remaining_rpm, remaining_tpm=remaining_tpm)

    async def record_request(self, provider: str) -> None:
        await self._store.increment(f"{provider.lower()}:rpm", WINDOW)

    async def record_tokens(self, provider: str, tokens: int) -> None:
        if tokens > 0:
            await self._store.increment(f"{provider.lower()}:tpm", WINDOW, amount=tokens)
