# AegisAI

AegisAI is an open-source AI security testing and evaluation platform for helping authorized security testers and AI developers assess the security, safety, privacy, and robustness of AI systems.

> **Authorized testing only.** AegisAI sends adversarial prompts to AI systems you configure. Only test systems you own or have explicit written authorization to assess. Creating a target in AegisAI is an attestation of that authorization.

## Project Goals

* AI safety testing
* Prompt injection testing
* Jailbreak resistance testing
* Privacy and data leakage testing
* RAG security testing
* AI agent and tool security testing
* Security regression testing
* Risk scoring
* Security findings and evidence
* Compliance mapping
* Automated security reports

## What It Does

- **Tests targets directly.** Point AegisAI at an OpenAI-compatible, Ollama, or custom REST endpoint and run an adversarial test suite against it.
- **Ships an attack library.** 89 test cases across prompt injection, jailbreak, privacy leakage, RAG, and agent/tool-use categories, with multi-turn conversation support.
- **Produces evidence.** Every finding carries the exact request and response that triggered it.
- **Scores and reports.** Automatic severity assessment, OWASP LLM Top 10:2025 compliance mapping, and JSON or Markdown reports.
- **Tracks regressions.** Compare report runs to see what is new, resolved, regressed, or improved.

## Architecture

| Component | Stack |
|---|---|
| Backend API | Python 3.11+, FastAPI, SQLAlchemy, Alembic, PostgreSQL |
| Frontend | React 19, TypeScript, Vite |
| Deployment | Docker, Docker Compose, nginx |
| CI | GitHub Actions |

The backend is the sole security boundary. The frontend is treated as an untrusted client and enforces no authorization of its own.

## Quick Start

### With Docker Compose (recommended)

```bash
export SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
docker compose up --build -d
docker compose ps
```

Then open <http://127.0.0.1:8080>. Apply migrations first:

```bash
docker compose exec backend alembic upgrade head
```

### Load the attack library

The 89 attack test cases ship as YAML files but must be imported before a
project can run anything. Find your project UUID in the URL when you open the
project in the UI, then:

```bash
docker compose exec backend python -m app.cli.seed_tests \
  --project <project-uuid> --email you@example.com
```

Add `--dry-run` to preview, `--category prompt_injection` to seed one category,
or `--prune` to remove them. Seeding is idempotent, so re-running is safe.

### Without Docker
Requires Python 3.11+ and PostgreSQL 16.

```bash
pip install .
cp .env.example .env      # fill in DATABASE_URL and SECRET_KEY
alembic upgrade head
uvicorn app.main:app --reload --app-dir backend --port 8000
```

In a second terminal, run the UI:

```bash
cd frontend
npm install
npm run dev               # http://localhost:5173
```

Full setup details are in [`docs/development.md`](docs/development.md) and [`docs/deployment.md`](docs/deployment.md).

## Documentation

| Document | Contents |
|---|---|
| **[`docs/OVERVIEW.md`](docs/OVERVIEW.md)** | **What this project is, its history, architecture, and honest limitations — read this first** |
| [`docs/Manual.md`](docs/Manual.md) | Complete user manual |
| [`docs/Beginner-Guide.md`](docs/Beginner-Guide.md) | Condensed quick start |
| [`docs/development.md`](docs/development.md) | Local setup, quality gates, running tests |
| [`docs/deployment.md`](docs/deployment.md) | VPS deployment, TLS, operations, troubleshooting |
| [`docs/secrets-management.md`](docs/secrets-management.md) | Secret handling and rotation procedures |
| [`docs/release-process.md`](docs/release-process.md) | Versioning, tagging, release, rollback |
| [`docs/risk-scoring.md`](docs/risk-scoring.md) | Severity rubric, scoring, compliance mapping |
| [`docs/test-cases.md`](docs/test-cases.md) | Test-case schema |
| [`docs/test-case-rationale.md`](docs/test-case-rationale.md) | Rationale and expected safe behavior per test case |
| [`docs/architecture.md`](docs/architecture.md) | System architecture |
| [`docs/threat-model.md`](docs/threat-model.md) | Threat model |
| [`docs/security-boundaries.md`](docs/security-boundaries.md) | Trust boundaries |
| [`docs/adr/`](docs/adr/) | Architecture decision records |
| [`CHANGELOG.md`](CHANGELOG.md) | Release history |

## Quality Gates

```bash
ruff check . && ruff format --check . && pyright && pytest   # backend
cd frontend && npm run lint && npm run typecheck && npm test # frontend
alembic check                                              # migration parity
```

All of these run in CI on every push and pull request.

## Contributing

1. Branch from `main`.
2. Keep `CHANGELOG.md` updated under `[Unreleased]`.
3. Ensure all quality gates and the container smoke test pass.
4. Open a pull request. `main` requires CI to pass and one approval.

## License

Apache License 2.0. See [LICENSE](./LICENSE) for the full text.
