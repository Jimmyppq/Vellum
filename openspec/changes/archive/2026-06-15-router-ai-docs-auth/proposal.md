# Proposal: router-ai-docs-auth

## Why

Último hallazgo crítico abierto de la auditoría del 31-may: `/docs`, `/openapi.json` y `/redoc` están excluidos de la autenticación por API key en `router-ai` (`EXCLUDED_PATHS` en `app/middleware/auth.py`), por lo que en producción cualquier actor con acceso de red puede leer el contrato completo de la API (endpoints, modelos, proveedores soportados) sin credenciales. La solución exacta ya está prescrita en el informe de auditoría.

## What Changes

- Nuevo setting `env` en `router-ai` (`ENV`, valores `dev | staging | prod`, default `prod` — seguro por defecto).
- El middleware de autenticación calcula los paths excluidos según el entorno: en `dev` se mantienen `/docs`, `/openapi.json` y `/redoc` sin auth; en cualquier otro entorno solo `/v1/health` queda exento.
- Tests: documentación accesible sin API key en `dev`; 401 en `staging`/`prod`; `/v1/health` siempre exento.
- Documentación: cerrar el TODO del developer-guide, marcar el hallazgo como resuelto en `auditorias/AUDITORIA 31-may.md` y actualizar `docs/ESTADO.md` al archivar.

## Capabilities

### New Capabilities

(ninguna)

### Modified Capabilities

- `api-key-auth`: el requirement de exclusión de autenticación pasa de ser una lista fija a depender del entorno — los endpoints de documentación solo quedan exentos cuando `ENV=dev`; `/v1/health` permanece exento en todos los entornos.

## Impact

- `router-ai/app/core/config.py`: nuevo campo `env` con validator.
- `router-ai/app/middleware/auth.py`: `EXCLUDED_PATHS` deja de ser una constante fija; se deriva del entorno.
- `router-ai/tests/`: nuevos tests del middleware por entorno.
- `router-ai/.env.example` (si existe) y `router-ai/docker-compose.yml`: documentar/establecer `ENV`.
- Sin cambios de contrato para clientes legítimos: los endpoints de negocio ya exigían API key. **No breaking** para integraciones; sí cambia el acceso anónimo a la documentación en despliegues no-dev (ese es el objetivo).
