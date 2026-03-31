"""Health and config tests."""
import pytest  # type: ignore[reportMissingImports]
from fastapi.testclient import TestClient  # type: ignore[reportMissingImports]

from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_health(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "service" in data
    assert "sdxl_gpu" in data
