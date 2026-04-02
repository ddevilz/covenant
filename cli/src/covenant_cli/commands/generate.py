from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional

import typer
import yaml

from covenant_cli import output
from covenant_cli.errors import EXIT_NOT_FOUND, EXIT_VALIDATION
from covenant_cli.services.generator import analyze, draft_spec, enhance_with_llm


def generate_cmd(
    source: Path = typer.Argument(..., help="Path to agent source file (.py or .ts)"),
    output_path: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output path (default: <source-stem>.covenant.yaml)"
    ),
    no_llm: bool = typer.Option(
        False, "--no-llm", help="Skip LLM enhancement even if COVENANT_LLM_KEY is set"
    ),
) -> None:
    """Generate a draft .covenant.yaml from an agent source file."""
    if not source.exists():
        output.error_panel(f"File not found: {source}")
        raise typer.Exit(EXIT_NOT_FOUND)

    stem = source.stem
    agent_name = re.sub(r"[^a-z0-9]+", "-", stem.lower()).strip("-")
    out_path = Path(output_path) if output_path else source.parent / f"{stem}.covenant.yaml"

    if out_path.exists():
        confirmed = typer.confirm(f"Overwrite existing {out_path}?", default=False)
        if not confirmed:
            raise typer.Exit(0)

    try:
        result = analyze(source)
        draft = draft_spec(result, agent_name)

        llm_key = os.environ.get("COVENANT_LLM_KEY")
        llm_enhanced = False
        if llm_key and not no_llm:
            try:
                source_text = source.read_text(encoding="utf-8")
                draft = enhance_with_llm(draft, source_text)
                llm_enhanced = True
            except Exception as e:
                output.err_console.print(
                    f"[yellow]! LLM enhancement failed: {e} -- using static analysis only[/yellow]"
                )

        out_path.write_text(
            yaml.dump(draft, sort_keys=False, allow_unicode=True), encoding="utf-8"
        )

    except Exception as e:
        output.error_panel(f"Generation failed: {e}")
        raise typer.Exit(EXIT_VALIDATION)

    body_lines = [f"Draft written to {out_path.absolute()}"]
    if llm_enhanced:
        body_lines.append("  * LLM-enhanced (llm_enhanced: true set in metadata)")
    body_lines.append("  ! capabilities.tools is empty -- fill in before publishing")
    if result.has_llm and not draft.get("capabilities", {}).get("models"):
        body_lines.append(
            "  ! capabilities.models is empty -- LLM usage detected"
        )

    output.success_panel(f"Generated  {agent_name}", body_lines=body_lines)
