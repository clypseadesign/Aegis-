"""System endpoint tests for AegisAI."""

from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_root_endpoint_returns_service_metadata() -> None:
    """The root endpoint should report service identity and status."""

    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "name": "AegisAI",
        "version": "0.1.0",
        "status": "ok",
    }


def test_health_endpoint_reports_ok() -> None:
    """The liveness endpoint should report ok whenever the process is running."""

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_endpoint_reports_database_status() -> None:
    """The readiness endpoint should report the database connectivity status."""

    response = client.get("/api/v1/system/ready")

    assert response.status_code in (200, 503)

    body = response.json()

    assert body["database"] in ("ok", "error")
    assert body["status"] in ("ok", "degraded")

    if body["database"] == "ok":
        assert response.status_code == 200
        assert body["status"] == "ok"
    else:
        assert response.status_code == 503
        assert body["status"] == "degraded"


def test_system_info_endpoint_reports_application_metadata() -> None:
    """The system info endpoint should report application name/version/status."""

    response = client.get("/api/v1/system/info")

    assert response.status_code == 200

    body = response.json()

    assert body["name"] == "AegisAI"
    assert body["version"] == "0.1.0"
    assert body["status"] == "ok"
