# Documento 6: Logging, Monitoreo y Trazabilidad

**Sistema Corporativo de Gestión de Prompts**

---

## 1. Objetivo del documento

Definir el sistema de logging, monitoreo y trazabilidad para garantizar:

* Observabilidad completa del sistema
* Auditoría de acciones
* Diagnóstico rápido de errores
* Base para analítica y optimización

---

## 2. Principios clave

* **Logging estructurado (no texto plano)**
* **Todo evento relevante debe registrarse**
* **Trazabilidad end-to-end (trace_id)**
* **Separación entre logs, métricas y datos operativos**
* **Preparado para centralización (ELK u otros)**

---

## 3. Tipos de logs

---

### 3.1 Logs de aplicación

Eventos internos del sistema:

* Creación/modificación de prompts
* Ejecuciones
* Errores
* Accesos

---

### 3.2 Logs de auditoría

Eventos críticos:

* Cambios de configuración
* Acciones de usuarios
* Uso de conectores
* Accesos a datos sensibles

---

### 3.3 Logs de sistema

* Estado de servicios
* Arranque/parada
* Recursos

---

### 3.4 Logs de seguridad

* Intentos fallidos de login
* Accesos no autorizados
* Violaciones de políticas

---

## 4. Formato de logging (ESTÁNDAR)

Formato obligatorio: **JSON estructurado**

---

### 4.1 Ejemplo de log

```json id="log1"
{
  "timestamp": "2026-04-16T17:45:32Z",
  "level": "INFO",
  "service": "backend",
  "component": "execution_service",
  "version": "1.2.0",
  "environment": "prod",
  "trace_id": "abc-123",
  "user_id": "user-456",
  "action": "execute_prompt",
  "message": "Prompt ejecutado correctamente",
  "metadata": {
    "prompt_id": "123",
    "version": "v5",
    "duration_ms": 230,
    "model": "gpt-4"
  }
}
```

---

## 5. Campos obligatorios

Todos los logs deben incluir:

* timestamp (ISO 8601)
* level (INFO, WARN, ERROR, DEBUG)
* service (backend, frontend, worker, gateway)
* component
* version (desde archivo global)
* environment
* trace_id
* message

---

## 6. Sistema de logging en Python

---

### 6.1 Requisitos

* Modular
* Configurable
* Reutilizable
* Compatible con FastAPI

---

### 6.2 Diseño

Módulo central:

```id="log2"
logging/
 ├── logger.py
 ├── formatter.py
 ├── config.py
```

---

### 6.3 Características

* Logging en JSON
* Configuración por entorno
* Soporte para múltiples handlers
* Integración con FastAPI middleware

---

## 7. Niveles de logging

---

* DEBUG → desarrollo
* INFO → operaciones normales
* WARN → situaciones anómalas
* ERROR → fallos
* CRITICAL → fallos graves

---

## 8. Rotación de logs

---

## 8.1 Requisitos

* Configurable por admin
* Basado en:

  * Tamaño (ej: 100MB)
  * Tiempo (ej: diario)

---

## 8.2 Estrategia

* RotatingFileHandler
* Backup de archivos
* Eliminación automática

---

## 8.3 Ejemplo

```id="log3"
max_size = 100MB
max_files = 10
rotation = daily
```

---

## 9. Trazabilidad (Traceability)

---

## 9.1 Trace ID

Cada request genera:

* `trace_id` único

---

## 9.2 Propagación

Debe viajar por:

* API Gateway
* Backend
* Worker
* Conectores

---

## 9.3 Beneficio

Permite reconstruir:

👉 Qué pasó
👉 Cuándo
👉 Dónde

---

## 10. Métricas

---

## 10.1 Métricas clave

* Número de ejecuciones
* Latencia
* Errores
* Uso por usuario
* Coste por modelo

---

## 10.2 Tipos

* Contadores
* Histogramas
* Gauges

---

## 10.3 Exposición

* Endpoint `/metrics`
* Formato compatible con Prometheus

---

## 11. Monitoreo

---

## 11.1 Herramientas

Futuro:

* Prometheus
* Grafana

---

## 11.2 Alertas

Ejemplos:

* Error rate alto
* Tiempo de respuesta elevado
* Fallos en conectores
* Caída de servicios

---

## 12. Integración con ELK

---

## 12.1 Componentes

* Elasticsearch
* Logstash
* Kibana

---

## 12.2 Flujo

1. Logs generados
2. Enviados a Logstash
3. Indexados en Elasticsearch
4. Visualizados en Kibana

---

## 13. Buenas prácticas

---

* No loggear datos sensibles
* Evitar logs excesivos
* Usar niveles correctamente
* Mantener consistencia

---

## 14. Ejemplos de eventos clave

---

### Ejecución exitosa

```json id="log4"
{
  "level": "INFO",
  "action": "execution_completed"
}
```

---

### Error en ejecución

```json id="log5"
{
  "level": "ERROR",
  "action": "execution_failed"
}
```

---

### Acceso no autorizado

```json id="log6"
{
  "level": "WARN",
  "action": "unauthorized_access"
}
```

---

## 15. Retención de logs

---

* Definida por política corporativa
* Ejemplo:

  * 30 días en disco
  * 1 año en sistema central

---

## 16. Riesgos

* Saturación de disco
* Logs mal estructurados
* Falta de trazabilidad
* Exposición de datos sensibles

---

## 17. Resumen ejecutivo

El sistema de logging no es un extra, es un componente crítico que permite:

* Entender el comportamiento del sistema
* Detectar problemas
* Auditar acciones
* Optimizar el uso de prompts

Sin esto, el sistema funciona… hasta que deja de hacerlo y nadie sabe por qué.

---
