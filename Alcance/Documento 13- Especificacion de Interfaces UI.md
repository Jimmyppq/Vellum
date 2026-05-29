# Documento 13: Especificación Detallada de Interfaces Web (UI)

---

## 1. Objetivo del Documento
Este documento está diseñado específicamente para ser consumido por un **agente experto en diseño y desarrollo de interfaces (UI/UX)**. 
Detalla todas las pantallas, modales, vistas y flujos de usuario necesarios para construir el Frontend de la **Plataforma Corporativa de Gobernanza de IA**. El sistema abarca la gestión versionada de Prompts, el procesamiento de Transcripciones de audio y la ejecución y envío de resultados a través de Conectores.

---

## 2. Layout Principal y UI/UX (Directrices Base)
Para todas las pantallas, el Sistema debe seguir una estructura empresarial limpia y escalable:
*   **Sidebar Izquierdo (Navegación):** Accesos a Dashboard, Prompts, Transcripciones, Ejecuciones (Playground), Historial y Administración, plegable para maximizar espacio.
*   **Topbar (Cabecera):** Buscador global (Omnibar), selector de Tema (Dark/Light mode), notificaciones (ej. "Audio transcribiéndose", "Prompt aprobado"), y menú de perfil de usuario.
*   **Contenido Principal:** Diseño basado en "Tarjetas" (Cards), tablas limpias con paginación/scroll virtual y modales deslizables laterales (Drawers) para no perder el contexto.
*   **Look & Feel:** Sofisticado, enfocado en datos, minimizando la carga cognitiva ("Enterprise UI").

---

## 3. Inventario Detallado de Vistas (Pantallas a Diseñar)

### Pantalla 0: Autenticación
*   **Login:** Pantalla centrada con opciones de Login Corporativo (SSO, Microsoft/Google) y usuario/contraseña tradicionales.
*   **Recuperar Contraseña:** Flujo sencillo de envío de email.

---

### Pantalla 1: Dashboard Principal (Resumen Ejecutivo)
*   **Objetivo:** Mostrar de un vistazo el estado y el uso de la IA en la empresa.
*   **Componentes:**
    *   **KPI Cards:** "Prompts Aprobados", "Horas de Audio Transcritas", "Ejecuciones este Mes", "Ahorro de Tiempo Estimado".
    *   **Gráficos:** Uso de IA por semana (líneas), Modelo más utilizado (torta/barras).
    *   **Quick Actions (Botones rápidos):** "Crear nuevo Prompt", "Subir Audio", "Ejecutar Tarea".
    *   **Tablas resumen:** "Últimos audios transcritos" y "Prompts pendientes de aprobación".

---

### Pantalla 2: Módulo de Prompts
#### 2.1 Lista de Prompts (Caja Fuerte de Prompts)
*   **Componentes:** Barra superior de búsqueda y filtros (Estado: *Draft*, *Aprobado*, *Deprecado*; Etiquetas; Autor). Botón principal "Nuevo Prompt".
*   **Visualización:** Tabla o Grilla de tarjetas mostrando Título, versión actual, estado (con badges de colores), propietario y fecha. Opciones en cada fila: *Ver/Editar, Ejecutar, Duplicar*.

#### 2.2 Editor Avanzado de Prompt (Split View)
*   **Lado Izquierdo (Configuración):** Título, Descripción, Categoría/Tags.
*   **Lado Izquierdo (Editor de Texto):** Área de texto enriquecido/código donde se escribe el prompt. **Crítico:** Debe resaltar visualmente las variables (ej. `{{transcript_texto}}` o `{{nombre_cliente}}`).
*   **Lado Derecho (Playground/Testing):** Panel para inyectar variables en tiempo real, presionar "Testear" y ver la respuesta de la IA.
*   **Bottom Bar (Acciones):** "Guardar como Borrador", "Solicitar Aprobación".

#### 2.3 Historial de Versiones (Drawer / Modal)
*   Panel lateral que muestra un Timeline con las versiones del Prompt (V1, V2, V3).
*   Vista de "Diff" (tipo Git) para ver qué palabras se añadieron (en verde) o quitaron (en rojo) entre versiones.

---

### Pantalla 3: Módulo de Transcripciones
#### 3.1 Lista de Transcripciones
*   **Componentes:** Buscador y Filtros.
*   **Visualización:** Tabla con Nombre de la reunión, Fecha, Duración, Status (*Uploading*, *Transcribiendo*, *Completado*, *Error*), y Botón de Acciones. (Un spinner o barra de progreso para las que están "Transcribiendo").

#### 3.2 Modal Dropzone (Subida de Medios)
*   Área central para "Drag & Drop" de archivos de audio/video (MP3, MP4, WAV).
*   Campos a llenar: Título de la reunión, Idioma esperado, Etiquetas. Botón "Subir y Transcribir".

#### 3.3 Editor y Visualizador de Transcripción (Media Review)
*   **Header:** Título del asset y estado.
*   **Sección Superior/Lateral:** Minicontrolador de Audio (Reproductor multimedia con Play, Pausa, velocidad de reproducción).
*   **Contenido Principal (Transcript Blocks):** Bloques de texto sincronizados con las marcas de tiempo (timestamps) del audio.
*   **Anotaciones:** Posibilidad de hacer clic en un bloque de texto para corregir una palabra (ej. arreglar apellidos o siglas que la IA escuchó mal).
*   **Acciones:** "Aplicar Prompt", "Descargar PDF", "Guardar Versión".

---

### Pantalla 4: Área de Ejecución Central (Playground de Tareas)
Esta interfaz es el puente donde un **Prompt** se cruza con un **Transcript** (u otro texto).
*   **Selector 1:** Escoger un "Prompt Aprobado" de un desplegable autocompletable.
*   **Selector 2:** Escoger el Input de contexto. (Radio buttons: a) "Texto Libre", b) "Seleccionar Transcripción Existente").
*   **Panel Central:** Si hay variables pendientes en el prompt, el sistema pide llenarlas (ej. `{{tono_respuesta}}` = "Formal").
*   **Output:** Área tipo terminal o markdown reader donde se genera la respuesta en streaming.
*   **Acción Final (Exportar):** Tras tener el resultado, un botón "Enviar a Conector" que abre un modal permitiendo enviar a Confluence, Slack, etc.

---

### Pantalla 5: Módulo de Conectores (Integración)
#### 5.1 Lista de Conectores
*   Grilla mostrando tarjetas con logos (Jira, Confluence, Slack, Webhook Genérico). Un "Toggle" encendido/apagado para activarlos a nivel organizacional.

#### 5.2 Configuración de Conector (Modal o Drawer)
*   **Formulario:** URL del servicio, Espacio/Canal de destino, Campos de credenciales (inputs tipo password para Tokens de API o Secrets).
*   Botón "Test Connection" para verificar que las credenciales están bien antes de guardar.

---

### Pantalla 6: Historial de Ejecuciones (Auditoría General)
*   **Visión Analítica:** Tabla extensa parecida a los "Logs" de nube.
*   **Columnas:** ID de Ejecución, Usuario, Prompt Utilizado, Transcripción utilizada (si aplica), Fecha, Token Cost (Coste estimado en centavos), y Status (*Success*, *Failed*).
*   **Detalle:** Al hacer clic en un log, se abre un cajón lateral (Drawer) mostrando el JSON técnico (el input enviado a OpenAI/Azure y el output devuelto).

---

### Pantalla 7: Administración (Configuración del Sistema)
*   **Pestaña Usuarios y Roles:** Tabla clásica ABM (Alta, Baja, Modificación) para invitar usuarios y asignarles roles (Admin, Editor, Aprobador, Consumidor).
*   **Pestaña Proveedores de IA:** Formulario para configurar qué motor ASR (Ej. credencial de OpenAI Whisper) y qué motores de LLM se usarán.

---

## 4. Requerimientos Funcionales de UX para el Agente
*   **Interacciones Asíncronas:** Las tareas largas (transcribir audio, ejecutar LLM) no deben bloquear la pantalla. Usar *Skeletons* (indicadores de carga con formas grises) y *Toast Notifications* (notificaciones flotantes de éxito/error).
*   **Accesibilidad (A11y):** Los colores de estados (Aprobado = Verde, Rechazado = Rojo, Borrador = Gris, Fallido = Naranja) deben venir acompañados de iconos consistentes.
*   **Código y JSON:** Todas las áreas que muestren información de logs o edición técnica deben implementar componentes tipo editor de código (como Monaco Editor) con resaltado de sintaxis.

---
*(Fin de la especificación - El agente generador de UI tiene permiso absoluto para proponer la arquitectura de componentes React/Angular, sistemas de diseño (Material/Tailwind) y paletas de color con base en este documento).*
