## Why

El router soporta Anthropic, OpenAI, DeepSeek, Ollama y LM Studio, pero carece de integración con Google AI (Gemini), dejando fuera una de las familias de modelos más relevantes del mercado. Añadir este conector amplía el abanico de proveedores disponibles sin cambiar el contrato de la API pública.

## What Changes

- Nuevo adaptador `app/adapters/google.py` implementando `BaseAdapter` con las operaciones `message`, `stream` y `embed`
- Nueva variable de configuración `GOOGLE_API_KEY` en `Settings` (`core/config.py`)
- Registro automático de `GoogleAdapter` en `ProviderRegistry.startup()` cuando la API key está presente
- Nueva dependencia `google-genai` en `requirements.txt`
- Documentación de la variable en `.env.example`

## Capabilities

### New Capabilities

- `google-gemini-provider`: Adaptador completo para Google AI Studio (Gemini API) con soporte de chat, streaming y embeddings, siguiendo el patrón `BaseAdapter` existente

### Modified Capabilities

_(sin cambios en requisitos de capabilidades existentes)_

## Impact

- **Código nuevo**: `router-ai/app/adapters/google.py`
- **Código modificado**: `core/config.py`, `core/registry.py`, `requirements.txt`, `.env.example`
- **Dependencia nueva**: `google-genai >= 1.0`
- **Sin cambios en API pública**: los endpoints `/chat`, `/stream`, `/embed` y `/health` permanecen iguales; Google queda disponible como nuevo valor de `provider`
- **Sin cambios breaking**: la ausencia de `GOOGLE_API_KEY` simplemente omite el registro del proveedor, igual que ocurre con los demás proveedores opcionales
