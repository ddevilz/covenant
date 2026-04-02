from __future__ import annotations

from pathlib import Path

import typer

from covenant_cli import output
from covenant_cli.errors import EXIT_VALIDATION, CliError, SpecLoadError
from covenant_cli.models import spec_loader
from covenant_cli.services import linter


def validate_cmd(
    path: Path = typer.Argument(..., help="Path to .covenant.yaml"),
    no_lint: bool = typer.Option(False, "--no-lint", help="Skip principle linting"),
) -> None:
    """Validate a .covenant.yaml against the JSON Schema and lint rules."""
    try:
        spec = spec_loader.load_spec(path)
        issues = [] if no_lint else linter.lint(spec)
        if issues:
            output.issues_table(issues)
            raise typer.Exit(EXIT_VALIDATION)
        output.success_panel(f"PASS  {spec.agent.name} {spec.agent.version}")
    except SpecLoadError as e:
        output.error_panel(
            message=f"[{e.phase.upper()}] {'; '.join(e.issues)}",
            hint=None,
        )
        raise typer.Exit(e.exit_code)
    except CliError as e:
        output.error_panel(e.message, hint=e.hint)
        raise typer.Exit(e.exit_code)
