from fastapi.testclient import TestClient

from vigilo_api.main import app

client = TestClient(app)


def test_healthz_returns_ok():
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_version_reflects_brand_config():
    response = client.get("/version")
    assert response.status_code == 200
    body = response.json()
    assert body["product"] == "Vigilo"
    assert "api_version" in body
    assert "registry_version" in body
