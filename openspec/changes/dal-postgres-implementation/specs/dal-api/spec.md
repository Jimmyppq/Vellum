## ADDED Requirements

### Requirement: All endpoints return the standard response envelope
The system SHALL wrap every successful response in `{"data": {...}, "meta": {"request_id": "<uuid>", "version": "1.0.0"}}` and every error in `{"error": {"code": "<UPPER_SNAKE_CASE>", "message": "<human-readable>", "trace_id": "<uuid>"}}`. No endpoint SHALL return a bare object or array.

#### Scenario: Successful GET returns data envelope
- **WHEN** `GET /v1/prompts/{id}` finds the resource
- **THEN** the response body SHALL match `{"data": {"id": "...", ...}, "meta": {"request_id": "...", "version": "1.0.0"}}`

#### Scenario: Not found returns error envelope with 404
- **WHEN** `GET /v1/prompts/{id}` cannot find the resource
- **THEN** the response SHALL be HTTP 404 with body `{"error": {"code": "NOT_FOUND", "message": "...", "trace_id": "..."}}`

### Requirement: Prompts endpoints are implemented
The system SHALL expose: `POST /v1/prompts` (201), `GET /v1/prompts/{id}` (200), `GET /v1/prompts` with query params `status`, `owner_id`, `limit`, `offset` (200), `PATCH /v1/prompts/{id}/status` (200).

#### Scenario: POST /v1/prompts creates a prompt
- **WHEN** a valid `PromptCreate` payload is sent to `POST /v1/prompts`
- **THEN** the response SHALL be HTTP 201 with the created prompt in the data envelope

#### Scenario: GET /v1/prompts filters by status
- **WHEN** `GET /v1/prompts?status=approved` is called
- **THEN** only prompts with `status=approved` SHALL appear in the response list

### Requirement: Prompt versions endpoints are implemented
The system SHALL expose: `POST /v1/prompts/{id}/versions` (201), `GET /v1/prompts/{id}/versions` (200), `GET /v1/prompts/{id}/versions/active` (200), `GET /v1/prompts/{id}/versions/{version_id}` (200).

#### Scenario: GET active version returns 404 when none exists
- **WHEN** `GET /v1/prompts/{id}/versions/active` is called for a prompt with no active version
- **THEN** the response SHALL be HTTP 404

### Requirement: Executions endpoints are implemented
The system SHALL expose: `POST /v1/executions` (201), `GET /v1/executions/{id}` (200), `PATCH /v1/executions/{id}/status` (200), `GET /v1/executions` with query params `prompt_id`, `status`, `limit`, `offset` (200).

#### Scenario: PATCH execution status to completed sets completed_at
- **WHEN** `PATCH /v1/executions/{id}/status` with `{"status": "completed"}` is sent
- **THEN** the returned execution SHALL have a non-null `completed_at` timestamp

### Requirement: Users endpoints are implemented
The system SHALL expose: `POST /v1/users` (201), `GET /v1/users/{id}` (200), `GET /v1/users/email/{email}` (200), `POST /v1/users/{id}/roles` (200).

#### Scenario: Duplicate email returns 409
- **WHEN** `POST /v1/users` is called with an email already registered
- **THEN** the response SHALL be HTTP 409 with error code `USER_EMAIL_CONFLICT`

### Requirement: Transcripts endpoints are implemented
The system SHALL expose: `POST /v1/transcripts` (201), `GET /v1/transcripts/{id}` (200), `PATCH /v1/transcripts/{id}/status` (200), `POST /v1/transcripts/{id}/versions` (201), `GET /v1/transcripts/{id}/versions/active` (200).

#### Scenario: POST transcript version increments version_number
- **WHEN** a second version is created for the same transcript
- **THEN** the new version SHALL have `version_number = 2`

### Requirement: Connectors endpoints are implemented
The system SHALL expose: `POST /v1/connectors` (201), `GET /v1/connectors` (200), `GET /v1/connectors/{id}` (200), `PATCH /v1/connectors/{id}/active` (200).

#### Scenario: PATCH connector active toggles is_active
- **WHEN** `PATCH /v1/connectors/{id}/active` with `{"is_active": false}` is sent
- **THEN** the connector SHALL have `is_active=false` in the response

### Requirement: Health and system config endpoints are implemented
The system SHALL expose: `GET /health` (200, public — no auth required), `GET /v1/config` (200), `PUT /v1/config/{key}` (200).

#### Scenario: GET /health returns service status
- **WHEN** `GET /health` is called
- **THEN** the response SHALL be HTTP 200 with at minimum `{"status": "ok", "db": true|false}`

### Requirement: HTTP status codes match the standard
The system SHALL use exactly: 200 for GET/PATCH success, 201 for POST success, 400 for invalid input, 401 for missing/invalid auth, 403 for insufficient permissions, 404 for not found, 409 for conflicts, 422 for Pydantic validation errors, 500 for unexpected server errors.

#### Scenario: Pydantic validation failure returns 422
- **WHEN** a request body fails Pydantic validation
- **THEN** the response SHALL be HTTP 422 with error details in the standard envelope
