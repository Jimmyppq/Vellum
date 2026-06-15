"""Protección por entorno de los endpoints de documentación (/docs, /openapi.json,
/redoc): exentos de API key solo en dev; /v1/health exento siempre."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.middleware.auth import APIKeyMiddleware, excluded_paths

API_KEY = "test-key-123"
DOC_PATHS = ["/docs", "/openapi.json", "/redoc"]


def make_client(env: str) -> TestClient:
    app = FastAPI()  # genera /docs, /openapi.json y /redoc por defecto

    @app.get("/v1/health")
    def health():
        return {"status": "ok"}

    app.add_middleware(APIKeyMiddleware, env=env)
    return TestClient(app)


@pytest.mark.parametrize("path", DOC_PATHS)
def test_docs_sin_key_en_dev_retorna_200(path):
    response = make_client("dev").get(path)
    assert response.status_code == 200


@pytest.mark.parametrize("env", ["staging", "prod"])
@pytest.mark.parametrize("path", DOC_PATHS)
def test_docs_sin_key_fuera_de_dev_retorna_401(env, path):
    response = make_client(env).get(path)
    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHORIZED"
    assert "requerido" in response.json()["message"]


@pytest.mark.parametrize("path", DOC_PATHS)
def test_docs_con_key_valida_en_prod_retorna_200(path):
    response = make_client("prod").get(path, headers={"X-API-Key": API_KEY})
    assert response.status_code == 200


@pytest.mark.parametrize("env", ["dev", "staging", "prod"])
def test_health_sin_key_en_todos_los_entornos(env):
    response = make_client(env).get("/v1/health")
    assert response.status_code == 200


def test_excluded_paths_por_entorno():
    assert excluded_paths("dev") == {"/v1/health", "/docs", "/openapi.json", "/redoc"}
    assert excluded_paths("staging") == {"/v1/health"}
    assert excluded_paths("prod") == {"/v1/health"}


# ── Validator del setting env ─────────────────────────────────────────────────

def make_settings(**kwargs) -> Settings:
    return Settings(router_ai_api_key="x", _env_file=None, **kwargs)


def test_env_ausente_es_prod():
    assert make_settings().env == "prod"


def test_env_no_reconocido_cae_a_prod_con_warning(caplog):
    with caplog.at_level("WARNING"):
        settings = make_settings(env="production")
    assert settings.env == "prod"
    assert "ENV='production' no válido" in caplog.text


def test_env_insensible_a_mayusculas():
    assert make_settings(env="DEV").env == "dev"
    assert make_settings(env="Staging").env == "staging"
