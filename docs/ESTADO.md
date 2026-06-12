# ESTADO.md — Estado de la Implementación de Vellum

**Propósito:** punto de entrada para cualquier agente (IA o humano) que necesite saber qué está construido, en qué fase estamos y qué sigue. Las reglas de arquitectura viven en `CLAUDE.md`; este documento dice dónde estamos respecto a ellas.

**Mantenimiento:** se actualiza al **archivar cada change de OpenSpec** (regla en CLAUDE.md §12). Si lees esto y la fecha de abajo es muy antigua, desconfía y contrasta con `openspec list` y `git log`.

*Última actualización: 2026-06-12 (change `router-ai-breaker-retry-after`)*

---

## 1. Matriz de componentes

Los 8 componentes de CLAUDE.md §1, con su estado real:

| Componente | Estado | Detalle | Referencia |
|---|---|---|---|
| `dal` | ✅ **Construido y endurecido** | API completa (prompts, versiones, executions, transcripts, users, connectors, config), PostgreSQL provider, migraciones Alembic con gate de arranque, tipos portables, máquina de estados de executions y prompts, soft delete. 108 tests | [DAL-developer-guide](DAL-developer-guide.md) |
| `router-ai` | ✅ **Construido y endurecido** | 6 adapters LLM (Anthropic, OpenAI, DeepSeek, Google, Ollama, LM Studio), streaming SSE, embeddings, circuit breaker con contrato 503+Retry-After, rate limiting distribuido (Redis), auth por API key, logging auditado. 54 tests. **Falta: módulo ASR** | [developer-guide](developer-guide.md) |
| `backend` | ⬜ **No iniciado** | El siguiente gran componente: orquestación, gobernanza, JWT/RBAC, conexión DAL ↔ router-ai | — |
| `worker` | ⬜ No iniciado | Celery + Redis; depende del backend. Decisiones ya tomadas en conversación: `acks_late`, backoff con `Retry-After`, reaper de ejecuciones huérfanas en `running` | — |
| `frontend` | ⬜ No iniciado | Angular; depende del backend | — |
| `gateway` | ⬜ No iniciado | Nginx; necesario antes de staging | — |
| `conector-in` | ⬜ No iniciado | Depende del backend y Object Storage | — |
| `conector-out` | ⬜ No iniciado | Depende del worker | — |

**Infraestructura:** PostgreSQL 15 ✅ · Redis 7 ✅ (rate limiting; cache/colas futuros) · Object Storage ⬜ · ELK ⬜

## 2. Fase actual

**Fase: capas de abstracción terminadas y endurecidas tras auditoría.** El DAL y el router-ai (las dos piezas estratégicas anti lock-in) están completos, auditados (31-may) y con todos sus críticos resueltos salvo uno. No existe aún nada que los conecte: el sistema todavía no ejecuta un prompt de extremo a extremo.

**Criterio de salida de la fase:** cerrar el último crítico de auditoría + los dos changes de verificación abiertos. **La siguiente fase es el backend**, que convierte las dos capas en un sistema.

## 3. Trabajo en curso

| Item | Estado | Qué falta |
|---|---|---|
| Change `dal-postgres-implementation` | 45/48 | Solo verificación: cobertura ≥80%, build Docker, checklist DoD |
| Change `google-ai-adapter` | 13/17 | Solo verificación manual de los 4 endpoints con key real |
| 🔴 Auditoría: docs sin auth en producción (router-ai) | **Pendiente — único crítico restante** | Acotar `EXCLUDED_PATHS` a `/v1/health` cuando `ENV != dev` |

## 4. Hallazgos de auditoría (31-may) — resumen

✅ Resueltos: `create_all` en producción · JSONB no portable · máquina de estados executions · hard delete prompts (+ transcripts + máquina de estados prompts) · rate limiter en memoria · campo `cost` (lado DAL).
🟡 Pendientes (no bloqueantes): filtros e índices de auditoría en executions · ASR ausente · healthcheck lento (separar liveness/readiness) · modelo de costes en router-ai · campo `options` sin validar.
Detalle y fechas: [auditorias/AUDITORIA 31-may.md](../auditorias/AUDITORIA%2031-may.md).

## 5. Próximos pasos (orden propuesto)

1. **Docs sin auth** (🔴, cambio pequeño) — cierra la auditoría al 100% de críticos.
2. Cerrar los dos changes de verificación abiertos y archivarlos.
3. 🟡 baratos que desbloquean al backend: filtros+índices de executions en el DAL.
4. **Backend** (componente nuevo): autenticación JWT/RBAC, orquestación de ejecuciones contra DAL + router-ai. Aquí se decide el detalle de la cola (worker).
5. Resto de 🟡 (healthcheck liveness/readiness, modelo de costes, validación de `options`) y módulo ASR.

## 6. Historial de cambios archivados

| Fecha | Change | Qué aportó |
|---|---|---|
| 2026-05-29 | `router-ai` | Servicio router-ai inicial completo |
| 2026-06-10 | `dal-schema-migration-gate` | Gate de migraciones, roles BD separados |
| 2026-06-10 | `dal-portable-column-types` | Tipos portables multi-motor |
| 2026-06-10 | `dal-execution-state-machine` | Máquina de estados de executions (CAS atómico, 409) |
| 2026-06-11 | `dal-prompt-soft-delete` | Soft delete prompts/transcripts + máquina de estados de prompts |
| 2026-06-12 | `router-ai-redis-rate-limit` | Rate limiting distribuido con Redis (fail-open) |
| 2026-06-12 | `router-ai-breaker-retry-after` | Contrato 503 + Retry-After del circuit breaker |

Specs vigentes de lo construido: `openspec/specs/` (12 capabilities).
