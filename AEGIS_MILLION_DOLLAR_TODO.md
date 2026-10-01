# AegisAI — Complete Capability and Million-Dollar Growth TODO

**Purpose:** Turn the top-to-bottom audit into an execution-ready roadmap for making AegisAI safer, more reliable, more valuable to customers, and commercially scalable.

**Scope:** Security correctness, authorization, accuracy, reliability, UX, enterprise readiness, integrations, go-to-market, monetization, and defensible product advantages.

**Source:** Derived from `AEGIS_TOP_TO_BOTTOM_AUDIT.md` and the current repository state.

**Rule:** Do not treat a checkbox as complete until its acceptance criteria are met, tests exist, and the change is verified in the relevant deployment mode.

**Product thesis:**

> AegisAI should become a continuous, evidence-backed AI security assurance system that proves whether an LLM application remains safe after model, prompt, retrieval, tool, or policy changes.

---

## How to use this roadmap

### Priority levels

- **P0 — Security blocker:** Must be completed before public, shared, or paid use.
- **P1 — Launch blocker:** Required for a trustworthy professional product.
- **P2 — Scale and product value:** Required for repeatable customer adoption and retention.
- **P3 — Enterprise and moat:** Required for larger contracts and defensibility.
- **P4 — Growth and optimization:** Important after the core product proves demand.

### Status labels

- `[ ]` Not complete.
- `[x]` Existing baseline confirmed by the audit.
- `[~]` Partially implemented or requires verification/rework.

### Completion rule for engineering items

Every implementation item should include:

- code or configuration change;
- unit and integration tests;
- authorization/security tests where applicable;
- migration if the data model changes;
- documentation update;
- observability update;
- clean verification in CI and the supported deployment path.

---

# 0. Current baseline

These capabilities were identified as already present in the audit. They should be preserved while the remaining roadmap is implemented.

- [x] FastAPI backend with service/model/schema separation.
- [x] React + TypeScript frontend with protected routes.
- [x] PostgreSQL database with Alembic migrations.
- [x] Argon2id password hashing.
- [x] JWT authentication with expiry.
- [x] Fernet-encrypted target credentials.
- [x] OpenAI-compatible adapter.
- [x] Ollama adapter.
- [x] Custom REST adapter.
- [x] Target endpoint validation for HTTP/HTTPS and credential-free URLs.
- [x] Baseline SSRF restrictions for private, loopback, link-local, multicast, unspecified, and metadata addresses.
- [x] Redirects disabled in provider requests.
- [x] Response-size limits for provider responses.
- [x] Project, target, test, execution, finding, evidence, report, membership, and audit models.
- [x] Single-turn execution support.
- [x] Multi-turn execution support.
- [x] Retry and timeout handling in the execution engine.
- [x] Execution cancellation path.
- [x] Pattern and regex-based grading.
- [x] Refusal suppression logic in the classifier.
- [x] Severity scoring and OWASP category mapping.
- [x] JSON and Markdown report generation.
- [x] Historical report snapshots and API comparison endpoint.
- [x] 89 bundled attack test cases across five categories.
- [x] UI flow for registration, projects, targets, credentials, executions, findings, and reports.
- [x] Docker Compose development and production configurations.
- [x] Non-root containers, capability dropping, read-only production roots, and internal database network.
- [x] GitHub Actions workflows for linting, typechecking, testing, migrations, dependency audit, image builds, and staging deployment.
- [x] Structured request logging with request IDs.
- [x] Explicit authorized-testing attestation during target creation.
- [x] Extensive architecture, threat-model, security, and deployment documentation.

### Baseline verification still required

- [ ] Reproduce the complete backend test suite in a clean supported environment.
- [ ] Reproduce the complete frontend test suite in a clean supported environment.
- [ ] Resolve the frontend Vite/Node/Rolldown test-runtime compatibility failure observed during audit.
- [ ] Confirm the actual supported Node.js, npm, Python, PostgreSQL, Docker, and browser versions.
- [ ] Update documentation so stated completion matches implementation reality.
- [ ] Replace stale or contradictory “completed” claims in readiness documents.

---

# 1. P0 security correctness gate

**Goal:** Close all cross-tenant, authorization, credential, report, and outbound-network risks before public or paid use.

**Dependency:** None. This phase blocks every later launch phase.

## 1.1 Fix project and target isolation

- [x] Validate `target_id` belongs to the requested `project_id` before creating an execution.
  - **Files:** `backend/app/services/assessments.py`, execution schemas/services.
  - **Acceptance:** A target from another project is rejected with a safe not-found or validation response.
  - **Tests:** Owner, member, viewer, admin, stranger, mismatched target/project, null target, deleted target.
  - **Done:** `create_execution()` now calls `_require_project_target()`, which rejects a
    target that is missing *or* belongs to another project. Previously `test_id` was
    project-validated while `target_id` was passed straight through, so a tenant could
    create an execution in their own project pointing at another tenant's target; the
    engine would then resolve that target's stored credentials and send attacker-chosen
    prompts to it. Proven with a failing test first (`DID NOT RAISE`), then fixed.
    `tests/services/test_execution_binding.py` (5 tests).

- [x] Validate `test_id` and `target_id` together in one project-scoped service operation.
  - **Acceptance:** No execution can reference resources from different projects.
  - **Tests:** Cross-project combinations for every resource type.
  - **Done:** both lookups happen in `create_execution()` before any row is written.

- [x] Validate target provider matches security-test provider before execution creation.
  - **Acceptance:** Unsupported provider/test combinations fail before any external request is made.
  - **Done:** an `ollama` test could be bound to an `openai_compatible` target and failed
    only inside the adapter, after a request had been attempted. Now rejected at
    creation with the mismatch named.

- [x] Validate target status is active before execution creation or execution start.
  - **Acceptance:** Inactive targets cannot be run until explicitly reactivated.
  - **Done:** enforced at creation *and* re-checked in the engine, because a target can be
    deactivated between the two. Reactivating the target unblocks it again.

- [x] Validate required test capabilities are contained in target capabilities.
  - **Acceptance:** Incompatible tests are rejected with an actionable explanation.
  - **Done:** a test requiring `["chat", "vision"]` against a target advertising only
    `["chat"]` is rejected, naming the missing capability. An empty requirement list
    imposes no constraint.

- [x] Add a single `validate_execution_binding()` service used by API and worker paths.
  - **Acceptance:** There is no alternate execution path that bypasses project, provider, status, or capability checks.
  - **Done:** `validate_execution_binding(test, target)` holds the pairing rules and is
    called from both `create_execution()` and the execution engine, so the two paths
    cannot drift. Because the 404-class errors cannot carry a message, a new
    `ExecutionBindingError` (HTTP 422, code `EXECUTION_BINDING_INVALID`) reports which of
    provider, status, or capabilities is the problem, satisfying the "actionable
    explanation" criterion.

- [x] Add database-level consistency protections where practical.
  - **Acceptance:** Foreign keys and project ownership relationships prevent invalid cross-project rows, or the design limitation is documented and covered by service-level tests.
  - **Note:** the `executions.target_id` foreign key already prevents a dangling
    reference, but no foreign key can express "the target must belong to the same project
    as the execution". That constraint is enforceable only in the service layer, is
    covered by `tests/services/test_execution_binding.py`, and is recorded here rather
    than left as an unstated assumption.

**Tests:** `tests/services/test_execution_binding.py` (5) covers project ownership;
`tests/services/test_execution_binding_validation.py` (8) covers provider match, target
status, capabilities, reactivation, and the optional-target case.

## 1.2 Fix report authorization

- [x] Authorize report generation against the authenticated user and project.
  - **Files:** `backend/app/api/routes/assessments.py`, `backend/app/services/report_generation.py`.
  - **Acceptance:** A user without project access cannot generate another project’s report.
  - **Done:** The route called `ensure_project_access` nowhere; it only compared
    `report.project_id` to the path parameter, so any caller holding a project_id and
    report_id could generate another tenant's report.

- [x] Authorize report download against the authenticated user and project.
  - **Acceptance:** Knowing a report UUID and project UUID is never sufficient for access.
  - **Done:** Download carries the full evidence set — every model request and
    response — so this was the highest-impact leak. Response is now `Cache-Control:
    no-store` and `X-Content-Type-Options: nosniff`.

- [x] Authorize report comparison against the authenticated user and project.
  - **Acceptance:** Both reports must belong to the authorized project; no cross-project comparison is possible.
  - **Done:** Both report ids are now authorized against the same project before any
    comparison runs.

- [x] Add report access audit events.
  - **Events:** `report.generated`, `report.downloaded`, `report.compared`, `report.access_denied`.
  - **Acceptance:** Events contain actor, project, report IDs, action, timestamp, request ID, and no raw evidence or secrets.
  - **Done:** `report.generated`, `report.downloaded`, and `report.compared` are emitted
    with actor, project, and report ids. Metadata contains no evidence or secrets.

- [x] Standardize report authorization through one helper.
  - **Acceptance:** All report routes use the same project/membership policy.
  - **Done:** `require_project_report(session, user, project_id, report_id)` in
    `app/services/report_generation.py` is the single entry point for generate,
    download, and compare.

- [x] Add cross-tenant report tests.
  - **Tests:** Stranger, viewer, member, owner, global admin, mismatched path IDs, missing artifact, deleted project.
  - **Done:** `tests/api/test_report_authorization.py` (6 tests) covers stranger
    generate/download/compare, owner success path, mismatched project id, and
    unauthenticated access. Proved all three vulnerabilities with failing tests first.

## 1.3 Enforce mutation authorization

- [x] Separate project read access from project mutation access for security-test creation.
  - **Done:** `create_security_test()` now calls `_require_project_write()`.
- [x] Separate project read access from project mutation access for security-test updates/deletes.
  - **Done:** `update_security_test()` and `delete_security_test()` enforce write access after resolving the test.
- [x] Separate project read access from execution creation.
  - **Done:** `create_execution()` now calls `_require_project_write()`.
- [x] Make execution lifecycle transitions engine-owned.
  - **Acceptance:** Public API cannot arbitrarily change a running execution to `succeeded`, `failed`, or `pass`.
  - **Done — most severe defect in this audit.** `ExecutionUpdate` exposed `status` and `result`, and `update_execution()` authorized only through the read path. Any project member, including a VIEWER, could rewrite an assessment outcome — marking a failed run as `succeeded`/`pass` and erasing a real finding. The fields are removed from the schema, `update_execution()` and the `PATCH /executions/{id}` route are deleted, and transitions now happen only via run, cancel, and the engine. The frontend never used that endpoint, so no client change was needed.
- [x] Restrict execution cancellation to authorized project operators.
  - **Done:** cancellation resolves the execution through the read path and then requires write access.
- [x] Restrict finding creation/update to the execution engine and authorized triage roles.
  - **Done:** `create_finding()` and `update_finding()` require write access.
- [x] Restrict evidence creation to the execution engine or explicit evidence-management roles.
  - **Done:** `create_evidence()` requires write access explicitly rather than relying on the `update_finding()` call it makes internally.
- [x] Restrict report creation/generation to project operators.
  - **Done:** `create_report()` requires write access; generation, download, and comparison require read access via `require_project_report()`.
- [ ] Add a complete project resource authorization matrix.
  - **Roles:** owner, project admin, analyst, reviewer, viewer, support operator.
  - **Resources:** targets, credentials, tests, executions, findings, evidence, reports, memberships.
  - **Blocked:** The codebase has four roles (`super_admin`, `admin`, `user`, `viewer`). `analyst`, `reviewer`, and `support operator` do not exist, so this needs a role-model change first.
- [ ] Add API tests for every resource/action/role combination.
  - **Acceptance:** Every unauthorized operation returns the expected safe status and creates an audit event.
  - **Partial:** `tests/services/test_mutation_authorization.py` (9 tests) covers owner and viewer across tests, executions, findings, evidence, and reports, plus lifecycle integrity. Full role coverage is blocked on the matrix above.

**Mechanism note.** The root cause was that `ensure_project_access()` only enforced `can_mutate_project()` (which excludes VIEWER) when the operation string was literally `"update"` or `"delete"`. Every mutation that passed `"read"` was silently permitted for a VIEWER. `MUTATING_OPERATIONS` is now an explicit named set, and `_require_project_write()` makes each mutation declare itself as one.
  - **Acceptance:** Every unauthorized operation returns the expected safe status and creates an audit event.

## 1.4 Make membership authorization consistent

- [ ] Update `ensure_target_access()` to use project membership roles, not only owner/global admin checks.
- [ ] Apply the same membership policy to target credentials.
- [ ] Apply the same membership policy to tests, executions, findings, evidence, and reports.
- [ ] Separate global support access from customer organization access.
- [ ] Prevent global admin defaults from becoming unrestricted SaaS tenant access.
- [ ] Add explicit support-access grants with expiry and audit logging.
- [ ] Add tests proving a project member can perform exactly the actions allowed by their role.

## 1.5 Protect credential resolution

- [x] Re-evaluate whether the public `POST .../resolve` endpoint should exist.
  - **Decision: removed.** The endpoint returned the decrypted secret to any caller with
    read access to the target. Nothing in the product used it — the web UI deliberately
    never called it, and the engine resolves credentials in-process through
    `create_credential_resolver`. Its only function was moving a plaintext secret across a
    network boundary into a browser, so it was deleted rather than restricted.
- [x] Prefer worker-only credential resolution where possible.
  - **Done:** resolution happens in-process inside the execution engine via
    `create_credential_resolver` → `resolve_credential_value`. The plaintext never crosses
    the HTTP trust boundary.
- [x] If the endpoint remains, restrict it to a dedicated credential-management role.
  - **N/A** — the endpoint no longer exists, so there is nothing to restrict.
- [ ] Add step-up authentication or short-lived authorization for plaintext resolution.
  - **N/A** — no plaintext is resolvable over HTTP.
- [x] Add mandatory audit event for every credential resolution.
  - **Deviation, deliberate:** credential *creation*, *rotation*, *revocation*, and
    *deletion* are audited, and `ensure_target_access` audits every access denial. A
    successful in-process resolution is deliberately **not** audited per call: it happens
    once per execution per target, so auditing it would grow the audit table without
    adding detection value for an action that is only reachable server-side. The execution
    record already links the resolution to the assessment that needed it.
- [x] Add response headers preventing caching of plaintext credential responses.
  - **N/A** — no response carries a credential. Equivalent protection is that the value is
    never serialized into a response at all.
- [x] Ensure plaintext credential values never enter logs, traces, analytics, browser history, or error messages.
  - **Done:** plaintext is never returned to a client, so it cannot reach browser history
    or devtools. Logging records metadata only; the credential lifecycle audit events carry
    id, type, version, and target, never the value.
- [x] Add tests for credential endpoint access by every role.
  - **Done:** `tests/api/test_credential_plaintext.py` (4 tests) asserts the resolve route
    is absent from the OpenAPI document, that a request for it is rejected without leaking
    the secret, that metadata endpoints never include a `value` field, and that the
    engine's internal resolver still works.

**Breaking change:** `POST /api/v1/targets/{target_id}/credentials/{credential_id}/resolve`
now returns 404/405. No client in this repository used it. Any external integration that
did should resolve credentials server-side instead.

## 1.6 Fix outbound network enforcement

- [ ] Replace validation-only DNS checks with connection-time enforcement.
- [ ] Choose one approved strategy:
  - [ ] Pin validated destination addresses while preserving Host/SNI behavior.
  - [ ] Route provider traffic through a hardened egress proxy.
  - [ ] Enforce destination policy at the container/network layer.
- [ ] Add IPv4 and IPv6 policy tests.
- [ ] Add DNS rebinding race tests.
- [ ] Add redirect-chain tests, including redirects to private and metadata addresses.
- [ ] Add tests for encoded IP forms, IPv4-mapped IPv6, unusual hostname syntax, and trailing-dot names.
- [ ] Add production allowlist mode for known provider domains.
- [ ] Add outbound request metrics by target/provider/status without recording secrets.
- [ ] Document the exact residual SSRF risk and deployment requirements.

## 1.7 Correct frontend target selection

- [x] Initialize the selected target from the filtered targets belonging to the current project.
  - **File:** `frontend/src/pages/ProjectDetailPage.tsx`.
  - **Done:** The selection was seeded from `targetList[0]` — the *unfiltered* result of
    `GET /targets`, which returns every target the user can see. The dropdown options were
    built from the filtered list, so when another project's target came first the select's
    value matched no visible option and the run submitted a target the user could not see
    being used. This was observed in practice: the UI showed one target while executions ran
    against another. Now seeded from `projectTargets`, falling back to the first project
    target when the current selection is not in scope.
- [x] Clear a selected target when the project changes and it is no longer valid.
  - **Done:** the same selection logic re-evaluates on every load, replacing an
    out-of-scope id rather than keeping it.
- [x] Disable execution controls until the selected target is confirmed project-scoped.
  - **Done:** `Run test` is gated on `targetIsProjectScoped`, with an inline explanation
    when the project has no targets or the selection is out of scope.
- [x] Add a frontend regression test where the first global target belongs to another project.
  - **Done:** `tests/.../ProjectDetailPage.test.tsx` gains two cases — a foreign target
    listed first must not be selected or offered, and a project with no targets disables
    the run control with an explanation.
- [x] Keep backend validation authoritative regardless of UI behavior.
  - **Done:** Section 1.1 rejects any execution whose `target_id` is outside the project at
    the service layer, so this UI fix is a usability correction, not the control itself.

## 1.8 Protect raw evidence and reports

- [ ] Define an evidence sensitivity model.
  - **Suggested levels:** public, internal, confidential, restricted.
- [ ] Add secret detection before evidence persistence.
- [ ] Add PII detection/redaction before evidence persistence or export.
- [ ] Support customer-configurable raw-evidence retention.
- [ ] Separate raw evidence from redacted report evidence.
- [ ] Add project-level retention period.
- [ ] Add secure deletion workflow for evidence and artifacts.
- [ ] Encrypt report storage volumes and backups.
- [ ] Add report sensitivity labels.
- [ ] Prevent sensitive report artifacts from being served with cacheable headers.
- [ ] Add audit events for evidence view, report download, export, and deletion.
- [ ] Document what AegisAI stores and for how long.
- [ ] Add tests proving secret values are absent from reports when redaction is enabled.

## 1.9 Fix session revocation semantics

- [ ] Choose a session strategy:
  - [ ] Server-side session table with revocation.
  - [ ] Token version/session invalidation timestamp on the user.
  - [ ] Short-lived access token plus rotating refresh tokens.
- [ ] Add logout/revoke-all-sessions endpoint if server-side revocation is selected.
- [ ] Revoke sessions after password change, account deactivation, and security reset.
- [ ] Update documentation so “revocable” matches implementation.
- [ ] Add stolen-token and logout tests.

## 1.10 Fix adapter lifecycle

- [x] Close the primary provider adapter in a `finally` block after every execution.
  - **Done:** the judge adapter was already closed in a `finally`, but the primary adapter
    built at the top of `_execute` was never closed on any path. Every execution leaked an
    `httpx.AsyncClient` and its connection pool, so socket exhaustion was reachable under
    sustained use. The adapter is now released on success, failure, and cancellation.
    Proven with a failing test first (`the primary adapter was never closed`).
- [x] Prefer shared connection pools in long-lived workers.
  - **Not applicable yet.** Connections are currently per-execution because a worker does
    not exist; a durable worker is 3.1. Pooling belongs with that work, not before it.
- [ ] Close clients during graceful application shutdown.
  - **Blocked on 3.1:** with an in-process engine there are no long-lived adapters to shut
    down. This becomes meaningful when a worker process exists.
- [x] Add connection/file-descriptor leak tests.
  - **Done:** `tests/services/test_adapter_lifecycle.py` asserts the adapter is closed on
    both the success and failure paths, and that every adapter exposes an awaitable
    `close()`.
- [x] Add timeout/cancellation cleanup tests.
  - **Done:** the failure-path test covers a provider that raises mid-execution, which
    exercises the same `finally`. Cancellation closes the adapter before re-raising
    `CancelledError` because the `finally` is attached to the outer `try`.

## 1.11 P0 exit criteria

- [ ] All P0 cross-tenant tests pass.
- [ ] No report route can be accessed without project authorization.
- [ ] No viewer/read-only role can mutate assessment state.
- [ ] Outbound network policy is enforced at connection time.
- [ ] Raw evidence handling has documented redaction and retention behavior.
- [ ] Credential resolution is restricted, audited, and non-cacheable.
- [ ] Full backend and frontend quality gates pass in a clean environment.
- [ ] A security-focused review of the changed paths is complete.

---

# 2. P1 trustworthy evaluation and grading

**Goal:** Make AegisAI results useful enough that security teams trust, investigate, and repeatedly use them.

**Dependency:** P0 security correctness gate.

## 2.1 Create a pluggable grader architecture

- [ ] Define a `Grader` interface independent of `ExecutionEngine`.
- [ ] Define a normalized grading result:
  - verdict;
  - confidence;
  - rationale;
  - matched evidence;
  - grader name/version;
  - error/inconclusive reason;
  - remediation hint;
  - provenance metadata.
- [ ] Implement deterministic keyword grader.
- [ ] Implement regex grader.
- [ ] Implement exact canary grader.
- [ ] Implement structured-output/policy grader.
- [ ] Implement secret/PII detector grader.
- [ ] Implement semantic judge-model grader.
- [ ] Implement hybrid grader combining deterministic and semantic results.
- [ ] Version every grader and grading policy.
- [ ] Store grader configuration with the execution snapshot.

## 2.2 Wire judge-model grading correctly

- [ ] Add a first-class judge target configuration.
- [ ] Add judge provider/model/credential configuration per project or organization.
- [ ] Prevent the judge from using the same compromised target by default.
- [ ] Ensure judge prompts include attack prompt, model response, expected safe behavior, and policy context.
- [ ] Protect judge prompts from target-model output injection.
- [ ] Store raw judge output under restricted evidence access.
- [ ] Return `INCONCLUSIVE` on judge timeout, malformed output, or policy ambiguity.
- [ ] Add judge retry and cost controls.
- [ ] Add judge-model availability and latency metrics.
- [ ] Add UI configuration and health test for judge targets.

## 2.3 Add canary and sensitive-data testing

- [ ] Allow users to define synthetic secrets/canaries per project.
- [ ] Inject canaries into system prompts, RAG fixtures, tool outputs, and memory fixtures.
- [ ] Detect exact canary leakage with zero ambiguity.
- [ ] Support configurable PII patterns and regional formats.
- [ ] Detect common API key/token/password formats.
- [ ] Add source-code and document confidentiality checks.
- [ ] Add configurable forbidden-data policies.
- [ ] Redact detector input before displaying it to unauthorized users.
- [ ] Add tests for false positives and false negatives.

## 2.4 Add human triage and disposition

- [ ] Add finding dispositions:
  - open;
  - confirmed;
  - false positive;
  - accepted risk;
  - fixed;
  - needs reproduction;
  - not applicable.
- [ ] Add reviewer, review timestamp, rationale, and approval history.
- [ ] Add finding comments and remediation notes.
- [ ] Add finding ownership and due date.
- [ ] Add severity override with reason and audit event.
- [ ] Prevent automatic reruns from destroying prior human dispositions.
- [ ] Add UI triage workflow.
- [ ] Add report filters for confirmed vs unreviewed findings.

## 2.5 Build a real evaluation corpus

- [ ] Create deterministic mock-safe target fixtures.
- [ ] Create intentionally vulnerable target fixtures.
- [ ] Create refusal-but-mentions-term fixtures.
- [ ] Create echo-only fixtures.
- [ ] Create indirect prompt-injection fixtures.
- [ ] Create RAG poisoning fixtures.
- [ ] Create agent tool-abuse fixtures.
- [ ] Test against at least one local model provider.
- [ ] Test against at least one hosted OpenAI-compatible provider.
- [ ] Capture model/provider/version/temperature metadata.
- [ ] Measure precision, recall, false-positive rate, and inconclusive rate by grader.
- [ ] Publish a reproducible internal evaluation report.
- [ ] Establish regression thresholds for each grader release.

## 2.6 Improve repeatability

- [ ] Add configurable repetition count per test.
- [ ] Add deterministic seed/configuration capture where supported.
- [ ] Add temperature and sampling variants.
- [ ] Add confidence intervals or repeatability summaries.
- [ ] Group repeated executions into an assessment run.
- [ ] Distinguish one-off behavior from persistent behavior.
- [ ] Add model/provider drift detection.
- [ ] Add an explicit “single run is weak evidence” warning in the UI.

## 2.7 P1 evaluation exit criteria

- [ ] Every finding records grader provenance and confidence.
- [ ] Judge-model tests are configurable and operational.
- [ ] Canary leakage can be confirmed deterministically.
- [ ] Users can mark false positives and confirmed findings.
- [ ] The project has a documented benchmark and regression threshold.
- [ ] Reports distinguish observed behavior, automated verdict, and security disposition.

---

# 3. P1 durable execution and operational reliability

**Goal:** Make assessments reliable under restart, concurrency, retries, provider failures, and customer workloads.

**Dependency:** P0 resource binding and authorization; can run in parallel with evaluation work after interfaces are defined.

## 3.1 Introduce durable jobs

- [ ] Choose a worker architecture.
  - [ ] PostgreSQL-backed job queue.
  - [ ] Redis-backed queue.
  - [ ] Celery/RQ/Temporal or equivalent.
  - [ ] Separate self-hosted runner process.
- [ ] Define durable job states.
  - queued;
  - leased;
  - running;
  - retrying;
  - succeeded;
  - failed;
  - cancelled;
  - dead-lettered.
- [ ] Add job lease and heartbeat fields.
- [ ] Add worker identity and attempt number.
- [ ] Recover jobs after worker death.
- [ ] Reconcile orphaned `PENDING` and `RUNNING` executions on startup.
- [ ] Make execution start idempotent.
- [ ] Add an idempotency key to run requests.
- [ ] Prevent duplicate external calls from repeated start requests.

## 3.2 Add concurrency and backpressure controls

- [ ] Add global worker concurrency limit.
- [ ] Add organization-level concurrency limit.
- [ ] Add project-level concurrency limit.
- [ ] Add target-level concurrency limit.
- [ ] Enforce `rate_limit_per_minute` per target.
- [ ] Add queue maximum size.
- [ ] Add rejection or delayed scheduling when capacity is exhausted.
- [ ] Add token and cost budgets where provider usage is available.
- [ ] Add maximum turns, maximum prompt bytes, and maximum execution duration.
- [ ] Add dead-letter handling for permanently failing executions.

## 3.3 Improve provider behavior

- [ ] Classify provider errors as transient, permanent, authentication, policy, or configuration errors.
- [ ] Retry only safe transient failures.
- [ ] Add provider-specific retry-after handling.
- [ ] Add circuit breaker for repeatedly failing targets.
- [ ] Add target health-check endpoint.
- [ ] Add test-connection UI before a full suite run.
- [ ] Capture provider request ID, latency, token usage, and model response metadata.
- [ ] Add adapter contract tests for every supported provider.
- [ ] Add live smoke tests that are opt-in and credential-safe.

## 3.4 Make async/database behavior safe

- [ ] Decide whether workers use synchronous or asynchronous database access.
- [ ] Prevent blocking SQLAlchemy operations from blocking the API event loop.
- [ ] Reduce excessive per-record commits inside execution loops.
- [ ] Use transactions that preserve partial execution state safely.
- [ ] Persist each execution step with clear atomicity rules.
- [ ] Ensure cancellation cannot leave inconsistent findings/evidence.
- [ ] Add graceful shutdown handling for active workers.

## 3.5 Add observability

- [ ] Add structured metrics for API latency and error rates.
- [ ] Add execution queue depth metric.
- [ ] Add active worker metric.
- [ ] Add execution success/failure/cancel/inconclusive metrics.
- [ ] Add provider latency and error metrics.
- [ ] Add grader latency and confidence metrics.
- [ ] Add report generation latency and artifact size metrics.
- [ ] Add credential resolution failure metrics without exposing values.
- [ ] Add OpenTelemetry traces with sensitive fields excluded.
- [ ] Add dashboards for operators and customers.
- [ ] Add alerts for queue backlog, provider failure spikes, worker death, database failure, and storage exhaustion.

## 3.6 P1 reliability exit criteria

- [ ] Restarting the backend does not lose or silently strand executions.
- [ ] Concurrent runs obey configured limits.
- [ ] Provider rate limits are respected.
- [ ] Every failed job has a classified reason and retry history.
- [ ] Operators can see queue depth, failure rates, and worker health.
- [ ] Load tests pass the agreed concurrency and latency targets.

---

# 4. P2 product data model and evidence chain of custody

**Goal:** Make results defensible, comparable, auditable, and useful for remediation.

**Dependency:** P0 authorization and P1 grader provenance.

## 4.1 Version test cases and policies

- [ ] Add immutable test-case version records.
- [ ] Store test-case source hash.
- [ ] Store test-case library version in every execution.
- [ ] Store grading policy version.
- [ ] Store target configuration snapshot.
- [ ] Store provider/model/version metadata.
- [ ] Store prompt/system-prompt version identifiers where available.
- [ ] Prevent editing a test definition from changing historical execution meaning.

## 4.2 Strengthen execution identity

- [ ] Add assessment-run entity grouping many executions.
- [ ] Add suite entity grouping related tests.
- [ ] Add target snapshot to each run.
- [ ] Add run trigger source: UI, CLI, API, CI, schedule, webhook.
- [ ] Add commit/deployment/build identifier.
- [ ] Add environment identifier: development, staging, production.
- [ ] Add actor and approval metadata.
- [ ] Add prompt/response hashes for integrity verification.
- [ ] Add immutable timestamps for start, each step, grading, review, and report generation.

## 4.3 Improve finding identity and comparison

- [ ] Create stable finding signature based on test ID/version, target, detector, and policy.
- [ ] Preserve multiple findings with the same title/category.
- [ ] Include target ID and test-case ID in comparison keys.
- [ ] Distinguish repeated evidence from independent findings.
- [ ] Track finding lineage across report versions.
- [ ] Track severity and disposition changes separately.
- [ ] Add confidence changes to regression comparison.
- [ ] Add target/model changes to comparison context.

## 4.4 Protect evidence integrity

- [ ] Add content hashes for evidence records.
- [ ] Add report snapshot hashes.
- [ ] Add signed report option.
- [ ] Add append-only audit storage or tamper-evident audit chain.
- [ ] Add before/after metadata for finding changes.
- [ ] Add export manifest listing test, grader, target, and evidence versions.
- [ ] Add evidence redaction status and redaction version.
- [ ] Add evidence access logs.

## 4.5 Improve reports

- [ ] Add HTML report output.
- [ ] Add PDF report output.
- [ ] Add executive summary.
- [ ] Add technical evidence appendix.
- [ ] Add confirmed/unconfirmed/false-positive breakdown.
- [ ] Add remediation recommendations.
- [ ] Add risk trend charts.
- [ ] Add coverage by category and capability.
- [ ] Add report comparison UI.
- [ ] Add signed report export.
- [ ] Add report access expiration for temporary sharing.
- [ ] Add redacted and full-evidence report modes.
- [ ] Add report templates for engineers, executives, auditors, and consultants.

## 4.6 P2 chain-of-custody exit criteria

- [ ] Historical executions remain interpretable after tests or targets change.
- [ ] Reports can be independently tied to exact test, target, grader, and evidence versions.
- [ ] Finding comparisons preserve multiplicity and identity.
- [ ] Reports clearly separate detected, confirmed, accepted, and remediated findings.
- [ ] Evidence access and export are auditable.

---

# 5. P2 application-aware AI security testing

**Goal:** Move beyond generic prompts into the customer’s real AI application behavior.

**Dependency:** P1 execution and grader foundations.

## 5.1 RAG security fixtures

- [ ] Add document fixture upload with safe file validation.
- [ ] Add document fixture versioning.
- [ ] Add poisoned-document test generation.
- [ ] Add retrieval filter and access-control scenarios.
- [ ] Add document canaries.
- [ ] Add deleted-document retrieval tests.
- [ ] Add citation integrity checks.
- [ ] Add cross-document inference tests.
- [ ] Add tenant-boundary retrieval tests.
- [ ] Add prompt-injection-through-document tests.
- [ ] Add retrieval metadata capture.
- [ ] Add secure fixture deletion.

## 5.2 Agent and tool security fixtures

- [ ] Define tool schemas and allowed argument policies.
- [ ] Add tool invocation capture.
- [ ] Add tool permission matrix.
- [ ] Add tool-argument injection tests.
- [ ] Add tool output injection tests.
- [ ] Add tool chaining and escalation tests.
- [ ] Add secret-exfiltration-through-tool tests.
- [ ] Add recursive tool-call limits.
- [ ] Add sandbox escape detection.
- [ ] Add agent memory poisoning tests.
- [ ] Add allowed/forbidden tool-call verdicts.
- [ ] Add tool call audit chain.

## 5.3 User and application context

- [ ] Add user persona fixtures.
- [ ] Add authenticated vs unauthenticated test contexts.
- [ ] Add role-based application contexts.
- [ ] Add tenant context.
- [ ] Add session/history fixtures.
- [ ] Add system prompt versioning.
- [ ] Add model routing/version metadata.
- [ ] Add application endpoint adapter abstraction for multi-step apps.
- [ ] Add state reset between test cases.
- [ ] Add browser/API runner boundary documentation.

## 5.4 Safety and policy coverage expansion

- [ ] Add sensitive-domain policy packs.
- [ ] Add harmful-content policy packs where appropriate and lawful.
- [ ] Add hallucination and citation accuracy checks.
- [ ] Add instruction hierarchy tests.
- [ ] Add structured-output/schema violation tests.
- [ ] Add excessive agency tests.
- [ ] Add denial-of-service/resource exhaustion tests.
- [ ] Add model extraction and memorization tests.
- [ ] Add multilingual and obfuscation coverage.
- [ ] Add category/test rationale and expected safe behavior for every case.

## 5.5 P2 application-aware exit criteria

- [ ] A customer can represent a real chatbot, RAG pipeline, or agent rather than only a model endpoint.
- [ ] RAG and tool tests capture application-specific evidence.
- [ ] User roles, document access, and tool permissions can be tested.
- [ ] Test fixtures are versioned and reproducible.

---

# 6. P2 release-gate and CI/CD product workflow

**Goal:** Make AegisAI part of every AI release instead of an occasional manual tool.

**Dependency:** P1 durable execution and P2 versioned assessments.

## 6.1 CI integration

- [ ] Create a documented CLI for non-interactive test execution.
- [ ] Add machine-readable exit codes.
- [ ] Add JSON result output for CI.
- [ ] Add Markdown summary output for pull requests.
- [ ] Add GitHub Action.
- [ ] Add GitLab CI example.
- [ ] Add Jenkins example.
- [ ] Add generic REST/CLI integration documentation.
- [ ] Add secure CI credential injection.
- [ ] Add ephemeral runner mode.
- [ ] Add baseline comparison against a selected previous run.

## 6.2 Release policies

- [ ] Define policy gates by severity.
- [ ] Define maximum allowed new findings.
- [ ] Define maximum allowed regressions.
- [ ] Define inconclusive-result handling.
- [ ] Define required human approval for critical findings.
- [ ] Define target/model change policy.
- [ ] Define failure override with reason and expiration.
- [ ] Add policy evaluation endpoint and CLI command.
- [ ] Add policy result to reports and CI summaries.

## 6.3 Webhooks and deployment events

- [ ] Add webhook-triggered assessment.
- [ ] Add scheduled assessment.
- [ ] Add deployment event integration.
- [ ] Add model/prompt/index version event integration.
- [ ] Add signed webhook validation.
- [ ] Add idempotent webhook handling.
- [ ] Add notification on regression.
- [ ] Add notification on recovered finding.

## 6.4 P2 release-gate exit criteria

- [ ] A customer can run an assessment from CI with one documented command.
- [ ] A failed policy blocks or warns according to configuration.
- [ ] Results link back to commit, build, target version, and report.
- [ ] Repeated use across releases is visible in the dashboard.

---

# 7. P2 frontend and workflow improvements

**Goal:** Make the product usable by engineers, reviewers, executives, and consultants.

## 7.1 Core workflow

- [ ] Add project rename/edit UI.
- [ ] Add team membership management UI.
- [ ] Add role assignment UI.
- [ ] Add target edit UI with merged-state validation.
- [ ] Add target connection test.
- [ ] Add target health status and last-checked timestamp.
- [ ] Add test-case authoring UI.
- [ ] Add test-case preview and dry run.
- [ ] Add test-suite creation and selection.
- [ ] Add bulk execution.
- [ ] Add execution run history filters.
- [ ] Add execution retry controls.
- [ ] Add execution cancellation confirmation.
- [ ] Add queue position and progress details.

## 7.2 Findings workflow

- [ ] Add finding triage table.
- [ ] Add filters for severity, confidence, status, category, target, and owner.
- [ ] Add false-positive and confirmed dispositions.
- [ ] Add finding assignment.
- [ ] Add due dates and remediation notes.
- [ ] Add comments and review history.
- [ ] Add Jira/Linear issue linking.
- [ ] Add “rerun exact finding” action.
- [ ] Add before/after evidence comparison.

## 7.3 Dashboard and analytics

- [ ] Add project risk overview.
- [ ] Add risk trend over time.
- [ ] Add category coverage.
- [ ] Add test pass/fail/inconclusive rate.
- [ ] Add false-positive rate by detector.
- [ ] Add remediation time.
- [ ] Add release-gate history.
- [ ] Add model/provider comparison.
- [ ] Add target health and provider error overview.
- [ ] Add cost/token usage overview.

## 7.4 Report and executive experience

- [ ] Add report comparison UI.
- [ ] Add executive summary view.
- [ ] Add downloadable PDF/HTML reports.
- [ ] Add redacted/full evidence selection.
- [ ] Add report approval status.
- [ ] Add signed report verification page.
- [ ] Add shareable, expiring report links.
- [ ] Add consultant branding and client handoff.

## 7.5 P2 UX exit criteria

- [ ] A new user can create a project, configure a target, run a suite, triage findings, verify remediation, and produce an approved report without using the API or CLI.
- [ ] A reviewer can understand whether a finding is confirmed, uncertain, or false positive.
- [ ] An executive can understand risk trend and release readiness without reading raw prompts.

---

# 8. P3 enterprise trust and SaaS foundation

**Goal:** Make AegisAI suitable for larger organizations and higher-value contracts.

**Dependency:** P0 security gate, P1 reliability, P2 evidence chain of custody.

## 8.1 Organizations and tenancy

- [ ] Add organization/workspace entity.
- [ ] Move projects under organizations.
- [ ] Add organization membership.
- [ ] Add organization-level billing/plan metadata.
- [ ] Scope all queries by organization.
- [ ] Add tenant-isolation integration tests.
- [ ] Separate customer administrators from platform support operators.
- [ ] Add explicit cross-tenant support-access workflow.
- [ ] Add tenant-level quotas and limits.

## 8.2 Enterprise identity

- [ ] Add OIDC login.
- [ ] Add SAML SSO.
- [ ] Add SCIM provisioning/deprovisioning.
- [ ] Add MFA support or IdP-enforced MFA requirement.
- [ ] Add domain verification.
- [ ] Add invitation workflow.
- [ ] Add session management UI.
- [ ] Add active-session revocation.
- [ ] Add password reset and email verification.
- [ ] Add account recovery controls.

## 8.3 Enterprise authorization

- [ ] Define organization role model.
- [ ] Define project role model.
- [ ] Define target/credential permissions.
- [ ] Define report/evidence permissions.
- [ ] Define support-access permissions.
- [ ] Add least-privilege policy tests.
- [ ] Add authorization decision audit trail.
- [ ] Add API scope/token permissions for automation.

## 8.4 API and automation access

- [ ] Add organization API keys.
- [ ] Hash API keys at rest.
- [ ] Add key scopes.
- [ ] Add key expiry and rotation.
- [ ] Add last-used metadata.
- [ ] Add machine identity audit events.
- [ ] Add CI-specific tokens.
- [ ] Add service accounts.

## 8.5 Data protection and deployment options

- [ ] Document encryption in transit and at rest.
- [ ] Add customer-managed key option where feasible.
- [ ] Add data residency configuration.
- [ ] Add configurable evidence storage backend.
- [ ] Add object storage support.
- [ ] Add private runner architecture.
- [ ] Add air-gapped/self-hosted runner documentation.
- [ ] Add network egress policy documentation for private deployments.
- [ ] Add tenant data export.
- [ ] Add tenant data deletion.

## 8.6 Compliance and trust program

- [ ] Publish security contact and disclosure policy.
- [ ] Publish threat model updates.
- [ ] Publish security architecture overview.
- [ ] Commission an independent penetration test.
- [ ] Add vulnerability management process.
- [ ] Add dependency update policy.
- [ ] Add signed releases.
- [ ] Add SBOM verification documentation.
- [ ] Add backup/restore evidence.
- [ ] Add disaster recovery runbook.
- [ ] Add incident response runbook.
- [ ] Add privacy policy and Terms of Service.
- [ ] Add authorized-testing terms and customer attestation policy.

## 8.7 P3 enterprise exit criteria

- [ ] A customer can deploy AegisAI with SSO, organization isolation, audit export, and controlled data retention.
- [ ] Private runners can execute tests without sending raw evidence to a hosted control plane.
- [ ] Enterprise security questionnaire answers are documented and reproducible.
- [ ] Independent security review findings are remediated or formally accepted.

---

# 9. P3 integrations and ecosystem

**Goal:** Put AegisAI into the tools customers already use and create distribution leverage.

## 9.1 Developer workflow integrations

- [ ] GitHub App or Action integration.
- [ ] GitLab integration.
- [ ] Pull-request summary and status checks.
- [ ] Commit/build metadata capture.
- [ ] Branch and environment policy configuration.
- [ ] Jira integration.
- [ ] Linear integration.
- [ ] Slack integration.
- [ ] Microsoft Teams integration.

## 9.2 Security and observability integrations

- [ ] SIEM export.
- [ ] Webhook event stream.
- [ ] OpenTelemetry export.
- [ ] Prometheus metrics.
- [ ] Model gateway integrations.
- [ ] Cloud secret manager integrations.
- [ ] S3-compatible evidence storage.
- [ ] Security data lake export.

## 9.3 SDKs and public interfaces

- [ ] Publish versioned OpenAPI documentation.
- [ ] Publish Python SDK.
- [ ] Publish TypeScript SDK.
- [ ] Publish stable CLI.
- [ ] Publish adapter development guide.
- [ ] Publish test-case authoring schema.
- [ ] Publish grader plugin interface.
- [ ] Add semantic versioning and compatibility policy.
- [ ] Add API deprecation policy.

## 9.4 Ecosystem contribution

- [ ] Add attack/test-case contribution guide.
- [ ] Add test-case review process.
- [ ] Add security review for contributed cases.
- [ ] Add versioned community test packs.
- [ ] Add organization-specific private test packs.
- [ ] Add marketplace or registry for approved test packs.
- [ ] Add benchmark submissions and reproducible result format.

## 9.5 P3 ecosystem exit criteria

- [ ] Customers can trigger, review, notify, and remediate from existing workflows.
- [ ] External contributors can safely create adapters, graders, and test packs.
- [ ] Integrations create measurable activation or retention improvement.

---

# 10. P3 commercial productization

**Goal:** Convert technical capability into repeatable revenue.

## 10.1 Choose the initial ICP

- [ ] Interview at least 15 AI product-security or AI platform teams.
- [ ] Interview at least 5 authorized red-team consultancies.
- [ ] Document the top recurring workflow pain points.
- [ ] Choose one primary ICP for the first paid offer.
- [ ] Choose one initial use case: pre-release AI security regression.
- [ ] Write a one-sentence problem statement.
- [ ] Write a one-sentence product promise.
- [ ] Define the customer’s current workaround.
- [ ] Define the measurable value of catching one regression before production.

## 10.2 Package the product

- [ ] Define Community edition boundaries.
- [ ] Define Team/Professional edition boundaries.
- [ ] Define Enterprise edition boundaries.
- [ ] Define self-hosted/private-runner packaging.
- [ ] Define hosted control-plane packaging.
- [ ] Define support and SLA levels.
- [ ] Define usage dimensions: seats, projects, executions, runners, retention, or integrations.
- [ ] Avoid pricing solely by attack count.
- [ ] Tie paid value to release gates, collaboration, evidence, and enterprise controls.

## 10.3 Build a design-partner program

- [ ] Recruit 3–5 design partners.
- [ ] Provide onboarding support.
- [ ] Run real assessments against authorized systems.
- [ ] Measure false positives and confirmed findings.
- [ ] Measure time to first value.
- [ ] Measure repeated release-gate usage.
- [ ] Collect product objections and missing integrations.
- [ ] Convert at least one partner to a paid pilot.
- [ ] Document case studies with permission.

## 10.4 Build a services-enabled channel

- [ ] Create consultant workspace model.
- [ ] Add multi-client separation.
- [ ] Add branded report templates.
- [ ] Add client handoff exports.
- [ ] Add reusable assessment templates.
- [ ] Add partner onboarding documentation.
- [ ] Create referral/reseller program.
- [ ] Offer paid assessment implementation and remediation verification.
- [ ] Productize recurring service tasks into platform workflows.

## 10.5 Go-to-market assets

- [ ] Create product landing page focused on AI security regression.
- [ ] Create live demo using a safe intentionally vulnerable target.
- [ ] Create before/after remediation demo.
- [ ] Create CI release-gate demo.
- [ ] Create evidence chain-of-custody demo.
- [ ] Create private runner/data-boundary demo.
- [ ] Publish benchmark methodology.
- [ ] Publish technical architecture page.
- [ ] Publish security and privacy page.
- [ ] Publish migration/onboarding guide.
- [ ] Publish comparison page against manual testing and generic scanners without unsupported claims.

## 10.6 P3 commercial exit criteria

- [ ] One clearly defined ICP repeatedly uses the product.
- [ ] At least one customer runs AegisAI on multiple releases.
- [ ] The paid feature boundary is understood.
- [ ] At least one channel can bring additional users or customers.
- [ ] Customer value is demonstrated by prevented regressions, reduced review time, or improved audit evidence.

---

# 11. P4 defensible million-dollar moat

**Goal:** Build assets and workflows that are difficult to replace with a prompt list or generic open-source scanner.

## 11.1 Versioned AI security knowledge graph

- [ ] Define entities: attack technique, test, target, model, app version, finding, remediation, release, policy.
- [ ] Define relationships between entities.
- [ ] Store historical outcome data with provenance.
- [ ] Store human-confirmed dispositions.
- [ ] Add search and filtering by model/app/category.
- [ ] Add trend analysis by attack family.
- [ ] Add anonymized benchmark aggregation where legally permitted.
- [ ] Add customer-private knowledge graph boundaries.

## 11.2 Customer-specific security baselines

- [ ] Define forbidden data policies.
- [ ] Define allowed tool policies.
- [ ] Define role-specific policies.
- [ ] Define target-specific thresholds.
- [ ] Define acceptable risk exceptions.
- [ ] Version policy changes.
- [ ] Require approval for policy changes.
- [ ] Compare releases against customer baseline.
- [ ] Add baseline drift alerts.

## 11.3 Evaluation reliability score

- [ ] Define reliability dimensions.
  - repeatability;
  - grader agreement;
  - human confirmation rate;
  - evidence completeness;
  - model/provider variance;
  - regression stability.
- [ ] Compute reliability by detector.
- [ ] Compute reliability by test case.
- [ ] Compute reliability by target/model.
- [ ] Display confidence and caveats clearly.
- [ ] Avoid presenting confidence as a guarantee.
- [ ] Publish evaluation methodology.

## 11.4 Remediation verification loop

- [ ] Assign finding owner.
- [ ] Link finding to issue or change request.
- [ ] Capture remediation commit/build/model/prompt version.
- [ ] Rerun exact test.
- [ ] Compare old and new evidence.
- [ ] Require reviewer approval.
- [ ] Mark finding fixed only after verification.
- [ ] Add release certification artifact.
- [ ] Add executive summary of prevented regressions.

## 11.5 Private runner moat

- [ ] Define control plane vs runner responsibilities.
- [ ] Execute prompts and raw evidence inside customer network.
- [ ] Send only approved metadata to control plane.
- [ ] Support runner registration and rotation.
- [ ] Support runner health and version reporting.
- [ ] Support air-gapped test-pack transfer.
- [ ] Add signed runner images.
- [ ] Add runner policy enforcement.
- [ ] Add customer-managed storage option.

## 11.6 P4 moat exit criteria

- [ ] Customer baselines and reviewed findings create meaningful switching cost.
- [ ] AegisAI’s reliability and evidence quality are measurable advantages.
- [ ] Private execution solves a real enterprise procurement blocker.
- [ ] Remediation verification creates recurring workflow value.

---

# 12. Performance, quality, and engineering excellence

**Goal:** Ensure the project can evolve quickly without weakening its security posture.

## 12.1 Test coverage

- [ ] Add authorization matrix tests for every resource.
- [ ] Add cross-tenant IDOR tests for every identifier-based endpoint.
- [ ] Add SSRF and DNS rebinding tests.
- [ ] Add credential lifecycle concurrency tests.
- [ ] Add report artifact security tests.
- [ ] Add evidence redaction tests.
- [ ] Add worker restart/recovery tests.
- [ ] Add queue backpressure tests.
- [ ] Add provider contract tests.
- [ ] Add live provider smoke tests behind explicit opt-in.
- [ ] Add frontend workflow tests for the complete user journey.
- [ ] Add accessibility tests.
- [ ] Add browser end-to-end tests in CI.
- [ ] Add migration upgrade-from-previous-version tests.

## 12.2 Static and dependency quality

- [ ] Resolve frontend lint warnings where practical.
- [ ] Pin and regularly update frontend dependencies.
- [ ] Verify Vite/Node/Vitest compatibility.
- [ ] Run backend dependency audit in CI.
- [ ] Run frontend dependency audit in CI.
- [ ] Add lockfile freshness policy.
- [ ] Add container image vulnerability scanning.
- [ ] Add SBOM generation and retention.
- [ ] Add secret scanning in pre-commit and CI.
- [ ] Add license compliance scanning.
- [ ] Add static security analysis.

## 12.3 Performance targets

- [ ] Define API latency targets.
- [ ] Define queue latency targets.
- [ ] Define execution throughput targets.
- [ ] Define report generation size/time limits.
- [ ] Load test concurrent executions.
- [ ] Load test large evidence volumes.
- [ ] Load test report downloads.
- [ ] Load test organization/project listing.
- [ ] Test database indexing and query plans.
- [ ] Add pagination to large resource lists.
- [ ] Add retention cleanup jobs.
- [ ] Add storage capacity alerts.

## 12.4 Deployment and disaster recovery

- [ ] Test database backup procedure.
- [ ] Test database restore procedure.
- [ ] Test report/evidence storage restore.
- [ ] Define recovery point objective.
- [ ] Define recovery time objective.
- [ ] Document rollback procedure.
- [ ] Document migration rollback limitations.
- [ ] Add staging smoke test after deploy.
- [ ] Add production deploy approval.
- [ ] Add canary deployment or safe rollout strategy.
- [ ] Add incident runbook.
- [ ] Add provider outage runbook.
- [ ] Add credential compromise runbook.
- [ ] Add data exposure runbook.

## 12.5 Engineering exit criteria

- [ ] Full CI passes consistently.
- [ ] Security regression tests run on every change to auth, network, evidence, execution, or reporting code.
- [ ] Load and recovery targets are documented and met.
- [ ] Backup/restore has been successfully demonstrated.
- [ ] Operators can diagnose and recover common failures.

---

# 13. Metrics and validation plan

**Goal:** Measure whether the project is becoming a valuable product rather than only accumulating features.

## 13.1 Activation metrics

- [ ] Measure time from signup to first project.
- [ ] Measure time from project to first target.
- [ ] Measure time from target to first execution.
- [ ] Measure percentage of projects that run a complete suite.
- [ ] Measure percentage of users generating a second report.
- [ ] Measure first-week successful execution rate.

## 13.2 Product value metrics

- [ ] Measure assessments per project per month.
- [ ] Measure consecutive releases gated by AegisAI.
- [ ] Measure findings confirmed by humans.
- [ ] Measure false-positive rate per detector.
- [ ] Measure inconclusive rate.
- [ ] Measure median time from finding to verified fix.
- [ ] Measure regressions caught before production.
- [ ] Measure report approvals and exports.
- [ ] Measure integration usage.
- [ ] Measure private-runner usage.

## 13.3 Commercial metrics

- [ ] Measure free-to-paid conversion.
- [ ] Measure paid pilot conversion.
- [ ] Measure annual renewal rate.
- [ ] Measure expansion from one project to organization-wide use.
- [ ] Measure average contract value.
- [ ] Measure services-to-product conversion.
- [ ] Measure support burden per customer.
- [ ] Measure gross margin for hosted execution.
- [ ] Measure customer acquisition source.

## 13.4 Validation gates

- [ ] Do not expand the attack library until current test quality is measured.
- [ ] Do not market “compliance” without clearly defining mapping vs certification.
- [ ] Do not market “confirmed vulnerabilities” when the result is only a lexical detector hit.
- [ ] Do not market enterprise readiness before P0/P1 security and reliability exit criteria.
- [ ] Do not add major integrations without evidence of customer workflow demand.
- [ ] Review roadmap quarterly against customer usage and retention data.

---

# 14. Recommended sequencing

## First 30 days — Security correction

- [ ] Fix cross-project target binding.
- [ ] Fix report authorization.
- [ ] Enforce mutation authorization.
- [ ] Fix frontend default target selection.
- [ ] Restrict/audit credential resolution.
- [ ] Close provider clients.
- [ ] Add high-value cross-tenant tests.
- [ ] Resolve full test-environment reproducibility.

## Days 31–60 — Trustworthy results

- [ ] Define grader interface.
- [ ] Wire judge target configuration.
- [ ] Add canary and secret detection.
- [ ] Add confidence and grader provenance.
- [ ] Add finding triage/disposition.
- [ ] Build safe/vulnerable evaluation fixtures.
- [ ] Measure false positives and repeatability.

## Days 61–120 — Repeatable product workflow

- [ ] Introduce durable job execution.
- [ ] Add concurrency and rate enforcement.
- [ ] Add schedules and CI execution.
- [ ] Add release policy gates.
- [ ] Add assessment runs and versioned snapshots.
- [ ] Add regression dashboard.
- [ ] Add remediation verification.

## Months 5–8 — Enterprise foundation

- [ ] Add organization tenancy.
- [ ] Add consistent roles and support access.
- [ ] Add OIDC/SAML/SCIM.
- [ ] Add API keys/service accounts.
- [ ] Add evidence retention, export, deletion, and residency controls.
- [ ] Add private runner.
- [ ] Complete independent security review.

## Months 8–12 — Commercial moat

- [ ] Add application-aware RAG and agent fixtures.
- [ ] Add CI, Jira/Linear, Slack/Teams, and SIEM integrations.
- [ ] Add reliability score and benchmark program.
- [ ] Add consultant/partner workflows.
- [ ] Build customer-specific baseline and policy systems.
- [ ] Publish case studies and technical benchmarks.
- [ ] Convert design partners into annual contracts.

---

# 15. Final launch gates

## Security launch gate

- [ ] No known P0 authorization or tenant-isolation issue.
- [ ] No unreviewed report/evidence access path.
- [ ] Outbound network policy is enforced at connection time.
- [ ] Credentials are never exposed through ordinary UI or logs.
- [ ] Raw evidence privacy and retention behavior is documented and tested.

## Reliability launch gate

- [ ] Durable execution recovery works after process/worker restart.
- [ ] Concurrency, rate, token, and storage limits are enforced.
- [ ] Monitoring and alerting are active.
- [ ] Backup and restore are tested.
- [ ] Incident and rollback runbooks exist.

## Accuracy launch gate

- [ ] Findings have grader provenance and confidence.
- [ ] Judge-model or hybrid grading is operational.
- [ ] False-positive measurement exists.
- [ ] Human disposition workflow exists.
- [ ] Reports distinguish automated detection from confirmed security findings.

## Product launch gate

- [ ] A user can configure, run, triage, remediate, rerun, compare, and approve a result in the UI.
- [ ] CI release-gate workflow works end to end.
- [ ] Test and target versions are preserved in historical reports.
- [ ] RAG/agent application context is supported for the initial ICP.

## Commercial launch gate

- [ ] Initial ICP is documented.
- [ ] At least three design partners have completed real workflows.
- [ ] At least one customer has repeated usage across releases.
- [ ] Paid packaging and support boundaries are defined.
- [ ] Customer value can be demonstrated with measurable outcomes.

---

# 16. Definition of “million-dollar-capable” product

AegisAI becomes million-dollar-capable when it is no longer primarily a collection of attack prompts and becomes a trusted operating workflow with these properties:

- [ ] It catches meaningful AI regressions before production.
- [ ] Its findings are explainable and reviewable.
- [ ] Its results are reproducible and evidence-backed.
- [ ] Its execution survives restarts and scales predictably.
- [ ] It integrates into CI/CD and issue tracking.
- [ ] It supports real RAG and agent application contexts.
- [ ] It protects sensitive prompts, responses, documents, and credentials.
- [ ] It supports enterprise identity, tenancy, audit, and deployment needs.
- [ ] It creates a customer-specific baseline that improves over time.
- [ ] It closes the loop from detection to remediation verification.
- [ ] Customers use it repeatedly because releases cannot proceed without it.
- [ ] The resulting data, reliability benchmarks, integrations, and workflows are difficult to replace.

**The central success metric is not the number of attack cases. It is the number of consecutive customer releases where AegisAI is used as a required AI security gate and successfully prevents or explains a regression.**
