from __future__ import annotations

import json
import os
from pathlib import Path

import httpx
import typer

from covenant_cli import output
from covenant_cli.errors import (
    EXIT_NETWORK,
    EXIT_SIGNING,
    EXIT_VALIDATION,
    SpecLoadError,
)
from covenant_cli.models import spec_loader
from covenant_cli.services import linter


def publish_cmd(
    path: Path = typer.Argument(..., help="Path to .covenant.yaml"),
) -> None:
    """Publish a signed .covenant.yaml to the registry."""
    # 1. Load and lint
    try:
        spec = spec_loader.load_spec(path)
    except SpecLoadError as e:
        output.error_panel(f"[{e.phase.upper()}] {'; '.join(e.issues)}")
        raise typer.Exit(e.exit_code)

    issues = linter.lint(spec)
    error_issues = [i for i in issues if i.level == "error"]
    if issues:
        output.issues_table(issues)
    if error_issues:
        output.error_panel("Spec has lint errors -- fix them before publishing.")
        raise typer.Exit(EXIT_VALIDATION)

    # 2. Must be signed
    if not (spec.provenance and spec.provenance.signature):
        output.error_panel(
            "Spec must be signed before publishing.",
            hint=f"Run `covenant sign {path.absolute()}`",
        )
        raise typer.Exit(EXIT_SIGNING)

    # 3. Env vars
    registry_url = os.environ.get("COVENANT_REGISTRY_URL")
    api_key = os.environ.get("COVENANT_API_KEY")
    if not registry_url:
        output.error_panel("COVENANT_REGISTRY_URL is not set.")
        raise typer.Exit(EXIT_NETWORK)
    if not api_key:
        output.error_panel("COVENANT_API_KEY is not set.")
        raise typer.Exit(EXIT_NETWORK)

    # 4. HTTP POST
    raw_yaml = path.read_bytes()
    try:
        response = httpx.post(
            f"{registry_url.rstrip('/')}/contracts",
            content=raw_yaml,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/yaml",
            },
            timeout=30,
        )
    except httpx.ConnectError:
        output.error_panel(
            f"Registry unreachable at {registry_url}. Is COVENANT_REGISTRY_URL correct?"
        )
        raise typer.Exit(EXIT_NETWORK)

    if response.status_code == 201:
        try:
            body = response.json()
            contract_url = body.get("url", "")
        except Exception:
            contract_url = ""
        output.success_panel(
            f"Published  {spec.agent.name} {spec.agent.version}",
            body_lines=[contract_url] if contract_url else [],
        )

    elif response.status_code == 422:
        try:
            body = response.json()
            detail = body.get("detail", {})
            breaking_raw = detail.get("breaking_changes", [])
            try:
                from covenant_cli.services.diff_engine import Change, DiffResult

                breaking = [Change(**c) for c in breaking_raw]
                diff_result = DiffResult(
                    breaking=breaking,
                    non_breaking=[],
                    semver_verdict="major",
                    old_version=detail.get("current_version", "?"),
                    new_version=detail.get("incoming_version", "?"),
                )
                output.diff_renderer(diff_result)
            except Exception:
                output.err_console.print(json.dumps(breaking_raw, indent=2))
        except Exception:
            output.error_panel(
                f"Registry rejected publish (422): {response.text[:200]}"
            )
        raise typer.Exit(EXIT_VALIDATION)

    elif response.status_code == 409:
        output.error_panel(
            f"Version {spec.agent.version} already published."
            " Bump the version and re-sign."
        )
        raise typer.Exit(EXIT_VALIDATION)

    elif response.status_code in (401, 403):
        output.error_panel("Authentication failed. Check COVENANT_API_KEY.")
        raise typer.Exit(EXIT_NETWORK)

    else:
        output.error_panel(
            f"Unexpected registry response: {response.status_code}\n{response.text[:200]}"
        )
        raise typer.Exit(EXIT_NETWORK)
