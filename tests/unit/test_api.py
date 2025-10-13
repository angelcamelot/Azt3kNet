from fastapi.testclient import TestClient

from azt3knet.api.main import app


EXPECTED_AGENT_FIELDS = {
    "id",
    "seed",
    "name",
    "username_hint",
    "country",
    "city",
    "locale",
    "timezone",
    "age",
    "gender",
    "interests",
    "bio",
    "posting_cadence",
    "tone",
    "behavioral_biases",
}


client = TestClient(app)


def _assert_agent_payload(agent: dict[str, object]) -> None:
    assert set(agent.keys()) == EXPECTED_AGENT_FIELDS
    assert isinstance(agent["id"], str)
    assert isinstance(agent["seed"], str)
    assert isinstance(agent["name"], str)
    assert isinstance(agent["username_hint"], str)
    assert isinstance(agent["country"], str)
    assert isinstance(agent["city"], str)
    assert isinstance(agent["locale"], str)
    assert isinstance(agent["timezone"], str)
    assert isinstance(agent["age"], int)
    assert isinstance(agent["gender"], str)
    assert isinstance(agent["interests"], list)
    assert isinstance(agent["bio"], str)
    assert isinstance(agent["posting_cadence"], str)
    assert isinstance(agent["tone"], str)
    assert isinstance(agent["behavioral_biases"], list)


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
    _assert_agent_payload(payload["agents"][0])


def test_population_endpoint_rejects_invalid_gender():
    response = client.post(
        "/api/populate",
        json={"count": 1, "country": "MX", "gender": "robot"},
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "gender" in detail
