import json
from pathlib import Path

from typer.testing import CliRunner

from covenant_cli.main import app

runner = CliRunner()
FIXTURES = Path(__file__).parent / "fixtures"


def _write_events(path: Path, events: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(e) for e in events))


def _base_event(**overrides) -> dict:  # type: ignore[no-untyped-def]
    base: dict = {
        "contract": "code-reviewer@1.0.0",
        "outcome": "ok",
        "tool_calls": ["read_files"],
        "cost_usd": 0.05,
        "duration_ms": 1000,
        "occurred_at": "2026-03-01T00:00:00+00:00",
        "violation_code": None,
        "model_used": None,
    }
    base.update(overrides)
    return base


def test_audit_basic_report(tmp_path: Path) -> None:
    evs = tmp_path / "events.jsonl"
    _write_events(evs, [_base_event(), _base_event()])
    result = runner.invoke(
        app,
        ["audit", str(evs), "--spec", str(FIXTURES / "valid.covenant.yaml")],
    )
    assert result.exit_code == 0
    assert "code-reviewer" in result.output


def test_audit_zero_valid_events(tmp_path: Path) -> None:
    evs = tmp_path / "empty.jsonl"
    evs.write_text("")
    result = runner.invoke(app, ["audit", str(evs)])
    assert result.exit_code == 1


def test_audit_all_malformed_is_exit_1(tmp_path: Path) -> None:
    evs = tmp_path / "bad.jsonl"
    evs.write_text("not json\nalso not json\n")
    result = runner.invoke(app, ["audit", str(evs)])
    assert result.exit_code == 1


def test_audit_specless_mode(tmp_path: Path) -> None:
    evs = tmp_path / "events.jsonl"
    _write_events(evs, [_base_event()])
    # Run without --spec and no .covenant.yaml in cwd
    result = runner.invoke(app, ["audit", str(evs)])
    assert result.exit_code == 0
