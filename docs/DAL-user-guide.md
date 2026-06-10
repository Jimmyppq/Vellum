# dal — Manual de Uso

## Arranque rápido

```bash
# Desde la raíz del proyecto
cp dal/.env.example dal/.env
# Editar dal/.env con los valores reales (DB_HOST, DB_NAME, DB_USER, DB_PASSWORD)
docker compose up -d postgres dal
```

El servicio queda disponible en `http://localhost:8002`.  
Health check: `http://localhost:8002/health`

> El DAL es un servicio interno. En producción solo es accesible desde la red Docker interna `vellum-internal`. No exponer el puerto 8002 hacia el exterior.

---

## Configuración

### Variables de entorno (`.env`)

```bash
cd dal
cp .env.example .env
```

**Base de datos** — valores obligatorios:

```bash
DB_HOST=localhost        # o el nombre del servicio Docker (ej. "postgres")
DB_PORT=5432
DB_NAME=vellum
DB_USER=vellum_user
DB_PASSWORD=tu-password-segura
```

**Pool de conexiones** — ajustar según la carga esperada:

```bash
DB_POOL_SIZE=10          # conexiones permanentes en el pool
DB_MAX_OVERFLOW=20       # conexiones extra permitidas sobre el pool
DB_POOL_TIMEOUT=30       # segundos de espera antes de error de pool
```

**Autenticación interna** — en entornos dev (`MTLS_ENABLED=false`):

```bash
INTERNAL_SERVICE_TOKEN=genera-un-token-con-openssl-rand-base64-32
```

Todos los servicios que llamen al DAL deben incluir este token en el header `X-Internal-Service-Token`. Si no se configura, el DAL acepta todas las solicitudes con un warning en el log de arranque.

**mTLS** — requerido en staging y producción:

```bash
MTLS_ENABLED=true
MTLS_CERT_PATH=/certs/dal.crt
MTLS_KEY_PATH=/certs/dal.key
MTLS_CA_PATH=/certs/ca.crt
```

Cuando `MTLS_ENABLED=true`, la validación por token queda deshabilitada automáticamente.

---

## Autenticación

En entornos dev (`MTLS_ENABLED=false`), todas las solicitudes (excepto `GET /health`) requieren el header:

```
X-Internal-Service-Token: tu-token-configurado
```

En staging y producción (`MTLS_ENABLED=true`), la autenticación la gestiona el certificado mTLS del cliente y no se requiere el header.

El endpoint `GET /health` está siempre exento de autenticación.

---

## Índice de endpoints

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `GET` | `/health` | Estado del servicio y de la base de datos |
| `POST` | `/v1/prompts` | Crear prompt |
| `GET` | `/v1/prompts` | Listar prompts (con filtros) |
| `GET` | `/v1/prompts/{id}` | Obtener prompt por ID |
| `PATCH` | `/v1/prompts/{id}/status` | Cambiar estado del prompt |
| `DELETE` | `/v1/prompts/{id}` | Eliminar prompt |
| `POST` | `/v1/prompts/{id}/versions` | Crear versión de prompt |
| `GET` | `/v1/prompts/{id}/versions` | Listar versiones de un prompt |
| `GET` | `/v1/prompts/{id}/versions/active` | Obtener versión activa |
| `GET` | `/v1/prompts/{id}/versions/{version_id}` | Obtener versión específica |
| `POST` | `/v1/executions` | Registrar ejecución |
| `GET` | `/v1/executions/{id}` | Obtener ejecución por ID |
| `PATCH` | `/v1/executions/{id}/status` | Actualizar estado de ejecución |
| `GET` | `/v1/executions` | Listar ejecuciones (filtro por `prompt_id`) |
| `POST` | `/v1/users` | Crear usuario |
| `GET` | `/v1/users/{id}` | Obtener usuario por ID |
| `GET` | `/v1/users/email/{email}` | Obtener usuario por email (case-insensitive) |
| `POST` | `/v1/users/{id}/roles` | Asignar rol a usuario |
| `POST` | `/v1/transcripts` | Crear transcripción |
| `GET` | `/v1/transcripts/{id}` | Obtener transcripción |
| `POST` | `/v1/transcripts/{id}/versions` | Crear versión de transcripción |
| `GET` | `/v1/transcripts/{id}/versions` | Listar versiones de transcripción |
| `GET` | `/v1/transcripts/{id}/versions/active` | Obtener versión activa de transcripción |
| `POST` | `/v1/connectors` | Crear conector |
| `GET` | `/v1/connectors/{id}` | Obtener conector |
| `GET` | `/v1/connectors` | Listar conectores activos |
| `PATCH` | `/v1/connectors/{id}/active` | Activar/desactivar conector |
| `GET` | `/v1/config` | Leer configuración del sistema |
| `PUT` | `/v1/config/{key}` | Crear o actualizar valor de configuración |

---

## Endpoints

### `GET /health` — Estado del servicio

No requiere autenticación. Retorna el estado del servicio y de la conexión a la base de datos.

```bash
curl -s http://localhost:8002/health | jq
```

**Respuesta:**

```json
{
  "status": "ok",
  "db": true,
  "service": "dal",
  "version": "1.0.0"
}
```

Cuando `db` es `false`, la base de datos no es accesible pero el servicio está en pie. Usar en health checks de Kubernetes/Docker.

---

### Prompts

#### `POST /v1/prompts` — Crear prompt

```bash
curl -s -X POST http://localhost:8002/v1/prompts \
  -H "Content-Type: application/json" \
  -H "X-Internal-Service-Token: tu-token" \
  -d '{
    "name": "Clasificador de tickets",
    "description": "Clasifica tickets de soporte por categoría y urgencia",
    "owner_id": "550e8400-e29b-41d4-a716-446655440000"
  }' | jq
```

**Campos:**

| Campo | Tipo | Requerido | Descripción |
|-------|------|:---------:|-------------|
| `name` | string | **Sí** | Nombre del prompt |
| `owner_id` | UUID | **Sí** | ID del usuario propietario |
| `description` | string | No | Descripción legible |
| `visibility` | `"private"` \| `"public"` | No | Visibilidad; default `"private"` |

**Respuesta (201):**

```json
{
  "data": {
    "id": "a1b2c3d4-...",
    "name": "Clasificador de tickets",
    "description": "Clasifica tickets de soporte por categoría y urgencia",
    "owner_id": "550e8400-...",
    "status": "draft",
    "visibility": "private",
    "created_at": "2026-05-31T10:00:00Z",
    "updated_at": "2026-05-31T10:00:00Z"
  },
  "meta": {
    "request_id": "uuid",
    "version": "1.0.0"
  }
}
```

Todo prompt se crea con `status: "draft"`. Para activarlo, usar `PATCH /{id}/status`.

#### `GET /v1/prompts` — Listar prompts

```bash
# Todos los prompts aprobados de un propietario
curl -s "http://localhost:8002/v1/prompts?status=approved&owner_id=550e8400-...&limit=20&offset=0" \
  -H "X-Internal-Service-Token: tu-token" | jq
```

**Query params:**

| Param | Tipo | Descripción |
|-------|------|-------------|
| `status` | string | Filtrar por estado: `draft`, `approved`, `deprecated` |
| `owner_id` | UUID | Filtrar por propietario |
| `limit` | int | Máximo de resultados (1–200, default 50) |
| `offset` | int | Paginación (default 0) |

#### `PATCH /v1/prompts/{id}/status` — Cambiar estado

```bash
curl -s -X PATCH http://localhost:8002/v1/prompts/a1b2c3d4-.../status \
  -H "Content-Type: application/json" \
  -H "X-Internal-Service-Token: tu-token" \
  -d '{"status": "approved"}' | jq
```

Estados válidos: `draft`, `approved`, `deprecated`. La transición es libre entre cualquier estado válido.

---

### Versiones de prompt

Las versiones de prompt son **inmutables**: una vez creadas, su contenido no cambia. Para modificar el texto de un prompt se crea una nueva versión.

#### `POST /v1/prompts/{id}/versions` — Crear versión

```bash
curl -s -X POST http://localhost:8002/v1/prompts/a1b2c3d4-.../versions \
  -H "Content-Type: application/json" \
  -H "X-Internal-Service-Token: tu-token" \
  -d '{
    "content": "Eres un clasificador. Dado el siguiente ticket: {{ticket}}\nResponde con: categoría y urgencia.",
    "created_by": "550e8400-...",
    "is_active": true,
    "change_log": "Mejora del prompt con variable de plantilla"
  }' | jq
```

**Campos:**

| Campo | Tipo | Requerido | Descripción |
|-------|------|:---------:|-------------|
| `content` | string | **Sí** | Texto completo del prompt |
| `created_by` | UUID | **Sí** | ID del usuario autor |
| `is_active` | bool | No | Si es `true`, desactiva la versión actual atómicamente |
| `change_log` | string | No | Descripción del cambio |

Cuando `is_active: true`, el sistema desactiva todas las versiones previas del mismo prompt en la misma transacción. Solo puede haber una versión activa por prompt.

#### `GET /v1/prompts/{id}/versions/active` — Obtener versión activa

```bash
curl -s http://localhost:8002/v1/prompts/a1b2c3d4-.../versions/active \
  -H "X-Internal-Service-Token: tu-token" | jq
```

Retorna HTTP 404 si el prompt no tiene ninguna versión activa.

---

### Ejecuciones

#### `POST /v1/executions` — Registrar ejecución

```bash
curl -s -X POST http://localhost:8002/v1/executions \
  -H "Content-Type: application/json" \
  -H "X-Internal-Service-Token: tu-token" \
  -d '{
    "prompt_id": "a1b2c3d4-...",
    "version_id": "b2c3d4e5-...",
    "executed_by": "550e8400-...",
    "input_data": {
      "ticket": "El sistema de login no responde desde las 09:00."
    }
  }' | jq
```

**Campos:**

| Campo | Tipo | Requerido | Descripción |
|-------|------|:---------:|-------------|
| `prompt_id` | UUID | **Sí** | ID del prompt ejecutado |
| `version_id` | UUID | **Sí** | ID de la versión específica usada |
| `executed_by` | UUID | **Sí** | ID del usuario que inicia la ejecución |
| `input_data` | object | **Sí** | Variables de entrada del prompt (JSONB) |
| `transcript_id` | UUID | No | ID de transcripción asociada (si aplica) |

La ejecución se crea con `status: "queued"`. El worker actualiza el estado conforme procesa.

#### `PATCH /v1/executions/{id}/status` — Actualizar estado

```bash
curl -s -X PATCH http://localhost:8002/v1/executions/c3d4e5f6-.../status \
  -H "Content-Type: application/json" \
  -H "X-Internal-Service-Token: tu-token" \
  -d '{
    "status": "completed",
    "output_data": {
      "categoria": "Infraestructura",
      "urgencia": "alta",
      "resumen": "Fallo en el servicio de autenticación."
    }
  }' | jq
```

**Estados válidos:** `queued` → `running` → `completed` | `failed`

Cuando el estado pasa a `completed` o `failed`, el campo `completed_at` se setea automáticamente con la hora UTC actual.

**Campos del body:**

| Campo | Tipo | Requerido | Descripción |
|-------|------|:---------:|-------------|
| `status` | string | **Sí** | Nuevo estado |
| `output_data` | object | No | Resultado de la ejecución (requerido en `completed`) |

---

### Usuarios

#### `POST /v1/users` — Crear usuario

```bash
curl -s -X POST http://localhost:8002/v1/users \
  -H "Content-Type: application/json" \
  -H "X-Internal-Service-Token: tu-token" \
  -d '{
    "username": "ana.garcia",
    "email": "ana.garcia@empresa.com"
  }' | jq
```

Si el email ya existe, retorna HTTP 409 con código `USER_EMAIL_CONFLICT`. El email se normaliza a minúsculas internamente.

#### `GET /v1/users/email/{email}` — Buscar por email

La búsqueda es case-insensitive: `Ana.Garcia@Empresa.COM` encuentra el mismo usuario que `ana.garcia@empresa.com`.

```bash
curl -s "http://localhost:8002/v1/users/email/Ana.Garcia@Empresa.COM" \
  -H "X-Internal-Service-Token: tu-token" | jq
```

#### `POST /v1/users/{id}/roles` — Asignar rol

```bash
curl -s -X POST http://localhost:8002/v1/users/550e8400-.../roles \
  -H "Content-Type: application/json" \
  -H "X-Internal-Service-Token: tu-token" \
  -d '{"role_id": "rol-uuid-aqui"}' | jq
```

Retorna HTTP 404 si el usuario o el rol no existen. Retorna HTTP 409 con `ROLE_ALREADY_ASSIGNED` si el rol ya está asignado.

---

### Configuración del sistema

#### `GET /v1/config` — Leer toda la configuración

```bash
curl -s http://localhost:8002/v1/config \
  -H "X-Internal-Service-Token: tu-token" | jq
```

#### `PUT /v1/config/{key}` — Crear o actualizar un valor

```bash
curl -s -X PUT http://localhost:8002/v1/config/max_prompt_size_kb \
  -H "Content-Type: application/json" \
  -H "X-Internal-Service-Token: tu-token" \
  -d '{"value": 10}' | jq
```

La operación es un upsert: si la clave existe la actualiza, si no existe la crea. `value` acepta cualquier tipo JSON válido (número, string, objeto, array).

---

## Formato de respuestas

### Respuesta exitosa

```json
{
  "data": { ... },
  "meta": {
    "request_id": "uuid-unico-por-solicitud",
    "version": "1.0.0"
  }
}
```

### Respuesta de error

```json
{
  "detail": {
    "code": "NOT_FOUND",
    "message": "Prompt a1b2c3d4 not found"
  }
}
```

---

## Códigos de error

| HTTP | `code` | Descripción |
|------|--------|-------------|
| 401 | `MISSING_SERVICE_TOKEN` | Header `X-Internal-Service-Token` ausente |
| 401 | `INVALID_SERVICE_TOKEN` | Token incorrecto |
| 404 | `NOT_FOUND` | Entidad no encontrada |
| 409 | `USER_EMAIL_CONFLICT` | Email de usuario ya registrado |
| 409 | `ROLE_ALREADY_ASSIGNED` | El usuario ya tiene ese rol asignado |
| 422 | (Pydantic) | Campo requerido ausente o tipo incorrecto |
| 500 | `INTERNAL_SERVER_ERROR` | Error interno no controlado |

---

## Headers de respuesta

| Header | Descripción |
|--------|-------------|
| `X-Trace-Id` | UUID propagado de extremo a extremo; se genera si la solicitud no lo incluía |

Para correlacionar una solicitud con los logs del DAL, usa el valor de `X-Trace-Id` de la respuesta:

```bash
curl -si http://localhost:8002/v1/prompts/a1b2c3d4-... \
  -H "X-Internal-Service-Token: tu-token" \
  -H "X-Trace-Id: mi-trace-id-personalizado" \
  | grep -i "x-trace-id"
```

---

## Ejemplos de integración desde el backend

El backend nunca debe importar código del DAL directamente. Toda comunicación es HTTP:

```python
import httpx
from uuid import UUID

DAL_URL = "http://dal:8002"  # nombre del servicio Docker
HEADERS = {
    "X-Internal-Service-Token": settings.INTERNAL_SERVICE_TOKEN,
    "X-Trace-Id": request.state.trace_id,  # propagar trace_id
}

# Obtener versión activa de un prompt
async def get_active_version(prompt_id: UUID) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{DAL_URL}/v1/prompts/{prompt_id}/versions/active",
            headers=HEADERS,
        )
        resp.raise_for_status()
        return resp.json()["data"]


# Registrar una ejecución
async def create_execution(prompt_id: UUID, version_id: UUID, user_id: UUID, input_data: dict) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{DAL_URL}/v1/executions",
            headers=HEADERS,
            json={
                "prompt_id": str(prompt_id),
                "version_id": str(version_id),
                "executed_by": str(user_id),
                "input_data": input_data,
            },
        )
        resp.raise_for_status()
        return resp.json()["data"]
```

En staging y producción, pasar los certificados mTLS al cliente httpx:

```python
async with httpx.AsyncClient(
    cert=(settings.MTLS_CERT_PATH, settings.MTLS_KEY_PATH),
    verify=settings.MTLS_CA_PATH,
) as client:
    ...
```

---

## Ejecución de tests

```bash
cd dal
# Tests contra PostgreSQL real vía Docker
docker compose -f docker-compose.test.yml up --build --abort-on-container-exit

# Ver coverage
docker compose -f docker-compose.test.yml logs tests
```
