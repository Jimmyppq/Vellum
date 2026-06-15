# Tasks: router-ai-docs-auth

## 1. Configuración

- [x] 1.1 Añadir `env: str = "prod"` a `Settings` (`router-ai/app/core/config.py`) con validator: minúsculas, valores `dev|staging|prod`, valor no reconocido → warning + `prod`
- [x] 1.2 Establecer `ENV=dev` en `router-ai/docker-compose.yml` (entorno local) y documentar la variable en `.env.example` si existe

## 2. Middleware

- [x] 2.1 Sustituir la constante `EXCLUDED_PATHS` por `excluded_paths(env)` en `router-ai/app/middleware/auth.py`: `{"/v1/health"}` siempre; añadir `/docs`, `/openapi.json`, `/redoc` solo si `env == "dev"`; evaluar una vez en `__init__`
- [x] 2.2 Verificar que el registro del middleware en `app/main.py` pasa el entorno desde `settings`

## 3. Tests

- [x] 3.1 Tests del middleware por entorno: docs 200 sin key en `dev`; docs/openapi/redoc 401 sin key en `prod` y `staging`; docs 200 con key válida en `prod`; `/v1/health` 200 sin key en todos
- [x] 3.2 Tests del validator de `env`: ausente → `prod`; `ENV=production` → warning + `prod`; insensible a mayúsculas
- [x] 3.3 Suite completa de router-ai en verde (contenedor efímero, `pytest tests/ -q`)

## 4. Documentación y cierre

- [x] 4.1 Cerrar el TODO correspondiente en `docs/developer-guide.md` y documentar el comportamiento por entorno
- [x] 4.2 Marcar el hallazgo "docs sin auth en producción" como resuelto en `auditorias/AUDITORIA 31-may.md`
