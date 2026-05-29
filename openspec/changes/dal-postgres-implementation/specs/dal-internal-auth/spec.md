## ADDED Requirements

### Requirement: DAL validates that requests originate from internal services
The system SHALL reject requests that do not present valid internal credentials. In staging and production environments (when `MTLS_ENABLED=true`), the mutual TLS handshake at the Nginx gateway level serves as authentication. In development (`MTLS_ENABLED=false`), the DAL SHALL validate the `X-Internal-Service-Token` header against the value of `INTERNAL_SERVICE_TOKEN` environment variable.

#### Scenario: Missing token in dev returns 401
- **WHEN** `MTLS_ENABLED=false` and a request arrives without the `X-Internal-Service-Token` header
- **THEN** the DAL SHALL respond with HTTP 401 and error code `MISSING_SERVICE_TOKEN`

#### Scenario: Wrong token in dev returns 401
- **WHEN** `MTLS_ENABLED=false` and `X-Internal-Service-Token` does not match `INTERNAL_SERVICE_TOKEN`
- **THEN** the DAL SHALL respond with HTTP 401 and error code `INVALID_SERVICE_TOKEN`

#### Scenario: Correct token in dev passes through
- **WHEN** `MTLS_ENABLED=false` and `X-Internal-Service-Token` matches `INTERNAL_SERVICE_TOKEN`
- **THEN** the request SHALL proceed to the handler

#### Scenario: mTLS mode skips token validation
- **WHEN** `MTLS_ENABLED=true`
- **THEN** the `X-Internal-Service-Token` header SHALL be ignored and no token validation SHALL occur

### Requirement: /health endpoint is exempt from internal auth
The system SHALL allow `GET /health` to be called without any authentication credentials, in both dev and mTLS modes.

#### Scenario: Health check is accessible without credentials
- **WHEN** `GET /health` is called without any auth header or certificate
- **THEN** the response SHALL be HTTP 200 regardless of `MTLS_ENABLED` value

### Requirement: Internal service token is never hardcoded
The system SHALL read the `INTERNAL_SERVICE_TOKEN` exclusively from the environment. The token SHALL NOT appear in any source file, Dockerfile, or docker-compose file committed to the repository.

#### Scenario: Missing INTERNAL_SERVICE_TOKEN in dev does not start silently
- **WHEN** `MTLS_ENABLED=false` and `INTERNAL_SERVICE_TOKEN` is not set
- **THEN** the application SHALL log a warning at startup indicating that no service token is configured
