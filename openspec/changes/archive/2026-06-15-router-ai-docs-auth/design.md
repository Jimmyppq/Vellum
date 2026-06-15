# Design: router-ai-docs-auth

## Context

`APIKeyMiddleware` (`router-ai/app/middleware/auth.py`) usa una constante `EXCLUDED_PATHS = {"/v1/health", "/docs", "/openapi.json", "/redoc"}` idéntica en todos los entornos. La auditoría 31-may lo marcó 🔴: en producción la documentación interactiva expone el contrato completo de la API sin credenciales. `Settings` (`app/core/config.py`) no tiene noción de entorno todavía.

## Goals / Non-Goals

**Goals:**
- Documentación (`/docs`, `/openapi.json`, `/redoc`) sin auth **solo** en `dev`.
- `/v1/health` exento en todos los entornos (probes/load balancers, requirement vigente).
- Seguro por defecto: si `ENV` no está definido, comportarse como producción.

**Non-Goals:**
- No deshabilitar la generación de la documentación (`docs_url=None`): con API key sigue siendo útil en staging/prod.
- No tocar el mecanismo de validación de la API key ni el formato de error 401.
- No introducir auth diferenciada por endpoint (scopes); eso es territorio del backend (JWT).

## Decisions

1. **Setting `env: str = "prod"` con validator** (valores `dev | staging | prod`; valor no reconocido → warning y `prod`). Default `prod` y no `dev` deliberadamente: olvidar la variable en un despliegue nunca puede abrir la documentación. En el compose de desarrollo se fija `ENV=dev` explícitamente. Mismo patrón que el validator existente de `log_level`.

2. **Función `excluded_paths(env)` en el middleware** en lugar de la constante: devuelve `{"/v1/health"} | DOC_PATHS` si `env == "dev"`, si no `{"/v1/health"}`. El middleware la evalúa en `__init__` (una vez, no por request). Alternativa descartada: leer `settings` en cada `dispatch` — coste innecesario y dificulta los tests.

3. **Tests parametrizados por entorno** construyendo la app/middleware con `env` inyectado (monkeypatch de settings o parámetro del middleware), sin depender de variables de entorno reales del runner.

## Risks / Trade-offs

- [Quien dependiera de `/docs` abierto en staging] → es exactamente el comportamiento que la auditoría exige cerrar; el acceso sigue disponible con `X-API-Key`.
- [`ENV` mal escrito en despliegue (`production`, `PROD`)] → el validator normaliza a minúsculas y cae a `prod` ante valores desconocidos: el fallo es hacia el lado seguro.
