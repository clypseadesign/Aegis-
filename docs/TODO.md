# AegisAI Development Todo List

Status: Completed scope; remaining roadmap work is tracked below.

## Authentication and Authorization

- [x] Add local user model and schema.
- [x] Add password hashing and JWT token support.
- [x] Add authentication service for registration and login.
- [x] Add current-user dependency and bearer-token authentication.
- [x] Add standardized authentication and authorization errors.
- [x] Add API handlers for authentication and permission-denied responses.
- [x] Add user registration and login API routes.
- [x] Add authentication service and API authorization tests.

## Project Management

- [x] Add project ownership model support.
- [x] Add project create, list, get, update, and delete services.
- [x] Add project create, list, get, update, and delete API routes.
- [x] Add project ownership and administrative authorization behavior.
- [x] Add project service and API tests.
- [x] Document the current project authorization matrix.

## Target Management

- [x] Add target model with provider, endpoint, model, capabilities, timeout, rate limit, status, and timestamps.
- [x] Add target create, update, and response schemas.
- [x] Add target service with project-scoped authorization.
- [x] Add target API routes for list, create, get, update, and delete.
- [x] Add target Alembic migration with enum types, constraints, indexes, and project foreign key.
- [x] Register target model, schema, service, and route exports.
- [x] Add target CRUD and authorization tests.
- [x] Add target validation coverage for endpoint, provider model requirements, and empty updates.
- [x] Ensure target responses do not expose credentials.

## Observability and System Endpoints

- [x] Add audit log model and audit event service.
- [x] Add readiness endpoint with database connectivity status.
- [x] Add liveness health endpoint.
- [x] Add system info response schema.
- [x] Add system endpoint tests.

## Migration Validation

- [x] Import application models before Alembic metadata assignment.
- [x] Validate Alembic upgrade to head against temporary PostgreSQL.
- [x] Validate Alembic current revision is `5d8b9e6a2c41 (head)`.
- [x] Validate Alembic schema consistency with `alembic check`.
- [x] Validate offline migration SQL generation with `alembic upgrade head --sql`.
- [x] Remove temporary PostgreSQL container `aegis-alembic-test`.

## Quality Checks

- [x] Run Ruff lint: passed.
- [x] Run Ruff formatting check: passed.
- [x] Run Pyright type check: passed.
- [x] Run full pytest suite: 82 passed, 1 dependency warning.
- [x] Run final `git diff --check`: passed, with only expected CRLF warning messages.
- [x] Review final tracked and untracked diff.

## Remaining Work

All items previously listed here are complete. For the current roadmap, see
`docs/production-readiness-todo.md`.

- [x] Implement model adapter clients for `openai_compatible`, `ollama`, and `custom_rest`.
- [x] Add normalized `ModelMessage`, `ModelRequest`, `ModelResponse`, and `ModelUsage` contracts in `app/models/model.py`.
- [x] Add `app/adapters` package with `base`, `errors`, `registry`, and provider adapters.
- [x] Add model adapter tests covering normalization, fallback parsing, error mapping, timeouts, and validation.
- [x] Implement target credential storage, secret resolution, and credential lifecycle management.
- [x] Add encrypted `TargetCredential` model with versioning, revocation, and audit events.
- [x] Add `SecretStore` (Fernet) and credential resolution backed by the target credential store.
- [x] Add target credential API routes (create/list/get/revoke/rotate/delete) with redaction. The plaintext resolve endpoint was later removed entirely; plaintext is resolved in-process by the execution engine only.
- [x] Add credential service and API tests.
- [x] Implement outbound network policy, SSRF protection, DNS rebinding defense, and redirect handling.
- [x] Add `app/security/network.py` policy validation integrated into the base adapter and covered by tests.
- [x] Add project membership and organization models with refined project-level RBAC.
- [x] Implement test suite, execution job, finding, evidence, and report models, services, and APIs.
- [x] Implement risk scoring, severity assessment, and report generation.
- [x] Implement attack orchestration and multi-turn execution workflows.
- [x] Build the frontend experience for targets, assessments, executions, findings, evidence, and reports.
- [x] Add production deployment, secret-management, monitoring, and operational hardening.

## Environment Notes

- `uv` was not available on `PATH`; validation used `.venv\Scripts\python.exe`, `.venv\Scripts\ruff.exe`, `.venv\Scripts\pyright.exe`, and `.venv\Scripts\alembic.exe`.
- `cryptography>=43,<44` was added as a runtime dependency for Fernet-at-rest credential encryption.
- No commit was created.
