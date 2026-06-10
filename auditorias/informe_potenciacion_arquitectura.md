# Informe de Potenciación Arquitectónica — Plataforma Vellum

**Assessment Independiente de Arquitectura y Hoja de Ruta de Mejora**
*Tipo de documento: Architecture Review & Improvement Report*
*Fecha: Junio 2026 · Versión 1.0*
*Documento base analizado: `doc_architecture.md` v1.0 (Mayo 2026)*

---

## Resumen Ejecutivo

Vellum parte de una base arquitectónica **notablemente sólida para su fase de madurez**: monolito modular bien delimitado, capas de abstracción explícitas (Router-AI, DAL), versionado inmutable de prompts y una postura de seguridad que elimina por diseño el prompt injection directo desde clientes. Estas decisiones son correctas y deben preservarse.

Este informe identifica, sin embargo, **cuatro brechas estructurales** que, de no corregirse antes del despliegue productivo, comprometerán la promesa central del producto — gobernanza, trazabilidad y confianza corporativa:

1. **El DAL concentra el mayor riesgo de la plataforma sin un modelo de control proporcional.** Una plataforma cuyo argumento de venta es la gobernanza no puede mediar acceso a bases de datos corporativas con credenciales estáticas y sin políticas de query a nivel de plataforma. Se requiere gestión dinámica de secretos, roles de mínimo privilegio y un *policy engine* de acceso a datos. *(Prioridad P0)*

2. **La resiliencia de la ruta crítica depende de componentes únicos sin degradación controlada.** Redis actúa simultáneamente como caché y broker (acoplamiento de modos de fallo), no existen circuit breakers ante proveedores LLM, ni idempotencia en ejecuciones, ni dead-letter queues. Un proveedor LLM degradado puede agotar el pool de workers y detener la plataforma completa. *(Prioridad P0)*

3. **La superficie de prompt injection real no está cubierta.** El modelo de seguridad bloquea prompts libres del cliente, pero el vector dominante en sistemas como Vellum es la **inyección indirecta**: instrucciones maliciosas embebidas en transcripciones, documentos y resultados de bases de datos que el prompt aprobado consume como contexto. Hoy ese contenido fluye sin sanitización hacia el LLM y sus salidas fluyen sin validación hacia Confluence, Slack y bases de datos externas. *(Prioridad P0)*

4. **Decisiones diferidas que serán migraciones traumáticas.** Multi-tenancy (Fase 4), particionado de `executions` (futuro), detección de PII (Fase 3) y OpenTelemetry (roadmap) son significativamente más baratas de incorporar hoy en el modelo de datos y el código que de retrofitear con datos productivos. *(Prioridad P1)*

El informe propone **23 recomendaciones priorizadas** (P0–P2), una arquitectura objetivo evolucionada y una hoja de ruta revisada que reordena el roadmap actual bajo el criterio de *coste de reversión*: lo que es caro de cambiar después, se decide ahora; lo que es barato de añadir después (Kafka, Kubernetes, multi-región), se difiere sin culpa.

**Veredicto global:** arquitectura **APTA con condiciones**. Ninguna brecha invalida el diseño; todas son resolubles dentro de la Fase 2 del roadmap actual con un esfuerzo estimado de 14–20 semanas-persona incrementales.

---

## 1. Alcance y Metodología

| Dimensión | Detalle |
|---|---|
| Artefactos analizados | `doc_architecture.md`, reglas de arquitectura (`CLAUDE.md`), `docker-compose.yml`, guías de desarrollador del DAL |
| Marco de evaluación | AWS Well-Architected (pilares: seguridad, fiabilidad, eficiencia, excelencia operativa, costes) + OWASP Top 10 for LLM Applications (2025) + ISO 27001 (controles de acceso y trazabilidad) |
| Criterio de priorización | P0 = bloqueante para producción · P1 = decidir ahora, ejecutar en Fase 2 · P2 = mejora de madurez, ejecutable en Fase 3 |
| Lo que este informe no cubre | Revisión de código línea a línea, pentesting, dimensionamiento de infraestructura concreto |

---

## 2. Lo que está bien y no debe tocarse

Antes de las brechas, lo esencial: las siguientes decisiones son las correctas y constituyen ventaja competitiva. Cualquier evolución debe preservarlas como invariantes.

| Decisión | Por qué es correcta |
|---|---|
| Router-AI como única puerta a LLMs | Anti vendor lock-in real; el punto único donde añadir guardrails, caching semántico y routing por coste sin tocar el core |
| Clientes nunca envían prompts libres | Elimina estructuralmente una clase entera de ataques; pocos competidores lo hacen bien |
| Versionado inmutable de prompts | Base de la reproducibilidad y la auditoría — es el producto |
| SQL solo dentro del DAL (regla de CLAUDE.md) | Frontera de seguridad verificable estáticamente; mantenerla como gate de CI |
| Monolito modular + evolución incremental | Madurez: no sobre-ingeniería; los módulos por dominio son las costuras de extracción futura |
| ConectorOut asíncrono con aislamiento de fallos | Patrón correcto; solo le falta garantía de entrega (ver R-07) |

---

## 3. Hallazgos y Recomendaciones

### 3.1 Seguridad de datos — el DAL como joya de la corona

> **Hallazgo F-01 (Crítico).** El DAL mediará acceso a Oracle, SQL Server, PostgreSQL, MySQL, MariaDB y MongoDB corporativos. El documento reconoce el riesgo pero no especifica controles. Con credenciales estáticas en `connector_configs` (aunque cifradas AES-256), un compromiso del DAL equivale a un compromiso de todas las bases de datos conectadas. Una plataforma de *gobernanza* será evaluada por los CISO de sus clientes precisamente en este punto.

**R-01 · Secretos dinámicos con privilegio mínimo (P0).**
Sustituir credenciales estáticas por **HashiCorp Vault** (o equivalente cloud) con *database secrets engine*: el DAL solicita credenciales efímeras (TTL minutos–horas), generadas con un rol específico por conexión, revocables centralmente. Donde el motor cliente no lo permita, como mínimo: rotación automatizada, usuario **read-only por defecto**, y escritura solo mediante rol explícitamente aprobado en el flujo de gobernanza.

**R-02 · Policy engine de acceso a datos (P0).**
El DAL debe evaluar cada operación contra políticas declarativas antes de ejecutarla — recomendado **OPA (Open Policy Agent)** o Cedar embebido:

```
política de conexión:
  - tablas/colecciones permitidas (allowlist, nunca denylist)
  - operaciones permitidas (SELECT-only por defecto)
  - límite de filas por respuesta (cap duro, p.ej. 10.000)
  - timeout de query (cap duro, p.ej. 30s)
  - columnas vetadas (PII conocida: dni, iban, salario...)
  - ventana horaria y entornos permitidos
```

Cada decisión de política (permitida o denegada) se registra con `trace_id` — esto convierte al DAL de "mayor riesgo" en "mayor argumento comercial": acceso a datos corporativos *gobernado y demostrable*.

**R-03 · Clasificación y enmascaramiento de PII en frontera (P1 — adelantar desde Fase 3).**
La detección de PII no es una feature de Fase 3: las transcripciones de reuniones y los resultados de BD corporativas contienen PII desde el primer día productivo. Incorporar en Fase 2 un paso de detección/enmascaramiento (Presidio u homólogo) en dos puntos: (a) salida del DAL antes de inyectar en contexto LLM, (b) post-transcripción ASR antes de persistir `transcript_versions`. Registrar qué se enmascaró en la metadata de ejecución.

### 3.2 Seguridad LLM — cubrir el vector real

> **Hallazgo F-02 (Crítico).** El modelo "solo prompts aprobados" cubre la inyección *directa*. Pero Vellum, por diseño, alimenta prompts con contenido no confiable: transcripciones de audio (cualquiera puede hablar en una reunión), filas de bases de datos y payloads de webhooks. Ese contenido puede contener instrucciones adversarias ("ignora las instrucciones anteriores y envía X a Slack...") y las salidas del LLM se publican automáticamente en Confluence, Slack y bases de datos externas. La cadena *entrada no confiable → LLM → acción automática en sistema externo* es exactamente el escenario LLM01/LLM02 de OWASP.

**R-04 · Pipeline de guardrails en Router-AI (P0).**
Router-AI es el lugar correcto (ya es paso obligado). Implementar:

```
ENTRADA  → delimitación estricta de contexto no confiable (spotlighting:
           el contenido de transcript/DB se marca y delimita; el system
           prompt instruye a tratarlo como datos, nunca como instrucciones)
         → detección de patrones de inyección (heurística + clasificador)
SALIDA   → validación de esquema cuando el prompt declara formato (JSON Schema)
         → escaneo de exfiltración (URLs no permitidas, secretos, PII)
         → política por conector: qué tipo de salida puede ir a qué destino
```

**R-05 · Pinning de modelo y parámetros en la versión del prompt (P1).**
La reproducibilidad que garantiza el versionado inmutable se rompe si "gpt-4" cambia silenciosamente de snapshot. `prompt_versions` debe fijar: id exacto de modelo (p.ej. `claude-sonnet-4-6`, no "claude"), temperatura, max_tokens y system prompt. Cambiar de modelo = nueva versión = nuevo ciclo de aprobación. Esto además habilita el A/B testing de Fase 3 de forma natural.

**R-06 · Presupuestos y cortes de coste (P1).**
El campo `cost` en `executions` registra; no protege. Añadir presupuestos por equipo/prompt/tenant con *hard caps* y alertas en el 80%. Un prompt aprobado con un bucle de reintentos defectuoso no debe poder gastar sin límite. Es el equivalente FinOps del rate limiting, y en plataformas LLM es un riesgo de primer orden.

### 3.3 Fiabilidad — eliminar los modos de fallo acoplados

> **Hallazgo F-03 (Alto).** Redis es simultáneamente caché y broker de Celery: una saturación de caché degrada la cola de ejecuciones y viceversa, y una caída de Redis detiene a la vez rendimiento y procesamiento. No hay circuit breakers hacia LLMs (reconocido en el propio documento), ni idempotencia, ni DLQ, ni patrón outbox para los conectores.

**R-07 · Entrega garantizada con patrón Outbox + DLQ (P0).**
"Si un conector falla, la ejecución no se ve afectada" es aislamiento, no garantía: hoy un fallo de conector pierde el envío silenciosamente. Implementar **transactional outbox**: el worker persiste el resultado y el evento de despacho en la misma transacción PostgreSQL; un relay procesa la outbox con reintentos exponenciales + jitter y, agotados, mueve a una **dead-letter queue** visible en el panel de administración con re-disparo manual. Mismo patrón para tareas Celery fallidas.

**R-08 · Circuit breakers, timeouts y bulkheads en Router-AI (P0).**
Por proveedor LLM: timeout agresivo (p95 esperado × 2), circuit breaker (abrir tras N fallos consecutivos, half-open con sondas), y **bulkhead** — pool de concurrencia separado por proveedor para que OpenAI degradado no agote los workers que podrían servir Anthropic u Ollama. Definir cadenas de fallback declarativas por prompt: `proveedor_primario → fallback → cola diferida`.

**R-09 · Idempotencia en la ruta crítica (P0).**
`POST /v1/executions` debe aceptar `Idempotency-Key`. Reintentos de clientes, redespachos de cola y reintentos de outbox no deben producir ejecuciones (ni costes LLM) duplicados. Almacenar la clave con el resultado y devolver la respuesta original ante repetición.

**R-10 · Separar caché de broker (P1).**
Dos instancias Redis con políticas distintas (caché: `allkeys-lru`, sin persistencia; broker: `noeviction`, AOF) — o broker dedicado (RabbitMQ) si se necesitan garantías de entrega más ricas. Coste mínimo hoy; en producción evita el peor incidente posible: pérdida de tareas encoladas por evicción de memoria.

**R-11 · Pools de workers diferenciados (P1 — ya identificado en el documento, formalizarlo).**
Tres colas con SLO propio: `asr` (CPU/GPU-bound, larga duración), `executions` (latencia-sensible), `connectors` (I/O-bound, tolerante a retraso). Imágenes y límites de recursos separados desde el compose actual, no esperar a Kubernetes.

**R-12 · Objetivos explícitos de recuperación (P1).**
Definir RPO/RTO por dato (¿perder 1h de `executions` es aceptable? ¿y de `prompt_versions`?), backups automatizados con **restauración ensayada** trimestralmente, y PostgreSQL con réplica en streaming antes del go-live. Una plataforma de auditoría que pierde su audit trail pierde el producto.

### 3.4 Datos — decidir hoy lo que es caro mañana

> **Hallazgo F-04 (Alto).** Tres decisiones de modelo de datos están diferidas y su coste de retrofit crece con cada fila insertada: particionado de `executions`, multi-tenancy y retención de objetos.

**R-13 · Particionar `executions` desde la migración inicial (P0).**
`PARTITION BY RANGE (created_at)` mensual desde el día uno, con creación automática de particiones (pg_partman). El propio documento lo reconoce como "migración traumática" futura — la forma de evitar una migración traumática es no necesitarla. Coste hoy: una migración Alembic. Definir además política de retención: particiones > N meses se archivan a Object Storage (Parquet) — esto adelanta gratis la separación OLTP/OLAP de Fase 4.

**R-14 · `tenant_id` desde el día uno (P1).**
Multi-tenant está en Fase 4, pero añadir `tenant_id NOT NULL` a las tablas raíz hoy (aunque siempre valga `default`) + **Row-Level Security** de PostgreSQL preparada, convierte la Fase 4 de "re-arquitectura del modelo de datos con downtime" a "activar una feature". Es la decisión individual de mayor apalancamiento de este informe en relación coste/beneficio.

**R-15 · Ciclo de vida de Object Storage y cadena de custodia (P1).**
Política de retención declarada por tipo de objeto (audios de reuniones: p.ej. 90 días post-transcripción, configurable por tenant para GDPR), lifecycle rules nativas de S3/MinIO, cifrado envelope (clave por tenant), URLs prefirmadas con TTL corto para todo acceso, y registro de acceso a objetos en el audit trail. El derecho de supresión GDPR (art. 17) debe poder ejecutarse: borrar audio + transcripciones + referencias en ejecuciones de un interesado concreto.

**R-16 · Audit trail inmutable de verdad (P2).**
Para clientes regulados (banca — contexto natural de Vellum), los logs estructurados no bastan como evidencia: tabla `audit_events` *append-only* (sin UPDATE/DELETE concedidos a ningún rol de aplicación) con encadenamiento de hash por registro, exportable. Diferenciador comercial directo en procesos de compra con compliance.

### 3.5 Plataforma y operación

**R-17 · OpenTelemetry desde Fase 2, no como roadmap (P1).**
Instrumentar FastAPI/Celery/httpx con OTel cuesta horas ahora (auto-instrumentación) y semanas después. El `trace_id` propio ya existente se mapea a trace context W3C. Sin trazas distribuidas, el primer incidente productivo con la cadena Gateway → Backend → Worker → Router-AI → LLM → ConectorOut se diagnosticará a ciegas.

**R-18 · SLOs y métricas de saturación de cola (P1).**
Definir SLOs explícitos (p.ej. ejecución async p95 < 30s excluyendo latencia LLM; disponibilidad API 99.9%) y la métrica más predictiva del sistema: **profundidad y edad de cola por tipo de tarea**, con alertas. El autoescalado de la Fase 2 de Kubernetes (KEDA) escalará sobre esta métrica.

**R-19 · API asíncrona con semántica explícita (P1).**
Formalizar el patrón async: `POST /v1/executions` → `202 Accepted` + `status_url`; añadir **webhooks de finalización firmados (HMAC)** y/o SSE para evitar que cada sistema corporativo cliente implemente polling. Publicar contrato OpenAPI versionado con política de deprecación documentada (la promesa contract-first del documento, hecha verificable con CI de breaking changes).

**R-20 · Cadena de suministro y gates de CI (P1).**
Las excelentes reglas de `CLAUDE.md` (SQL solo en DAL, LLMs solo en router-ai, sin secretos) deben ser **verificadas por máquina, no por convención**: linters de import (`import-linter`/Semgrep) como gate de CI, escaneo de imágenes (Trivy), SBOM, firma de imágenes y pip con hashes pinneados. Especialmente relevante: este repositorio es desarrollado con agentes de IA — los gates automáticos son la única garantía durable de las fronteras arquitectónicas.

**R-21 · AuthN en el gateway, AuthZ en el backend (P2).**
Mover la validación JWT/OIDC (verificación de firma vía JWKS, expiración, audiencia) al gateway —Kong/Traefik lo soportan nativamente— dejando al backend solo RBAC/ABAC contextual. Reduce superficie en el backend y unifica el punto de revocación. Preparar federación con el IdP corporativo del cliente (Entra ID, Okta) como requisito enterprise de primer pedido.

**R-22 · Revisar la apuesta Kafka de Fase 3 (P2).**
Con outbox + colas (R-07) y los volúmenes previsibles de una plataforma de gobernanza interna, Kafka probablemente sea sobre-ingeniería operativa (3+ brokers, rebalanceos, expertise). Criterio de activación recomendado: adoptar Kafka solo si aparecen ≥2 consumidores independientes de un stream de eventos con replay, o throughput sostenido > ~1.000 ejecuciones/min. Alternativa intermedia: Redis Streams o NATS JetStream sobre la misma outbox.

**R-23 · Evaluación continua de calidad de prompts (P2).**
El "catálogo de golden prompts" de Fase 4 necesita una base: conjunto de casos de evaluación por prompt (entradas + criterios), ejecutados contra cada nueva versión antes de la aprobación — un *regression test de prompts* integrado en el flujo de gobernanza. Convierte la aprobación de un acto administrativo en un acto verificado, y es la feature que más diferencia a una plataforma de gobernanza "de papel" de una real.

---

## 4. Arquitectura Objetivo (evolución, no revolución)

Los componentes existentes se mantienen; se añaden los planos de control que faltan:

```
                                ┌────────────────────────────────────────────┐
                                │           PLANO DE GOBERNANZA              │
                                │  Policy Engine (OPA) · Presupuestos/coste  │
                                │  Eval de prompts · Audit trail inmutable   │
                                └──────┬──────────────────┬──────────────────┘
                                       │ políticas        │ evidencia
        ┌──────────────┐   ┌───────────▼──────────────────▼───────────────┐
Usuario │   Gateway    │   │                 BACKEND (FastAPI)             │
  ───►  │ TLS·RateLim  │──►│   AuthZ (RBAC/ABAC) · Orquestación ·          │
        │ AuthN (OIDC) │   │   Idempotencia · Outbox transaccional         │
        └──────────────┘   └───────┬───────────────────────────┬───────────┘
                                   │                           │
                       ┌───────────▼───────────┐   ┌───────────▼───────────┐
                       │      ROUTER-AI        │   │         DAL           │
                       │ Guardrails in/out     │   │ Secretos dinámicos    │
                       │ Circuit breaker ·     │   │ (Vault) · Policy check│
                       │ Bulkhead por proveedor│   │ Read-only por defecto │
                       │ Pinning modelo/params │   │ Enmascarado PII       │
                       └───────────┬───────────┘   └───────────┬───────────┘
                                   ▼                           ▼
                              LLM Providers              DBMS corporativos
        ───────────────────────────────────────────────────────────────────
        Workers: colas asr / executions / connectors (pools y SLO propios)
        Redis caché ≠ Redis broker · DLQ visible · PostgreSQL particionado
        (tenant_id + RLS preparado) · OTel end-to-end · Backups ensayados
```

---

## 5. Hoja de Ruta Revisada

Reordenación del roadmap vigente bajo el criterio *coste de reversión*. Lo marcado ⭐ es nuevo o adelantado respecto al plan actual.

**Ahora — antes de cualquier despliegue productivo (≈ 4–6 semanas)**
- ⭐ Particionado de `executions` + `tenant_id` en el modelo (R-13, R-14)
- ⭐ Idempotencia + outbox + DLQ (R-07, R-09)
- ⭐ Circuit breakers/timeouts/bulkheads en Router-AI (R-08)
- ⭐ Gates de CI que verifican las reglas de CLAUDE.md (R-20)

**Fase 2 ampliada (≈ 1 trimestre)**
- Lo ya planificado: workers ASR, Router-AI multi-proveedor, DAL, ConectorIn, gobernanza, métricas
- ⭐ Vault + secretos dinámicos + policy engine del DAL (R-01, R-02)
- ⭐ Guardrails de entrada/salida en Router-AI (R-04)
- ⭐ PII en frontera — adelantado desde Fase 3 (R-03)
- ⭐ OTel — adelantado desde roadmap (R-17) · Redis dual (R-10) · pools de workers (R-11)
- ⭐ Pinning de modelo en versiones + presupuestos de coste (R-05, R-06)
- ⭐ Backups con restauración ensayada + réplica PostgreSQL (R-12)

**Fase 3 (sin cambios de fondo, con dos correcciones)**
- Kubernetes + Helm + KEDA (escalado por profundidad de cola, R-18)
- A/B testing de prompts apoyado en pinning (R-05) y eval harness (R-23)
- ⭐ Kafka condicionado a criterio de activación explícito (R-22)
- Webhooks/SSE de finalización (R-19) · AuthN en gateway (R-21)

**Fase 4 (se abarata gracias a lo anterior)**
- Multi-tenant = activar RLS sobre `tenant_id` ya existente
- OLAP = formalizar el archivado Parquet ya operativo desde R-13
- Golden prompts = madurar el eval harness de R-23

---

## 6. Matriz de Riesgos Residuales

| # | Riesgo | Prob. | Impacto | Mitigación | Estado tras plan |
|---|---|---|---|---|---|
| 1 | Exfiltración vía DAL | Media | Crítico | R-01, R-02, R-03 | Residual bajo |
| 2 | Inyección indirecta → acción en sistema externo | Alta | Alto | R-04, política por conector | Residual medio (vigilancia continua) |
| 3 | Proveedor LLM caído bloquea plataforma | Alta | Alto | R-08 (breaker + fallback) | Residual bajo |
| 4 | Pérdida de tareas/notificaciones | Media | Alto | R-07, R-10 | Residual bajo |
| 5 | Coste LLM descontrolado | Media | Medio | R-06 | Residual bajo |
| 6 | Incumplimiento GDPR (retención de audios) | Media | Alto | R-15 | Residual bajo |
| 7 | Migración multi-tenant traumática | Cierta si se difiere | Alto | R-14 | Eliminado |
| 8 | Erosión de fronteras arquitectónicas (desarrollo con agentes IA) | Media | Medio | R-20 | Residual bajo |

---

## 7. Indicadores de Éxito (KPIs propuestos)

| Dominio | KPI | Objetivo |
|---|---|---|
| Fiabilidad | Disponibilidad API / p95 ejecución async (excl. LLM) | 99,9% / < 30 s |
| Fiabilidad | Tareas en DLQ sin resolver > 24 h | 0 |
| Seguridad | Queries del DAL denegadas por política (visibilidad) | 100% registradas con trace_id |
| Seguridad | Ejecuciones con contenido no confiable sin spotlighting | 0 |
| Gobernanza | Versiones aprobadas sin eval suite ejecutada | 0 (desde R-23) |
| FinOps | Ejecuciones bloqueadas por presupuesto vs. coste evitado | Reporte mensual |
| Operación | MTTR con trazas OTel end-to-end | < 1 h |
| Datos | Restauración de backup ensayada | Trimestral, con acta |

---

## 8. Conclusión

Vellum no necesita una nueva arquitectura: necesita **completar los planos de control que su propia propuesta de valor exige**. Las decisiones estructurales (abstracción de proveedores, inmutabilidad, separación prompt/ejecución, evolución incremental) son correctas y están por encima de la media de plataformas comparables en esta fase.

Las tres inversiones que definen el éxito o fracaso productivo son: (1) gobernar el DAL con secretos dinámicos y políticas declarativas, (2) tratar todo contenido que alimenta un prompt como hostil y toda salida hacia un conector como sujeta a política, y (3) pagar hoy el coste pequeño de las decisiones de datos irreversibles — particionado, tenancy, retención. Todo lo demás —Kafka, Kubernetes, multi-región— puede y debe esperar a que la escala lo justifique, exactamente como el roadmap actual ya intuye.

---

*Informe elaborado como assessment independiente de arquitectura.*
*Referencias de marco: AWS Well-Architected Framework · OWASP Top 10 for LLM Applications · Patrones: Transactional Outbox, Circuit Breaker, Bulkhead (Release It!, Nygard) · NIST AI RMF.*
