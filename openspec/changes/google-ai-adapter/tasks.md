## 1. Dependencias y configuración

- [x] 1.1 Añadir `google-genai>=1.0` a `router-ai/requirements.txt`
- [x] 1.2 Añadir `GOOGLE_API_KEY=AIza...` a `router-ai/.env.example` con comentario descriptivo
- [x] 1.3 Añadir `google_api_key: SecretStr | None = None` a `Settings` en `router-ai/app/core/config.py`

## 2. Implementación del adaptador

- [x] 2.1 Crear `router-ai/app/adapters/google.py` con la clase `GoogleAdapter(BaseAdapter)`
- [x] 2.2 Implementar `__init__` inicializando `google.genai.Client` con `api_key`
- [x] 2.3 Implementar `message()` con modelo default `gemini-2.0-flash` y mapeo de rol `assistant` → `model`
- [x] 2.4 Implementar `stream()` usando `client.aio.models.generate_content_stream`, emitiendo chunks y chunk final con `done=True`
- [x] 2.5 Implementar `embed()` con modelo default `text-embedding-004`, soportando input único y lista
- [x] 2.6 Implementar `health()` con llamada a `models.list()` y timeout de 5 segundos

## 3. Registro del proveedor

- [x] 3.1 Importar `GoogleAdapter` en `router-ai/app/core/registry.py`
- [x] 3.2 Añadir bloque condicional en `startup()`: si `settings.google_api_key` → registrar `"google"` con `GoogleAdapter`

## 4. Verificación

- [x] 4.1 Instalar dependencias (`pip install google-genai`) y verificar que el servidor arranca sin errores con `GOOGLE_API_KEY` presente
- [ ] 4.2 Verificar que `GET /v1/health` incluye el proveedor `"google"` cuando la key está configurada
- [ ] 4.3 Verificar que `POST /v1/chat` con `provider="google"` devuelve respuesta válida
- [ ] 4.4 Verificar que `POST /v1/stream` con `provider="google"` emite chunks SSE correctamente
- [ ] 4.5 Verificar que `POST /v1/embed` con `provider="google"` devuelve vectores de embeddings
- [x] 4.6 Verificar que el servidor arranca correctamente **sin** `GOOGLE_API_KEY` (el proveedor simplemente no se registra)
