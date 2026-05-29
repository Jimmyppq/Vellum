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
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    ollama_base_url: str = "http://localhost:11434"
    lmstudio_base_url: str = "http://localhost:1234/v1"

    # Logging
    log_level: str = "INFO"
    log_dir: str = "/logs"

    # Rate limiting
    rate_limits_config: str = "config/rate_limits.yaml"

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
