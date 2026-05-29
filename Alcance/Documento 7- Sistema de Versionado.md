# Documento 7: Sistema de Versionado Global de la Aplicación

**Sistema Corporativo de Gestión de Prompts**

---

## 1. Objetivo del documento

Definir un mecanismo centralizado, consistente y único para la gestión de la versión del sistema, garantizando que:

* Todos los componentes compartan la misma versión
* Los logs sean trazables por versión
* Las integraciones conozcan el estado del sistema
* Los despliegues sean auditables

---

## 2. Principio clave

👉 **Existe una única fuente de verdad para la versión del sistema**

---

## 3. Archivo de versión único

---

### 3.1 Nombre del archivo

```id="vfile1"
VERSION
```

---

### 3.2 Ubicación

* Raíz del repositorio

---

### 3.3 Contenido

Formato simple:

```id="vfile2"
1.2.0
```

---

### 3.4 Regla fundamental

* Ningún componente define su propia versión
* Todos consumen este archivo

---

## 4. Estrategia de versionado

---

### 4.1 Estándar

* Semantic Versioning (SemVer)

Formato:

```id="vfile3"
MAJOR.MINOR.PATCH
```

---

### 4.2 Significado

* MAJOR → cambios incompatibles
* MINOR → nuevas funcionalidades
* PATCH → correcciones

---

### 4.3 Ejemplos

* 1.0.0 → primera versión estable
* 1.1.0 → nueva funcionalidad
* 1.1.1 → bug fix

---

## 5. Consumo de la versión

---

## 5.1 Backend (FastAPI)

Debe:

* Leer el archivo `VERSION` al iniciar
* Exponerlo en:

  * logs
  * respuestas API

---

Ejemplo:

```id="vfile4"
version = open("VERSION").read().strip()
```

---

## 5.2 Frontend (Angular)

Opciones:

* Inyectar en build
* Consumir vía API `/version`

---

Recomendado:

👉 consumir desde backend (evita inconsistencias)

---

## 5.3 Logging

Todos los logs deben incluir:

```json id="vfile5"
"version": "1.2.0"
```

---

## 5.4 API

Endpoint obligatorio:

**GET** `/v1/version`

```json id="vfile6"
{
  "version": "1.2.0"
}
```

---

## 6. Integración con CI/CD

---

## 6.1 Flujo recomendado

1. Se actualiza archivo `VERSION`
2. Se hace commit
3. Pipeline:

   * build
   * test
   * deploy

---

## 6.2 Automatización opcional

* Incremento automático de versión
* Generación de tags en Git

---

## 6.3 Ejemplo

```id="vfile7"
git tag v1.2.0
```

---

## 7. Uso en logs y debugging

---

Permite responder:

* ¿Qué versión generó este error?
* ¿Desde cuándo ocurre?
* ¿Qué cambió entre versiones?

---

👉 Sin esto, debugging en producción es adivinanza.

---

## 8. Versionado en base de datos

---

Opcional pero recomendado:

* Registrar versión en ejecuciones:

```id="vfile8"
executions.version_app = "1.2.0"
```

---

## 9. Versionado en conectores

---

Cuando un conector publique información:

* Incluir versión del sistema

Ejemplo:

```id="vfile9"
"generated_by_version": "1.2.0"
```

---

## 10. Compatibilidad entre versiones

---

Reglas:

* No romper APIs existentes
* Mantener `/v1` estable
* Introducir `/v2` si hay cambios grandes

---

## 11. Versionado de configuración

---

Cuando cambian estructuras internas:

* Mantener compatibilidad
* Versionar config si es necesario

---

## 12. Versionado en contenedores

---

### 12.1 Tags de Docker

```id="vfile10"
backend:1.2.0
frontend:1.2.0
```

---

### 12.2 Regla

* El tag del contenedor debe coincidir con `VERSION`

---

## 13. Riesgos

---

* Múltiples versiones desincronizadas
* Olvidar actualizar VERSION
* Versionado manual inconsistente

---

## 14. Buenas prácticas

---

* Cambiar versión en cada release
* Automatizar validaciones
* Incluir versión en logs siempre
* No duplicar la fuente de versión

---

## 15. Validación automática

---

El sistema puede validar:

* Que el backend y frontend usen misma versión
* Que los logs incluyan versión
* Que el endpoint `/version` sea consistente

---

## 16. Extensión futura

---

* Versionado por microservicio
* Versionado de modelos IA
* Versionado de prompts (ya definido)

---

## 17. Resumen ejecutivo

El sistema de versionado global:

* Centraliza la información de versión
* Garantiza consistencia
* Facilita debugging y auditoría
* Se integra con todo el sistema

---

👉 Es simple en apariencia, pero crítico en operación real.

---
