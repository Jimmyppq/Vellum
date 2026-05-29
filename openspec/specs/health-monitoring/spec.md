## ADDED Requirements

### Requirement: Endpoint de salud del servicio
El sistema SHALL exponer `GET /v1/health` que retorna el estado global del microservicio y el estado individual de cada proveedor configurado.

#### Scenario: Todos los proveedores disponibles
- **WHEN** se llama a `GET /v1/health` y todos los proveedores configurados responden correctamente
- **THEN** el sistema retorna HTTP 200 con `{"status": "ok", "providers": {"anthropic": "ok", "openai": "ok"}}`

#### Scenario: Algún proveedor no disponible
- **WHEN** se llama a `GET /v1/health` y al menos un proveedor configurado no responde
- **THEN** el sistema retorna HTTP 200 con `{"status": "degraded", "providers": {"anthropic": "ok", "openai": "error: ..."}}`

#### Scenario: Sin proveedores configurados
- **WHEN** el servicio arranca sin ninguna API key configurada
- **THEN** `GET /v1/health` retorna HTTP 200 con `{"status": "degraded", "providers": {}}` indicando que no hay proveedores disponibles

### Requirement: Verificación de conectividad por proveedor
El método `health()` de cada adaptador SHALL realizar una comprobación ligera de conectividad (ej. listar modelos disponibles o hacer un ping mínimo a la API) y retornar `{"status": "ok"}` o `{"status": "error", "detail": "..."}`.

#### Scenario: Health check exitoso de Anthropic
- **WHEN** se invoca `health()` en `AnthropicAdapter` y la API key es válida y alcanzable
- **THEN** el adaptador retorna `{"status": "ok"}` en menos de 5 segundos

#### Scenario: Health check con timeout
- **WHEN** la API del proveedor no responde dentro de 5 segundos
- **THEN** el adaptador retorna `{"status": "error", "detail": "timeout"}` sin lanzar excepción

#### Scenario: Health check con credencial inválida
- **WHEN** la API key configurada es inválida o ha sido revocada
- **THEN** el adaptador retorna `{"status": "error", "detail": "credencial inválida"}` con el código de error del proveedor

### Requirement: Endpoint de proveedores disponibles
El sistema SHALL exponer `GET /v1/providers` que lista los proveedores actualmente registrados y su estado de configuración.

#### Scenario: Lista de proveedores registrados
- **WHEN** se llama a `GET /v1/providers`
- **THEN** el sistema retorna una lista con los nombres de los proveedores registrados y si su `health()` está disponible, ej. `[{"name": "anthropic", "status": "ok"}, {"name": "openai", "status": "ok"}]`
