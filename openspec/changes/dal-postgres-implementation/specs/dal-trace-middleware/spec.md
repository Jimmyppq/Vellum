## ADDED Requirements

### Requirement: X-Trace-Id is propagated or generated on every request
The system SHALL include FastAPI middleware in `dal/app/middleware/trace_id.py` that reads the `X-Trace-Id` header from incoming requests. If the header is absent, the middleware SHALL generate a new UUID v4 as the trace ID. The trace ID SHALL be stored in `request.state.trace_id` and appended to the response headers as `X-Trace-Id`.

#### Scenario: Request with X-Trace-Id preserves the value
- **WHEN** a request arrives with `X-Trace-Id: 550e8400-e29b-41d4-a716-446655440000`
- **THEN** the response SHALL include `X-Trace-Id: 550e8400-e29b-41d4-a716-446655440000`

#### Scenario: Request without X-Trace-Id receives a generated one
- **WHEN** a request arrives without `X-Trace-Id`
- **THEN** the response SHALL include `X-Trace-Id` with a valid UUID v4

### Requirement: All DAL log entries include the trace_id in JSON format
The system SHALL emit all log entries as structured JSON. Every log entry SHALL include at minimum the fields: `timestamp` (ISO 8601 UTC), `level`, `trace_id`, `service` (always `"dal"`), `action`, `duration_ms`, `status`. Sensitive data (DSN with password, token values, full PII content) SHALL NOT appear in any log entry.

#### Scenario: Log entry for a repository action contains required fields
- **WHEN** `PromptsRepository.create` executes successfully
- **THEN** the emitted log entry SHALL contain `trace_id`, `action` (e.g., `"prompts.create"`), `duration_ms`, and `status: "success"`

#### Scenario: Log entry for a failed action contains error info without sensitive data
- **WHEN** a repository operation fails due to a database error
- **THEN** the log entry SHALL contain `status: "failure"` and an error description that does NOT include DSN credentials or user PII

### Requirement: trace_id is accessible to all layers via request.state
The system SHALL make `request.state.trace_id` available throughout the request lifecycle so that repositories and routers can include it in log entries without passing it as a function parameter.

#### Scenario: Repository accesses trace_id from request context
- **WHEN** a router calls a repository method during a request
- **THEN** the repository SHALL be able to read the trace_id without it being passed as an explicit argument
