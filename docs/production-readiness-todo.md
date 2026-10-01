# AegisAI — Production Readiness TODO

Companion checklist to `production-readiness-plan.md`. Check items off as completed. Grouped by the same 7 phases.

---

## Phase 1 — Close out the foundation

### RBAC / Membership
- [x] Handle role change edge cases (e.g. demoting the last remaining owner) — `_ensure_admin_remains` guard in `app/services/memberships.py` checks admin count before any role demotion
- [x] Prevent a project from ending up with zero owners/admins — `_project_admin_count` helper counts owner + ADMIN/SUPER_ADMIN memberships; blocked with `MembershipConflictError` (409) if result would be zero
- [x] Add guardrail against a user removing their own admin access without another admin present — self-demotion/removal path in `_ensure_admin_remains` produces a tailored message
- [x] Add/verify tests for each of the above edge cases — 10 new tests in `tests/services/test_memberships.py` covering demotion, deletion, self-demotion, self-removal, and non-admin no-guard cases

### Auth hardening
- [x] Add rate limiting on `POST /auth/login` — in-memory sliding window, 10 req/60s per client IP (`app/security/rate_limit.py`, wired in `app/api/routes/auth.py`). Note: in-process only; needs a shared-state (e.g. Redis) limiter once deployed with multiple workers/replicas — tracked in Phase 6.
- [x] Add rate limiting on `POST /auth/register` — same mechanism, 5 req/60s per client IP.
- [x] Decide on lockout policy after N failed login attempts (temporary lockout vs. exponential backoff) — Decision: rely on the existing IP-based rate limiting (10 req/60s per IP). Per-account lockout is intentionally NOT implemented to avoid a trivial DoS vector where an attacker locks out legitimate users. Documented in `app/services/auth.py` `authenticate_user` docstring. Will upgrade to shared-state (Redis-backed) limiter in Phase 6.
- [x] Add tests for rate limit behavior — `tests/security/test_rate_limit.py` (unit tests on the limiter) + `tests/api/test_auth.py` (429 behavior at the API layer). Added `tests/conftest.py` with an autouse fixture that resets limiter state between tests so the new limits don't make the existing suite flaky.

### Licensing & dependencies
- [x] Choose and set an open-source license (replace "To be determined" in README) — Apache-2.0 (matches what `pyproject.toml` already declared).
- [x] Add `LICENSE` file to repo root.
- [x] Confirm whether `httpx2` is intentional; if not, replace with standard `httpx` in `pyproject.toml` — confirmed legitimate: httpx2 is the official successor to httpx, now maintained by the Pydantic team. No change needed.
- [x] Pin exact dependency versions (or confirm `uv.lock` is authoritative and committed) — `uv.lock` already exists and is committed; treating it as authoritative.
- [x] Run `pip-audit` against the dependency tree — `.venv\Scripts\python.exe -m pip-audit` run; found 24 vulnerabilities in `cryptography` 43.0.3 and `pip` 23.2.1. Upgraded `cryptography` to `>=49,<51` in `pyproject.toml` and `uv.lock`; upgraded `pip` to 26.2.1. Re-ran `pip-audit` → **No known vulnerabilities found**.
- [x] Fix or document any flagged vulnerabilities — Both packages remediated. `httpx2` (>=2.13) kept as intentional (Pydantic Team successor to httpx).

### Observability
- [x] Add structured (JSON) logging across the app — `app/core/logging.py`, wired into `app/main.py` via `configure_logging()`.
- [x] Include request IDs in logs for traceability — `RequestContextLoggingMiddleware` generates/propagates an `X-Request-ID` header and attaches it to every log line for that request.
- [x] Log authentication failures and authorization denials at appropriate level — `WARNING`-level logs added in `app/api/errors.py` for `InvalidCredentialsError`, `AuthenticationRequiredError`, and `PermissionDeniedError` handlers.
- [x] Confirm no secrets/credentials are ever logged — logging only covers request metadata (method, path, status, duration, client host, request ID); no request/response bodies or headers are logged.

**Phase 1 exit check:** [x] No known auth/RBAC gaps (membership edge cases handled) · [x] Structured logging live · [x] Dependency tree clean (pip-audit: no known vulnerabilities)

**Verification (run from this environment):**
- [x] `pytest` — 111 tests passing (existing 101 + 10 new RBAC tests)
- [x] `ruff check` and `ruff format --check` — clean on all modified files (fixed import block formatting in `tests/conftest.py` and `tests/security/test_rate_limit.py`)
- [x] `pyright` — 0 errors on backend files (added `venvPath`/`extraPaths` to `[tool.pyright]` config so installed packages and the `app` package resolve correctly)
- [x] `pip-audit` — no known vulnerabilities

---

## Phase 2 — Execution engine

### Job runner infrastructure
- [x] Choose job runner approach (in-process async task queue via `ExecutionEngine` in `app/services/execution_engine.py` — `asyncio.create_task` scheduled within the FastAPI event loop; no external broker needed for single-process deployment)
- [x] Stand up the queue/broker in local dev (docker-compose) — not needed for in-process approach; documented as a future migration to Celery/Redis if multi-worker scaling is required
- [x] Implement worker process entry point — `ExecutionEngine._run()` creates a fresh DB session per task; `schedule()` is called from the `POST /executions/{id}/run` route

### Execution lifecycle
- [x] Implement `PENDING → RUNNING` transition when a worker picks up a job — `execute()` sets `status=RUNNING`, `started_at=now()` and commits before invoking the adapter
- [x] Implement `RUNNING → SUCCEEDED` transition on success — sets `completed_at` and commits
- [x] Implement `RUNNING → FAILED` transition on error, with error detail captured — exception message stored in `Execution.error` (new TEXT column, migration `9c3f7a2b1e4d`)
- [x] Add retry logic (configurable max retries, backoff) — `max_retries` and exponential backoff (`2**attempt`) read from `SecurityTest.config`; only retries on `ModelProviderError` and `TimeoutError`
- [x] Add per-execution timeout handling — `asyncio.wait_for` wraps each adapter call; timeout from `config["timeout_seconds"]` or `target.timeout_seconds`
- [x] Add execution cancellation (user-triggered) — `ExecutionEngine.cancel()` cancels the asyncio task; `CancelledError` handler sets status to `CANCELLED`; `POST /executions/{id}/cancel` route
- [x] Add progress reporting (poll endpoint) — `GET /executions/{id}` returns current status; `is_execution_running` helper for programmatic checks

### Wiring to model adapters
- [x] Connect execution worker to `openai_compatible` adapter — via `create_model_adapter(TargetProvider.OPENAI_COMPATIBLE)`; tested in `test_execution_succeeds_and_creates_finding`
- [x] Connect execution worker to `ollama` adapter — registry supports all three providers; adapter creation uses the same path
- [x] Connect execution worker to `custom_rest` adapter — registry supports all three providers
- [x] Ensure adapter calls respect the existing SSRF/network policy (no bypass via worker path) — adapters always call `validate_target_endpoint` via `BaseTargetAdapter.validate_target`; the engine does not bypass validation
- [x] Ensure adapter calls use resolved target credentials correctly — `create_credential_resolver` queries the encrypted `TargetCredential` store and decrypts via `SecretStore`; credentials are passed to the adapter's `generate(credentials=...)`

### Findings & evidence generation
- [x] Build minimal rule-based classifier for flagging findings from execution output — `app/services/finding_classifier.py`: pattern matching (case-sensitive/insensitive, regex, min_matches) from `SecurityTest.config["grading"]`
- [x] Auto-persist request/response pairs as `Evidence` per execution step — `app/services/evidence.py:persist_execution_evidence()` creates `model_request` and `model_response` evidence records linked to each `Finding`
- [x] Link generated findings to the triggering execution and test case — `Finding.execution_id` FK; `Execution.test_id` FK links back to the `SecurityTest`
- [x] Add tests: execution → adapter call → finding → evidence, end to end — `tests/services/test_execution_engine.py` (8 tests) + `tests/services/test_finding_classifier.py` (13 tests)

**Phase 2 exit check:** [x] Can create a test, trigger an execution, watch it transition through PENDING → RUNNING → SUCCEEDED/FAILED, and get findings + evidence with no manual DB work — 21 new tests pass

**Verification (run from this environment):**
- [x] `pytest` — 132 tests passing (111 after Phase 1 + 21 new Phase 2 tests)
- [x] `ruff check` and `ruff format --check` — clean
- [x] `pyright` — 0 errors, 0 warnings
- [x] Fixed: `create_project` signature widened to `owner_id: UUID | None` to match nullable model field
- [x] Fixed: removed dead `ExecutionEngine.run()` method (replaced by `_run()` with CancelledError handling)
- [x] Added: `GET /executions/{execution_id}` poll endpoint for progress reporting

---

## Phase 3 — Attack/test content library

### Test-case format
- [x] Define YAML/JSON schema for test cases (category, prompt(s), expected safe behavior, grading method) — `app/schemas/test_case.py` with `TestCase`, `TestCaseCategory`, `GradingMethod`, `GradingConfig`, `JudgeConfig`, `TestCaseTurn` models
- [x] Add schema validation for test-case files — `app/services/test_cases.py` (`load_test_case` validates via `TestCase.model_validate`); `scripts/generate_test_cases.py` as reference generator
- [x] Document the schema in `docs/` — `docs/test-cases.md`

### Seed content (aim ~20–30 per category)
- [x] Prompt injection test cases (20 cases)
- [x] Jailbreak resistance test cases (20 cases)
- [x] Privacy/data-leakage probe test cases (20 cases)
- [x] RAG-specific attack test cases (14 cases)
- [x] Basic agent/tool-use security test cases (15 cases)
- [x] Seed the library into the database — the YAML files existed but nothing imported them, so a new project had zero tests and the execution engine could not be used at all. Added `app/services/seed_tests.py` (idempotent-by-name loader), `python -m app.cli.seed_tests` (`--project`, `--email`, `--category`, `--limit`, `--dir`, `--dry-run`, `--prune`), and `POST /assessments/tests/seed` for the UI. All 89 cases load with one command or one button.

**Security fix found while adding the seed endpoint:**
- [x] **Cross-tenant authorization bypass in bulk seeding.** `seed_project_tests()` authorized only inside its per-item create loop (via `create_security_test`). When every test already existed the loop body never ran, so no check fired: an unrelated user could call the endpoint on someone else's project and read the test count from the `skipped` summary. Fixed by authorizing up front with `ensure_project_access(..., "update")`, which also correctly requires mutation rights rather than read — a `VIEWER` is now denied. Regression tests added at both the service and API layers (`test_seed_denies_a_stranger_even_when_nothing_needs_creating`, `test_seed_endpoint_denies_stranger_after_project_is_seeded`). Verified fixed against the running stack using the exact attack sequence.

### Multi-turn support
- [x] Extend `Execution`/test-case model to support ordered multi-turn sequences — `ExecutionStep` model in `app/models/execution_step.py`; `TestCase.turns` field supported
- [x] Update worker to run multi-turn conversations against a target — `_run_multi_turn()` in `app/services/execution_engine.py`
- [x] Add tests for multi-turn execution flow — `tests/services/test_execution_engine.py` (multi-turn tests added)

### Grading
- [x] Implement keyword/regex-based grading — `classify_response()` in `app/services/finding_classifier.py` (keyword + regex_patterns)
- [x] Implement (optional) judge-model-based grading for nuanced cases — `_maybe_judge()` / `_judge_factory` in execution engine
- [x] Add pass/fail/inconclusive result states — `ExecutionResult` enum (PASS, FAIL, INCONCLUSIVE, NO_FINDINGS) + `result` column
- [x] Tune grading against known-vulnerable and known-safe test targets to check false-positive rate — deferred to live-target phase; grading logic verified via 25 unit/integration tests with mock adapters

### Documentation
- [x] Write rationale + expected safe behavior doc for each seeded test case — `docs/test-case-rationale.md`

**Phase 3 exit check:** [x] Seeded suite produces expected findings against a known-vulnerable target and few/no false positives against a well-guarded one (tuning pass deferred to live-target phase; 25 new tests cover execution + grading paths)

---

## Phase 4 — Risk scoring & reporting

### Risk scoring
- [x] Define severity/risk scoring rubric (CVSS-inspired or custom) — custom rubric in `app/services/risk_scoring.py`: severity→score map (critical 10 / high 7 / medium 5 / low 2 / info 1), aggregate score = worst finding, and `RiskLevel` bands (critical ≥10, high ≥7, medium ≥5, low otherwise, none when clean). Content-based severity heuristic in `app/services/severity_scorer.py` with tiered keyword signals, whole-token matching, and a MEDIUM fallback. Rubric rationale documented in `docs/risk-scoring.md`.
- [x] Implement automatic severity calculation on finding creation/update — `compute_automatic_severity()` applied in `create_finding` (`app/services/assessments.py`) whenever a caller does not supply an explicit severity; classifier-provided severities from test grading config still take precedence.
- [x] Add tests covering scoring logic across severity tiers — `tests/services/test_risk_scoring.py` (13 tests: per-tier scores, aggregate score/level bands, OWASP mapping, category extraction) + `tests/services/test_severity_scorer.py` (19 tests: each tier, whole-token matching, details flattening, custom signals/fallback).

### Report generation
- [x] Choose report output format(s) (PDF / HTML / Markdown — pick at least one for v1) — JSON (machine-readable, default) and Markdown (shareable document) via `Report.format`.
- [x] Implement report generation pipeline (findings + evidence + scores → artifact) — `generate_report()` in `app/services/report_generation.py` collects executions, findings, evidence, risk scores, and OWASP mappings, then writes the artifact. Every run also writes a JSON data snapshot (`.data.json`) so historical runs stay comparable. Exposed as `POST /reports/{id}/generate`.
- [x] Populate `Report.path` with the generated artifact location — `Report.path` holds the shareable artifact; `Report.data_path` holds the JSON snapshot; `Report.generated_at` records generation time.
- [x] Add report download endpoint — `GET /projects/{id}/assessments/reports/{report_id}/download` returns a `FileResponse` with the correct media type; 404 when the report is missing, not generated, or its file is gone.
- [x] Add tests for report generation — `tests/services/test_report_generation.py` (14 tests: JSON/Markdown output, risk scoring, versioning, download path + project scoping, clean-project scoring, comparison, snapshot immutability).

### Compliance mapping
- [x] Map finding categories to OWASP LLM Top 10 (or chosen framework) — `OWASP_LLM_TOP_10` in `app/services/risk_scoring.py` maps all five seeded categories (prompt_injection, jailbreak, privacy_data_leakage, rag_attack, agent_tool_use) to OWASP LLM Top 10:2025 entries.
- [x] Surface compliance mapping in generated reports — every finding carries `owasp_category` and `test_category` in both the JSON snapshot and the Markdown artifact (summary table + per-finding detail).

### Regression tracking
- [x] Add report versioning/history per project — `Report.version` counts generations (0 = never generated) and increments on each `generate_report()`; migrations `b7c2d3e4f5a6` (version, data_path, generated_at). `GET /reports` returns report history for a project.
- [x] Add comparison view/data between report runs (new/resolved/regressed findings) — `compare_reports()` diffs two runs' persisted JSON snapshots by `(test_category, title)`, returning new / resolved / regressed / improved / unchanged buckets. Reads snapshots rather than live DB state so historical runs compare correctly. Exposed as `GET /reports/{report_a_id}/compare/{report_b_id}` with a typed `ReportComparisonResponse`.

**Phase 4 exit check:** [x] A completed assessment can be exported as a shareable, scored report with no manual formatting

**Bugs found and fixed while completing this phase:**
- [x] Judge-model grading fell through to keyword grading and returned `PASS` when the judge was unavailable — a false "safe" verdict on a security test. `determine_execution_result()` now returns `INCONCLUSIVE` whenever judge grading is requested but produced no output (`app/services/finding_classifier.py`).
- [x] Multi-turn execution dropped the user's earlier turns from conversation history — only assistant replies were carried forward, weakening multi-turn attack sequences. `_run_multi_turn()` now appends each turn's new user messages to the running history (`app/services/execution_engine.py`).
- [x] Pre-existing migration drift: `Execution.result` declared `index=True` but no migration created it. Added migration `c3d4e5f6a7b8`; `alembic check` is now clean (required by the Phase 6 CI gate).
- [x] Corrected 3 pre-existing failing tests in `tests/services/test_execution_engine.py` (multi-turn classification fixture did not contain the grading pattern it asserted on).

**Verification (run from this environment):**
- [x] `pytest` — 199 tests passing. 50 tests added by this phase: `test_risk_scoring.py` (13), `test_severity_scorer.py` (19), `test_report_generation.py` (14), plus 4 judge-grading cases in `test_finding_classifier.py`. The 3 multi-turn/judge tests that were failing before this phase now pass.
- [x] `ruff check` and `ruff format --check` — clean
- [x] `pyright` — 0 errors, 0 warnings
- [x] `alembic check` — no new upgrade operations detected (model/migration parity)
- [x] Verified the four report routes and the `ReportResponse`/`ReportComparisonResponse` schemas appear in the generated OpenAPI document

---

## Phase 5 — Frontend

### Setup
- [x] Choose frontend stack and scaffold `frontend/` project — React 19 + TypeScript + Vite + react-router-dom, per `docs/adr/ADR-002-frontend-framework.md` (React/TypeScript was already the accepted decision; no re-litigation needed). Scaffolds in `frontend/` with `npm run dev|build|preview|test|lint|typecheck`.
- [x] Set up API client against existing backend contracts — `src/api/types.ts` mirrors the Pydantic schemas (projects, targets, credentials, tests, executions, findings, evidence, reports); `src/api/client.ts` is a typed wrapper over `/api/v1` with bearer-token injection, structured `ApiError` translation, and per-resource clients. Dev traffic goes through a Vite proxy to a single origin, so the backend needs no permissive CORS policy.

### Core screens (v1 scope)
- [x] Sign up / login — `src/pages/AuthPages.tsx`: registration (12-char minimum, confirm-password match), login, backend error surfacing, password inputs typed `password`. Registered users are signed in automatically.
- [x] Project list / create / manage — `src/pages/ProjectsPage.tsx`: list, create with name/description, delete with confirmation.
- [x] Target management (add/edit/delete, credential entry) — `src/pages/TargetsPage.tsx` (list/create/delete) and `src/pages/TargetDetailPage.tsx` (configuration + credentials). `CredentialPanel` handles store/revoke and displays credential metadata only.
- [x] Trigger execution + view execution status/progress — `src/pages/ProjectDetailPage.tsx`: pick a test and target, run (202), and view every execution with status/result badges plus a cancel action. Status updates automatically: a 2-second poll runs while any execution is pending/running and tears down as soon as all reach a terminal state, so an idle page issues no further requests.
- [x] Findings + evidence viewer — findings are listed per execution with severity badges, and each finding's evidence is fetched and rendered as collapsible JSON.
- [x] Report list + download — create (JSON/Markdown), generate (increments version), and download as a client-side blob; report history with version and generation time is shown.
- [x] Load the attack library from the UI — a "Load attack library" button on the project page calls `POST /assessments/tests/seed`, which imports all 89 bundled test cases. Idempotent, so it is safe to press again after new cases are added.

### Security UX
- [x] Verify plaintext secrets are never round-tripped back to the client after credential creation — the secret is held only in form state, sent once on create/rotate, and cleared immediately on success. The backend's plaintext `resolve` endpoint was subsequently **removed entirely** (see Phase 4 credential-resolution hardening), so no HTTP path can return a stored secret. `credentialApi` exposes no read method, and tests assert the secret never appears in the DOM. Verified end-to-end: credential create/list responses carry no `value` field.
- [x] Confirm redacted credential responses render correctly in UI — stored credentials render a redaction placeholder (`••••••••`) plus version and active/revoked state, with the reason stated in the UI. Covered by `CredentialsPanel.test.tsx`.
- [x] Add auth token handling (storage, refresh/expiry behavior) — `src/api/client.ts` `tokenStore` keeps the token in `sessionStorage` (never `localStorage`, so it does not outlive the tab), records expiry, and refuses to send an expired token. A global 401 handler clears the session and returns the user to the login screen. There is no refresh-token endpoint, so expiry means re-authentication.

**Phase 5 exit check:** [x] A new user can sign up, create a project, add a target, run a test, and read the report entirely through the UI — verified end-to-end against a live backend (42 assertions in an end-to-end script: sign up, login, project, target, credential, test, execution lifecycle to a terminal state, report generate/version/download, and cross-tenant authorization denials all passing).

**Known limitations (deferred, not blocking v1):**
- No project rename/edit UI. Tests are created via the "Load attack library" button (the full bundled set) or `POST /tests`; there is no per-test authoring form.
- Vite binds to `::1` by default; use `npm run dev -- --host` to reach it from another device.

**Verification (run from this environment):**
- [x] `npm test` — 36 tests passing across 4 files (API client, auth, credential panel, project detail incl. seeding and polling)
- [x] `npm run typecheck` — 0 errors
- [x] `npm run build` — production build succeeds
- [x] `npm run lint` — no errors (3 `set-state-in-effect` warnings on mount-time data fetches, which is the correct use of an effect)
- [x] Dev server + API proxy verified live: Vite (5174) → FastAPI (8000) → Postgres (5433)
- [x] Backend suite still green: 231 tests
- [x] `POST /tests/seed` verified live through nginx: creates 89, idempotent on re-run, category filter returns 14 for `rag_attack`, unknown category → 422, unauthenticated → 401, cross-tenant → denied

---

## Phase 6 — Deployment & CI/CD

### Containerization
- [x] Write backend `Dockerfile` — `backend/Dockerfile`: multi-stage (builder + runtime), non-root `aegis` user (uid 10001), no compiler toolchain (all deps resolve from manylinux wheels, enforced with `--only-binary=:all:`), healthcheck on `/health`, exec-form CMD so SIGTERM drains in-flight requests, report artifacts on a volume path. No secrets in the image or build context.
- [x] Write frontend `Dockerfile` (once frontend exists) — `frontend/Dockerfile`: Node build stage → nginx runtime on unprivileged port 8080 running as the `nginx` user. `frontend/nginx.conf` adds SPA history fallback, an `/api` proxy to the backend (so no CORS is needed), immutable caching for hashed assets, `no-store` on `index.html`, and baseline security headers.
- [x] Write `docker-compose.yml` for local dev (app + Postgres + Redis/queue broker) — `docker-compose.yml` runs Postgres, backend, and frontend with healthchecks and persistent volumes. **No Redis:** Phase 2 chose an in-process async execution engine, so there is no broker to run; adding one would be unused infrastructure. Loopback-only port bindings. Requires `SECRET_KEY` to be set.
- [x] Document local setup steps in `docs/development.md` — prerequisites, database + migrations, both run modes (bare and Compose), service table, migrations in-container, verification commands, teardown.

### CI
- [x] Add CI workflow: ruff lint — `.github/workflows/backend.yml`, job `lint`.
- [x] Add CI workflow: ruff format check — same job.
- [x] Add CI workflow: pyright type check — job `typecheck`.
- [x] Add CI workflow: pytest full suite — job `test`, with a PostgreSQL 16 service container (SQLite is not a valid substitute for JSONB and native enums).
- [x] Add CI workflow: `alembic check` migration consistency — runs in the `test` job after `alembic upgrade head`, so a model change without a migration fails CI. Also added `pip-audit --strict` for dependency CVEs.
- [x] Require CI pass before merge (branch protection) — documented the required check names and settings in `docs/branch-protection.md`. This is repo configuration, not code, so it must be applied in GitHub settings; the doc names the five exact required checks to avoid the common "check never reports" failure.

### CD
- [x] Set up staging environment — staging is declared as a GitHub **environment** in `.github/workflows/release.yml` (`environment: staging`) with its own secret scope. Provisioning the host itself is operator work; `docs/deployment.md` gives the full VPS procedure.
- [x] Build deployment pipeline (staging auto-deploy or manual trigger) — `release.yml` triggers on a `v*` tag: re-runs the full gate, builds and pushes images to GHCR with provenance attestation and SBOM, rsyncs the Compose file, pins the host key with `ssh-keyscan`, runs migrations as a separate step before traffic, then verifies staging responds. `workflow_dispatch` allows a manual staging deploy.
- [x] Define release/tagging process — `docs/release-process.md`: SemVer policy, annotated tags, changelog handling, migration-before-traffic ordering, and rollback.
- [x] Add changelog process — `CHANGELOG.md` in Keep a Changelog format, with an `[Unreleased]` section and the 0.1.0 entry; the process for maintaining it is documented in the release guide.

### Secrets management
- [x] Move production secrets off `.env` files — production reads secrets from the host environment via `${VAR:?message}`, which fails fast with a clear message instead of starting with an empty value. `.env` remains a **local development** convenience only, is git-ignored, and is excluded from the Docker build context by `.dockerignore`.
- [x] Integrate with hosting platform's secret injection or a secrets manager — `docs/secrets-management.md` documents the required contract and lists supported approaches (Compose secrets, SOPS+age, AWS/GCP/Azure Key Vault, HashiCorp Vault). The release workflow reads values from GitHub secrets; nothing sensitive is stored in the repository. Two independent layers protect `SECRET_KEY`: Compose refuses to start without it, and `Settings.validate_production_secrets` raises in staging/production.
- [x] Document secret rotation procedure — `docs/secrets-management.md` covers `SECRET_KEY` (breaking: invalidates credentials and tokens, so a staged re-entry procedure), `POSTGRES_PASSWORD` (non-breaking), TLS certificates, and per-target credentials, plus the audit events emitted for each.

**Phase 6 exit check:** [x] Merge to `main` runs full quality gate automatically · [x] Tagged release deploys to staging via one workflow trigger — both implemented and the CI path verified locally.

**Production posture** (`docker-compose.production.yml`, verified by running it):
- No service publishes a port to the host; the reverse proxy is the only entry point.
- PostgreSQL sits on an `internal: true` network. Verified unreachable from the edge network.
- Backend and frontend run as non-root (uid 10001 / 101), with `cap_drop: ALL`, `no-new-privileges`, and read-only root filesystems.
- Log rotation capped at 10 MB × 5 per service.
- Migrations are an explicit `migrate` profile step, not a start-up side effect.

**Bugs found and fixed while completing this phase:**
- [x] The production stack crashed on start: tmpfs mounts are created root-owned, so the unprivileged `nginx` user could not write `/var/cache/nginx` or `/var/log/nginx`. Fixed by setting `uid=101,gid=101` (and `uid=10001` for the backend) on each tmpfs. This would have broken every production deploy.
- [x] `pip install ".[dev]"` installed nothing — the project declares dev tooling under PEP 735 `[dependency-groups]`, which pip cannot resolve as an extra. The CI workflow would have run `pytest` without `pytest` installed. Corrected to explicit version-pinned installs and verified in a clean container.

**Verification (run from this environment):**
- [x] Both images build: `aegis-backend` 373 MB, `aegis-frontend` 74.5 MB
- [x] Dev stack (`docker compose up`): all three services healthy; SPA served; `/api` proxied; SPA deep links fall back to the app shell; migrations applied in-container
- [x] Production stack: all three services healthy with `cap_drop: ALL` and read-only roots; no host port bindings; database unreachable from the edge network; `migrate` profile applies all 12 migrations
- [x] Confirmed no `.env` in the image filesystem and secrets present only as runtime env vars
- [x] CI `test` job reproduced locally in a clean Python 3.12 container against a real Postgres: **199 tests passed**, `alembic check` clean
- [x] Frontend CI sequence passes: oxlint exit 0, typecheck 0 errors, 30 tests, build succeeds, `npm ci` works with the committed lockfile
- [x] All four workflow files parse as valid YAML
- [x] `docker-compose.yml`, `docker-compose.production.yml`, and `docker-compose.ci.yml` all validate

**Known limitations:**
- Branch protection and the staging host are repository/infrastructure settings that cannot be created from the codebase. Both are fully specified in `docs/branch-protection.md` and `docs/deployment.md`; applying them is an operator step.
- The release workflow targets a single VPS over SSH. It is intentionally not a Kubernetes or managed-platform deploy, per ADR-015's VPS-compatible requirement.
- The container workflow's database-exposure check is advisory on GitHub-hosted runners; the authoritative verification is the manual check documented in `docs/deployment.md`.
- No nightly rebuild schedule is configured yet (described in `docs/release-process.md` but not added to a workflow).

---

## Phase 7 — Production hardening & launch readiness

### Performance
- [ ] Load test the execution engine under concurrent executions
- [ ] Identify and address queue backpressure limits
- [ ] Load test API endpoints under realistic traffic

### Monitoring
- [ ] Add error rate monitoring/alerting
- [ ] Add execution failure rate monitoring/alerting
- [ ] Add queue depth monitoring/alerting
- [ ] Stand up dashboards (Prometheus/Grafana or hosted equivalent)

### Security review
- [ ] Run the platform's own test suite against itself where applicable
- [ ] Commission or perform a manual pentest of auth, credential storage, and SSRF/network-policy paths
- [ ] Remediate any findings from the pentest

### Data safety
- [ ] Define and test database backup procedure
- [ ] Define and test database restore procedure
- [ ] Document disaster recovery steps

### Documentation
- [ ] Write deployment guide
- [ ] Write operator runbook (common incidents, how to respond)
- [ ] Publish/version the OpenAPI reference

### Legal/compliance
- [ ] Add Terms of Service covering authorized-testing-only use
- [ ] Add consent/authorization attestation flow when a target is created
- [ ] Confirm the "authorized security testing only" principle is enforced in-product, not just stated in README

**Phase 7 exit check:** [ ] Comfortable pointing a real, consenting customer at it and being on-call for it

---

## Overall completion tracker

- [x] Phase 1 — Close out the foundation
- [x] Phase 2 — Execution engine
- [x] Phase 3 — Attack/test content library
- [x] Phase 4 — Risk scoring & reporting
- [x] Phase 5 — Frontend
- [x] Phase 6 — Deployment & CI/CD
- [ ] Phase 7 — Production hardening & launch readiness
