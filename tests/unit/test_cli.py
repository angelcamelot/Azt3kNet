import json

from typer.testing import CliRunner

from azt3knet.cli.app import app


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


runner = CliRunner()


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


def test_cli_populate_outputs_preview_json():
    result = runner.invoke(
        app,
        [
            "populate",
            "--count",
            "2",
            "--country",
            "MX",
            "--preview",
            "1",
            "--seed",
            "cli-seed",
        ],
    )
    assert result.exit_code == 0, result.stdout
    data = json.loads(result.stdout)
    assert len(data) == 1
    assert data[0]["seed"] == "cli-seed:0"
    _assert_agent_payload(data[0])


def test_cli_populate_rejects_invalid_gender():
    result = runner.invoke(
        app,
        [
            "populate",
            "--gender",
            "robot",
            "--count",
            "1",
            "--country",
            "MX",
        ],
    )
    assert result.exit_code != 0
    assert "Invalid value for '--gender'" in result.stdout
