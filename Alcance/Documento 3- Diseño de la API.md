# Documento 3: Diseño de la API (Contract-First)

**Sistema Corporativo de Gestión de Prompts**

---

## 1. Objetivo del documento

Definir de manera formal y detallada los contratos de la API REST que gobiernan el sistema, garantizando:

* Consistencia
* Seguridad
* Escalabilidad
* Trazabilidad

Este documento sirve como base directa para implementación en FastAPI y generación de OpenAPI.

---

## 2. Principios de diseño

* RESTful y stateless
* Versionado explícito (`/v1/`)
* JSON como formato estándar
* Respuestas consistentes
* Errores estructurados
* Seguridad por defecto
* Separación estricta entre **prompt** y **ejecución**

---

## 3. Convenciones generales

### 3.1 Base URL

```id="b1"
https://api.company.com/v1
```

---

### 3.2 Headers obligatorios

```id="b2"
Authorization: Bearer <JWT>
Content-Type: application/json
X-Request-Id: <uuid>
X-Environment: dev | staging | prod
```

---

### 3.3 Formato de respuesta estándar

```json id="b3"
{
  "data": {},
  "meta": {
    "request_id": "uuid",
    "version": "1.2.0"
  }
}
```

---

### 3.4 Formato de error

```json id="b4"
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Descripción clara",
    "details": {},
    "trace_id": "uuid"
  }
}
```

---

## 4. Autenticación

### 4.1 Tipo

* OAuth2 / JWT

---

### 4.2 Flujos soportados

* Authorization Code (usuarios)
* Client Credentials (sistemas externos)

---

## 5. Recursos principales

* Prompts
* Versions
* Executions
* Users
* Roles
* Connectors
* Config
* Metrics

---

# 6. API de Prompts

---

## 6.1 Crear prompt

**POST** `/prompts`

```json id="p1"
{
  "name": "Resumen de texto",
  "description": "Resume contenido largo",
  "content": "Resume el siguiente texto: {{text}}",
  "tags": ["nlp", "resumen"],
  "visibility": "team"
}
```

---

## 6.2 Listar prompts

**GET** `/prompts?tag=nlp&owner=user1`

---

## 6.3 Obtener prompt

**GET** `/prompts/{prompt_id}`

---

## 6.4 Actualizar prompt

**PUT** `/prompts/{prompt_id}`

---

## 6.5 Eliminar prompt

**DELETE** `/prompts/{prompt_id}`

---

# 7. API de Versiones

---

## 7.1 Crear nueva versión

**POST** `/prompts/{id}/versions`

```json id="v1"
{
  "content": "Nuevo contenido del prompt",
  "change_log": "Mejora en instrucciones"
}
```

---

## 7.2 Listar versiones

**GET** `/prompts/{id}/versions`

---

## 7.3 Obtener versión específica

**GET** `/prompts/{id}/versions/{version_id}`

---

# 8. API de Ejecución (CRÍTICA)

---

## 8.1 Ejecutar prompt

**POST** `/executions`

```json id="e1"
{
  "prompt_id": "123",
  "version": "v5",
  "inputs": {
    "text": "Contenido a resumir"
  },
  "options": {
    "async": false,
    "model": "gpt-4"
  }
}
```

---

## 8.2 Respuesta síncrona

```json id="e2"
{
  "data": {
    "execution_id": "abc123",
    "output": "Resumen generado",
    "status": "completed"
  }
}
```

---

## 8.3 Respuesta asíncrona

```json id="e3"
{
  "data": {
    "execution_id": "abc123",
    "status": "queued"
  }
}
```

---

## 8.4 Consultar ejecución

**GET** `/executions/{execution_id}`

---

# 9. API de Gobernanza

---

## 9.1 Aprobar prompt

**POST** `/prompts/{id}/approve`

---

## 9.2 Deprecar prompt

**POST** `/prompts/{id}/deprecate`

---

# 10. API de Búsqueda

---

## 10.1 Buscar prompts

**GET** `/search`

Parámetros:

* query
* tags
* owner
* status

---

# 11. API de Conectores

---

## 11.1 Crear conector

**POST** `/connectors`

```json id="c1"
{
  "type": "confluence",
  "config": {
    "base_url": "...",
    "space": "DEV",
    "token": "****"
  }
}
```

---

## 11.2 Listar conectores

**GET** `/connectors`

---

## 11.3 Activar/desactivar

**POST** `/connectors/{id}/enable`

---

# 12. API de Configuración

---

## 12.1 Obtener configuración

**GET** `/config`

---

## 12.2 Actualizar configuración

**PUT** `/config`

---

# 13. API de Métricas

---

## 13.1 Métricas por prompt

**GET** `/metrics/prompts/{id}`

---

## 13.2 Métricas globales

**GET** `/metrics/usage`

---

# 14. API de Usuarios y Roles

---

## 14.1 Listar usuarios

**GET** `/users`

---

## 14.2 Asignar rol

**POST** `/users/{id}/roles`

---

# 15. API de versión del sistema

---

## 15.1 Obtener versión

**GET** `/version`

```json id="ver1"
{
  "version": "1.2.0"
}
```

---

# 16. Rate limiting

* Por usuario
* Por API key
* Por endpoint

Ejemplo:

* 100 requests/min

---

# 17. Idempotencia

Para endpoints críticos:

Header:

```id="idem"
Idempotency-Key: <uuid>
```

---

# 18. Seguridad adicional

* Validación de inputs
* Sanitización
* Protección contra inyección
* Auditoría obligatoria

---

# 19. Versionado de API

* `/v1/` actual
* `/v2/` futura

Estrategia:

* No romper contratos existentes
* Deprecación controlada

---

# 20. Códigos de estado HTTP

* 200 OK
* 201 Created
* 400 Bad Request
* 401 Unauthorized
* 403 Forbidden
* 404 Not Found
* 500 Internal Error

---

# 21. Resumen ejecutivo

La API define un **control plane centralizado** donde:

* Los prompts nunca se ejecutan directamente por clientes
* Todo pasa por validación y gobernanza
* Se garantiza trazabilidad total
* Se habilita integración segura con sistemas externos

---
