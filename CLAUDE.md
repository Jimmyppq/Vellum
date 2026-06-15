# CLAUDE.md — Reglas de Arquitectura para Agentes de IA

**Proyecto:** Vellum — Sistema Corporativo de Gestión de Prompts  
**Aplicable a:** Todo agente de IA (Claude Code u otros) que genere, modifique o revise código en este repositorio.  
**Nivel de cumplimiento:** OBLIGATORIO. Estas reglas no son sugerencias. Ninguna excepción sin aprobación explícita del arquitecto del proyecto.

---

## 1. Mapa de Componentes — Lo que existe y sus fronteras

El sistema está compuesto por los siguientes microservicios. Cada uno es un proceso independiente con su propio repositorio o subdirectorio, su propio Dockerfile y su propia responsabilidad. **No mezclar responsabilidades entre componentes.**

| Componente | Tecnología | Responsabilidad única |
|---|---|---|
| `frontend` | Angular | UI, visualización, interacción de usuario |
| `backend` | FastAPI | Lógica de negocio, orquestación, gobernanza |
| `router-ai` | FastAPI | Abstracción de proveedores LLM y ASR |
| `dal` | FastAPI | Abstracción de motores de base de datos (DAL) |
| `worker` | Celery + Redis | Procesamiento asíncrono: transcripciones, conectores |
| `conector-in` | FastAPI | Ingress de datos externos (webhooks, uploads) |
| `conector-out` | FastAPI | Egress hacia sistemas corporativos externos |
| `gateway` | Nginx | Reverse proxy, TLS termination, rate limiting |

---

## 2. Reglas Absolutas — PROHIBICIONES

### 2.1 SQL — PROHIBIDO generarlo fuera del DAL

```
❌ PROHIBIDO en cualquier parte del código que no sea el componente `dal`:
   - Strings SQL crudos: "SELECT * FROM ...", "INSERT INTO ...", "UPDATE ..."
   - Concatenación de strings para construir queries
   - f-strings con contenido SQL
   - Cualquier llamada directa a drivers de base de datos (psycopg2, cx_Oracle, pymysql, pyodbc)

✅ CORRECTO:
   - El backend llama al DAL mediante su API FastAPI interna
   - El DAL usa SQLAlchemy Core/ORM con bind parameters
   - Nunca se acepta SQL crudo como input desde ningún cliente
```

Justificación: el DAL es la única capa que conoce el dialecto del motor del cliente (Oracle, PostgreSQL, SQL-Server, MySQL, MariaDB). Centralizar aquí garantiza portabilidad entre clientes on-premise con distintos DBMS y elimina SQL injection estructuralmente.

### 2.2 LLMs — PROHIBIDO llamarlos directamente desde cualquier componente que no sea `router-ai`

```
❌ PROHIBIDO en backend, worker, conector-in, conector-out o cualquier otro componente:
   - import openai  (y uso directo de openai.ChatCompletion, openai.chat.completions, etc.)
   - import anthropic
   - import google.generativeai
   - Cualquier HTTP directo a https://api.openai.com, https://api.anthropic.com, etc.
   - Llamadas a Ollama, LMStudio o DeepSeek fuera del router-ai

✅ CORRECTO:
   - El backend envía una ExecutionIntent estructurada al router-ai vía FastAPI interna
   - El router-ai resuelve el proveedor, ejecuta y retorna el resultado
```

Justificación: el router-ai es la capa de abstracción que evita vendor lock-in. Si mañana el cliente requiere un modelo on-premise (Ollama) en lugar de OpenAI, el cambio es de configuración, no de código.

### 2.3 Frontend — PROHIBIDO acceder directamente a servicios internos

```
❌ PROHIBIDO en el frontend Angular:
   - Llamadas HTTP directas al backend saltando el API Gateway
   - Cualquier referencia a puertos internos (8000, 8001, 8002...)
   - Lógica de negocio crítica (validaciones que afecten seguridad o gobernanza)
   - Almacenar tokens JWT o credenciales en localStorage o sessionStorage

✅ CORRECTO:
   - Todo tráfico del frontend pasa por el API Gateway (puerto 443 / 80)
   - Los tokens se almacenan en cookies httpOnly
   - Las validaciones de negocio críticas viven en el backend
```

### 2.4 Secretos — PROHIBIDO hardcodear cualquier credencial

```
❌ PROHIBIDO en cualquier archivo de código fuente, incluyendo tests:
   - API keys de LLMs (OpenAI, Anthropic, Google...)
   - Credenciales de base de datos
   - Tokens de conectores (Confluence, Slack, Zapier...)
   - DSN de conexión a DBMS del cliente
   - Claves de cifrado o signing secrets

✅ CORRECTO:
   - Variables de entorno mediante archivo .env (nunca commiteado)
   - En producción: Secret Manager (HashiCorp Vault, AWS Secrets Manager)
   - Las credenciales de conectores van cifradas en connector_configs (AES-256)
```

---

## 3. Comunicación entre Microservicios — Reglas de Transporte

### 3.1 Protocolo: FastAPI sobre mTLS

Toda comunicación servicio-a-servicio (backend ↔ router-ai, backend ↔ dal, backend ↔ worker, etc.) usa **HTTP/REST con FastAPI** y debe operar sobre **mTLS (mutual TLS)** en entornos staging y producción.

```
✅ Patrón correcto de llamada inter-servicio:

# Desde el backend hacia el router-ai
import httpx

async def execute_prompt(intent: ExecutionIntent) -> ExecutionResult:
    async with httpx.AsyncClient(cert=CLIENT_CERT, verify=CA_CERT) as client:
        response = await client.post(
            "https://router-ai:8001/v1/execute",
            json=intent.model_dump(),
            headers={"X-Trace-Id": trace_id}
        )
    return ExecutionResult(**response.json())
```

```
❌ PROHIBIDO:
   - HTTP plano (sin TLS) entre servicios en staging/prod
   - Comunicación directa entre servicios que no sea a través de sus APIs FastAPI
   - Imports cruzados de módulos Python entre proyectos de distintos microservicios
   - Llamadas directas a funciones de otro microservicio (no son librerías compartidas)
```

### 3.2 Certificados mTLS

Cada microservicio tiene su propio par de certificados (cert + key) firmados por la CA interna del proyecto. El cliente presenta su certificado al servidor y viceversa. En desarrollo local se puede usar HTTP plano dentro de la red Docker interna, pero el código debe soportar la configuración mTLS mediante variables de entorno.

```
Variables de entorno requeridas por cada servicio:
  MTLS_CERT_PATH=/certs/service.crt
  MTLS_KEY_PATH=/certs/service.key
  MTLS_CA_PATH=/certs/ca.crt
  MTLS_ENABLED=true  # false solo en entorno dev local
```

### 3.3 Propagación de Trace ID

Todo request entre servicios debe propagar el header `X-Trace-Id`. Si un request llega sin él, el servicio receptor lo genera. Nunca se pierde a lo largo de la cadena.

```python
# Patrón obligatorio en todos los endpoints FastAPI
from fastapi import Request
import uuid

@app.middleware("http")
async def propagate_trace_id(request: Request, call_next):
    trace_id = request.headers.get("X-Trace-Id", str(uuid.uuid4()))
    request.state.trace_id = trace_id
    response = await call_next(request)
    response.headers["X-Trace-Id"] = trace_id
    return response
```

---

## 4. Arquitectura del DAL — Reglas de Implementación

El DAL (Database Abstraction Layer) es el único componente que tiene drivers de base de datos instalados. Implementa el patrón Repository sobre SQLAlchemy Core.

```python
# Estructura obligatoria del DAL
dal/
  ├── providers/
  │   ├── base.py          # Interfaz abstracta: nunca SQL crudo aquí
  │   ├── postgres.py      # Implementación PostgreSQL
  │   ├── oracle.py        # Implementación Oracle
  │   ├── sqlserver.py     # Implementación SQL-Server
  │   ├── mysql.py         # Implementación MySQL/MariaDB
  └── router.py            # Selecciona el provider según configuración
```

```
Reglas internas del DAL:
  ✅ Usar SQLAlchemy Core con Table() + select() + insert() + update()
  ✅ Siempre bind parameters, nunca interpolación de strings
  ✅ Conexiones en modo read-only cuando la operación es solo consulta
  ✅ Pool de conexiones configurado por variables de entorno
  ✅ Loggear toda query ejecutada con su trace_id (sin datos sensibles)
  ❌ No aceptar strings SQL como input en ningún endpoint
  ❌ No exponer el DSN ni credenciales en respuestas de la API
  ❌ No instalar drivers de MongoDB (fuera de scope)
```

---

## 5. Arquitectura del Router-AI — Reglas de Implementación

El router-ai es el único componente que importa SDKs de LLMs. Implementa el patrón Strategy para selección de proveedor.

```python
# Estructura obligatoria del router-ai
router-ai/
  ├── providers/
  │   ├── base.py           # Interfaz abstracta BaseProvider
  │   ├── openai_provider.py
  │   ├── anthropic_provider.py
  │   ├── google_provider.py
  │   ├── ollama_provider.py
  │   ├── deepseek_provider.py
  │   └── lmstudio_provider.py
  ├── asr/
  │   ├── base.py           # Interfaz abstracta BaseASRProvider
  │   ├── whisper_provider.py
  │   └── azure_speech_provider.py
  └── router.py             # Selecciona provider según ExecutionIntent
```

```
Reglas internas del router-ai:
  ✅ Todo proveedor implementa la interfaz BaseProvider
  ✅ La selección de proveedor es configurable por variables de entorno o por ExecutionIntent
  ✅ Implementar circuit breaker por proveedor (timeout + fallback)
  ✅ Loggear: proveedor usado, modelo, tokens consumidos, latencia, coste estimado
  ❌ No mezclar lógica de negocio de prompts aquí (eso es responsabilidad del backend)
  ❌ No cachear prompts aquí (el cache vive en el backend con Redis)
```

---

## 6. Seguridad — Reglas Transversales

### 6.1 Autenticación y Autorización

```
- Todo endpoint del backend requiere JWT válido (OAuth2/OIDC, RS256)
- JWT contiene: sub (user_id), roles[], exp, iss
- Expiración máxima de access token: 60 minutos
- Refresh tokens con rotación obligatoria
- Endpoints de solo lectura: scope viewer suficiente
- Endpoints de ejecución: scope service o superior
- Endpoints de aprobación: scope approver o admin
- Endpoints de administración: scope admin exclusivamente
```

### 6.2 Validación de Inputs

```
- Todos los modelos Pydantic deben tener validators explícitos
- Tamaño máximo de input para ejecución de prompts: configurable, default 10KB
- Sanitización obligatoria de cualquier input que se inyecte en un prompt
- Detección de PII antes de enviar al router-ai (configurable por entorno)
- Los IDs siempre son UUID, nunca enteros secuenciales expuestos
```

### 6.3 Logging — Lo que NUNCA debe aparecer en logs

```
❌ Nunca loggear:
   - Tokens JWT completos
   - Credenciales de base de datos o DSN con password
   - API keys de LLMs
   - Tokens de conectores
   - Contenido de inputs que pueda contener PII
   - Outputs completos de LLMs si contienen datos sensibles

✅ Siempre loggear:
   - trace_id
   - user_id (no username, no email)
   - Acción ejecutada
   - Timestamp UTC
   - Resultado (success/failure)
   - Código de error si aplica
```

---

## 7. Modelo de Datos — Reglas de Evolución

```
- Las migraciones se gestionan con Alembic
- Cada migración debe ser reversible (upgrade + downgrade implementados)
- Nunca usar features propietarios de un motor en migraciones (usar tipos SQLAlchemy estándar)
- La tabla executions debe particionarse por fecha desde el inicio: PARTITION BY RANGE(created_at)
- Los campos content de prompts y transcripciones son inmutables: nunca UPDATE, siempre INSERT de nueva versión
- Los campos de configuración sensible en connector_configs siempre van cifrados (encrypted=true)
- JSONB solo en campos donde la estructura es genuinamente variable (input_data, output_data, config)
```

---

## 8. Estructura de Respuestas API

Todo endpoint FastAPI del sistema debe retornar este formato. Sin excepciones.

```python
# Respuesta exitosa
{
  "data": { ... },
  "meta": {
    "request_id": "uuid",
    "version": "1.0.0"
  }
}

# Error
{
  "error": {
    "code": "PROMPT_NOT_APPROVED",   # snake_case en mayúsculas
    "message": "Descripción legible",
    "trace_id": "uuid"
  }
}
```

```
Códigos HTTP obligatorios:
  200 → OK (GET, PUT exitoso)
  201 → Created (POST exitoso)
  202 → Accepted (operación asíncrona encolada)
  400 → Bad Request (input inválido)
  401 → Unauthorized (sin token o token inválido)
  403 → Forbidden (token válido pero sin permisos)
  404 → Not Found
  409 → Conflict (violación de unicidad o estado inválido)
  422 → Unprocessable Entity (validación Pydantic)
  500 → Internal Server Error
```

---

## 9. Contenerización — Reglas Docker

```
- Cada microservicio tiene su propio Dockerfile
- Las imágenes base deben ser slim o alpine (minimizar superficie de ataque)
- Los contenedores no corren como root (USER appuser)
- Los secretos nunca van en el Dockerfile ni en docker-compose commiteado
- El archivo .env nunca se commitea (está en .gitignore)
- Cada servicio expone un endpoint /health para healthcheck
- Los volúmenes de datos (PostgreSQL, logs) son nombrados explícitamente
- La base de datos nunca expone su puerto fuera de la red Docker interna
```

---

## 10. Lo que un Agente de IA DEBE hacer antes de generar código

0. **Leer `docs/ESTADO.md`** para conocer qué está construido, en qué fase está el proyecto y qué sigue. Este archivo (CLAUDE.md) da las reglas; ESTADO.md da la situación.
1. **Identificar a qué microservicio pertenece** el código que va a generar. Si no está claro, preguntar.
2. **Verificar que no cruza fronteras**: un módulo del backend no importa código del dal ni del router-ai directamente.
3. **Verificar que toda query pasa por el DAL** si el código involucra acceso a datos.
4. **Verificar que toda llamada a LLM pasa por el router-ai** si el código involucra ejecución de prompts.
5. **Verificar que las llamadas inter-servicio usan httpx** (async) con la configuración mTLS correspondiente.
6. **Verificar que los modelos Pydantic tienen validators** cuando el input viene del exterior.
7. **Verificar que el trace_id se propaga** si el código maneja requests.

---

## 11. Referencia Rápida — Dependencias Permitidas por Componente

| Componente | Puede llamar a | No puede llamar a |
|---|---|---|
| `frontend` | `gateway` | Cualquier servicio interno directamente |
| `backend` | `router-ai`, `dal`, `redis`, `worker (via Redis)` | LLMs directamente, DBMS directamente |
| `router-ai` | LLMs externos, modelos locales, `redis` | `dal`, `backend`, DBMS |
| `dal` | DBMS del cliente | LLMs, `backend`, `router-ai` |
| `worker` | `router-ai`, `dal`, `conector-out`, `redis` | LLMs directamente, DBMS directamente |
| `conector-in` | `backend` | LLMs, DBMS, conectores externos |
| `conector-out` | Sistemas externos (Confluence, Slack, Zapier...) | `dal`, `router-ai` directamente |

---

## 12. Estado de la Implementación — docs/ESTADO.md

`docs/ESTADO.md` es el registro vivo del estado del proyecto: matriz de componentes (construido / en curso / no iniciado), fase actual, trabajo en curso y próximos pasos.

```
Reglas OBLIGATORIAS para todo agente:
  ✅ Leer docs/ESTADO.md al inicio de cualquier tarea de implementación o análisis
  ✅ Al COMPLETAR una implementación (típicamente al archivar un change de OpenSpec),
     actualizar docs/ESTADO.md en el mismo turno de trabajo:
       - fila del componente afectado en la matriz (§1)
       - trabajo en curso (§3), próximos pasos (§5) y cola de propuestas (§6)
       - añadir la fila al historial de cambios (§7)
       - fecha de "Última actualización"
  ❌ No duplicar en ESTADO.md el detalle técnico (eso va en docs/ y openspec/specs/)
  ❌ No marcar nada como construido sin tests en verde
```

Justificación: sin un punto de entrada actualizado, cada agente debe reconstruir el contexto desde auditorías, git log y openspec — costoso y propenso a conclusiones desfasadas.

---

*Este archivo es la fuente de verdad arquitectónica para cualquier agente de IA trabajando en este proyecto.*  
*Última actualización: Junio 2026 — v1.1: router-ai autorizado a llamar a `redis` (§11); añadido §12 (docs/ESTADO.md)*
