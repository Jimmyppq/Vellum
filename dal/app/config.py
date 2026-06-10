import logging
import sys
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    DB_HOST: str
    DB_PORT: int = 5432
    DB_NAME: str
    DB_USER: str
    DB_PASSWORD: str
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30
    DB_ENGINE: str = "postgres"

    # Environment
    ENV: Literal["dev", "staging", "prod"] = "dev"

    # mTLS
    MTLS_ENABLED: bool = False
    MTLS_CERT_PATH: str = "/certs/dal.crt"
    MTLS_KEY_PATH: str = "/certs/dal.key"
    MTLS_CA_PATH: str = "/certs/ca.crt"

    # Internal auth (dev only)
    INTERNAL_SERVICE_TOKEN: str = ""

    # Logging
    LOG_LEVEL: str = "INFO"

    @field_validator("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD", mode="before")
    @classmethod
    def must_not_be_empty(cls, v: str, info) -> str:
        if not v or not v.strip():
            raise ValueError(f"{info.field_name} must not be empty")
        return v

    @property
    def async_database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    @property
    def safe_database_url(self) -> str:
        """DSN without password — safe for logging."""
        return f"{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"


def get_settings() -> Settings:
    return Settings()


# ---------------------------------------------------------------------------
# Structured JSON logger
# ---------------------------------------------------------------------------

class _JSONFormatter(logging.Formatter):
    import json as _json

    def format(self, record: logging.LogRecord) -> str:
        import json
        from datetime import datetime, timezone

        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "service": "dal",
            "trace_id": getattr(record, "trace_id", ""),
            "action": getattr(record, "action", record.name),
            "duration_ms": getattr(record, "duration_ms", None),
            "status": getattr(record, "status", None),
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps({k: v for k, v in payload.items() if v is not None})


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JSONFormatter())
    logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO), handlers=[handler], force=True)
