import logging
from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Autenticación interna
    router_ai_api_key: SecretStr

    # Proveedores
    anthropic_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    deepseek_api_key: SecretStr | None = None
    google_api_key: SecretStr | None = None
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    ollama_base_url: str | None = None
    lmstudio_base_url: str | None = None

    # Logging
    log_level: str = "INFO"
    log_dir: str = "/logs"

    # Rate limiting
    rate_limits_config: str = "config/rate_limits.yaml"

    # mTLS (false en dev local, true en staging/producción)
    mtls_enabled: bool = False
    mtls_cert_path: str = "/certs/service.crt"
    mtls_key_path: str = "/certs/service.key"
    mtls_ca_path: str = "/certs/ca.crt"

    @field_validator("log_level", mode="before")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        upper = str(v).upper()
        if upper not in VALID_LOG_LEVELS:
            logging.warning(
                "LOG_LEVEL='%s' no válido; usando INFO por defecto.", v
            )
            return "INFO"
        return upper


settings = Settings()
