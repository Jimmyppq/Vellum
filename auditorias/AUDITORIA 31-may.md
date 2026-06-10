# AUDITORIA 31-may

## DAL — Observaciones

### ✅ Bien resuelto

La decisión de usar SQLAlchemy Core (no ORM declarativo) es correcta y consistente con el objetivo multi-DBMS. Los UUIDs en Python, la atomicidad en la activación de versiones, el patrón rollback en tests, y la propagación de trace_id están bien implementados.

### 🔴 Crítico

**`metadata.create_all()` en el lifespan de arranque.**
> ✅ **RESUELTO (2026-06-10)** — change `dal-schema-migration-gate`: `verify_schema_version()` fail-fast en todos los entornos, contenedor efímero `dal-migrate` como único mecanismo DDL, y roles de BD separados (`vellum_app` sin DDL / `vellum_migrator`). `create_all` quedó confinado a fixtures de tests.

En producción esto es peligroso. El DAL está modificando el esquema de base de datos cada vez que arranca un contenedor. En un entorno bancario, el esquema lo gestiona Alembic con control explícito y revisión humana — nunca la aplicación en caliente. Un reinicio de contenedor en producción no debería poder alterar la base de datos. La solución: `create_all` solo en entorno `dev`, y en staging/prod el arranque falla si el esquema no está migrado previamente.

```python
if settings.ENV == "dev":
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
else:
    # Verificar que el schema existe, no crearlo
    await verify_schema_version()
```

**`JSONB` de PostgreSQL hardcodeado en schema.py.**
> ✅ **RESUELTO (2026-06-10)** — change `dal-portable-column-types`: nuevo `app/models/types.py` con `PortableJSON()` (`JSON` genérico con variante `JSONB` en PostgreSQL y `CLOB` serializado en Oracle) y `PortableUUID()` (`sa.Uuid`, que también estaba hardcodeado como tipo de dialecto en todas las tablas). `schema.py` y la migración inicial ya no importan `sqlalchemy.dialects`; un test de autogenerate con diff vacío garantiza que el DDL desplegado en PostgreSQL no cambió, y un test anti-regresión por AST impide reintroducir tipos de dialecto. Verificado: 76/76 tests, DDL compilable en oracle/mssql/mysql/sqlite.

El developer guide lo reconoce honestamente: *"Al migrar a otro motor, estos campos son el único punto de adaptación."* Pero en la práctica, `sqlalchemy.dialects.postgresql.JSONB` importado directamente en `schema.py` hace que el módulo falle al importar con cualquier motor que no sea PostgreSQL. El provider de Oracle o SQL-Server nunca podría arrancar con este schema. La solución es usar un tipo genérico que se resuelva según el motor activo:

```python
# En lugar de importar JSONB directamente
from sqlalchemy import JSON  # tipo genérico que funciona en todos los motores
# O mejor: un tipo condicional que use JSONB solo si el motor es postgres
```

**Sin máquina de estados en transiciones de ejecuciones.**
El endpoint `PATCH /v1/executions/{id}/status` acepta cualquier transición. Puedes marcar una ejecución `failed` como `running` de nuevo. En un sistema de gobernanza bancario, el historial de ejecuciones es un registro de auditoría — una transición inválida lo contamina. Las transiciones permitidas deben ser explícitas:

```
queued → running
running → completed
running → failed
# Todo lo demás: HTTP 409 INVALID_STATE_TRANSITION
```

### 🟡 Mejoras importantes

**Hard delete en prompts.** El endpoint `DELETE /v1/prompts/{id}` elimina físicamente. Si hay ejecuciones asociadas, se rompe la cadena de auditoría. En banca necesitas soft delete: campo `deleted_at TIMESTAMP` + `is_deleted BOOLEAN`. Un prompt con ejecuciones no debería poder eliminarse — solo deprecarse.

**Filtros insuficientes en ejecuciones.** `GET /v1/executions` solo filtra por `prompt_id`. Para una auditoría bancaria necesitas: `executed_by`, `status`, `created_at` (rango), `transcript_id`. Sin estos filtros, cualquier consulta de auditoría requiere un full table scan o hacerla fuera del DAL.

**Índices faltantes.**
```python
# Faltan estos:
Index("idx_executions_executed_by", executions.c.executed_by)
Index("idx_executions_transcript_id", executions.c.transcript_id)
Index("idx_executions_completed_at", executions.c.completed_at)
```

**El campo `cost` y `model_used` en ejecuciones nunca se populan.** El schema los define, el DAL los almacena, pero el PATCH de status solo recibe `status` y `output_data`. Falta el mecanismo: el worker debería enviarlos en el PATCH cuando la ejecución se completa.

---

## Router-AI — Observaciones

### ✅ Bien resuelto

El Circuit Breaker es el componente más valioso y está bien implementado. El patrón de registro condicional por API key presente, el rate limiter con YAML externo al contenedor, los headers SSE correctos, y el estado `degraded` en el healthcheck son decisiones acertadas.

### 🔴 Crítico

**Los endpoints de documentación están sin autenticación y hay un TODO explícito.**
El developer guide lo documenta textualmente:

> *"se debe modificar la variable `EXCLUDED_PATHS`... para que no sea accesible desde producción"*

`/docs`, `/openapi.json` y `/redoc` son accesibles sin autenticación ahora mismo. Esto no puede llegar a staging en un producto bancario. La solución inmediata es que `EXCLUDED_PATHS` solo incluya `/v1/health` cuando `ENV != "dev"`:

```python
EXCLUDED_PATHS = {"/v1/health"}
if settings.ENV == "dev":
    EXCLUDED_PATHS |= {"/docs", "/openapi.json", "/redoc"}
```

**El `InMemoryRateLimitStore` no es compatible con escalado horizontal.**
Si despliegas dos instancias del router-ai (lo que harás en producción para HA), cada instancia tiene su propio contador en memoria. Con dos instancias y un límite de 100 RPM por proveedor, en realidad permites 200 RPM. Los límites de OpenAI/Anthropic se aplican a tu API key, no a tu instancia — puedes llegar a los límites del proveedor sin que ninguna instancia individual lo detecte. Esto necesita `RedisRateLimitStore` antes de escalar. El framework ya está preparado, hay que implementarlo y activarlo.

### 🟡 Mejoras importantes

**ASR ausente.** La arquitectura definida en los documentos de alcance contempla transcripción de audio mediante Whisper o Azure Speech como función central del sistema. El router-ai no tiene ningún endpoint `/v1/transcribe` ni adaptador ASR. Este es un módulo completo pendiente de implementar.

**El healthcheck hace llamadas reales a todos los proveedores.** `GET /v1/health` llama a `adapter.health()` de cada proveedor registrado. Si Ollama está caído y tarda 30 segundos en timeout, tu health check de Kubernetes también tarda 30 segundos — lo que dispara un reinicio del pod. Separa los conceptos:
- `/v1/health` → liveness: ¿está el proceso vivo? Respuesta inmediata, sin llamadas externas.
- `/v1/providers` → readiness: ¿están los proveedores accesibles? Esta puede ser lenta.

**Sin modelo de costes.** El router-ai retorna `usage` (tokens de entrada y salida) pero no calcula coste. El DAL tiene el campo `cost` en `executions` pero nunca recibe un valor. Para el caso de uso bancario (control de costes por equipo, por prompt, por área), necesitas que el router-ai retorne el coste calculado basándose en `provider + model + tokens`. Esto requiere mantener una tabla de precios actualizable, similar al YAML de rate limits.

**El campo `options` es un dict sin validar.** Cualquier cosa que el backend mande en `options` llega al proveedor. En un entorno de auditoría, necesitas saber exactamente qué parámetros se enviaron a cada proveedor. Un dict libre no auditado es un riesgo.

---

## Resumen ejecutivo

| Componente | Estado | Bloqueante para staging |
|---|---|---|
| DAL — `create_all` en producción | ✅ Resuelto (2026-06-10) | No — gate de migraciones + roles separados |
| DAL — JSONB no portable | ✅ Resuelto (2026-06-10) | No — tipos portables en `types.py` |
| DAL — Máquina de estados en executions | 🔴 Crítico | Sí (auditoría) |
| Router-AI — Docs sin auth en producción | 🔴 Crítico | Sí |
| Router-AI — Rate limiter en memoria | 🔴 Crítico | Sí (si escala) |
| Router-AI — ASR ausente | 🟡 Importante | No (feature pendiente) |
| DAL — Hard delete en prompts | 🟡 Importante | No |
| DAL — Filtros de auditoría en executions | 🟡 Importante | No |
| Router-AI — Healthcheck lento | 🟡 Importante | No |
| Ambos — Campo `cost` sin poblar | 🟡 Importante | No |

Los tres críticos del DAL y los dos del router-ai son los que yo resolvería antes de conectar el backend. El resto puede ir en iteraciones posteriores.

*Actualización 2026-06-10: dos de los tres críticos del DAL (`create_all` y JSONB no portable) están resueltos. Quedan pendientes: máquina de estados en executions, docs sin auth y rate limiter en memoria del router-ai.*