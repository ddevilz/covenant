from pathlib import Path

import yaml
from typer.testing import CliRunner

from covenant_cli.main import app

runner = CliRunner()
FIXTURES = Path(__file__).parent / "fixtures"


def test_diff_same_spec_shows_none() -> None:
    result = runner.invoke(
        app,
        ["diff", str(FIXTURES / "valid.covenant.yaml"), str(FIXTURES / "valid.covenant.yaml")],
    )
    assert result.exit_code == 0
    assert "none" in result.output.lower()


def test_diff_fail_on_breaking(tmp_path: Path) -> None:
    with open(FIXTURES / "valid.covenant.yaml") as f:
        data = yaml.safe_load(f)
    data["agent"]["version"] = "2.0.0"
    data["capabilities"]["tools"].append("write_files")
    new_path = tmp_path / "new.covenant.yaml"
    with open(new_path, "w") as f:
        yaml.dump(data, f)

    result = runner.invoke(
        app,
        ["diff", "--fail-on-breaking", str(FIXTURES / "valid.covenant.yaml"), str(new_path)],
    )
    assert result.exit_code == 1


def test_diff_nonexistent_file() -> None:
    result = runner.invoke(
        app,
        ["diff", "/no/such/old.yaml", str(FIXTURES / "valid.covenant.yaml")],
    )
    assert result.exit_code != 0
