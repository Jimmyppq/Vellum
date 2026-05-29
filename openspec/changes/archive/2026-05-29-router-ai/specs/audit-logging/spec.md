## ADDED Requirements

### Requirement: Logging estructurado en formato JSON
El sistema SHALL emitir todos los logs en formato JSON con los campos: `timestamp` (ISO 8601), `level`, `request_id`, `message` y campos adicionales según el tipo de evento. El formato JSON facilita la ingestión en sistemas de observabilidad (Loki, ELK, Datadog, etc.).

#### Scenario: Log de solicitud completada
- **WHEN** una solicitud a `/v1/message` o `/v1/stream` se completa con éxito
- **THEN** el sistema emite una línea de log con `level: "INFO"` que incluye `request_id`, `provider`, `model`, `input_tokens`, `output_tokens`, `duration_ms` y `status: "ok"`

#### Scenario: Log de solicitud fallida
- **WHEN** una solicitud termina con error (HTTP 4xx o 5xx)
- **THEN** el sistema emite una línea de log con `level: "WARNING"` o `level: "ERROR"` según la gravedad, incluyendo `request_id`, `provider`, `error_code` y `error_message`

### Requirement: Niveles de log configurables
El sistema SHALL respetar el nivel mínimo de log definido en la variable de entorno `LOG_LEVEL`. Los valores válidos son `DEBUG`, `INFO` y `WARNING`. El nivel por defecto SHALL ser `INFO`.

#### Scenario: Nivel DEBUG activo
- **WHEN** `LOG_LEVEL=DEBUG` y el sistema procesa una solicitud
- **THEN** el log incluye además el cuerpo completo del request (sin API keys), los parámetros enviados al proveedor LLM y el tiempo de cada fase interna

#### Scenario: Nivel WARNING activo
- **WHEN** `LOG_LEVEL=WARNING` y el sistema procesa una solicitud exitosa
- **THEN** no se emite ninguna línea de log para esa solicitud (sólo se registran advertencias y errores)

#### Scenario: Valor de LOG_LEVEL inválido
- **WHEN** `LOG_LEVEL` contiene un valor distinto a `DEBUG`, `INFO` o `WARNING`
- **THEN** el servicio usa el nivel `INFO` por defecto y registra un warning de configuración al arranque

### Requirement: Escritura en volumen persistente externo
El sistema SHALL escribir los logs en un archivo rotativo dentro del directorio configurado por la variable de entorno `LOG_DIR` (default: `/logs`). El archivo principal SHALL llamarse `router-ai.log`. La rotación SHALL ocurrir al alcanzar 10 MB, conservando los últimos 5 archivos (`router-ai.log.1` … `router-ai.log.5`).

#### Scenario: Escritura exitosa en volumen
- **WHEN** el directorio `LOG_DIR` existe y el proceso tiene permisos de escritura
- **THEN** los logs se escriben en `{LOG_DIR}/router-ai.log` además de enviarse a stdout

#### Scenario: Volumen no disponible al arranque
- **WHEN** el directorio `LOG_DIR` no existe o no es accesible
- **THEN** el servicio arranca igualmente, registra el error de configuración de logs en stdout y continúa sólo con salida estándar

#### Scenario: Rotación de archivo al alcanzar el límite
- **WHEN** `router-ai.log` alcanza 10 MB
- **THEN** el archivo se renombra a `router-ai.log.1`, los anteriores se numeran correlativamente y se crea un nuevo `router-ai.log` vacío

### Requirement: Generación de request_id por solicitud
El sistema SHALL generar un `request_id` UUID v4 único para cada solicitud HTTP entrante e incluirlo en todos los logs relacionados con esa solicitud. El `request_id` SHALL también retornarse en el header de respuesta `X-Request-ID`.

#### Scenario: Trazabilidad end-to-end
- **WHEN** el backend recibe una respuesta del microservicio
- **THEN** puede correlacionar la respuesta con las líneas de log usando el `X-Request-ID` del header de respuesta
