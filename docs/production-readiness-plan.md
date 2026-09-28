# AegisAI — Phased Plan to Production Readiness

Based on a full codebase audit (see summary below), this is a sequenced plan to take AegisAI from its current early-development state to production-ready. Each phase has a goal, concrete deliverables, and an exit criterion — don't move to the next phase until the exit criterion is met, since later phases depend on the execution engine and data model being solid.

## Audit summary (context for this plan)

Rough completion by area at time of writing: **Auth/RBAC/credentials/network-security ~85%**, **data layer ~90%**, **core testing engine ~10%**, **frontend 0%**, **deployment/CI 0%**. Overall, roughly **20–25%** of the way to a production-ready platform.

Strong points already in place: JWT + Argon2id auth, project-scoped RBAC with audit logging, Fernet-encrypted target credentials (PBKDF2-derived key), a thorough SSRF/outbound network policy (blocks loopback/link-local/private CIDRs, cloud metadata hosts, DNS rebinding), normalized model adapters (`openai_compatible`, `ollama`, `custom_rest`), and a solid Alembic migration history with a decent test suite (~82+ tests passing).

Core gap: `Execution` records are created but nothing actually runs a test — no worker/orchestration calls the model adapters, `Report.path` is always empty (no report generation), and there's no attack/test-case content library or risk scoring yet. Frontend, Docker, and CI/CD are all unbuilt.

---

## Phase 1 — Close out the foundation (1–2 weeks)

**Goal:** Finish what's already 80–90% done so nothing structural needs revisiting later.

- Finalize project membership RBAC edge cases (role changes, removing the last owner, self-demotion guardrails).
- Add rate limiting / brute-force protection on `/auth/login` and `/auth/register` (e.g. slowapi or a Redis-backed limiter).
- Decide and set the license (currently "To be determined" — blocks any real open-source release).
- Resolve the `httpx2` dependency question — confirm intentional or swap to standard `httpx`.
- Add structured logging (JSON logs with request IDs) — currently only `/health` and `/ready` exist for observability.
- Pin all dependency versions properly and run a `pip-audit` / `safety` pass on the dependency tree.

**Exit criterion:** `main` branch has no known auth/RBAC gaps, structured logging is in place, and the dependency tree is clean.

---

## Phase 2 — Execution engine (the core gap) (3–5 weeks)

**Goal:** Make an `Execution` actually *do something* instead of sitting at `PENDING`.

- Design a job runner: start simple (in-process async task queue or Celery/RQ + Redis/Postgres-backed queue) rather than building custom orchestration.
- Implement the execution lifecycle: `PENDING → RUNNING → COMPLETED/FAILED`, with retries and timeout handling per the existing `ExecutionStatus` enum.
- Wire executions to the model adapters (`openai_compatible`, `ollama`, `custom_rest`) so a test run actually sends prompts to the target and captures responses.
- Add structured `Finding` generation from execution results — even a minimal rule-based classifier (e.g. "response contains X pattern → flag as finding") is enough for v1.
- Persist raw request/response pairs as `Evidence` automatically per execution step, not just via manual API calls.
- Add execution cancellation and progress reporting (poll or websocket).

**Exit criterion:** A user can create a `SecurityTest`, trigger an `Execution` against a real target, and see it transition through states and produce at least one `Finding` with linked `Evidence` — without any manual DB manipulation.

---

## Phase 3 — Attack/test content library (3–4 weeks, can overlap Phase 2's tail)

**Goal:** Give the engine something meaningful to run — this is the actual product value.

- Build a structured test-case format (YAML/JSON) for: prompt injection, jailbreak resistance, privacy/data-leakage probes, RAG-specific attacks, basic agent/tool-use security checks.
- Seed an initial library (start with ~20–30 well-known, well-documented test cases per category rather than trying to be exhaustive).
- Support multi-turn conversation attacks (the `Execution` model needs to support a sequence of turns, not just single request/response).
- Add pass/fail/inconclusive grading logic per test case (keyword match, regex, or a judge-model call for more nuanced grading).
- Document each test case's rationale and expected safe behavior (important for an "evidence-based findings" project).

**Exit criterion:** Running the seeded test suite against a known-vulnerable target produces expected findings, and against a well-guarded target produces few/no false positives.

---

## Phase 4 — Risk scoring & reporting (2–3 weeks)

**Goal:** Turn raw findings into something a security team can act on.

- Implement severity/risk scoring (e.g. CVSS-inspired or a custom rubric tied to your finding categories) — currently `Finding.severity` exists as a field but nothing computes it systematically.
- Build report generation: fill in `Report.path` with an actual generated artifact (PDF/HTML/Markdown) summarizing findings, evidence, and risk scores per project.
- Add compliance mapping (even a lightweight version — mapping findings to OWASP LLM Top 10 or similar) since it's listed as a project goal.
- Add report versioning/history so re-running tests over time shows regression or improvement (this is listed as "security regression testing" in the project goals).

**Exit criterion:** A completed assessment can be exported as a shareable report with scored findings and evidence, without manual formatting.

---

## Phase 5 — Frontend (4–6 weeks, can start once Phase 2 API is stable)

**Goal:** Make the platform usable without hitting the API directly.

- Scope v1 tightly: project/target management, triggering and monitoring executions, viewing findings/evidence, downloading reports. Skip anything fancy.
- Build against the existing API contracts (auth, projects, targets, credentials, assessments) — these are already stable and tested.
- Add basic UX for credential entry (never round-trip plaintext secrets back to the client after creation — confirm the API's redaction behavior is respected in the UI).

**Exit criterion:** A new user can sign up, create a project, add a target, run a test, and read the resulting report entirely through the UI.

---

## Phase 6 — Deployment & CI/CD (2–3 weeks, can run in parallel with Phase 5)

**Goal:** Make the project deployable and continuously verified — currently both are at 0%.

- Dockerfile(s) for backend (and frontend once it exists), plus `docker-compose.yml` for local dev (app + Postgres + Redis if the job queue needs it).
- GitHub Actions (or equivalent) CI: lint (ruff), type-check (pyright), test (pytest), migration check (`alembic check`) on every PR.
- CD pipeline for at least a staging environment; add a release process (tagged versions, changelog).
- Secrets management for production — move beyond `.env` files (e.g. environment-injected secrets via your hosting platform, or a secrets manager).

**Exit criterion:** A merge to `main` automatically runs the full quality gate, and a tagged release can be deployed to staging with one command/workflow trigger.

---

## Phase 7 — Production hardening & launch readiness (2–4 weeks)

**Goal:** The "operational maturity" pass before calling it production-ready.

- Load/perf testing on the execution engine (concurrent executions, queue backpressure).
- Add monitoring/alerting (error rates, execution failure rates, queue depth) — Prometheus/Grafana or hosted equivalent.
- Third-party or self-run security review of the platform itself (dogfood it against itself where relevant, plus a manual pentest of auth/credential/SSRF paths given how security-sensitive this product is).
- Backup/restore procedure for the database (especially since it holds encrypted credentials).
- Finalize docs: deployment guide, operator runbook, API reference (OpenAPI is free from FastAPI — just needs to be published/versioned).
- Legal/compliance pass: since this handles credentials and tests third-party AI systems, make sure the "authorized testing only" principle is enforced somewhere in the product (ToS, consent flow, or authorization attestation on target creation) — not just stated in the README.

**Exit criterion:** You'd be comfortable pointing a real (consenting) customer at it and being on-call for it.

---

## Suggested sequencing at a glance

```
Phase 1 (harden) ─┬─ Phase 2 (execution engine) ─── Phase 3 (attack library) ─── Phase 4 (scoring/reports)
                   │                                                                        │
                   └─────────────── Phase 6 (CI/CD, in parallel) ──────────────────────────┤
                                                                                              │
                                        Phase 5 (frontend, starts once Phase 2 API stable) ───┤
                                                                                              │
                                                                    Phase 7 (hardening/launch)
```

Total: roughly **4–6 months** for a small team (1–3 engineers), assuming Phase 2 and 3 are the long poles since they're currently unbuilt and are the actual differentiator.
