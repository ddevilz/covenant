from __future__ import annotations

from pathlib import Path

import typer

from covenant_cli import output
from covenant_cli.errors import EXIT_NOT_FOUND, EXIT_VALIDATION, SpecLoadError
from covenant_cli.models import spec_loader
from covenant_cli.services import diff_engine


def diff_cmd(
    old: Path = typer.Argument(..., help="Path to old .covenant.yaml"),
    new: Path = typer.Argument(..., help="Path to new .covenant.yaml"),
    fail_on_breaking: bool = typer.Option(
        False,
        "--fail-on-breaking",
        help="Exit 1 if any breaking changes (for CI)",
    ),
) -> None:
    """Show behavioral diff between two .covenant.yaml versions."""
    old_spec = None
    new_spec = None
    load_errors: list[str] = []

    try:
        old_spec = spec_loader.load_spec(old)
    except SpecLoadError as e:
        load_errors.append(f"OLD spec: [{e.phase.upper()}] {'; '.join(e.issues)}")

    try:
        new_spec = spec_loader.load_spec(new)
    except SpecLoadError as e:
        load_errors.append(f"NEW spec: [{e.phase.upper()}] {'; '.join(e.issues)}")

    if load_errors:
        for err in load_errors:
            output.error_panel(err)
        has_missing = any("not found" in e.lower() for e in load_errors)
        raise typer.Exit(EXIT_NOT_FOUND if has_missing else EXIT_VALIDATION)

    assert old_spec is not None and new_spec is not None
    result = diff_engine.diff(old_spec, new_spec)
    output.diff_renderer(result)

    if fail_on_breaking and result.breaking:
        raise typer.Exit(EXIT_VALIDATION)
