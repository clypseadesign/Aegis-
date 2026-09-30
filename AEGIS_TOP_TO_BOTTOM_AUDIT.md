# AegisAI — Top-to-Bottom Project Audit

**Audit type:** Read-only repository and architecture review
**Scope:** Backend, frontend, database models/migrations, security controls, execution engine, adapters, test library, reports, deployment, CI/CD, documentation, product positioning, and commercialization strategy
**Repository reviewed:** `C:\proeject aegis`
**Important constraint:** No files in the project were edited or modified.

---

## 1. Executive verdict

AegisAI is a credible early-stage foundation for an AI security testing product. It is not merely a UI prototype: it has a real FastAPI backend, PostgreSQL/Alembic data model, model adapters, encrypted target credentials, an adversarial test library, multi-turn execution, evidence capture, risk scoring, reporting, a React UI, Docker deployment, and CI workflows.

The strongest product idea is:

> **A repeatable, evidence-backed security regression system for LLM applications and agents.**

That positioning is more valuable than presenting AegisAI as a generic “jailbreak tester.” The regression, evidence, authorization record, and integration potential are the foundations of a product teams can use repeatedly.

However, the repository is not yet safe to position as an enterprise security platform without a focused hardening pass. The most important issues are not cosmetic:

1. **Execution creation does not verify that the selected target belongs to the selected project.** This creates a cross-project target and credential binding risk.
2. **Report generation, report download, and report comparison routes do not authorize the authenticated user against the project.** They validate project/report ID relationships but not user access.
3. **Several assessment mutation endpoints check read access rather than mutation permission.** Project members or viewers may be able to create or modify tests, executions, findings, or evidence depending on their access path.
4. **The claimed DNS-rebinding protection is incomplete.** The hostname is resolved and checked, but the HTTP client later connects to the hostname again without pinning the validated address.
5. **Evidence and reports retain raw model prompts/responses without an explicit redaction, retention, classification, or export-control layer.** These records can contain secrets, PII, or customer data.
6. **Judge-model grading exists in code but is not wired into the default engine.** The primary grading approach remains lexical keyword/regex matching, which the project documentation correctly acknowledges can produce false positives.
7. **The execution engine is process-local and non-durable.** Restarts lose running work, concurrency/backpressure are not controlled, and the configured target rate limit is not enforced.
8. **The audit evidence from this environment is partial.** Ruff and Pyright passed; the backend suite timed out after 13 of 264 tests had completed, and the frontend test command failed with a Vite/Node runtime compatibility error in this environment.

### Overall assessment

| Area | Assessment |
|---|---|
| Product concept | Strong wedge; clear pain and defensible workflow potential |
| Core architecture | Well-structured for an early product |
| Security intent | Strong documentation and several good controls |
| Security implementation | Good foundation, but important authorization and SSRF gaps remain |
| Detection accuracy | Useful tripwire; not yet trustworthy as a standalone verdict |
| Operational maturity | Suitable for controlled single-host use, not enterprise scale |
| UX completeness | Functional v1 workflow, but shallow for professional teams |
| Commercial readiness | Pre-product-market-fit; needs a narrow ICP and repeatable workflow |
| Million-dollar potential | Plausible only if converted from a prompt library into a continuous assurance system with integrations, trust, and measurable accuracy |

---

## 2. What the project is and how it works

AegisAI is an authorized-testing platform for assessing AI systems that a user owns or has permission to test. It sends adversarial prompts to a configured model endpoint, classifies the response, stores evidence, assigns severity, maps the result to an OWASP LLM category, and generates reports.

The repository describes five attack categories:

- `prompt_injection`
- `jailbreak`
- `privacy_data_leakage`
- `rag_attack`
- `agent_tool_use`

The bundled library contains 89 YAML test cases according to `README.md`, `docs/OVERVIEW.md`, and the seed service.

### End-to-end user flow

1. **Register** with email and password.
2. **Authenticate** using a stateless JWT access token.
3. **Create a project** representing one AI system or assessment boundary.
4. **Create a target** with provider, base endpoint, model, capabilities, timeout, and authorization attestation.
5. **Store a target credential** encrypted with Fernet-derived key material.
6. **Seed the attack library** into the project.
7. **Create and run an execution** linking a test and target.
8. **Execution engine** sends single-turn or multi-turn requests through a provider adapter.
9. **Classifier** evaluates model output using configured keyword/regex rules, or an optional judge path.
10. **Findings and evidence** are persisted in PostgreSQL.
11. **Risk scoring** uses the highest finding severity.
12. **Report generation** writes JSON or Markdown artifacts and a historical JSON snapshot.
13. **Report comparison** compares historical snapshots for new, resolved, regressed, improved, and unchanged findings.

### Main request/data flow

```text
Browser
  -> nginx / SPA
  -> FastAPI /api/v1
  -> authentication + project/target authorization
  -> PostgreSQL records
  -> ExecutionEngine
  -> provider adapter
  -> external model endpoint
  -> normalized ModelResponse
  -> classifier / optional judge
  -> Finding + Evidence
  -> risk scoring + report snapshot
  -> browser download/viewer
```

### Important implementation locations

| Responsibility | Main files |
|---|---|
| FastAPI application | `backend/app/main.py` |
| API aggregation | `backend/app/api/router.py` |
| Authentication | `backend/app/api/routes/auth.py`, `backend/app/services/auth.py`, `backend/app/security/tokens.py` |
| Authorization | `backend/app/services/projects.py`, `backend/app/services/targets.py`, `backend/app/services/memberships.py` |
| Target credentials | `backend/app/services/credentials.py`, `backend/app/security/secrets.py` |
| SSRF/network policy | `backend/app/security/network.py` |
| Model adapter interface | `backend/app/adapters/base.py` |
| Provider registry | `backend/app/adapters/registry.py` |
| Execution engine | `backend/app/services/execution_engine.py` |
| Finding classification | `backend/app/services/finding_classifier.py` |
| Risk scoring | `backend/app/services/risk_scoring.py`, `backend/app/services/severity_scorer.py` |
| Evidence | `backend/app/services/evidence.py` |
| Reports | `backend/app/services/report_generation.py` |
| Seed library | `backend/app/services/seed_tests.py`, `backend/app/test_cases/` |
| Frontend shell | `frontend/src/App.tsx` |
| Frontend API client | `frontend/src/api/client.ts` |
| Main product workspace | `frontend/src/pages/ProjectDetailPage.tsx` |
| Target and credential UI | `frontend/src/pages/TargetsPage.tsx`, `frontend/src/pages/TargetDetailPage.tsx` |
| Containers | `docker-compose.yml`, `docker-compose.production.yml`, `backend/Dockerfile`, `frontend/Dockerfile` |
| CI/CD | `.github/workflows/` |

---

## 3. Architecture audit

### 3.1 Backend structure

The backend is sensibly divided into API routes, services, models, schemas, adapters, security, database, and CLI code. This is a healthy separation for a product that will need to grow.

The main architectural choice is an **in-process asynchronous execution engine**. `ExecutionEngine.schedule()` uses `asyncio.create_task()` and keeps task references in an in-memory dictionary (`backend/app/services/execution_engine.py:42-99`). Each task opens a fresh database session and runs the execution lifecycle.

This is acceptable for a controlled single-process development or small private deployment. It is not a durable job system.

### 3.2 Frontend structure

The frontend is a React/TypeScript/Vite SPA with:

- login and registration;
- protected routes;
- project list and creation/deletion;
- target creation and deletion;
- target credential storage/revocation;
- attack-library seeding;
- execution creation, polling, and cancellation;
- findings/evidence display;
- JSON/Markdown report creation, generation, and download.

The UI is intentionally thin and uses the backend as the security authority. That is the correct security model.

### 3.3 Database model

The core entities are:

```text
User
  -> Project
      -> Target
          -> TargetCredential versions
      -> SecurityTest
          -> Execution
              -> ExecutionStep
              -> Finding
                  -> Evidence
      -> Report + report snapshot artifact
  -> ProjectMembership
  -> AuditLog
```

The use of PostgreSQL JSONB and native enums is appropriate for storing variable test configurations and structured evidence while preserving lifecycle values.

### 3.4 Adapter layer

`BaseTargetAdapter` normalizes provider calls into `ModelRequest` and `ModelResponse`. The static registry supports:

- OpenAI-compatible endpoints;
- Ollama;
- configurable custom REST.

This is a good extensibility boundary. The engine does not need provider-specific parsing logic.

A major future advantage is that the adapter boundary can become an ecosystem boundary: SDKs, connectors, self-hosted runners, and target-specific instrumentation can be added without rewriting the grading/reporting core.

---

## 4. Confirmed high-priority findings

Severity meanings:

- **P0:** Fix before exposing to untrusted or paying users.
- **P1:** Serious security, integrity, or reliability issue; fix before enterprise positioning.
- **P2:** Important product or engineering issue; fix for professional usability and scale.
- **P3:** Improvement or polish.

### P0-1 — Cross-project target binding in execution creation

**Evidence:** `backend/app/services/assessments.py:117-145`

`create_execution()` validates that `test_id` belongs to `project_id`, but it does not validate that `target_id` belongs to the same project. The resulting execution is stored with project A and target B.

The engine later loads the target from `execution.target_id` and creates a credential resolver for that target (`backend/app/services/execution_engine.py:141-166`, `513-539`). This means a caller who can create an execution in one project and knows or obtains another target ID may cause the engine to use the other target and its active credential.

**Impact:**

- cross-project target invocation;
- possible use of another project’s encrypted credential;
- unauthorized model-provider spend or testing;
- evidence attached to the wrong project boundary;
- incorrect reports and audit interpretation.

**Why this matters:** This is a direct violation of the project isolation model.

**Required fix:** Resolve both test and target inside the same project authorization transaction. Reject when `target.project_id != project_id`. Also validate provider compatibility and target status before creating the execution.

### P0-2 — Missing authorization on report generation, download, and comparison

**Evidence:**

- `backend/app/api/routes/assessments.py:331-349`
- `backend/app/api/routes/assessments.py:365-376`
- `backend/app/api/routes/assessments.py:379-394`
- `backend/app/services/report_generation.py:265-307`

The report routes check whether the report belongs to the path-supplied project, but they do not call `ensure_project_access()` or another user-aware authorization service. `current_user` is accepted by the route but not used to authorize the report operation.

The download service verifies only `report.project_id == project_id`. The comparison service likewise verifies report/project relationships but has no user parameter.

**Impact:** Any authenticated user who obtains valid project/report UUIDs may be able to:

- generate another project’s report;
- download another project’s report containing findings and raw evidence;
- compare another project’s historical assessment snapshots.

UUIDs are not an authorization mechanism.

**Required fix:** Pass `current_user` through report generation, download, and comparison services and call project authorization before any file access or data loading. Use the same access policy consistently for all project-owned resources.

### P0-3 — Assessment mutation endpoints use read authorization

**Evidence:**

- `backend/app/services/assessments.py:39-65` — test creation calls `_require_project()`, which only checks read access;
- `backend/app/services/assessments.py:117-145` — execution creation also checks only read access;
- `backend/app/services/assessments.py:168-199` — execution updates do not require mutation access;
- `backend/app/services/assessments.py:211-245` — finding/evidence changes use execution read access;
- `backend/app/api/routes/assessments.py:189-200`, `265-318`.

The project authorization service distinguishes read from mutation, but several assessment operations do not use that distinction. A project member or viewer who can read the project may be able to create tests, create executions, alter execution state/result, create findings, update findings, or add evidence.

This is especially important because `ExecutionUpdate` allows direct status/result changes. A user can potentially alter the semantic result of a security assessment outside the execution engine.

**Impact:**

- false “pass” or “succeeded” states;
- evidence and finding tampering;
- unauthorized provider calls and cost consumption;
- loss of report integrity;
- broken role expectations.

**Required fix:** Define a resource authorization matrix and apply it at the service boundary. Read-only roles must never mutate tests, executions, findings, evidence, or reports. Execution lifecycle fields should be engine-owned, not generally writable through a public PATCH endpoint.

### P1-1 — DNS-rebinding protection is incomplete

**Evidence:**

- `backend/app/security/network.py:46-57`, `59-100`
- `backend/app/adapters/base.py:95-127`

The policy resolves the hostname and rejects restricted addresses. The adapter then makes an HTTP request using the original hostname:

```python
f"{target.endpoint.rstrip('/')}{path}"
```

The HTTP client can resolve the hostname again. If DNS changes between validation and the request, the second resolution may point to a private or metadata address.

The module documentation says DNS rebinding is addressed, but the implementation does not pin the validated address or use a controlled resolver/egress proxy.

**Required fix options:**

1. Resolve and pin an approved address for the request, while preserving the correct Host/SNI behavior.
2. Route all outbound target traffic through a hardened egress proxy that enforces destination policy at connection time.
3. Use an allowlist of explicit hostnames plus network-level egress controls, not just application-level resolution checks.
4. Add tests for rebinding/race behavior and IPv4/IPv6 edge cases.

### P1-2 — Raw evidence and reports have no redaction or retention policy

**Evidence:** `backend/app/services/evidence.py:14-75` and `backend/app/services/report_generation.py:50-140`.

Every finding stores request and response evidence. Reports then embed evidence content. There is no visible secret detector, PII redactor, tenant-configurable retention, deletion schedule, export classification, or evidence access policy.

A model response may contain:

- API keys or passwords;
- personal data;
- proprietary source code;
- system prompts;
- customer documents;
- regulated information.

A prompt itself may intentionally include sensitive test fixtures.

**Impact:** AegisAI can become a sensitive-data repository. The report IDOR issue makes this materially more dangerous.

**Required fix:**

- classify evidence by sensitivity;
- add configurable redaction before persistence and before report export;
- retain raw evidence only when explicitly enabled;
- support tenant/project retention policies;
- encrypt report volumes and backups;
- add audit events for evidence/report access;
- provide secure deletion and export controls;
- clearly label reports as containing potentially sensitive model data.

### P1-3 — Token sessions are described as revocable but are not revocable

**Evidence:**

- `backend/app/security/tokens.py:19-65`
- `backend/app/security/dependencies.py:17-41`
- `frontend/src/api/client.ts:67-117`

Tokens are stateless JWTs. The backend validates signature, expiry, subject, and user activity, but there is no token ID blacklist, session table, revocation timestamp, or logout endpoint. The frontend logout only clears `sessionStorage`.

`docs/OVERVIEW.md:241-245` describes the session as “revocable,” which is not true for a stolen token before expiry.

**Impact:** A stolen token remains valid until expiry, even after a user logs out or requests deactivation, unless the user record itself is disabled.

**Required fix:** Either:

- implement a server-side session/token model with revocation; or
- add a user `session_invalidated_at`/token-version field and include it in JWT validation; or
- explicitly document that logout is client-side only and reduce the risk with short-lived access tokens plus refresh-token rotation.

### P1-4 — Judge grading is not wired into the production engine

**Evidence:**

- `backend/app/services/execution_engine.py:52-62` — judge factory is optional;
- `backend/app/services/execution_engine.py:342-390` — judge path exists;
- `backend/app/services/execution_engine.py:437-445` — default engine is constructed as `ExecutionEngine()` with no judge factory;
- `backend/app/services/finding_classifier.py:310-343` — unavailable judge becomes `INCONCLUSIVE`.

The code path is thoughtfully designed to avoid falsely returning PASS when a requested judge is unavailable. However, the default engine never configures a judge factory, so judge-based tests are effectively inconclusive unless external initialization replaces the engine.

The project’s own documentation also states that grading is mainly keyword/regex and can generate false positives.

**Product impact:** A security tool that produces false findings loses trust quickly. Findings must be investigation prompts until semantic grading and repeatability are improved.

**Required fix:** Create a pluggable grader interface with deterministic, rule-based, judge-model, and hybrid strategies. Persist:

- grader version;
- judge target/model;
- grading prompt version;
- confidence;
- raw judge output;
- human disposition;
- reproducibility metadata.

### P1-5 — In-process execution is not durable and has no backpressure

**Evidence:** `backend/app/services/execution_engine.py:42-111`.

Running tasks exist only in process memory. A process restart loses the task reference and leaves database executions potentially stuck in `PENDING` or `RUNNING`. Multiple workers do not share task state. There is no durable queue, lease, retry coordinator, dead-letter state, concurrency limit, or queue-depth metric.

The target’s `rate_limit_per_minute` is persisted, but a repository search shows no execution throttling implementation using it.

**Impact:**

- unpredictable behavior under load;
- duplicate or abandoned work during deployment;
- provider throttling and unexpected cost;
- denial of service through unbounded execution scheduling;
- no reliable SLA for customers.

**Required fix:** Introduce a durable job model and worker system. Redis, a PostgreSQL-backed queue, Celery/RQ, or Temporal are possible choices. The required properties are more important than the brand:

- durable job ownership/lease;
- recovery after worker death;
- concurrency limits per tenant/project/target;
- per-target request rate enforcement;
- idempotency key for execution starts;
- cancellation and timeout state persisted in the job lifecycle;
- queue depth and failure metrics.

### P1-6 — Provider adapter clients are not closed after normal executions

**Evidence:**

- `backend/app/adapters/base.py:31-44` defines an owned async client and `close()`;
- `backend/app/services/execution_engine.py:165-176`, `213-260`, `262-340` create/use adapters;
- normal execution paths do not close the target adapter.

The judge adapter is closed in `_maybe_judge()`, but the main adapter is not closed after `_run_single_turn()` or `_run_multi_turn()`.

**Impact:** Repeated executions can accumulate open connections and file descriptors, especially when the default adapter creates a new client per execution.

**Required fix:** Use `try/finally` around the adapter lifecycle, or create a shared connection pool owned by the worker process and close it on shutdown.

---

## 5. Important functional and integrity findings

### P2-1 — Target status, capabilities, provider compatibility, and target rate limit are mostly metadata

The models and schemas expose:

- target `status`;
- target `capabilities`;
- target `rate_limit_per_minute`;
- test `required_capabilities`;
- test `provider`.

But the execution path does not visibly enforce all of these constraints. A test can be run against a target without a clear capability compatibility check. Inactive targets are not visibly rejected by the execution service. The rate-limit field is not used to control traffic.

This creates an important difference between the product’s apparent model and its actual behavior.

**Recommendation:** Add a target/test compatibility service that validates provider, required capabilities, status, quotas, and policy before execution creation.

### P2-2 — Target updates can bypass provider/base-URL pairing validation

`TargetCreate` performs provider-aware base-URL validation. `TargetUpdate` validates the endpoint only against a provider if the provider is included in the same patch (`backend/app/schemas/target.py:151-173`). If a user updates only the endpoint, the existing provider is not available to the schema validator.

This can reintroduce a full request path or provider/path mismatch after creation.

**Recommendation:** Validate the merged target state inside the service after loading the existing target, not only the incoming partial payload.

### P2-3 — Report comparison collapses distinct findings by category and title

**Evidence:** `backend/app/services/report_generation.py:326-328`.

Comparison indexes findings by:

```text
(test_category, title)
```

If multiple distinct tests share a title/category, one finding overwrites another in the comparison index. Multi-turn executions can also produce multiple findings that collapse to one comparison entry.

**Recommendation:** Use a stable test-case identifier plus target identifier and a finding signature. Preserve multiplicity and distinguish repeated evidence from independent test failures.

### P2-4 — API-created findings cannot use automatic severity as intended

`FindingCreate.severity` is non-optional and defaults to `MEDIUM` (`backend/app/schemas/assessment.py:90-98`). `create_finding()` only calls automatic scoring when `finding.severity is None` (`backend/app/services/assessments.py:184-199`). Through the API, that branch cannot normally be reached.

**Recommendation:** Make severity optional in the create schema when automatic scoring is desired, or remove the misleading fallback and require an explicit policy.

### P2-5 — Credential versioning is not transaction-safe under concurrent writes

`_latest_version()` reads the highest version and adds one (`backend/app/services/credentials.py:73-83`, `100-115`). There is a uniqueness constraint on `(target_id, credential_type, version)`, but no database-side serialization or active-credential uniqueness constraint.

Concurrent creation/rotation can produce a conflict or an unexpected active-state result.

**Recommendation:** Use a database transaction with row locking, a sequence strategy, or a retry loop; enforce one active credential per target/type at the database level where PostgreSQL supports it.

### P2-6 — Blocking database work runs inside async execution tasks

The execution engine is async, but it uses synchronous SQLAlchemy sessions and many synchronous commits inside the async task. Under concurrency, database work can block the event loop and delay other executions.

**Recommendation:** Move execution workers to a synchronous worker process, use SQLAlchemy async sessions, or isolate blocking database work with a controlled thread pool.

### P2-7 — Audit logging is incomplete for assessment integrity operations

There are audit events for several account, target, credential, project, and execution lifecycle actions. However, the reviewed assessment services do not consistently audit:

- test updates;
- execution state/result updates;
- finding creation/update;
- evidence creation;
- report download/access;
- report comparison;
- report generation authorization outcomes.

For a security assessment product, these events are part of the chain of custody.

**Recommendation:** Add immutable audit records with actor, project, resource, action, timestamp, request ID, source IP where appropriate, and before/after metadata without storing secrets.

### P2-8 — Project membership is not a coherent end-to-end authorization model

`ensure_project_access()` recognizes project membership for project access. But `ensure_target_access()` only recognizes global admin or project owner (`backend/app/services/targets.py:32-65`). Therefore, a legitimate project member may be able to read project assessments but be denied access to the project’s targets and credentials.

At the same time, assessment mutation paths use read access, creating the opposite inconsistency: project members may mutate assessment records while being unable to manage the target they assess.

**Recommendation:** Define explicit project roles such as owner, admin, analyst, and viewer, then apply the same policy to projects, targets, credentials, tests, executions, findings, evidence, and reports.

### P2-9 — Global admin scope is too broad for a SaaS product

The current project service treats global `ADMIN`/`SUPER_ADMIN` roles as able to read and mutate all projects. That may be acceptable for an internal single-organization deployment, but it is not a safe default for a multi-tenant SaaS model.

**Recommendation:** Introduce organization/workspace boundaries. Make support operators separate from customer administrators, use explicit support access grants, and log every privileged cross-tenant access.

---

## 6. Frontend audit

### Strengths

- Uses protected routes and a centralized typed API client.
- Stores tokens in `sessionStorage` rather than `localStorage`.
- Does not expose a credential resolve method in the UI.
- Clears plaintext credential form state after successful storage.
- Polls executions only while active work exists.
- Surfaces backend execution error details instead of showing only “failed.”
- Uses accessible labels, tables, captions, and collapsible evidence sections.

### Confirmed frontend issue: wrong default target selection

**Evidence:** `frontend/src/pages/ProjectDetailPage.tsx:63-78`.

The page correctly filters targets for display at line 73, but initializes the selected target using the unfiltered global `targetList` at line 77:

```text
setSelectedTargetId((current) => current || targetList[0]?.id || '')
```

If the first global target belongs to another project, the page can hold a target ID that is not in the current project. Because the backend also fails to validate target/project binding, this UI bug can amplify the P0 cross-project execution issue.

**Required fix:** Choose the default from the filtered targets for the current project and make the backend reject any mismatched target regardless of UI state.

### UX/product limitations

- No report comparison UI even though the API exists.
- No test-case authoring/editing workflow.
- No project rename/edit workflow in the visible UI.
- No bulk run, bulk export, or campaign workflow.
- No dashboard showing risk trend, coverage, pass rate, false-positive review, or remediation status.
- No explicit target health/test connection check before launching a suite.
- No run configuration for repetitions, sampling, temperature variants, or model version capture.
- No human review/disposition workflow for findings.
- No visible team membership administration workflow.
- Report download is client-side blob creation rather than a governed export flow.
- The UI does not clearly communicate that a `FAIL` is an investigation signal rather than a confirmed vulnerability.

### Environment validation result

The delegated read-only validation reported:

- Ruff: passed with 0 errors/warnings.
- Pyright: passed with 0 errors/warnings.
- Backend tests: full run timed out after 13 tests had passed, with 251 remaining at timeout.
- Frontend typecheck: passed.
- Frontend lint: three warnings related to mount-time state updates in `ProjectsPage.tsx`, `TargetsPage.tsx`, and `ProjectDetailPage.tsx`.
- Frontend tests: failed in the current environment with a Vite/Node/Rolldown runtime compatibility error.

This does not prove that all tests fail in every environment. It does prove that the repository’s claimed green quality state was not reproducible end-to-end in this audit environment.

---

## 7. Security control review

### Strong controls already present

1. **Argon2id password hashing** in `backend/app/security/passwords.py`.
2. **JWT signature and expiry validation** in `backend/app/security/tokens.py`.
3. **Explicit production secret requirement** in `backend/app/core/config.py:29-38`.
4. **Fernet-encrypted target credentials** in `backend/app/security/secrets.py`.
5. **No credential values in normal credential response schemas.**
6. **Base URL validation and credential-in-URL rejection** in `backend/app/schemas/target.py`.
7. **SSRF checks for loopback, private, link-local, multicast, unspecified, and metadata addresses** in `backend/app/security/network.py`.
8. **Redirects disabled** in `backend/app/adapters/base.py`.
9. **Response-size limits** on provider responses.
10. **Non-root containers and dropped Linux capabilities** in production Compose.
11. **Read-only container filesystems and internal database network** in production Compose.
12. **Structured request logging with request IDs** while avoiding request/response bodies.
13. **Explicit authorized-testing attestation** in target creation schema and persistence.
14. **Project-scoped resource relationships in most database models.**
15. **Migration parity checks and dependency scanning in CI configuration.**

These are meaningful positives and should be preserved while fixing the authorization gaps.

### Security design/documentation mismatches

- Documentation says DNS rebinding is addressed, but hostname re-resolution remains possible.
- Documentation says sessions are revocable, but the token system has no server-side revocation.
- Documentation describes project-scoped RBAC, but target access and assessment mutation do not consistently follow the same project role model.
- Documentation says security reports are protected, but report routes do not consistently authorize access.
- Documentation says the system should preserve chain of custody, but assessment mutations lack complete audit coverage.
- Documentation says report artifacts are shareable, but the report payload may contain raw sensitive evidence without a redaction policy.

The documentation quality is unusually good for an early project, but it now needs to become an implementation contract rather than a statement of intended controls.

---

## 8. Accuracy and evaluation audit

### Current grading model

The classifier matches configured patterns against model output. It has useful refusal suppression logic, disclosure markers, regex support, minimum match thresholds, severity, and finding details.

This is appropriate as a first detector but insufficient as the sole evaluator for security claims.

### Main accuracy risks

1. **Lexical matches are not semantic proof.** A model can mention “system prompt” while refusing to disclose it.
2. **Models may echo the attack payload.** Echoing can look like successful compliance even when no protected information was revealed.
3. **Patterns can be too broad.** Generic terms such as “password,” “system,” or “instructions” can generate noise.
4. **Single-run results are weak evidence.** Model behavior varies with temperature, provider behavior, model version, and context.
5. **No confidence calibration is visible.** Findings have severity but not detector confidence.
6. **No human triage loop is integrated.** Users cannot easily mark false positive, confirmed, accepted risk, or needs reproduction.
7. **No deterministic test-target corpus is included.** Mock adapter tests test control flow, not grader validity against real model behavior.

### Recommended evaluation architecture

Use a hybrid grading pipeline:

```text
Deterministic checks
  + structured-output validation
  + secret/PII detectors
  + exact canary matching
  + refusal/disclosure rules
  + judge-model semantic review
  + optional human approval
  -> confidence + verdict + rationale + reproducibility record
```

For high-value customers, the product should report three different concepts separately:

- **Observed behavior:** what the model returned.
- **Automated verdict:** what the grader inferred.
- **Security disposition:** what a human or policy workflow accepted as a real issue.

This separation will make the product more defensible than competitors that present every detector hit as a vulnerability.

---

## 9. Target audience and why

### Primary beachhead: AI product security teams

**Who:** Security engineers and AI application engineers at companies shipping chatbots, RAG systems, copilots, and agents.

**Why they fit:**

- They already understand threat modeling and evidence.
- They need repeatable regression tests after prompt/model/retrieval changes.
- They can connect targets and credentials.
- They have budget justification tied to release risk and incident prevention.
- They are more likely to understand false positives and use a triage workflow.

**Best initial job-to-be-done:**

> “Before every production release, prove that the AI application still resists our critical attack scenarios, and show exactly what changed since the last release.”

### Secondary audience: AI governance and risk teams

**Why:** The OWASP mapping, authorization attestation, reports, evidence, and audit trail are relevant to governance. However, this audience will require stronger report provenance, retention, approval workflows, policy mapping, and enterprise identity.

### Secondary audience: consultancies and authorized red teams

**Why:** They can use AegisAI as an accelerator across client assessments. This is a promising channel because consultants value reusable test packs, branded reports, evidence exports, and multi-client separation.

### Developer and researcher audience

**Why:** Local model support, Docker, open source, and inspectable YAML cases make the project accessible to researchers and students.

**Commercial caveat:** This audience helps distribution and community growth but usually should not be the primary revenue engine.

### Who should not be the first target

Do not initially market to “everyone doing AI safety.” That market includes model researchers, governance leaders, DevSecOps teams, red-team consultancies, and infrastructure security teams with materially different requirements.

Choose one wedge first: **security regression for production LLM applications and agents**.

---

## 10. What would make AegisAI worth more than one million dollars

No feature can guarantee a valuation or sale price. A million-dollar outcome requires recurring customer value, credible security outcomes, a scalable delivery model, and a defensible advantage.

The most effective strategy is not to add dozens of unrelated attack prompts. It is to turn AegisAI into a **continuous AI assurance control**.

### Strategic positioning

Use this product promise:

> **AegisAI continuously proves whether your AI application remains safe across model, prompt, retrieval, tool, and policy changes.**

That is stronger than:

- “jailbreak scanner;”
- “prompt injection demo;”
- “OWASP checklist;”
- “collection of YAML attacks.”

### Product pillars

#### Pillar 1 — Release-gate regression testing

Integrate with GitHub Actions, GitLab CI, Jenkins, and deployment pipelines.

A team should be able to define:

- required test suites;
- acceptable failure thresholds;
- severity gates;
- changed target/model version;
- approval requirements;
- automatic report artifact.

This converts AegisAI from a tool people try once into a control they run on every release.

#### Pillar 2 — Application-aware testing

Generic prompts are easy to copy. Application context is harder to reproduce and creates more value.

Add first-class concepts for:

- system prompt versions;
- RAG index/version;
- retrieval filters;
- document canaries;
- tool definitions and permissions;
- agent memory;
- authentication context;
- user roles/personas;
- model/provider/version;
- temperature and generation settings;
- dataset fixtures.

The strongest tests should know what data must never be returned and what tools must never be invoked.

#### Pillar 3 — Trustworthy grading

Build a grader registry and make accuracy a core differentiator.

Support:

- exact canary detection;
- structured policy checks;
- regex and rule checks;
- PII and secret detection;
- semantic judge models;
- cross-model judge consensus;
- human review;
- confidence calibration;
- false-positive feedback;
- per-customer policy thresholds.

Publish reproducible evaluation methodology and detector benchmarks. Trust is the moat.

#### Pillar 4 — Evidence and chain of custody

Make every result defensible:

- immutable execution record;
- test-case version;
- grader version;
- target/model metadata;
- prompt and response hashes;
- redaction status;
- actor and approval history;
- signed report artifact;
- comparison lineage;
- retention policy.

This is what turns a developer tool into a security and governance product.

#### Pillar 5 — Integrations

Prioritize integrations that put AegisAI inside existing workflows:

- GitHub/GitLab pull requests;
- Jira/Linear issue creation;
- Slack/Teams alerts;
- SIEM export;
- OpenTelemetry;
- cloud secret managers;
- model gateways;
- observability platforms;
- ticket status synchronization.

Do not build every integration at once. Start with CI, issue tracking, and notifications.

#### Pillar 6 — Enterprise trust

Before enterprise selling, add:

- OIDC/SAML SSO;
- SCIM provisioning;
- MFA or identity-provider-enforced MFA;
- organization/workspace tenancy;
- granular roles;
- audit export;
- customer-managed keys or a clear encryption model;
- data residency options;
- self-hosted/air-gapped runner;
- backup/restore and disaster recovery;
- security disclosure process;
- signed releases and SBOM verification;
- independent penetration test.

#### Pillar 7 — Services-enabled distribution

A practical route to early revenue is to support expert services without becoming a services-only company.

Offer:

- assessment templates;
- consultant workspaces;
- branded reports;
- client handoff packages;
- reusable test packs;
- multi-client isolation;
- remediation verification;
- partner/reseller program.

Consultancies can bring many end customers while validating which workflows deserve productization.

---

## 11. Recommended monetization model

Use a hybrid model that matches value:

### Community edition

- Apache-2.0 self-hosted core;
- local model support;
- base attack library;
- basic JSON/Markdown reports;
- single workspace;
- community support.

Purpose: distribution, trust, developer adoption, and attack-library contributions.

### Team cloud or professional tier

- hosted execution control plane;
- private runners;
- CI/CD integration;
- judge-model grading;
- regression dashboards;
- Jira/Slack integrations;
- finding triage;
- higher retention and collaboration limits.

### Enterprise tier

- SSO/SCIM;
- organization tenancy;
- self-hosted or air-gapped runner;
- customer-managed encryption options;
- advanced audit export;
- data residency;
- support and SLA;
- custom policy packs;
- security review support.

### Services and partner revenue

- implementation;
- test-pack authoring;
- threat-model workshops;
- model/application migration assessments;
- remediation verification.

A simple revenue path to a million in annual recurring revenue is a portfolio of enterprise and team customers with a repeatable annual contract—not a large number of free users. The key metric is not attack-count downloads; it is **weekly active production assessment workflows and renewal-driving regression value**.

---

## 12. Defensible moat ideas

### 12.1 Versioned AI security knowledge graph

Connect:

```text
attack technique
  -> test case
  -> target capability
  -> model/app version
  -> observed behavior
  -> finding
  -> remediation
  -> regression outcome
```

Over time, the dataset of real, reviewed, versioned outcomes becomes more valuable than the initial prompt library.

### 12.2 Customer-specific security baselines

Every organization has different secrets, tools, documents, and unacceptable behaviors. Let customers define canaries, forbidden data, allowed tool calls, and role-specific policies.

This creates switching cost because the baseline becomes part of the customer’s release process.

### 12.3 Evaluation reliability score

Give each detector and finding a reliability profile based on:

- repeatability across runs;
- grader agreement;
- human confirmation rate;
- model/provider variance;
- evidence completeness;
- regression stability.

AegisAI can become the product that tells teams not just “fail,” but “fail with 94% confidence under this tested configuration.”

### 12.4 Private runner and data boundary

Many organizations will not send sensitive prompts/responses to a SaaS control plane. A self-hosted runner that executes locally while sending only metadata is a strong enterprise feature and an architectural extension of the current adapter/engine boundary.

### 12.5 Remediation verification

Do not stop at detecting a finding. Let users:

1. assign an owner;
2. link a code/model/prompt change;
3. rerun the exact test;
4. compare evidence;
5. approve the fix;
6. attach the verification to the release.

That closed loop is much more valuable than a static report.

---

## 13. Prioritized execution roadmap

### Phase 0 — Security correctness gate

Before public or paid use:

1. Fix project/target binding.
2. Fix report authorization.
3. Apply mutation authorization to all assessment resources.
4. Review credential resolve exposure.
5. Fix or redesign DNS/egress enforcement.
6. Add adapter cleanup.
7. Add audit coverage.
8. Add raw-evidence redaction/retention controls.
9. Re-run the full backend and frontend quality gates in a clean, documented environment.

### Phase 1 — Make results trustworthy

1. Implement the grader interface.
2. Wire a configurable judge target.
3. Add canary/secret/PII detectors.
4. Store confidence and grader provenance.
5. Add human disposition and false-positive feedback.
6. Build a real-target evaluation corpus with known-safe and known-vulnerable fixtures.
7. Repeat tests across model versions, temperatures, and providers.

### Phase 2 — Make the product repeatable

1. Add a durable job queue.
2. Add schedules and CI triggers.
3. Add idempotency and retries at job level.
4. Enforce per-target/project concurrency and rate limits.
5. Capture model/version/config metadata.
6. Add regression dashboard and release gates.

### Phase 3 — Make it enterprise-credible

1. Organization tenancy.
2. SSO/OIDC/SAML and SCIM.
3. Granular project roles.
4. Audit export and signed reports.
5. Retention, deletion, and data residency controls.
6. Private runners and self-hosted deployment.
7. Backup/restore, monitoring, alerting, and incident runbooks.
8. Independent security assessment.

### Phase 4 — Build the commercial moat

1. CI and issue-tracker integrations.
2. Application-aware RAG/tool/agent fixtures.
3. Customer-specific policies and canaries.
4. Consultant/partner workflows.
5. Benchmark and reliability program.
6. Curated security knowledge graph.
7. Remediation verification and release certification.

---

## 14. Suggested product metrics

Track metrics that prove customer value:

### Activation

- time from signup to first target;
- time from target to first completed execution;
- percentage of projects that seed and run a full suite;
- percentage of users who generate a second report.

### Product value

- assessments run per project per month;
- percentage of releases gated by AegisAI;
- findings confirmed by humans;
- false-positive rate by detector;
- median time from finding to verified remediation;
- regression failures caught before production;
- report downloads/shared approvals.

### Commercial health

- team-to-paid conversion;
- annual renewal rate;
- expansion from one project to organization-wide use;
- runner/integration adoption;
- services-to-product conversion;
- support burden per customer.

The most valuable leading indicator is likely: **a customer’s number of consecutive releases using AegisAI as a required AI security gate**.

---

## 15. Final recommendation

Do not broaden AegisAI into a generic AI governance suite yet. The strongest path is:

1. **Fix the authorization and evidence-protection issues first.**
2. **Make grading trustworthy and explainable.**
3. **Turn executions into durable, scheduled, CI-triggered regression campaigns.**
4. **Add application-aware test context for RAG and agents.**
5. **Make findings part of a remediation and release-approval workflow.**
6. **Sell to AI security/product security teams and specialized consultancies.**
7. **Use open source for distribution, while monetizing collaboration, private runners, enterprise controls, integrations, and verified assurance workflows.**

The project’s current differentiator is not the number of attack prompts. Its real opportunity is to become the system of record for answering:

> “Did this AI application become less safe after the last change, and can we prove the answer?”

That is the product direction most likely to support recurring revenue, strong retention, enterprise adoption, and a business materially more valuable than a standalone prompt scanner.

---

## Appendix A — Repository facts used in this audit

The review used the following repository material:

- `README.md`
- `docs/OVERVIEW.md`
- `docs/Manual.md`
- `docs/architecture.md`
- `docs/security.md`
- `docs/security-boundaries.md`
- `docs/threat-model.md`
- `docs/production-readiness-plan.md`
- `docs/production-readiness-todo.md`
- backend application source under `backend/app/`
- frontend source under `frontend/src/`
- tests under `tests/`
- `pyproject.toml`, `uv.lock`, and `frontend/package.json`
- Docker Compose files and GitHub Actions workflows

The audit was read-only. No source, configuration, test, documentation, or deployment files were changed.
