## Context

El router implementa un patrón de adaptadores donde cada proveedor LLM extiende `BaseAdapter` (4 métodos abstractos: `message`, `stream`, `embed`, `health`). El registro de proveedores ocurre en `ProviderRegistry.startup()` condicionado a la presencia de una API key en `Settings`. Actualmente hay 5 proveedores: Anthropic, OpenAI, DeepSeek, Ollama y LM Studio.

Google ofrece dos superficies de API para Gemini:
1. **Google AI Studio** — API key simple (`AIza...`), SDK `google-genai`
2. **Vertex AI** — credenciales GCP, más complejo

Este diseño cubre únicamente Google AI Studio por ser el equivalente directo a los demás proveedores (API key → cliente → llamadas).

## Goals / Non-Goals

**Goals:**
- Implementar `GoogleAdapter` siguiendo exactamente el patrón `BaseAdapter`
- Soportar `message`, `stream` y `embed` con el SDK `google-genai`
- Registrar el proveedor bajo el nombre `"google"` en el registry
- Modelo default: `gemini-3.5-flash` 
- Soportar embeddings con `text-embedding-004`

**Non-Goals:**
- Vertex AI / credenciales de servicio GCP
- Funcionalidades exclusivas de Gemini (grounding, thinking tokens, safety settings avanzados)
- Cambios en la API pública del router

## Decisions

### D1: SDK `google-genai` sobre endpoint OpenAI-compatible

Google expone un endpoint OpenAI-compatible (`https://generativelanguage.googleapis.com/v1beta/openai/`) que permitiría reutilizar `OpenAIAdapter` con solo cambiar `base_url`. Se descarta porque:
- Los embeddings de Google usan una API diferente (no compatible con `/v1/embeddings`)
- El health check sería una imitación del de OpenAI, no una verificación real
- Rompe la consistencia del patrón: cada proveedor tiene su propio adapter

El SDK `google-genai` ofrece cliente async nativo, streaming real y acceso a la API de embeddings.

### D2: Nombre del proveedor `"google"`

Se registra como `"google"` (no `"gemini"` ni `"google-ai"`) para seguir la convención de los demás proveedores que usan el nombre de la empresa: `"anthropic"`, `"openai"`, `"deepseek"`.

### D3: Mapeo de roles `assistant` → `model`

Google Gemini usa el rol `"model"` donde OpenAI/Anthropic usan `"assistant"`. El adapter normaliza esta diferencia internamente:

```
request.messages[].role == "assistant"  →  Google Content role = "model"
request.messages[].role == "user"       →  Google Content role = "user"
```

Esto mantiene la interfaz pública del router sin cambios.

### D4: Modelo default `gemini-3.5-flash`

Si el modelo `gemini-3.5-flash` mencionado en el brief no existe como modelo público en la API de Google AI Studio. El equivalente estable más reciente es `gemini-2.0-flash`, que es el modelo rápido/económico de Google. Se documenta en el adapter.

### D5: Embeddings con `text-embedding-004`

A diferencia de Anthropic (que lanza `NotImplementedError`), Google sí soporta embeddings. Se implementa usando el modelo `text-embedding-004` (el más reciente de Google AI Studio). La respuesta normaliza al formato `EmbedResponse` del router.

## Risks / Trade-offs

- **Modelo default obsoleto** → Riesgo: Google puede deprecar modelos. Mitigación: el caller puede especificar `request.model` explícitamente; el default es solo un fallback.
- **API key scope** → El SDK `google-genai` acepta la API key de Google AI Studio; si el usuario tiene restricciones de quota en su key, fallará silenciosamente en el health check. Mitigación: el health check llama a `models.list()` con timeout de 5s, igual que Anthropic/OpenAI.
- **Versión del SDK** → `google-genai` tiene una API que cambió entre versiones (v0.x vs v1.x). Se fija `>= 1.0` para usar la API estable del cliente async (`client.aio.*`).

## Open Questions

- ¿Se requiere soporte de Vertex AI en el futuro? Si sí, convendrá un segundo adapter `VertexAdapter` o un parámetro `use_vertex: bool` en el constructor. Por ahora, fuera de scope.
