from __future__ import annotations

import re
from pathlib import Path

import typer
import yaml

from covenant_cli import output


def init_cmd(
    path: str = typer.Argument(".covenant.yaml", help="Output path"),
) -> None:
    """Interactively scaffold a .covenant.yaml contract file."""
    out_path = Path(path)

    if out_path.exists():
        confirmed = typer.confirm(f"Overwrite existing {out_path}?", default=False)
        if not confirmed:
            raise typer.Exit(0)

    # 1. Agent name
    while True:
        name = typer.prompt("Agent name (kebab-case)").strip()
        if re.match(r"^[a-z0-9-]+$", name):
            break
        typer.echo("Name must be kebab-case (lowercase letters, digits, hyphens only)")

    # 2. Version
    version = typer.prompt("Version", default="0.1.0").strip()

    # 3. Runtime
    runtime = typer.prompt("Runtime [python/typescript/any]", default="python").strip()
    if runtime not in ("python", "typescript", "any"):
        runtime = "python"

    # 4. Allowed tools
    while True:
        tools_raw = typer.prompt(
            "Allowed tools (comma-separated, at least one required)"
        ).strip()
        tools = [t.strip() for t in tools_raw.split(",") if t.strip()]
        if tools:
            break
        typer.echo("At least one tool is required.")

    # 5. Max cost USD
    while True:
        cost_raw = typer.prompt("Max cost USD per invocation", default="0.10").strip()
        try:
            max_cost = float(cost_raw)
            if max_cost > 0:
                break
        except ValueError:
            pass
        typer.echo("Must be a positive number.")

    # 6. Deny tools (optional)
    deny_raw = typer.prompt(
        "Deny tools (comma-separated, optional)", default=""
    ).strip()
    deny_tools = [t.strip() for t in deny_raw.split(",") if t.strip()]

    # 7. Invariants (optional loop)
    invariants: list[dict] = []
    while typer.confirm("Add an invariant?", default=False):
        inv_id = typer.prompt("  Invariant ID (e.g. INV-001)").strip()
        inv_desc = typer.prompt("  Description").strip()
        inv_expr = typer.prompt(
            "  Assert expression (e.g. cost_usd < 0.10)"
        ).strip()
        inv_sev = typer.prompt(
            "  Severity [error/warn]", default="error"
        ).strip()
        invariants.append(
            {
                "id": inv_id,
                "description": inv_desc,
                "assert": inv_expr,
                "severity": inv_sev if inv_sev in ("error", "warn") else "error",
            }
        )

    # 8. Description (optional)
    description = typer.prompt("Description (optional)", default="").strip()

    # Build spec dict
    spec: dict = {
        "covenant": "1.0",
        "agent": {"name": name, "version": version, "runtime": runtime},
        "capabilities": {"tools": tools},
        "constraints": {"budget": {"max_cost_usd": max_cost}},
    }
    if deny_tools:
        spec["constraints"]["deny_tools"] = deny_tools
    if invariants:
        spec["invariants"] = invariants
    if description:
        spec["metadata"] = {"description": description}

    out_path.write_text(
        yaml.dump(spec, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )

    output.success_panel(
        f"Created  {name} {version}",
        body_lines=[
            f"Written to {out_path.absolute()}",
            f"Run `covenant validate {out_path.absolute()}` to check it.",
        ],
    )
