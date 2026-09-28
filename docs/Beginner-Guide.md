# AegisAI Beginner Guide

A quick-start introduction to AegisAI: what it is, how to set it up, and how to use the core features.

## What is AegisAI?

AegisAI is an open-source AI security testing and evaluation platform. It lets authorized security testers and AI developers assess the security, safety, privacy, and robustness of AI systems.

Key capabilities:

- AI safety and prompt injection testing
- Jailbreak resistance testing
- Privacy and data leakage testing
- RAG and AI agent tool security testing
- Security regression testing, risk scoring, and reporting

> AegisAI is intentionally used to test authorization, access controls, and security boundaries of AI systems **with explicit permission only**. Never test systems you do not own or are not authorized to test.

## Prerequisites

- Python 3.11 or 3.12
- PostgreSQL (for the database)
- (Recommended) a virtual environment tool such as `venv` or `uv`

## Project Layout

```
.
├── backend/                  # Backend application code
│   └── app/
│       ├── api/routes/       # HTTP route handlers (auth, projects, assessments, ...)
│       ├── models/           # SQLAlchemy ORM models
│       ├── schemas/          # Pydantic request/response schemas
│       ├── services/         # Business logic / application services
│       ├── security/         # Authn/authz, network policy, secrets
│       └── core/config.py    # Settings (env-driven configuration)
├── alembic/                  # Database migrations
├── tests/                    # Test suite (pytest)
├── .env.example              # Example environment variables
├── pyproject.toml            # Dependencies and tool configuration
└── docs/                     # Architecture and ADR documentation
```

## Setup

### 1. Create and activate a virtual environment

```bash
python -m venv .venv
# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1
# Linux/macOS
source .venv/bin/activate
```

### 2. Install dependencies

AegisAI installs dependencies from `pyproject.toml`. Using `uv` (fast) or pip:

```bash
# with uv (recommended)
uv sync

# alternatively with pip
pip install -e ".[dev]"
```

The dev group includes testing and quality tools: `pytest`, `ruff`, `pyright`, and `pre-commit`.

### 3. Configure environment variables

Copy the example and fill in real values:

```bash
cp .env.example .env
```

Edit `.env` and set at minimum a non-empty `SECRET_KEY` and a valid `DATABASE_URL` for PostgreSQL:

```dotenv
APP_ENV=development
DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/aegis
SECRET_KEY=change-me-to-a-long-random-secret
```

- In `staging` and `production`, a non-empty `SECRET_KEY` is required.
- `DATABASE_URL` must point to a PostgreSQL database the application can access and create tables in.

## Database Setup

AegisAI uses Alembic for database migrations. After configuring `DATABASE_URL`:

```bash
# Apply all migrations to your database
alembic upgrade head

# Verify the database is at the latest migration
alembic current     # should match the latest head
alembic check       # run automatically as part of the test suite
```

Migrations live in `alembic/versions/`. Each adds a small, reviewable change to the schema.

## Running the Application

Start the development server:

```bash
uvicorn app.main:app --reload --port 8000
```

Then visit:

- API root: `http://localhost:8000/`
- Health check (process liveness): `http://localhost:8000/health`
- System readiness (database): `http://localhost:8000/api/v1/system/ready`
- API documentation (Swagger UI): `http://localhost:8000/docs`
- Alternative docs (ReDoc): `http://localhost:8000/redoc`

The API is versioned under `/api/v1`.

## Code Quality

The project enforces three quality gates:

```bash
ruff check .           # linting (E, F, I, B, UP rules)
ruff format --check .  # formatting verification
pyright                # static type checking
```

Run them together before committing changes. A `pre-commit` configuration is provided for automation.

## Testing

Run the test suite with pytest:

```bash
pytest -q
```

Tests run against a live PostgreSQL database via `DATABASE_URL`. Ensure your `.env` is configured before running tests.

To run a single test file:

```bash
pytest tests/services/test_assessments.py -q
```

## Using the API

The API is the primary interface. Below is a typical beginner workflow. Full schemas are defined in `app/schemas/`.

### 1. Register and authenticate

Register a user (creates an account and returns credentials):

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"a-very-strong-password-123"}'
```

Log in to obtain an access token:

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"a-very-strong-password-123"}'
```

Use the returned token in subsequent requests:

```bash
TOKEN="eyJ..."   # your token from login
curl http://localhost:8000/api/v1/system/ready
```

Include it for authenticated endpoints:

```bash
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/projects
```

### 2. Create a project

Projects group targets, tests, and findings. Only authenticated users can create them.

```bash
curl -X POST http://localhost:8000/api/v1/projects \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"My First Project"}'
```

### 3. Create a target

Create a target (an AI model deployment or endpoint) using a model adapter. Adapters abstract the model API (for example `openai_compatible` or `ollama`).

```bash
curl -X POST "http://localhost:8000/api/v1/projects/$PROJECT_ID/targets" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
        "name":"My Model",
        "adapter":"openai_compatible",
        "endpoint_url":"https://api.example.com/v1",
        "model_name":"gpt-4o-mini"
      }'
```

### 4. Run a security test

Create a security test definition, then start an execution:

```bash
# Define a security test
curl -X POST "http://localhost:8000/api/v1/projects/$PROJECT_ID/assessments/tests" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
        "name":"Prompt Injection Test",
        "provider":"openai_compatible",
        "required_capabilities":["chat"]
      }'

# Start an execution against a test
curl -X POST "http://localhost:8000/api/v1/projects/$PROJECT_ID/assessments/executions" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"test_id":"<test-id>"}'
```

### 5. Record findings, evidence, and reports

Record findings from a test execution:

```bash
curl -X POST "http://localhost:8000/api/v1/projects/$PROJECT_ID/assessments/findings" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
        "execution_id":"<execution-id>",
        "title":"Prompt injection succeeded",
        "severity":"high",
        "description":"The model executed a disallowed action..."
      }'
```

Attach evidence to a finding:

```bash
curl -X POST "http://localhost:8000/api/v1/projects/$PROJECT_ID/assessments/evidence" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
        "finding_id":"<finding-id>",
        "kind":"prompt_output",
        "content":{"text":"injected response"}
      }'
```

Generate a report summarizing findings for a project:

```bash
curl -X POST "http://localhost:8000/api/v1/projects/$PROJECT_ID/assessments/reports" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title":"Q3 Security Report"}'
```

### 6. Manage credentials and project members

- **Credentials** (API keys, tokens) are stored via `app/services/credentials.py` and are encrypted at rest. Never commit real credentials.
- **Members** can be added to projects with roles (`viewer`, `user`, `admin`, `super_admin`). Memberships enforce per-project access control.

### Project authorization (who can do what)

| Role            | Create | List | Read | Update | Delete |
|------------------|:------:|:----:|:----:|:------:|:------:|
| `super_admin`    | Any    | All  | All  | All    | All    |
| `admin`          | Any    | All  | All  | All    | All    |
| `user`           | Own    | Own  | Own  | Own    | Own    |
| `viewer`         | No     | Own  | Own  | No     | No     |

Every protected operation is checked server-side using project ownership and membership. Client-side checks are not sufficient.

## Common Tasks and Commands

| Task                          | Command                                                       |
|-------------------------------|----------------------------------------------------------------|
| Start the dev server          | `uvicorn app.main:app --reload --port 8000`                   |
| Apply database migrations      | `alembic upgrade head`                                        |
| Check migration status        | `alembic current`                                             |
| Verify no pending migrations  | `alembic check`                                               |
| Run tests                     | `pytest -q`                                                   |
| Lint the codebase             | `ruff check .`                                                |
| Format the codebase           | `ruff format .`                                               |
| Type-check the codebase       | `pyright`                                                     |

## Getting Help and Contributing

- Review the architecture documents in `docs/` and the ADRs in `docs/adr/` for design decisions.
- Security requirements are defined in `docs/security-baseline.md`.
- Before opening a change for review, ensure `ruff check`, `ruff format --check`, `pyright`, and `pytest -q` all pass.

## Next Steps

This beginner guide covers local setup and the core API workflow. For deeper details, see:

- `docs/architecture.md` for the high-level system design.
- `docs/development.md` for code style and quality standards.
- `docs/security-baseline.md` for the full security requirements baseline.
- `.kilo/remaining-work-plan.md` for current development priorities.
