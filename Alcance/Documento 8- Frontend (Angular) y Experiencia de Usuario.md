# Documento 8: Frontend (Angular) y Experiencia de Usuario

**Sistema Corporativo de Gestión de Prompts**

---

## 1. Objetivo del documento

Definir la arquitectura, estructura y experiencia de usuario del frontend, garantizando:

* Alta adopción por parte de usuarios
* Facilidad de uso para perfiles técnicos y no técnicos
* Integración completa con la API
* Soporte para gobernanza y control

---

## 2. Principios de diseño UX/UI

* **Simplicidad primero** (no abrumar)
* **Progresivo** (mostrar complejidad solo cuando se necesita)
* **Basado en roles**
* **Feedback inmediato**
* **Consistencia visual y funcional**

---

## 3. Arquitectura del frontend

---

### 3.1 Framework

* Angular

---

### 3.2 Estructura por módulos

```id="f1"
app/
 ├── core/
 ├── shared/
 ├── features/
 │    ├── prompts/
 │    ├── executions/
 │    ├── connectors/
 │    ├── admin/
 │    └── metrics/
 └── layout/
```

---

### 3.3 Capas

* UI (componentes)
* Servicios (API calls)
* Estado (state management)

---

## 4. Gestión de estado

---

Opciones:

* RxJS (básico)
* NgRx (recomendado si escala)

---

👉 Recomendación:

* Empezar simple (RxJS)
* Evolucionar a NgRx si crece complejidad

---

## 5. Gestión de roles en UI

---

### 5.1 Roles soportados

* Admin
* Editor
* Approver
* Viewer

---

### 5.2 Comportamiento

La UI debe:

* Mostrar u ocultar funcionalidades
* Adaptar navegación
* Restringir acciones

---

### 5.3 Regla crítica

👉 La seguridad real está en backend, no en frontend

---

## 6. Layout principal

---

### 6.1 Estructura

* Sidebar (navegación)
* Topbar (usuario, entorno, versión)
* Contenido principal

---

### 6.2 Navegación

* Dashboard
* Prompts
* Ejecuciones
* Conectores
* Métricas
* Administración

---

## 7. Módulo de gestión de prompts

---

## 7.1 Funcionalidades

* Crear prompt
* Editar
* Versionar
* Aprobar
* Buscar

---

## 7.2 Vista lista

* Tabla con:

  * nombre
  * estado
  * versión activa
  * owner
  * tags

---

## 7.3 Editor de prompt

---

### Características clave:

* Editor estructurado:

  * instrucciones
  * variables (`{{variable}}`)
  * formato de salida

---

* Validación en tiempo real
* Preview / test rápido
* Historial de versiones

---

👉 Esto es crítico: si el editor es malo, nadie reutiliza nada.

---

## 8. Módulo de ejecución

---

## 8.1 Funcionalidades

* Ejecutar prompt manualmente
* Introducir inputs
* Ver resultados

---

## 8.2 UI de ejecución

* Formulario dinámico (según variables)
* Output claro
* Tiempo de ejecución
* Estado (running, completed, error)

---

## 9. Módulo de conectores

---

## 9.1 Funcionalidades

* Crear conector
* Configurar credenciales
* Activar/desactivar

---

## 9.2 Ejemplo: Confluence

Campos:

* URL base
* Espacio
* Token

---

## 9.3 Seguridad

* Nunca mostrar tokens completos
* Inputs protegidos

---

## 10. Módulo de administración

---

## 10.1 Funcionalidades

* Gestión de usuarios
* Roles
* Configuración global
* Rotación de logs
* Parámetros del sistema

---

## 10.2 Acceso

👉 Solo Admin

---

## 11. Módulo de métricas

---

## 11.1 Funcionalidades

* Visualización de uso
* Errores
* rendimiento

---

## 11.2 Visualización

* Gráficas simples
* Filtros por:

  * fecha
  * prompt
  * usuario

---

## 12. Experiencia de testing de prompts

---

Debe permitir:

* Probar prompt sin salir de UI
* Comparar versiones
* Ver outputs rápidamente

---

👉 Esto acelera adopción brutalmente.

---

## 13. Integración con API

---

### 13.1 Servicios Angular

Ejemplo:

```id="f2"
prompt.service.ts
execution.service.ts
connector.service.ts
```

---

### 13.2 Manejo de errores

* Mostrar mensajes claros
* Mapear errores API

---

## 14. Manejo de autenticación

---

* JWT
* Interceptor HTTP
* Refresh automático

---

## 15. Versionado en UI

---

Mostrar en topbar:

```id="f3"
Version: 1.2.0
Environment: PROD
```

---

👉 Clave para soporte.

---

## 16. Rendimiento

---

* Lazy loading de módulos
* Paginación
* Debounce en búsquedas

---

## 17. Accesibilidad

---

* Navegación clara
* Contrastes adecuados
* Inputs etiquetados

---

## 18. Responsividad

---

* Desktop primero
* Tablet opcional
* Mobile (limitado)

---

## 19. Riesgos

---

* UI demasiado compleja
* Baja adopción
* Falta de feedback
* Performance pobre

---

## 20. Buenas prácticas

---

* Componentes reutilizables
* Consistencia visual
* Validaciones claras
* Feedback inmediato

---

## 21. Resumen ejecutivo

El frontend no es solo una interfaz:

* Es el punto de adopción
* Es donde se materializa la gobernanza
* Es donde los usuarios deciden usar o ignorar el sistema

---

👉 Si esto es simple, útil y rápido, el sistema vive.
👉 Si no, muere aunque todo lo demás esté perfecto.

---
