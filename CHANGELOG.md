# Changelog

All notable changes to AegisAI are recorded here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Nothing yet.

## [0.1.0] — Unreleased

Initial functional release. The platform can register users, manage projects and
targets, run security tests against AI model endpoints, and produce scored,
evidence-backed reports through a web UI.

### Added

#### Security foundation

- JWT + Argon2id authentication with project-scoped RBAC and audit logging.
- Fernet-encrypted target credentials at rest, with a PBKDF2-derived key that is
  never persisted, credential versioning, and revocation.
- Outbound network policy blocking loopback, link-local, and private CIDRs, cloud
  metadata hosts, DNS rebinding, and unsafe redirects.
- Per-IP rate limiting on `/auth/login` and `/auth/register`.
- RBAC guards preventing a project from losing its last admin, including
  self-demotion and self-removal cases.
- Structured JSON logging with request-ID correlation on every log line.

#### Execution engine

- In-process async execution engine running security tests against
  `openai_compatible`, `ollama`, and `custom_rest` adapters.
- Full lifecycle: `PENDING → RUNNING → SUCCEEDED/FAILED/CANCELLED` with retries,
  exponential backoff, per-execution timeouts, and cancellation.
- Multi-turn conversation execution that preserves full conversation history.
- Rule-based finding classification with keyword and regex grading, plus optional
  judge-model grading.
- Automatic request/response evidence capture linked to each finding.

#### Attack content library

- 89 seeded test cases across prompt injection (20), jailbreak (20), privacy and
  data leakage (20), RAG attacks (14), and agent/tool-use (15).
- Typed YAML/JSON test-case schema with validation and documentation.

#### Risk scoring and reporting

- Custom severity and risk rubric, with content-based automatic severity
  derivation and an explicit MEDIUM fallback.
- Report generation in JSON and Markdown, with OWASP LLM Top 10:2025 compliance
  mapping surfaced per finding.
- Report versioning, machine-readable data snapshots, and run-to-run comparison
  producing new / resolved / regressed / improved findings.
- Report download endpoint.

#### Web frontend

- React 19 + TypeScript single-page application covering sign-up, projects,
  targets, credentials, test execution, findings, evidence, and reports.
- Typed API client with bearer-token injection and structured error handling.
- Session-scoped token storage that never writes to `localStorage` and refuses
  to send an expired token.
- Credential values are write-only in the UI: the API client deliberately omits
  the backend's credential-resolve endpoint.
- One-click loading of the 89-case attack library from the project page, backed by
  an idempotent seeding endpoint; live execution status polling that stops when no
  run is in flight.

#### Deployment and CI

- Multi-stage backend Dockerfile running as a non-root user with a healthcheck.
- Frontend Dockerfile building the SPA and serving it from unprivileged nginx
  with SPA history fallback and an internal `/api` proxy.
- Local development and hardened production Compose stacks; the production stack
  publishes no public ports, drops all Linux capabilities, and uses read-only
  root filesystems.
- GitHub Actions gates for Ruff lint and format, Pyright, pytest against a real
  PostgreSQL service, `alembic check`, `pip-audit`, and the frontend quality
  suite, plus a container build-and-smoke workflow.
- Tagged-release workflow that publishes signed, provenance-attested images and
  deploys to staging.

### Fixed

- **Cross-tenant authorization bypass in bulk test seeding.** Loading the bundled attack
  library authorized each individual test create but ran no check when there was nothing
  left to create, so an unrelated user could read another project's test count from the
  summary. Seeding now authorizes up front and requires mutation rights, so viewers are
  denied too.
- Judge-model grading returned `PASS` when the judge was unavailable, reporting a
  target as safe purely because grading could not run. It now returns
  `INCONCLUSIVE`, which avoids a false negative on a security test.
- Multi-turn execution dropped the user's earlier turns from conversation
  history, weakening multi-turn attack sequences. Prior turns are now preserved.
- Report comparison read live database state, making two historical runs
  indistinguishable. Comparison now reads persisted per-run data snapshots.
- `Execution.result` declared an index that no migration created; `alembic check`
  now reports no drift.

### Security notes

- Only authorized systems should be tested with AegisAI. Creating a target
  represents an attestation of authorization.
- Credential plaintexts are never returned by the API and are never displayed in
  the UI.

[Unreleased]: https://github.com/aegisai/aegis/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/aegisai/aegis/releases/tag/v0.1.0
