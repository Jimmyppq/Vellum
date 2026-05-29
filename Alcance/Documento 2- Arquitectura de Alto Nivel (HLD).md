# Documento 2: Arquitectura de Alto Nivel (HLD)

**Sistema Corporativo de Gestión de Prompts**

---

## 1. Objetivo del documento

Definir la arquitectura de alto nivel del sistema, describiendo sus componentes principales, interacciones, flujos y entornos, garantizando:

* Escalabilidad
* Seguridad
* Observabilidad
* Gobernanza

---

## 2. Principios arquitectónicos

* **API-first**: toda funcionalidad expuesta vía API REST
* **Separación de responsabilidades**
* **Desacoplamiento por servicios**
* **Seguridad por diseño**
* **Observabilidad nativa**
* **Preparado para cloud y contenerización**

---

## 3. Vista general de la arquitectura

El sistema se compone de los siguientes bloques principales:

1. Frontend (Angular)
2. API Gateway / Reverse Proxy
3. Backend (FastAPI)
4. Motor de ejecución de IA (LLMs y ASR)
5. Base de datos Relacional
6. Almacenamiento de Objetos (Object Storage)
7. Sistema de logs y métricas
8. Sistema de conectores
9. Servicios externos

---

## 4. Componentes principales

### 4.1 Frontend (Angular)

Responsabilidades:

* Interfaz de usuario
* Gestión de prompts
* Panel de administración
* Configuración de conectores
* Visualización de métricas

Características:

* Basado en roles (RBAC en UI)
* Consumo exclusivo de APIs
* No contiene lógica de negocio crítica

---

### 4.2 API Gateway / Reverse Proxy

Responsabilidades:

* Punto de entrada único
* Terminación TLS
* Routing hacia servicios internos
* Rate limiting
* Seguridad perimetral

Tecnologías posibles:

* Nginx
* Kong
* Traefik

---

### 4.3 Backend (FastAPI)

Responsabilidades:

* Lógica de negocio
* Gestión de prompts
* Gobernanza
* Ejecución de prompts
* Autenticación y autorización
* Exposición de API REST

Submódulos internos:

* Gestión de prompts
* Versionado
* Ejecución
* Usuarios y roles
* Conectores
* Logging

---

### 4.4 Motor de ejecución de IA

Responsabilidades:

* Enviar prompts a modelos de IA (Texto)
* Procesar audio mediante modelos ASR (Automatic Speech Recognition) como Whisper o Azure Speech para las transcripciones
* Gestionar múltiples proveedores
* Manejar respuestas

Características:

* Abstracción de proveedor (OpenAI, modelos locales, etc.)
* Configuración dinámica
* Control de costes

---

### 4.5 Base de datos

Responsabilidades:

* Persistencia estructurada

Tecnología recomendada:

* PostgreSQL

Contiene:

* prompts
* versiones
* ejecuciones
* usuarios
* roles
* conectores

---

### 4.6 Sistema de logs y métricas

Responsabilidades:

* Registro de eventos
* Auditoría
* Monitoreo

Características:

* Logging estructurado (JSON)
* Rotación configurable
* Preparado para integración con ELK

---

### 4.7 Sistema de conectores

Responsabilidades:

* Integración con sistemas externos
* Publicación de resultados

Características:

* Arquitectura modular (plugin-like)
* Configuración por admin
* Ejecución post-procesamiento

---

### 4.8 Servicios externos

Ejemplos:

* Plataformas de IA (LLM, ASR)
* Herramientas corporativas (ej: documentación, colaboración)
* Sistemas internos

---

### 4.9 Almacenamiento de Objetos (Object Storage)

Responsabilidades:

* Almacenamiento seguro de archivos binarios pesados (Audios, Videos de reuniones)

Tecnología recomendada:

* AWS S3 o MinIO (para despliegues on-premise)

---

## 5. Flujo de interacción principal

### 5.1 Flujo de gestión (usuario)

1. Usuario accede al frontend
2. Frontend llama a API Gateway
3. API Gateway enruta a backend
4. Backend valida permisos
5. Backend consulta base de datos
6. Backend responde al frontend

---

### 5.2 Flujo de ejecución (sistema externo)

1. Sistema externo invoca API (`/executions`)
2. API Gateway valida y enruta
3. Backend autentica (OAuth2/JWT)
4. Backend valida permisos
5. Backend obtiene prompt aprobado
6. Backend ejecuta en motor IA
7. Se registran logs y métricas
8. Se retorna resultado
9. (Opcional) se activa conector

---

## 6. Arquitectura lógica (capas)

### Capa de presentación

* Angular

### Capa de acceso

* API Gateway

### Capa de aplicación

* FastAPI

### Capa de dominio

* Lógica de prompts, ejecución, gobernanza

### Capa de infraestructura

* Base de datos
* Logging
* Motor IA

---

## 7. Arquitectura física (contenedores)

Cada componente se ejecuta como contenedor Docker:

* frontend-container
* backend-container
* db-container
* gateway-container
* (opcional) worker-container

Comunicación:

* Red interna Docker
* Sin exposición directa de DB

Persistencia:

* Volúmenes para base de datos
* Volúmenes para logs

---

## 8. Gestión de entornos

Se definen al menos tres entornos:

### 8.1 Desarrollo (dev)

* Uso local
* docker-compose
* Logs detallados

---

### 8.2 Staging

* Entorno de pruebas
* Validación antes de producción

---

### 8.3 Producción (prod)

* Seguridad reforzada
* Alta disponibilidad
* Monitoreo activo

---

## 9. Escalabilidad

### Horizontal

* Backend escalable (stateless)
* Uso de múltiples instancias

---

### Vertical

* Ajuste de recursos en contenedores

---

### Futuro

* Kubernetes
* Autoescalado

---

## 10. Observabilidad

Incluye:

* Logs estructurados
* Métricas de uso
* Trazabilidad completa

Integración futura:

* ELK Stack
* Prometheus / Grafana

---

## 11. Seguridad en arquitectura

* TLS en todo el tráfico
* Autenticación centralizada
* API protegida
* Base de datos aislada
* Gestión segura de secretos

---

## 12. Gestión de configuración

* Variables de entorno
* Configuración externa (no hardcodeada)
* Separación por entorno

---

## 13. Versionado del sistema

* Archivo único `VERSION`
* Consumido por todos los componentes
* Expuesto vía API

---

## 14. Puntos críticos

* API como único punto de acceso
* Separación prompt vs ejecución
* Logging obligatorio en cada operación
* Control estricto de permisos

---

## 15. Resumen ejecutivo

La arquitectura propuesta define un sistema desacoplado, escalable y seguro, donde:

* El backend centraliza la lógica
* La API gobierna el acceso
* Los prompts se ejecutan de forma controlada
* La observabilidad es nativa

El sistema está preparado para evolucionar hacia entornos distribuidos y de alta escala sin rediseños profundos.

---

## 16. Diagrama lógico detallado (descripción textual)

Dado que no estamos usando diagramas gráficos, esta es la representación clara de interacción:

```
[ Usuario / Sistema Externo ]
              │
              ▼
      [ API Gateway ]
              │
              ▼
        [ Backend API ]
        ├── Módulo Prompts
        ├── Módulo Versionado
        ├── Módulo Ejecución
        ├── Módulo Seguridad
        ├── Módulo Conectores
        └── Módulo Logging
              │
     ┌────────┼────────┐
     ▼        ▼        ▼
[ Base DB ] [ Motor IA ] [ Sistema Logs ]
                             │
                             ▼
                      [ Stack ELK (futuro) ]
```

---

## 17. Separación backend: API vs Workers

Para evitar cuellos de botella, el backend debe dividirse conceptualmente en:

### 17.1 API síncrona (FastAPI)

* Manejo de requests HTTP
* Validación
* Respuestas rápidas
* Orquestación

---

### 17.2 Worker asíncrono (obligatorio para transcripciones)

Responsabilidades:

* Ejecución de prompts pesados
* Transcripción de audios largos (proceso que puede tardar minutos)
* Integraciones externas (ej: Confluence)
* Procesamiento en background

Tecnologías posibles:

* Celery + Redis
* RQ (Redis Queue)
* Kafka (si escala mucho)

---

### 17.3 Patrón de ejecución

1. API recibe ejecución
2. API valida y registra
3. API envía tarea a cola
4. Worker ejecuta
5. Worker guarda resultado
6. API devuelve resultado (sync o async)

👉 Esto evita que la API se bloquee.

---

## 18. Gestión de colas y asincronía

Para soportar carga real:

* Cola de tareas (Redis o RabbitMQ)
* Soporte para:

  * reintentos
  * backoff exponencial
  * manejo de errores

Casos donde usar async:

* Prompts largos
* Integraciones externas
* Publicación en conectores

---

## 19. Estrategia de cache

Para mejorar rendimiento:

### 19.1 Qué cachear

* Prompts aprobados
* Versiones más usadas
* Configuración del sistema

---

### 19.2 Tecnología

* Redis

---

### 19.3 Beneficio

* Reduce carga en DB
* Mejora latencia en ejecución

---

## 20. Gestión de secretos

Nunca hardcodear nada.

### Solución:

* Variables de entorno
* Secret managers (futuro):

  * HashiCorp Vault
  * AWS Secrets Manager

Incluye:

* API keys
* Tokens de conectores
* Credenciales DB

---

## 21. Estrategia de conectores (detalle arquitectónico)

Los conectores deben diseñarse como módulos desacoplados.

### Patrón:

```
Connector Interface
    ├── ConfluenceConnector
    ├── SlackConnector (futuro)
    └── EmailConnector (futuro)
```

---

### Flujo:

1. Prompt ejecutado
2. Resultado generado
3. Sistema evalúa si hay conector activo
4. Se invoca conector
5. Conector publica resultado

---

### Características clave:

* Configuración por usuario/admin
* Aislamiento de fallos (si falla Confluence, no rompe ejecución)
* Logs independientes

---

## 22. Multi-proveedor de IA

No te amarres a un solo proveedor.

### Diseño:

```
AI Provider Interface
    ├── OpenAIProvider
    ├── LocalModelProvider
    └── FutureProvider
```

---

### Beneficios:

* Evitar lock-in
* Control de costes
* Flexibilidad

---

## 23. Estrategia de errores

Clasificación clara:

### 23.1 Errores de cliente

* Input inválido
* Permisos insuficientes

### 23.2 Errores de sistema

* Fallo en DB
* Timeout

### 23.3 Errores de integración

* Fallo en IA
* Fallo en conectores

---

### Respuesta estándar API:

```json
{
  "error": {
    "code": "PROMPT_NOT_FOUND",
    "message": "Prompt no existe",
    "trace_id": "abc-123"
  }
}
```

👉 El `trace_id` conecta con logs.

---

## 24. Estrategia de logging en arquitectura

Cada componente debe loggear:

* Backend
* Worker
* Gateway

---

### Flujo:

1. Request entra
2. Se genera `trace_id`
3. Se propaga a todos los componentes
4. Todos los logs incluyen ese ID

---

👉 Resultado: trazabilidad completa.

---

## 25. Gestión de configuración dinámica

No todo debe requerir redeploy.

### Configurable en runtime:

* Rotación de logs
* Límites de ejecución
* Configuración de conectores
* Flags de features

---

### Implementación:

* Tabla en DB
* Cache en Redis
* Endpoint admin

---

## 26. Estrategia de despliegue

### Inicial:

* Docker + docker-compose

---

### Evolución:

* Kubernetes
* Helm charts
* Autoescalado

---

### Recomendación clave:

Separar:

* Deploy de backend
* Deploy de frontend

---

## 27. Alta disponibilidad (HA)

Para producción:

* Múltiples instancias backend
* Balanceador de carga
* DB con replicación
* Redis cluster (si escala)

---

## 28. Observabilidad avanzada

Además de logs:

### Métricas:

* Prompts ejecutados
* Latencia
* Errores
* Uso por usuario

---

### Trazas:

* Distributed tracing (futuro)

  * OpenTelemetry

---

## 29. Gobernanza técnica

Reglas clave:

* Ningún sistema ejecuta prompts fuera de la API
* Todo pasa por control central
* Logs obligatorios
* Versionado obligatorio

---

## 30. Decisiones arquitectónicas clave

* FastAPI como núcleo backend
* Angular como frontend robusto
* PostgreSQL como fuente de verdad
* Redis como cache/cola
* Docker como base de ejecución
* API Gateway como frontera de seguridad

---

## 31. Riesgos técnicos

* Sobrecarga en ejecución síncrona
* Mal diseño de conectores
* Falta de control en versiones
* Crecimiento descontrolado de logs

---

## 32. Conclusión

Esta arquitectura no es experimental. Es una base sólida para:

* Escalar
* Integrar
* Gobernar
* Auditar

Y sobre todo, para evitar el caos típico cuando la IA entra en una organización sin control.

---
