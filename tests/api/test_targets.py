"""Target API integration tests for AegisAI."""

from uuid import UUID, uuid4

from app.db.session import create_session_factory
from app.main import app
from app.models.audit_log import AuditLog
from app.models.project import Project
from app.models.target import Target
from app.models.user import User, UserRole
from fastapi.testclient import TestClient
from sqlalchemy import select

client = TestClient(app)


def _cleanup_user(email: str) -> None:
    session = create_session_factory()()
    try:
        user = session.scalar(select(User).where(User.email == email.lower()))
        if user is not None:
            session.delete(user)
            session.commit()
    finally:
        session.close()


def _cleanup_project(project_id: UUID) -> None:
    session = create_session_factory()()
    try:
        project = session.get(Project, project_id)
        if project is not None:
            session.delete(project)
            session.commit()
    finally:
        session.close()


def _register_user(email: str, role: UserRole = UserRole.USER) -> UUID:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "a-very-strong-password-123",
        },
    )
    assert response.status_code == 201

    session = create_session_factory()()
    try:
        user = session.scalar(select(User).where(User.email == email.lower()))
        assert user is not None
        user_id = user.id
        if role != UserRole.USER:
            user.role = role
            session.commit()
            session.refresh(user)
        return user_id
    finally:
        session.close()


def _login(email: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": "a-very-strong-password-123",
        },
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_project(email: str, name: str) -> UUID:
    response = client.post(
        "/api/v1/projects",
        headers=_auth_headers(_login(email)),
        json={"name": name, "description": "API target project test"},
    )
    assert response.status_code == 201
    return UUID(response.json()["id"])


def _create_target(
    email: str,
    project_id: UUID,
    *,
    name: str | None = None,
    provider: str = "openai_compatible",
    model: str | None = "test-model",
) -> UUID:
    response = client.post(
        "/api/v1/targets",
        headers=_auth_headers(_login(email)),
        json={
            "project_id": str(project_id),
            "name": name or f"Target {uuid4()}",
            "description": "API target test",
            "provider": provider,
            "endpoint": "https://model.example.com/v1",
            "model": model,
            "capabilities": ["chat", "system_messages"],
            "timeout_seconds": 45.0,
            "rate_limit_per_minute": 120,
            "status": "active",
        },
    )
    assert response.status_code == 201
    return UUID(response.json()["id"])


def test_target_list_requires_authentication() -> None:
    response = client.get("/api/v1/targets")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


def test_target_create_returns_configuration_and_records_audit() -> None:
    email = f"api-target-create-{uuid4()}@example.com"
    project_id = None
    target_id = None
    owner_id = None

    try:
        owner_id = _register_user(email)
        project_id = _create_project(email, f"Create Target Project {uuid4()}")
        target_id = _create_target(email, project_id, name="Create Target")

        response = client.get(
            f"/api/v1/targets/{target_id}",
            headers=_auth_headers(_login(email)),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["project_id"] == str(project_id)
        assert body["name"] == "Create Target"
        assert body["provider"] == "openai_compatible"
        assert body["model"] == "test-model"
        assert body["capabilities"] == ["chat", "system_messages"]
        assert body["status"] == "active"
        assert "credential" not in body

        session = create_session_factory()()
        try:
            target = session.get(Target, target_id)
            assert target is not None
            assert target.project_id == project_id
            audit = session.scalar(
                select(AuditLog).where(
                    AuditLog.resource_id == str(target.id),
                    AuditLog.action == "target.created",
                ),
            )
            assert audit is not None
            assert owner_id is not None
            assert audit.actor_id == owner_id
            assert audit.resource_type == "target"
        finally:
            session.close()
    finally:
        if project_id is not None:
            _cleanup_project(project_id)
        _cleanup_user(email)


def test_target_crud_and_list_are_project_scoped() -> None:
    email = f"api-target-crud-{uuid4()}@example.com"
    project_id = None
    target_id = None

    try:
        _register_user(email)
        project_id = _create_project(email, f"Target CRUD Project {uuid4()}")
        target_id = _create_target(email, project_id, name="Listable Target")
        headers = _auth_headers(_login(email))

        response = client.get("/api/v1/targets", headers=headers)
        assert response.status_code == 200
        assert target_id in {UUID(item["id"]) for item in response.json()}

        response = client.get(
            f"/api/v1/targets/{target_id}",
            headers=headers,
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Listable Target"

        response = client.patch(
            f"/api/v1/targets/{target_id}",
            headers=headers,
            json={"description": "Updated target"},
        )
        assert response.status_code == 200
        assert response.json()["description"] == "Updated target"

        response = client.delete(f"/api/v1/targets/{target_id}", headers=headers)
        assert response.status_code == 204
        assert response.content == b""

        response = client.get(
            f"/api/v1/targets/{target_id}",
            headers=headers,
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "TARGET_NOT_FOUND"
    finally:
        if project_id is not None:
            _cleanup_project(project_id)
        _cleanup_user(email)


def test_target_get_update_and_delete_reject_other_users() -> None:
    owner_email = f"api-target-other-owner-{uuid4()}@example.com"
    other_email = f"api-target-other-{uuid4()}@example.com"
    project_id = None
    target_id = None

    try:
        _register_user(owner_email)
        _register_user(other_email)
        project_id = _create_project(owner_email, f"Target Other Project {uuid4()}")
        target_id = _create_target(owner_email, project_id, name="Private Target")
        headers = _auth_headers(_login(other_email))

        response = client.get(
            f"/api/v1/targets/{target_id}",
            headers=headers,
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "PERMISSION_DENIED"

        response = client.patch(
            f"/api/v1/targets/{target_id}",
            headers=headers,
            json={"name": "Stolen Target"},
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "PERMISSION_DENIED"

        response = client.delete(f"/api/v1/targets/{target_id}", headers=headers)
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "PERMISSION_DENIED"

        session = create_session_factory()()
        try:
            audit = session.scalar(
                select(AuditLog).where(
                    AuditLog.resource_id == str(target_id),
                    AuditLog.action == "target.access_denied",
                ),
            )
            assert audit is not None
        finally:
            session.close()
    finally:
        if project_id is not None:
            _cleanup_project(project_id)
        _cleanup_user(owner_email)
        _cleanup_user(other_email)


def test_viewer_can_read_own_target_but_not_mutate() -> None:
    owner_email = f"api-target-viewer-owner-{uuid4()}@example.com"
    viewer_email = f"api-target-viewer-{uuid4()}@example.com"
    project_id = None
    target_id = None

    try:
        _register_user(owner_email)
        _register_user(viewer_email, role=UserRole.VIEWER)
        project_id = _create_project(viewer_email, f"Viewer Target Project {uuid4()}")
        target_id = _create_target(viewer_email, project_id, name="Viewer Target")
        headers = _auth_headers(_login(viewer_email))

        response = client.get(
            f"/api/v1/targets/{target_id}",
            headers=headers,
        )
        assert response.status_code == 200
        assert response.json()["project_id"] == str(project_id)

        response = client.patch(
            f"/api/v1/targets/{target_id}",
            headers=headers,
            json={"name": "Viewer Update"},
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "PERMISSION_DENIED"

        response = client.delete(f"/api/v1/targets/{target_id}", headers=headers)
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "PERMISSION_DENIED"

        session = create_session_factory()()
        try:
            assert session.get(Target, target_id) is not None
        finally:
            session.close()
    finally:
        if project_id is not None:
            _cleanup_project(project_id)
        _cleanup_user(owner_email)
        _cleanup_user(viewer_email)


def test_admin_and_super_admin_can_manage_other_users_target() -> None:
    owner_email = f"api-target-admin-owner-{uuid4()}@example.com"
    admin_email = f"api-target-admin-{uuid4()}@example.com"
    super_admin_email = f"api-target-super-admin-{uuid4()}@example.com"
    project_id = None
    target_id = None

    try:
        _register_user(owner_email)
        _register_user(admin_email, role=UserRole.ADMIN)
        _register_user(super_admin_email, role=UserRole.SUPER_ADMIN)
        project_id = _create_project(owner_email, f"Admin Target Project {uuid4()}")
        target_id = _create_target(owner_email, project_id, name="Admin Target")

        response = client.patch(
            f"/api/v1/targets/{target_id}",
            headers=_auth_headers(_login(admin_email)),
            json={"description": "Admin managed"},
        )
        assert response.status_code == 200
        assert response.json()["description"] == "Admin managed"

        response = client.delete(
            f"/api/v1/targets/{target_id}",
            headers=_auth_headers(_login(super_admin_email)),
        )
        assert response.status_code == 204

        session = create_session_factory()()
        try:
            assert session.get(Target, target_id) is None
        finally:
            session.close()
    finally:
        if project_id is not None:
            _cleanup_project(project_id)
        _cleanup_user(owner_email)
        _cleanup_user(admin_email)
        _cleanup_user(super_admin_email)


def test_target_not_found_returns_target_not_found() -> None:
    email = f"api-target-not-found-{uuid4()}@example.com"
    missing_id = uuid4()

    try:
        _register_user(email)
        response = client.get(
            f"/api/v1/targets/{missing_id}",
            headers=_auth_headers(_login(email)),
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "TARGET_NOT_FOUND"
    finally:
        _cleanup_user(email)


def test_target_validation_rejects_invalid_configuration() -> None:
    email = f"api-target-validation-{uuid4()}@example.com"
    project_id = None
    target_id = None

    try:
        _register_user(email)
        project_id = _create_project(email, f"Validation Target Project {uuid4()}")
        headers = _auth_headers(_login(email))
        valid_payload = {
            "project_id": str(project_id),
            "name": "Valid Target",
            "provider": "custom_rest",
            "endpoint": "https://custom.example.com/infer",
            "capabilities": ["chat"],
        }

        response = client.post(
            "/api/v1/targets",
            headers=headers,
            json=valid_payload,
        )
        assert response.status_code == 201
        target_id = UUID(response.json()["id"])

        response = client.post(
            "/api/v1/targets",
            headers=headers,
            json={**valid_payload, "endpoint": "file:///etc/passwd"},
        )
        assert response.status_code == 422

        response = client.post(
            "/api/v1/targets",
            headers=headers,
            json={**valid_payload, "provider": "openai_compatible", "model": None},
        )
        assert response.status_code == 422

        response = client.patch(
            f"/api/v1/targets/{target_id}",
            headers=headers,
            json={},
        )
        assert response.status_code == 422
    finally:
        if project_id is not None:
            _cleanup_project(project_id)
        _cleanup_user(email)
