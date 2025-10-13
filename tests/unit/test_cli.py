import json

from typer.testing import CliRunner

from azt3knet.cli.app import app


runner = CliRunner()


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
