# Arquitectura Vellum — Análisis Técnico Senior

**Sistema Corporativo de Gestión de Prompts**  
*Versión del análisis: 1.1 — Junio 2026*

> **Changelog v1.1 (2026-06-12):** Redis pasa de infraestructura planificada a servicio desplegado. Su primer consumidor real es el **router-ai**, con un rol nuevo no contemplado en v1.0: contadores de rate limiting RPM/TPM compartidos entre réplicas (change `router-ai-redis-rate-limit`, resuelve el 🔴 de la auditoría del 31-may). La dependencia router-ai → redis está autorizada en CLAUDE.md §11, acotada a rate limiting y con semántica fail-open. Los roles de cache de prompts (backend) y cola Celery (worker) siguen siendo futuros.

---

## 1. Visión General

Vellum es una **plataforma de gobernanza del uso de IA** dentro de organizaciones corporativas. No es un chatbot ni un wrapper de LLMs: es un sistema de gestión del ciclo de vida completo de los prompts, tratándolos como activos corporativos con versionado, aprobación, trazabilidad y ejecución controlada.

El sistema resuelve el problema de fragmentación que ocurre cuando una organización adopta IA sin control: prompts dispersos, sin reutilización, sin auditoría, con riesgos de seguridad latentes.

**Propuesta de valor técnica:** Un control plane centralizado donde todo prompt pasa por validación, versionado y autorización antes de ejecutarse contra cualquier LLM o base de datos.

---

## 2. Diagrama General de Arquitectura

Versión gráfica: [Arquitectura-Vellum-v3.png](Arquitectura-Vellum-v3.png) (fuente editable: `Arquitectura-Vellum-v3.svg`; la v2 se conserva como histórico previo a Redis).

### ASCII Art

```
                          ┌─────────────────────────────────────────────────────────────────────┐
                          │                     REPOSITORIO EXTERNO CORPORATIVO                  │
                          │                                                                       │
                          │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │
                          │  │  Confluence │  │ Adhoc (API) │  │  Sharepoint │                 │
                          │  └─────────────┘  └─────────────┘  └─────────────┘                 │
                          │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │
                          │  │  DB Externa │  │    Slack    │  │    Zapier   │                 │
                          │  └─────────────┘  └─────────────┘  └─────────────┘                 │
                          └─────────────────────────────────────────────────────────────────────┘
                                                       ▲
                                                       │
  ┌──────────────────┐    ┌─────────────────────────────────────────────────┐   ┌──────────────────┐
  │                  │    │                    NÚCLEO                        │   │                  │
  │   CONECTOR IN    │    │                                                  │   │   CONECTOR OUT   │
  │                  │    │  ┌───────────────────────────────────────────┐  │   │                  │
  │  Webhook         │    │  │              FRONTEND (Angular)            │  │   │  Dispatcher      │
  │  Uploads (audio) │───►│  │   RBAC UI · Gestión Prompts · Métricas   │  │──►│  Plugin-like     │
  │  APIs externas   │    │  └───────────────────┬───────────────────────┘  │   │  Async Workers   │
  │  Sistemas corp.  │    │                       │ REST/JSON                │   │                  │
  └──────────────────┘    │                       ▼                          │   └──────────────────┘
                          │  ┌───────────────────────────────────────────┐  │
                          │  │           API GATEWAY (Nginx/Kong)         │  │
                          │  │   TLS · Rate Limit · Routing · AuthN       │  │
                          │  └───────────────────┬───────────────────────┘  │
                          │                       │                          │
                          │                       ▼                          │
                          │  ┌───────────────────────────────────────────┐  │
                          │  │             BACKEND (FastAPI)              │  │
                          │  │                                            │  │
                          │  │  ┌──────────┐  ┌──────────┐  ┌────────┐  │  │
                          │  │  │ Prompts  │  │ Versions │  │  Exec  │  │  │
                          │  │  └──────────┘  └──────────┘  └────────┘  │  │
                          │  │  ┌──────────┐  ┌──────────┐  ┌────────┐  │  │
                          │  │  │  AuthZ   │  │Connectors│  │Logging │  │  │
                          │  │  └──────────┘  └──────────┘  └────────┘  │  │
                          │  └──────────┬──────────────────────┬─────────┘  │
                          │             │ FastAPI               │ FastAPI    │
                          │             ▼                        ▼           │
                          │  ┌──────────────────┐  ┌───────────────────┐   │
                          │  │    ROUTER-AI      │  │    ROUTER-DB      │   │
                          │  │  (Abstracción LLM)│  │  (Abstracción DB) │   │
                          │  └───┬────────┬─────┘  └────────┬──────────┘   │
                          │      ┆        │                  │               │
                          └──────┆────────┼──────────────────┼───────────────┘
                                 ┆        │                  │
             contadores RPM/TPM  ┆  ┌─────▼───────────────┐  ┌▼──────────────────────────────┐
             compartidos entre   ┆  │     LLM LAYER        │  │         DBMS LAYER            │
             réplicas (fail-open)┆  │                      │  │                               │
                                 ┆  │ OpenAI Anthropic     │  │  Oracle   MariaDB   Postgres  │
                                 ┆  │ Google Ollama        │  │  MySQL    MongoDB   SQL-Server│
                                 ┆  │ DeepSeek LMStudio    │  │                               │
                                 ┆  └──────────────────────┘  └───────────────────────────────┘
                                 ┆
   ──────────────────────────────┆──────────────────────────────────────────────────────────
   INFRAESTRUCTURA TRANSVERSAL   ┆
   ──────────────────────────────┆──────────────────────────────────────────────────────────
                                 ▼
   ┌──────────────────────────┐   ┌──────────────────┐   ┌──────────────────┐   ┌──────────────┐
   │  Redis (desplegado)      │   │  Object Storage   │   │  Logs / ELK      │   │  Async       │
   │  · Rate limit router-ai  │   │  S3 / MinIO       │   │  Structured JSON │   │  Workers     │
   │  · Cache prompts (futuro)│   │  Audios/Videos    │   │  Audit Trail     │   │  Celery/RQ   │
   │  · Cola Celery  (futuro) │   │                   │   │                  │   │  (futuro)    │
   └──────────────────────────┘   └──────────────────┘   └──────────────────┘   └──────────────┘

   La flecha punteada ROUTER-AI ⇢ Redis es deliberadamente no crítica: con Redis caído, el
   router-ai degrada a contadores en memoria (fail-open) y lo reporta en /v1/health.
```

---

## 3. Componentes Principales

### 3.1 ConectorIN

Punto de entrada para datos que ingresan al sistema desde el exterior. Gestiona:

- Subida de archivos binarios (grabaciones de reuniones, audios) hacia Object Storage
- Invocaciones desde sistemas corporativos vía webhook
- Desencadena procesamiento ASR (Automatic Speech Recognition) asíncrono

Es el puente entre el mundo exterior y el pipeline de transcripción y ejecución de prompts. Arquitectónicamente es un módulo FastAPI con endpoints dedicados, separado conceptualmente del backend principal para aislar el ingress.

### 3.2 Frontend (Angular)

SPA con RBAC embebido en UI. Características relevantes:

- Sin lógica de negocio crítica: todo delegado a la API
- Consumo exclusivo del backend vía REST/JSON
- Tokens almacenados en cookies httpOnly (no localStorage)
- Vistas diferenciadas por rol: Admin, Editor, Approver, Viewer

### 3.3 API Gateway (Nginx / Kong / Traefik)

Frontera de seguridad perimetral. Responsabilidades:

- Terminación TLS (todo tráfico sobre HTTPS)
- Rate limiting por usuario, IP y endpoint
- Routing hacia servicios internos
- Primera línea de defensa antes de que el request llegue al backend

### 3.4 Backend (FastAPI) — Núcleo del Sistema

Monolito modular organizado por dominios. Es stateless para facilitar escalado horizontal. Módulos internos:

| Módulo | Responsabilidad |
|---|---|
| Prompts | CRUD + estado (draft/approved/deprecated) |
| Versions | Inmutabilidad: cada cambio genera nueva versión |
| Executions | Orquestación del flujo completo de ejecución |
| AuthN/AuthZ | OAuth2/JWT + RBAC + ABAC |
| Connectors | Dispatcher hacia ConectorOut |
| Logging | trace_id propagado a todos los subsistemas |
| Transcripts | Gestión del ciclo de vida de transcripciones |

### 3.5 Router-AI — Capa de Abstracción LLM

**Este es uno de los componentes más estratégicos de la arquitectura.** Es un microservicio FastAPI dedicado que implementa el patrón *Provider Abstraction*:

```
AI Provider Interface
    ├── OpenAIProvider     (GPT-4, GPT-3.5...)
    ├── AnthropicProvider  (Claude Opus, Sonnet...)
    ├── GoogleProvider     (Gemini...)
    ├── OllamaProvider     (modelos locales)
    ├── DeepSeekProvider   (coste optimizado)
    └── LMStudioProvider   (entorno local/dev)
```

Evita el vendor lock-in total. Permite cambiar o combinar proveedores sin modificar el backend. También habilita estrategias de routing inteligente: selección por coste, por latencia, o por capacidad del modelo según el tipo de prompt.

**Rate limiting distribuido (v1.1).** El router-ai aplica límites RPM/TPM por proveedor para proteger la cuota de la API key (que es global a la organización, no por instancia). Los contadores viven en un store intercambiable: `InMemoryRateLimitStore` (una sola instancia, dev) o `RedisRateLimitStore` (contadores compartidos entre réplicas, ventana deslizante por buckets de 1s). Selección por entorno (`RATE_LIMIT_STORE`), y degradación **fail-open**: si Redis cae, el servicio sigue operando con contadores locales y lo reporta en `/v1/health` — la caída de Redis nunca bloquea la ruta crítica de ejecución. Esta es la segunda capa de rate limiting del sistema, complementaria a la perimetral del gateway (por usuario/IP): el gateway protege la infraestructura propia; el router-ai protege la cuota ante los proveedores LLM.

### 3.6 DAL — Capa de Abstracción DBMS

Microservicio FastAPI que abstrae el acceso a múltiples motores de base de datos. Soporta:

- **Relacionales:** Oracle, MariaDB, Postgres, MySQL, SQL-Server
- **NoSQL:** MongoDB

Este componente es especialmente relevante para el caso de uso de prompts que consultan bases de datos corporativas existentes (el sistema actúa como intermediario entre un prompt gobernado y datos estructurados de la organización).

### 3.7 ConectorOut — Sistema de Integración de Salida

Dispatcher de integraciones externas. Arquitectura plugin-like con interfaz base:

```python
class BaseConnector:
    def send(self, execution_data: dict) -> None: ...
```

Destinos soportados:
- **Confluence** — publicación de resultados como páginas
- **Adhoc API** — webhooks genéricos a cualquier endpoint
- **Sharepoint** — integración documental corporativa
- **DB Externa** — escritura de resultados en bases de datos
- **Slack** — notificaciones y reportes
- **Zapier** — automatización de workflows corporativos

Principio de aislamiento de fallos: si un conector falla, la ejecución principal no se ve afectada. Toda ejecución de conectores es **asíncrona por diseño**.

### 3.8 Infraestructura de Soporte

| Componente | Tecnología | Rol | Estado |
|---|---|---|---|
| Cache / Cola / Contadores | Redis | Rate limiting distribuido del router-ai (**implementado**) · prompts frecuentes (futuro) · task queue para workers (futuro) | ✅ Desplegado (compose raíz, red interna, sin puerto al host) |
| Object Storage | S3 / MinIO | Archivos binarios (audios, vídeos de reuniones) | Planificado |
| Base de datos principal | PostgreSQL | Fuente de verdad del sistema | ✅ Desplegado |
| Workers asíncronos | Celery + Redis | ASR, ejecuciones pesadas, conectores | Planificado |
| Logs | JSON estructurado + ELK (futuro) | Auditoría y observabilidad | Parcial (JSON estructurado) |

El acceso del router-ai a Redis está autorizado en CLAUDE.md §11 **exclusivamente para rate limiting**; el cache de prompts seguirá siendo responsabilidad del backend cuando exista. Un único Redis sirve los tres roles, separables por base de datos lógica (`/0`, `/1`, `/2`) si la operación lo requiere.

---

## 4. Flujos Clave

### 4.1 Flujo de Ejecución de Prompt (ruta crítica)

```
Sistema externo / Usuario
        │
        ▼
  [API Gateway] ── rate limit + TLS
        │
        ▼
  [Backend] ── valida JWT + RBAC
        │
        ├── obtiene prompt_version aprobada (PostgreSQL)
        │
        ├── inyecta variables del input
        │
        ├── encola tarea (Redis)
        │
        ▼
  [Worker Celery]
        │
        ├── [Router-AI] ── selecciona proveedor LLM
        │         │
        │         └── LLM externo / local
        │
        ├── guarda resultado en executions (PostgreSQL)
        │
        └── [ConectorOut Dispatcher] ── async
                  │
                  ├── ConfluenceConnector
                  ├── SlackConnector
                  └── WebhookConnector
```

### 4.2 Flujo de Transcripción (ASR)

```
Audio / Video
     │
     ▼
[ConectorIN] ── sube a Object Storage (S3/MinIO)
     │
     ▼
[Backend] ── crea registro transcript (status=uploading)
     │
     ▼
[Worker Celery] ── invoca Router-AI con modelo ASR (Whisper, Azure Speech)
     │
     ├── genera transcript_version con texto resultante
     │
     └── estado → ready / failed
```

### 4.3 Ciclo de Vida de un Prompt

```
draft ──► [revisión] ──► approved ──► [ejecuciones en producción]
  │                                              │
  └── nueva edición ──► nueva version            └──► deprecated
```

Invariante crítico: **el contenido de una versión nunca se sobrescribe.** Toda modificación crea `prompt_versions.version_number + 1`.

---

## 5. Modelo de Datos — Entidades Principales

```
┌──────────┐       ┌─────────────────┐       ┌────────────┐
│  users   │──1:N──│    prompts      │──1:N──│prompt_ver- │
│          │       │  id, name,      │       │sions       │
│  id      │       │  status,        │       │  content,  │
│  email   │       │  visibility     │       │  is_active │
└──────────┘       └─────────────────┘       └────────────┘
     │                                               │
     │                                               │ 1:N
     │             ┌─────────────────┐       ┌────────────┐
     └──1:N────────│  transcripts    │──1:N──│transcript_ │
                   │  media_url,     │       │versions    │
                   │  status         │       │  content   │
                   └─────────────────┘       └────────────┘
                                                     │
                                                     │ N:1
                   ┌────────────────────────────────────────┐
                   │              executions                 │
                   │  prompt_id, version_id, transcript_id  │
                   │  input_data JSONB, output_data JSONB   │
                   │  status, model_used, cost              │
                   └────────────────────────────────────────┘
```

El campo `transcript_id` en `executions` es `NULL` para ejecuciones sobre texto libre y contiene el UUID de la transcripción cuando el prompt opera sobre una transcripción gobernada. Esto permite correlacionar completamente el origen de cualquier ejecución.

---

## 6. Modelo de Seguridad

La arquitectura implementa **Defense in Depth** con múltiples capas:

```
Internet
   │
   ▼ TLS 1.2+
[API Gateway] ── rate limiting, DDoS básico
   │
   ▼ JWT validation
[Backend] ── OAuth2/OIDC + RS256
   │
   ▼ RBAC + ABAC
[Autorización] ── por recurso, por rol, por atributo (owner, equipo, entorno)
   │
   ▼ Input validation
[Ejecución] ── solo prompts aprobados y registrados, no prompts libres del cliente
   │
   ▼ Encryption at rest
[PostgreSQL + Object Storage] ── AES-256, tokens nunca en texto plano
```

Puntos de control críticos:
- Los clientes **nunca envían prompts libres**: solo referencian `prompt_id` + `version_id` aprobados
- Los tokens de conectores se almacenan cifrados y nunca se exponen al frontend
- Cada request genera un `trace_id` UUID que se propaga a todos los subsistemas (correlación completa de logs)

---

## 7. Estrategia de Despliegue

### Fase actual: Monolito modular en Docker

```
docker-compose
    ├── frontend-container    (Nginx + Angular build)
    ├── gateway-container     (Nginx reverse proxy)
    ├── backend-container     (FastAPI + Uvicorn)
    ├── worker-container      (Celery)
    ├── router-ai-container   (FastAPI microservice)
    ├── dal-container   (FastAPI microservice)
    ├── db-container          (PostgreSQL 15)
    └── redis-container       (Redis 7)  ← desplegado: rate limiting distribuido del router-ai
```

Red interna Docker: los servicios se comunican por nombre de servicio. Ni la base de datos ni Redis exponen puertos al exterior; el router-ai alcanza Redis por nombre (`redis://redis:6379/0`) solo cuando `RATE_LIMIT_STORE=redis`.

### Evolución planificada

```
Fase 1 ──► Docker Compose (actual)
Fase 2 ──► Kubernetes + Helm + HPA (autoescalado)
Fase 3 ──► Event-driven con Kafka (ejecuciones → eventos → consumidores)
Fase 4 ──► Plataforma distribuida + multi-tenant
```

---

## 8. Análisis Crítico — Fortalezas y Riesgos

### Fortalezas arquitectónicas

**Router-AI y DAL como capas de abstracción independientes** es la decisión más valiosa de esta arquitectura. Permite que el sistema evolucione el pool de proveedores LLM (o motores de base de datos) sin tocar el backend core. En un contexto donde el mercado de LLMs cambia mensualmente, esta flexibilidad es crítica.

**Separación prompt / ejecución** es correcta y no negociable desde un punto de vista de gobernanza. El modelo impide que cualquier cliente externo inyecte instrucciones arbitrarias al LLM, eliminando una clase entera de vulnerabilidades (prompt injection desde clientes).

**El ConectorIN y ConectorOut como ciudadanos de primera clase** elevan la plataforma de "herramienta de gestión de prompts" a "motor de integración de IA corporativa". La arquitectura plugin-like de ConectorOut permite extensión sin modificar el core.

**Versionado inmutable** implementado correctamente: `prompt_versions` nunca se sobrescribe, lo que garantiza reproducibilidad y auditoría completa de qué versión exacta de un prompt produjo qué resultado.

### Riesgos y consideraciones técnicas

**DAL es el componente con mayor superficie de riesgo.** Abstrae acceso a múltiples DBMS corporativos (Oracle, SQL-Server, MongoDB...) lo que implica gestión de múltiples drivers, dialectos SQL distintos y credenciales de múltiples bases de datos. Requiere un modelo de credenciales robusto (rotación, cifrado, alcance mínimo) y límites estrictos sobre qué queries puede generar un prompt. Sin controles de query sanitization, este componente puede convertirse en un vector de exfiltración de datos.

**La tabla `executions` es el hot spot de la base de datos.** Con uso real, crecerá de forma exponencial. El documento indica particionado por fecha como estrategia futura, pero debería planificarse desde el modelo inicial con `PARTITION BY RANGE (created_at)` en PostgreSQL para evitar una migración traumática en producción.

**El Worker Celery comparte imagen con el Backend.** El Dockerfile actual lanza `celery -A app.worker worker` desde la misma imagen del backend. Esto está bien para MVP, pero en producción los workers de transcripción (ASR sobre audios largos, consumo intensivo de CPU/GPU) deberían estar en contenedores con recursos diferenciados del worker de conectores (I/O-bound).

**El Object Storage requiere política de ciclo de vida.** Los archivos de audio/vídeo no tienen una política de retención definida en los documentos. En producción, esto puede generar costes significativos y riesgos de compliance (GDPR) si se almacenan grabaciones de reuniones indefinidamente.

**Ausencia de circuit breaker en llamadas a LLMs.** Las llamadas a proveedores externos (OpenAI, Anthropic, etc.) desde Router-AI deben protegerse con circuit breaker (Hystrix pattern) y timeouts agresivos. Un proveedor lento o caído no debe bloquear el pool de workers.

---

## 9. API — Contratos Principales

La API sigue un diseño contract-first con versionado explícito `/v1/`. Separación estricta entre recursos de gestión y ejecución:

```
Gestión de prompts:
  POST   /v1/prompts                    ← crear prompt (draft)
  GET    /v1/prompts?tag=&owner=&status=
  PUT    /v1/prompts/{id}
  POST   /v1/prompts/{id}/versions      ← nueva versión inmutable
  POST   /v1/prompts/{id}/approve       ← transición de estado
  POST   /v1/prompts/{id}/deprecate

Ejecución (ruta crítica):
  POST   /v1/executions                 ← sync o async
  GET    /v1/executions/{id}            ← polling para async

Transcripciones:
  POST   /v1/transcripts                ← subida, desencadena ASR
  GET    /v1/transcripts/{id}
  POST   /v1/transcripts/{id}/execute   ← aplicar prompt sobre transcripción

Conectores:
  POST   /v1/connectors
  POST   /v1/connectors/{id}/enable

Observabilidad:
  GET    /v1/metrics/usage
  GET    /v1/metrics/prompts/{id}
  GET    /v1/version
  GET    /v1/health
```

Formato de respuesta estandarizado con `data` + `meta.request_id` + `meta.version`. Los errores incluyen `trace_id` que correlaciona con los logs del sistema.

---

## 10. Observabilidad

Tres pilares implementados:

**Logs estructurados (JSON)** con `trace_id` propagado desde el API Gateway hasta los workers y conectores. Preparados para ingestión en ELK Stack.

**Métricas operacionales:**
- Prompts ejecutados por período
- Latencia p50/p95/p99 por proveedor LLM
- Tasa de error por módulo
- Coste por ejecución (campo `cost` en `executions`)
- Uso por usuario/equipo

**Trazas distribuidas (roadmap):** OpenTelemetry como estándar, permite visualizar el camino completo de una ejecución: Gateway → Backend → Router-AI → LLM Provider → ConectorOut → Sistema externo.

---

## 11. Roadmap Técnico

```
MVP (Fase 1)
  ✓ Backend FastAPI modular
  ✓ PostgreSQL + Redis
  ✓ Docker Compose
  ✓ Autenticación JWT
  ✓ CRUD prompts + versionado
  ✓ Ejecución síncrona básica
  ✓ Router-AI (OpenAI como primer proveedor)
  ✓ ConectorOut (Confluence como primer conector)

Fase 2
  → Workers Celery para transcripción ASR
  → Router-AI completo (multi-proveedor)
  → DAL (consultas a DBMS corporativos)
  → ConectorIn (webhooks, uploads)
  → Gobernanza completa (flujos de aprobación)
  → Métricas y dashboard

Fase 3
  → Kubernetes + Helm
  → Event-driven (Kafka): ejecuciones como eventos
  → A/B testing de prompts
  → Detección automática de PII
  → OpenTelemetry distributed tracing
  → Multi-tenant (aislamiento por organización)

Fase 4
  → Data platform (OLAP separado de OLTP)
  → Routing inteligente de LLMs (coste/latencia)
  → Catálogo corporativo de golden prompts
  → Modelos de análisis de calidad de prompts
```

---

## 12. Conclusión Arquitectónica

La arquitectura de Vellum es **técnicamente sólida y bien pensada para su contexto**. Las decisiones más acertadas son la abstracción de proveedores LLM mediante Router-AI (anti lock-in), la separación estricta entre prompt y ejecución (seguridad), el versionado inmutable (auditoría), y la arquitectura plugin-like de conectores (extensibilidad sin regresiones).

El riesgo principal no es técnico sino operacional: el DAL expone la plataforma a la complejidad de múltiples dialectos SQL y credenciales corporativas, lo que requiere un modelo de seguridad muy cuidadoso para ese componente específico.

La estrategia de evolución incremental (monolito modular → escalado horizontal → event-driven) es correcta y pragmática. El sistema no sobre-ingeniería desde el inicio y tiene un camino claro hacia arquitecturas distribuidas cuando la escala lo justifique.

---

*Análisis elaborado por: Arquitecto Senior — Sistema Vellum*  
*Basado en: Business Case, Documentos de Alcance 1–13, Diagrama de Arquitectura (PDF)*
