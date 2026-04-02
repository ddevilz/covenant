from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from pydantic import ValidationError

from covenant_cli import output
from covenant_cli.errors import EXIT_VALIDATION, SpecLoadError
from covenant_cli.models import spec_loader
from covenant_cli.services.audit_engine import AuditEvent, analyze


def audit_cmd(
    events: Path = typer.Argument(
        ..., help="Path to NDJSON audit events file (.jsonl)"
    ),
    spec: Optional[Path] = typer.Option(
        None, "--spec", help="Explicit spec file path (overrides auto-resolution)"
    ),
) -> None:
    """Report declared vs observed behavior from an audit events log."""
    if not events.exists():
        output.error_panel(f"File not found: {events}")
        raise typer.Exit(2)

    # Parse NDJSON
    valid_events: list[AuditEvent] = []
    malformed = 0

    for line in events.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            valid_events.append(AuditEvent.model_validate(data))
        except (json.JSONDecodeError, ValidationError):
            malformed += 1

    if not valid_events:
        output.error_panel("Zero valid events parsed from input file.")
        raise typer.Exit(EXIT_VALIDATION)

    # Spec resolution
    loaded_spec = None
    if spec is not None:
        try:
            loaded_spec = spec_loader.load_spec(spec)
        except SpecLoadError as e:
            output.error_panel(f"[{e.phase.upper()}] {'; '.join(e.issues)}")
            raise typer.Exit(e.exit_code)
    else:
        auto = Path.cwd() / ".covenant.yaml"
        if auto.exists():
            try:
                loaded_spec = spec_loader.load_spec(auto)
            except SpecLoadError:
                pass  # fall through to specless mode

    report = analyze(valid_events, loaded_spec)

    if malformed:
        output.err_console.print(
            f"[yellow]! {malformed} malformed line(s) skipped[/yellow]"
        )

    output.audit_renderer(report)
