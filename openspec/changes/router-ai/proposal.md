## Por qué

El backend de las aplicaciones necesita integrar múltiples proveedores de LLM (Anthropic, OpenAI, DeepSeek, etc.) de forma transparente, sin acoplar su lógica al SDK o protocolo específico de cada proveedor. Centralizar este enrutamiento en un microservicio independiente elimina la duplicación, facilita el cambio de proveedor y permite gestionar credenciales y configuraciones en un único lugar.

## Qué Cambia

- **Nuevo microservicio `router-ai`**: Servicio FastAPI independiente que expone una API unificada para interactuar con LLMs.
- **Interfaz generalista**: Métodos como `connect`, `message`, `stream`, `embed` y `health` que el backend invoca sin conocer el proveedor subyacente.
- **Sistema de adaptadores**: Un adaptador por proveedor (Anthropic, OpenAI, DeepSeek, Ollama) que traduce la interfaz genérica a las llamadas específicas del SDK correspondiente.
- **Selección dinámica de proveedor**: El parámetro `provider` en cada solicitud determina qué adaptador se activa en tiempo de ejecución.
- **Gestión de configuración**: Variables de entorno por proveedor (API keys, modelos por defecto, timeouts) centralizadas en el microservicio.
- **Autenticación interna**: Header `X-API-Key` requerido en todas las solicitudes, validado por middleware.
- **Logging de auditoría**: Log JSON estructurado con niveles configurables (`DEBUG`, `INFO`, `WARNING`) escrito en volumen persistente externo.
- **Rate limiting por proveedor**: Límites de RPM y TPM configurables desde archivo YAML externo, con interfaz preparada para migrar a base de datos.

## Capacidades

### Nuevas Capacidades

- `llm-routing`: Enrutamiento dinámico de solicitudes al proveedor LLM indicado, con interfaz unificada independiente del proveedor.
- `provider-adapters`: Adaptadores individuales para cada proveedor LLM (Anthropic, OpenAI, DeepSeek, Ollama, LM Studio) que implementan el contrato de la interfaz generalista.
- `streaming-support`: Soporte de respuestas en streaming (Server-Sent Events) para todos los proveedores compatibles.
- `health-monitoring`: Endpoint de salud que verifica la disponibilidad y conectividad de cada proveedor configurado.
- `api-key-auth`: Autenticación de clientes del microservicio mediante API key interna en header `X-API-Key`.
- `audit-logging`: Logging estructurado en JSON con niveles configurables y escritura en volumen Docker persistente.
- `rate-limiting`: Control de tasa de peticiones y tokens por proveedor desde archivo YAML configurable, con path de migración a BD.

### Capacidades Modificadas

_(ninguna — este es un microservicio nuevo e independiente)_

## Impacto

- **Nuevo servicio independiente**: No modifica código existente; se despliega como contenedor Docker separado.
- **Dependencias externas**: `anthropic`, `openai`, `httpx` (para DeepSeek/Ollama via API REST), `fastapi`, `uvicorn`, `pydantic`, `pyyaml`.
- **API REST**: Expone endpoints HTTP/HTTPS consumibles por cualquier backend en cualquier lenguaje.
- **Variables de entorno**: Requiere configuración de API keys por proveedor en el entorno de despliegue.
