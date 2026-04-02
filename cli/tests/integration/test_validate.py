from pathlib import Path

from typer.testing import CliRunner

from covenant_cli.main import app

runner = CliRunner()
FIXTURES = Path(__file__).parent / "fixtures"


def test_validate_valid_spec() -> None:
    result = runner.invoke(app, ["validate", str(FIXTURES / "valid.covenant.yaml")])
    assert result.exit_code == 0
    assert "PASS" in result.output


def test_validate_missing_file() -> None:
    result = runner.invoke(app, ["validate", "/nonexistent/path.yaml"])
    assert result.exit_code == 2


def test_validate_missing_budget() -> None:
    result = runner.invoke(
        app, ["validate", str(FIXTURES / "missing_budget.covenant.yaml")]
    )
    assert result.exit_code == 1
    assert "MISSING_BUDGET" in result.output


def test_validate_deny_overlap() -> None:
    result = runner.invoke(
        app, ["validate", str(FIXTURES / "deny_overlap.covenant.yaml")]
    )
    assert result.exit_code == 1
    assert "DENY_OVERLAP" in result.output


def test_validate_no_tools() -> None:
    result = runner.invoke(
        app, ["validate", str(FIXTURES / "no_tools.covenant.yaml")]
    )
    assert result.exit_code == 1
    assert "EMPTY_TOOLS_LIST" in result.output


def test_validate_no_lint_flag() -> None:
    """--no-lint skips lint rules; missing_budget passes schema so should exit 0."""
    result = runner.invoke(
        app,
        ["validate", "--no-lint", str(FIXTURES / "missing_budget.covenant.yaml")],
    )
    # missing_budget.covenant.yaml is valid per JSON Schema (constraints: {} is allowed)
    assert result.exit_code == 0
