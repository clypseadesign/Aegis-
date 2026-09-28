# Remaining Work Plan — AegisAI

Status: After completion of **model adapters**, **target credential storage**,
**secret resolution/lifecycle**, and **outbound network/SSRF policy**.

Repository validations: Ruff lint/format clean, Pyright 0 errors,
`alembic check` consistent, 82 tests passing. `cryptography>=43,<44` added as
runtime dependency for Fernet-at-rest credential encryption.

## Remaining TODO (see docs/TODO.md)

- [ ] Add project membership and organization models with refined project-level RBAC.
- [ ] Implement test suite, execution job, finding, evidence, and report models, services, and APIs.
- [ ] Implement risk scoring, severity assessment, and report generation.
- [ ] Implement attack orchestration and multi-turn execution workflows.
- [ ] Build the frontend experience for targets, assessments, executions, findings, evidence, and reports.
- [ ] Add production deployment, secret-management, monitoring, and operational hardening.

## Proposed execution order

### Milestone 1 — Project membership + RBAC (ADR-006)
- Extend `Project` with a `membership` table (project_id, user_id, role) for
  fine-grained project roles (owner/admin/editor/viewer).
- Service: `projects.membership` add/remove/list members.
- API: `POST /api/v1/projects/{id}/members`, `GET ...`, `PATCH/DELETE`.
- Tests: membership authorization + RBAC scoping.
- Migration + alembic check.

### Milestone 2 — Test suite, execution, findings, evidence, reports (ADR-008/010)
- Models: `SecurityTest` (project-scoped, provider/capabilities),
  `Execution` (status enum), `Finding` (severity + status + metadata jsonb),
  `Evidence` (kind + content jsonb), `Report` (format + path).
- Schemas with secret/prompt redaction and response size bounds.
- Services enforcing authorization before any DB write and never persisting
  secrets.
- API routes nested under projects; response models exclude secrets.
- Migration + alembic check + service/API tests.

### Milestone 3 — Risk scoring & reporting (ADR-009)
- `Severity` enum + `RiskScore` computation helpers.
- Report generation service writing reports under a configured reports dir.

### Milestone 4 — Attack orchestration (ADR-011)
- `ExecutionPlan`/`ExecutionStep` models, cancellation propagation, bounded
  retries, correlation IDs, adapter integration with credential resolution.

### Milestone 5 — Operational hardening (ADR-014/015)
- `.env.example`, pre-commit secret scanning config, production startup checks.

## Validation gate (run after each milestone)
- `ruff check .`
- `ruff format --check .`
- `pyright --pythonpath ".venv\Scripts\python.exe"`
- `alembic check` + `alembic upgrade head` against temp Postgres
- `.venv\Scripts\python.exe -m pytest -q`
- update `docs/TODO.md`

## Notes
- All secrets remain server-side; `SECRET_KEY` required for `SecretStore`.
- Frontend build is out of scope for backend-first milestones.
