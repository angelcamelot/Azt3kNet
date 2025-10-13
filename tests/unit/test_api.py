from fastapi.testclient import TestClient

from azt3knet.api.main import app


client = TestClient(app)


def test_healthcheck():
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_population_endpoint_returns_agents():
    response = client.post(
        "/api/populate",
        json={"count": 2, "country": "MX", "seed": "api-seed", "preview": 1},
    )
    assert response.status_code == 200, response.json()
    payload = response.json()
    assert payload["seed"] == "api-seed"
    assert payload["count"] == 1
    assert len(payload["agents"]) == 1
