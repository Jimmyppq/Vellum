# ESTADO.md — Estado de la Implementación de Vellum

**Propósito:** punto de entrada para cualquier agente (IA o humano) que necesite saber qué está construido, en qué fase estamos y qué sigue. Las reglas de arquitectura viven en `CLAUDE.md`; este documento dice dónde estamos respecto a ellas.

**Mantenimiento:** se actualiza al **archivar cada change de OpenSpec** (regla en CLAUDE.md §12). Si lees esto y la fecha de abajo es muy antigua, desconfía y contrasta con `openspec list` y `git log`.

*Última actualización: 2026-06-15 (change `router-ai-docs-auth`)*

---

## 1. Matriz de componentes

Los 8 componentes de CLAUDE.md §1, con su estado real:

| Componente | Estado | Detalle | Referencia |
|---|---|---|---|
| `dal` | ✅ **Construido y endurecido** | API completa (prompts, versiones, executions, transcripts, users, connectors, config), PostgreSQL provider, migraciones Alembic con gate de arranque, tipos portables, máquina de estados de executions y prompts, soft delete. 108 tests | [DAL-developer-guide](DAL-developer-guide.md) |
| `router-ai` | ✅ **Construido y endurecido** | 6 adapters LLM (Anthropic, OpenAI, DeepSeek, Google, Ollama, LM Studio), streaming SSE, embeddings, circuit breaker con contrato 503+Retry-After, rate limiting distribuido (Redis), auth por API key con docs protegidas por entorno (`ENV`), logging auditado. 73 tests. **Falta: módulo ASR** | [developer-guide](developer-guide.md) |
| `backend` | ⬜ **No iniciado** | El siguiente gran componente: orquestación, gobernanza, JWT/RBAC, conexión DAL ↔ router-ai | — |
| `worker` | ⬜ No iniciado | Celery + Redis; depende del backend. Decisiones ya tomadas en conversación: `acks_late`, backoff con `Retry-After`, reaper de ejecuciones huérfanas en `running` | — |
| `frontend` | ⬜ No iniciado | Angular; depende del backend | — |
| `gateway` | ⬜ No iniciado | Nginx; necesario antes de staging | — |
| `conector-in` | ⬜ No iniciado | Depende del backend y Object Storage | — |
| `conector-out` | ⬜ No iniciado | Depende del worker | — |

**Infraestructura:** PostgreSQL 15 ✅ · Redis 7 ✅ (rate limiting; cache/colas futuros) · Object Storage ⬜ · ELK ⬜

## 2. Fase actual

**Fase: capas de abstracción terminadas y endurecidas tras auditoría.** El DAL y el router-ai (las dos piezas estratégicas anti lock-in) están completos, auditados (31-may) y con **todos sus críticos resueltos**. No existe aún nada que los conecte: el sistema todavía no ejecuta un prompt de extremo a extremo.

**Criterio de salida de la fase:** cerrar los dos changes de verificación abiertos. **La siguiente fase es el backend**, que convierte las dos capas en un sistema.

## 3. Trabajo en curso

| Item | Estado | Qué falta |
|---|---|---|
| Change `dal-postgres-implementation` | 45/48 | Solo verificación: cobertura ≥80%, build Docker, checklist DoD |
| Change `google-ai-adapter` | 13/17 | Solo verificación manual de los 4 endpoints con key real |

## 4. Hallazgos de auditoría (31-may) — resumen

✅ Resueltos (**todos los críticos cerrados**): `create_all` en producción · JSONB no portable · máquina de estados executions · hard delete prompts (+ transcripts + máquina de estados prompts) · rate limiter en memoria · campo `cost` (lado DAL) · docs sin auth en producción (router-ai).
🟡 Pendientes (no bloqueantes): filtros e índices de auditoría en executions · ASR ausente · healthcheck lento (separar liveness/readiness) · modelo de costes en router-ai · campo `options` sin validar.
Detalle y fechas: [auditorias/AUDITORIA 31-may.md](../auditorias/AUDITORIA%2031-may.md).

## 5. Próximos pasos (orden propuesto)

1. Cerrar los dos changes de verificación abiertos y archivarlos.
2. 🟡 baratos que desbloquean al backend: filtros+índices de executions en el DAL (cola §6.1).
3. **Backend** (componente nuevo), por slices verticales — ver plan detallado en §6.
4. Resto de 🟡 (healthcheck liveness/readiness, modelo de costes, validación de `options`) y módulo ASR.

## 6. Plan de propuestas pendientes (cola de `/opsx:propose`)

Detalle acordado el 2026-06-12 para los próximos changes, en orden de ejecución. Cada entrada tiene lo necesario para generar la propuesta OpenSpec cuando le toque. Al crear cada propose, mover la entrada a "Trabajo en curso" (§3) y al archivar, al historial (§7).

> 6.0 `router-ai-docs-auth` propuesto el 2026-06-12 (movido a §3); change en `openspec/changes/router-ai-docs-auth/`.

### 6.1 `dal-execution-audit-filters` — filtros e índices de auditoría en executions

- **Qué:** `GET /v1/executions` con filtros `executed_by`, `status`, `transcript_id`, rango de `created_at` (hoy solo `prompt_id`); índices `idx_executions_executed_by`, `idx_executions_transcript_id`, `idx_executions_completed_at` (migración Alembic reversible).
- **Por qué:** 🟡 de auditoría que se vuelve bloqueante cuando el backend liste ejecuciones por usuario/estado (slice 6.4); sin índices, cada consulta de auditoría es un full scan.
- **Alcance:** repositorio + router del DAL, migración, tests de filtros combinados. Paralelizable con 6.2/6.3.
- **Dependencias:** ninguna.

### 6.2 `backend-skeleton` — esqueleto transversal del backend

- **Qué:** scaffold FastAPI del componente `backend` con todo lo transversal de CLAUDE.md: middleware `trace_id` (§3.3), envelope `{data, meta}` / `{error}` con handler global (§8), settings por entorno, `/health`, Dockerfile (slim, non-root, §9) y alta en el compose raíz. Incluye los **clientes HTTP internos** `DALClient` y `RouterAIClient`: httpx async, preparados para mTLS por variables (§3.1-3.2), propagación de `X-Trace-Id`, y el `RouterAIClient` interpretando la taxonomía de reintentos (422 no reintentar / 503+`Retry-After` / 502 backoff) de `openspec/specs/llm-routing`.
- **Por qué:** las reglas transversales son baratas al inicio y carísimas de retrofitear; los clientes son la pieza de menor incertidumbre porque ambos contratos ya están especificados y endurecidos.
- **Alcance:** sin endpoints de negocio. Tests: middleware, envelope, clientes contra mocks (respx o similar).
- **Dependencias:** ninguna. **Decisión a tomar en design:** estructura de módulos del backend (por dominio, según CLAUDE.md §1).

### 6.3 `backend-auth` — AuthN/AuthZ JWT + RBAC

- **Qué:** validación JWT (OAuth2/OIDC, RS256) como dependencia FastAPI reutilizable; claims `sub`, `roles[]`, `exp`, `iss`; scopes `viewer` / `service` / `approver` / `admin` (§6.1); access token ≤ 60 min; tokens nunca en logs (§6.3).
- **Por qué:** "todo endpoint del backend requiere JWT" — construido *antes* del primer endpoint de negocio, cada endpoint nace protegido por defecto (evitar el primo del hallazgo `EXCLUDED_PATHS`).
- **Alcance:** dependencia de auth + emisión/validación según se decida, tests por scope.
- **Dependencias:** 6.2. **Decisiones a tomar en design:** ¿IdP externo (OIDC corporativo) o emisión propia para el MVP? ¿Refresh tokens con rotación ya, o en fase frontend? Gestión de claves RS256 (par de claves por entorno, nunca commiteadas).

### 6.4 `backend-prompt-governance` — slice vertical 1: gobernanza de prompts

- **Qué:** endpoints de gestión (`POST/GET /v1/prompts`, versiones, `POST /{id}/approve`, `/{id}/deprecate`, `DELETE` soft) que orquestan contra el DAL vía `DALClient`, con autorización por scope (aprobar = `approver`+; leer = `viewer`).
- **Por qué:** propuesta de valor del producto; bajo riesgo porque el DAL ya trae la parte difícil (máquina de estados de prompts, soft delete, versionado inmutable) — el backend traduce identidad/permisos y propaga errores (409 del DAL → 409 al cliente con el envelope §8).
- **Alcance:** primer uso real de 6.2+6.3 juntos; validators Pydantic en todos los inputs (§6.2); sin lógica duplicada del DAL.
- **Dependencias:** 6.2, 6.3.

### 6.5 `backend-sync-execution` — slice vertical 2: ejecución síncrona end-to-end ← **HITO**

- **Qué:** `POST /v1/executions` (scope `service`+): valida prompt `approved` y versión activa, crea ejecución en DAL (`queued→running`), construye el **`ExecutionIntent`**, invoca al router-ai, y cierra `running→completed` (+`output_data`, +`cost`) o `running→failed` según la taxonomía de errores. `GET /v1/executions/{id}` y listado con los filtros de 6.1.
- **Por qué:** primer prompt ejecutado de extremo a extremo — el sistema pasa a *ser* Vellum. Conecta todo lo endurecido: máquina de estados de executions, `cost` en transiciones terminales, contrato 503 del breaker.
- **Alcance:** solo síncrono (la variante async 202+cola llega con el worker, sin rediseño). Sanitización de inputs que se inyectan en el prompt y límite de tamaño configurable default 10KB (§6.2).
- **Dependencias:** 6.1, 6.4. **Decisión a tomar en design (la primera conversación de diseño del backend):** esquema del `ExecutionIntent` — CLAUDE.md §2.2 lo nombra pero nadie lo ha definido (campos: prompt resuelto con variables inyectadas, provider/model, options validadas, trace_id, presupuesto/timeout…).

> Tras 6.5, los siguientes candidatos naturales (sin detallar aún): worker Celery (ejecución async + reintentos con `Retry-After` + `acks_late` + reaper de huérfanas en `running`), gateway Nginx, y los 🟡 restantes del router-ai (healthcheck liveness/readiness, modelo de costes, validación de `options`).

## 7. Historial de cambios archivados

| Fecha | Change | Qué aportó |
|---|---|---|
| 2026-05-29 | `router-ai` | Servicio router-ai inicial completo |
| 2026-06-10 | `dal-schema-migration-gate` | Gate de migraciones, roles BD separados |
| 2026-06-10 | `dal-portable-column-types` | Tipos portables multi-motor |
| 2026-06-10 | `dal-execution-state-machine` | Máquina de estados de executions (CAS atómico, 409) |
| 2026-06-11 | `dal-prompt-soft-delete` | Soft delete prompts/transcripts + máquina de estados de prompts |
| 2026-06-12 | `router-ai-redis-rate-limit` | Rate limiting distribuido con Redis (fail-open) |
| 2026-06-12 | `router-ai-breaker-retry-after` | Contrato 503 + Retry-After del circuit breaker |
| 2026-06-15 | `router-ai-docs-auth` | Docs protegidas por entorno (`ENV`); cierra el último crítico de auditoría |

Specs vigentes de lo construido: `openspec/specs/` (12 capabilities).
