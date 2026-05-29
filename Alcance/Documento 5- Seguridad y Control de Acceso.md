# Documento 5: Seguridad y Control de Acceso

**Sistema Corporativo de Gestión de Prompts**

---

## 1. Objetivo del documento

Definir el modelo de seguridad integral del sistema, cubriendo:

* Autenticación
* Autorización
* Protección de datos
* Seguridad en ejecución de prompts
* Auditoría

---

## 2. Principios de seguridad

* **Zero Trust**: no se confía en ningún actor por defecto
* **Least Privilege**: acceso mínimo necesario
* **Defense in Depth**: múltiples capas de seguridad
* **Security by Design**: no como añadido, sino como base
* **Auditabilidad total**

---

## 3. Autenticación

---

### 3.1 Estándar

* OAuth 2.0 + OpenID Connect (OIDC)

---

### 3.2 Tipos de autenticación

#### Usuarios humanos

* Login vía SSO corporativo
* Tokens JWT

---

#### Sistemas externos (machine-to-machine)

* Client Credentials Flow
* API Keys (opcional, menos recomendable)

---

### 3.3 Tokens JWT

Contenido mínimo:

```json id="s1"
{
  "sub": "user_id",
  "roles": ["admin"],
  "exp": 1710000000,
  "iss": "auth-server"
}
```

---

### 3.4 Buenas prácticas

* Expiración corta (15–60 min)
* Refresh tokens
* Firma segura (RS256)
* Validación en cada request

---

## 4. Autorización

---

## 4.1 Modelo híbrido

Se combina:

* RBAC (roles)
* ABAC (atributos)

---

## 4.2 Roles base

* **Admin** → control total
* **Editor** → crea y modifica
* **Approver** → aprueba prompts
* **Viewer** → solo lectura
* **Service** → acceso API

---

## 4.3 Atributos (ABAC)

* Owner del prompt
* Área / equipo
* Sensibilidad del prompt
* Entorno (dev/prod)

---

## 4.4 Ejemplos de reglas

* Un editor solo modifica prompts propios
* Un approver no puede ejecutar prompts sin aprobación
* Un sistema externo solo ejecuta prompts autorizados

---

## 4.5 Implementación en FastAPI

* Dependencias (`Depends`)
* Middleware de seguridad
* Decoradores por endpoint

---

## 5. Seguridad en la API

---

### 5.1 Protección básica

* HTTPS obligatorio
* Validación de headers
* Sanitización de inputs

---

### 5.2 Rate limiting

* Por usuario
* Por IP
* Por cliente

---

### 5.3 Protección contra ataques comunes

* SQL Injection → ORM + validación
* XSS → sanitización
* CSRF → tokens
* Replay attacks → expiración + nonce

---

## 6. Seguridad en ejecución de prompts

---

## 6.1 Restricciones clave

❌ No se permite:

* Enviar prompts libres desde cliente
* Modificar prompts en runtime

---

✅ Solo se permite:

* Ejecutar prompts registrados
* Versiones aprobadas

---

## 6.2 Validación de inputs

* Tamaño máximo
* Tipo de datos
* Sanitización

---

## 6.3 Protección contra filtración de datos

* Detección de PII
* Reglas por prompt
* Enmascaramiento

---

## 6.4 Control de modelos

* Lista blanca de modelos permitidos
* Restricciones por entorno

---

## 7. Seguridad de datos

---

## 7.1 Datos en tránsito

* TLS 1.2+ obligatorio

---

## 7.2 Datos en reposo

* Cifrado en base de datos
* Volúmenes cifrados

---

## 7.3 Datos sensibles

Incluye:

* Tokens
* Credenciales
* Configuración de conectores

---

### Protección:

* Encriptación (AES-256)
* Acceso restringido
* Nunca en logs

---

## 8. Gestión de secretos

---

## 8.1 Estrategia

* No almacenar secretos en código
* Uso de variables de entorno

---

## 8.2 Futuro

* Secret Manager (Vault, cloud providers)

---

## 9. Auditoría y trazabilidad

---

## 9.1 Qué auditar

* Creación de prompts
* Cambios de versión
* Ejecuciones
* Accesos
* Cambios de configuración

---

## 9.2 Datos de auditoría

* Usuario
* Acción
* Timestamp
* IP
* Resultado

---

## 9.3 Trace ID

Cada request debe incluir:

* `trace_id` único

---

👉 Permite correlacionar logs.

---

## 10. Seguridad en conectores

---

## 10.1 Riesgos

* Fuga de datos
* Uso indebido de tokens
* Integraciones inseguras

---

## 10.2 Medidas

* Tokens cifrados
* Permisos limitados
* Validación de endpoints

---

## 10.3 Ejemplo (Confluence)

* Token almacenado cifrado
* Solo accesible por backend
* Nunca expuesto al frontend

---

## 11. Seguridad en frontend

---

* No almacenar tokens sensibles en localStorage
* Uso de cookies seguras (httpOnly)
* Validación de permisos en UI (pero no confiar solo en UI)

---

## 12. Gestión de sesiones

---

* Expiración automática
* Revocación de tokens
* Logout seguro

---

## 13. Seguridad en despliegue

---

* Variables sensibles fuera de repositorio
* Acceso restringido a contenedores
* Escaneo de vulnerabilidades

---

## 14. Cumplimiento

Dependiendo de la empresa:

* GDPR
* ISO 27001
* SOC2

---

## 15. Riesgos críticos

* Uso indebido de prompts
* Fuga de datos en outputs
* Integraciones inseguras
* Falta de control de acceso

---

## 16. Controles clave (resumen)

* Autenticación fuerte
* Autorización granular
* Logs obligatorios
* Control de ejecución
* Cifrado de datos

---

## 17. Resumen ejecutivo

Este sistema no solo gestiona prompts, **controla cómo se usan**.

Define:

* Quién puede crear
* Quién puede modificar
* Quién puede ejecutar
* Qué datos se pueden usar

Y lo más importante:

👉 Garantiza que ningún prompt se convierta en un vector de riesgo para la organización.

---
