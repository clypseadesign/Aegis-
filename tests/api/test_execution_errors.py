"""The API must expose why an execution failed.

Without `error` in the response, the UI can only report "failed", which looks
identical for a misconfigured target, an unreadable credential, and a provider
outage. Users cannot act on that.
"""

from uuid import uuid4

from app.db.session import create_session_factory
from app.main import app
from app.models.execution import Execution, ExecutionResult, ExecutionStatus
from fastapi.testclient import TestClient

client = TestClient(app)
PASSWORD = "a-very-strong-password"


def _auth(email: str) -> dict[str, str]:
    client.post("/api/v1/auth/register", json={"email": email, "password": PASSWORD})
    token = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD}).json()[
        "access_token"
    ]
    return {"Authorization": f"Bearer {token}"}


def _seed_failed_execution(project_id: str, error: str | None) -> str:
    session = create_session_factory()()
    try:
        execution = Execution(
            project_id=project_id,
            status=ExecutionStatus.FAILED,
            result=ExecutionResult.INCONCLUSIVE,
            error=error,
        )
        session.add(execution)
        session.commit()
        session.refresh(execution)
        return str(execution.id)
    finally:
        session.close()


def test_failed_execution_exposes_its_error() -> None:
    email = f"exec-error-{uuid4()}@example.com"
    auth = _auth(email)
    project_id = client.post(
        "/api/v1/projects", headers=auth, json={"name": "Error surfacing"}
    ).json()["id"]

    execution_id = _seed_failed_execution(project_id, "credential could not be decrypted")

    try:
        response = client.get(
            f"/api/v1/projects/{project_id}/assessments/executions/{execution_id}",
            headers=auth,
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == "failed"
        assert body["result"] == "inconclusive"
        assert body["error"] == "credential could not be decrypted"
    finally:
        session = create_session_factory()()
        try:
            row = session.get(Execution, execution_id)
            if row is not None:
                session.delete(row)
            session.commit()
        finally:
            session.close()


def test_successful_execution_has_null_error() -> None:
    email = f"exec-noerror-{uuid4()}@example.com"
    auth = _auth(email)
    project_id = client.post("/api/v1/projects", headers=auth, json={"name": "No error"}).json()[
        "id"
    ]

    execution_id = _seed_failed_execution(project_id, None)

    try:
        response = client.get(
            f"/api/v1/projects/{project_id}/assessments/executions/{execution_id}",
            headers=auth,
        )
        assert response.status_code == 200
        assert response.json()["error"] is None
    finally:
        session = create_session_factory()()
        try:
            row = session.get(Execution, execution_id)
            if row is not None:
                session.delete(row)
            session.commit()
        finally:
            session.close()


def test_execution_list_includes_error() -> None:
    """The table view the UI renders must carry the reason too."""

    email = f"exec-list-{uuid4()}@example.com"
    auth = _auth(email)
    project_id = client.post("/api/v1/projects", headers=auth, json={"name": "List errors"}).json()[
        "id"
    ]

    execution_id = _seed_failed_execution(project_id, "model provider returned HTTP 404")

    try:
        response = client.get(f"/api/v1/projects/{project_id}/assessments/executions", headers=auth)
        assert response.status_code == 200
        match = [row for row in response.json() if row["id"] == execution_id]
        assert match, "seeded execution missing from list"
        assert match[0]["error"] == "model provider returned HTTP 404"
    finally:
        session = create_session_factory()()
        try:
            row = session.get(Execution, execution_id)
            if row is not None:
                session.delete(row)
            session.commit()
        finally:
            session.close()
