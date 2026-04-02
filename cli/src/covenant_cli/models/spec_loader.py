from __future__ import annotations

import importlib.resources
import json
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft7Validator
from pydantic import ValidationError

from covenant_cli.errors import SpecLoadError
from covenant_cli.models.spec import CovenantSpec

_schema: dict[str, Any] | None = None


def _get_schema() -> dict[str, Any]:
    """Load the bundled covenant.schema.json once and cache it.

    Returns:
        Parsed JSON Schema dict.
    """
    global _schema
    if _schema is None:
        data = (
            importlib.resources.files("covenant_cli.data")
            .joinpath("covenant.schema.json")
        )
        _schema = json.loads(data.read_text(encoding="utf-8"))
    return _schema


def load_spec(path: Path) -> CovenantSpec:
    """Load and validate a .covenant.yaml through four sequential phases.

    Phase 1 -- FILE:   path exists and is readable
    Phase 2 -- YAML:   valid YAML, top-level mapping
    Phase 3 -- SCHEMA: Draft7 JSON Schema validation (all errors collected)
    Phase 4 -- MODEL:  Pydantic model_validate (skipped if Phase 3 has errors)

    Args:
        path: Path to the .covenant.yaml file.

    Returns:
        A fully-validated CovenantSpec instance.

    Raises:
        SpecLoadError: On failure at any phase, with all issues for that phase.
    """
    # Phase 1 -- FILE
    if not path.exists():
        raise SpecLoadError(
            phase="file",
            path=path,
            issues=[f"File not found: {path}"],
            exit_code=2,
        )
    if not path.is_file():
        raise SpecLoadError(
            phase="file",
            path=path,
            issues=[f"Not a file: {path}"],
            exit_code=2,
        )

    text = path.read_text(encoding="utf-8")

    # Phase 2 -- YAML
    try:
        raw: Any = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise SpecLoadError(
            phase="yaml", path=path, issues=[str(e)], exit_code=1
        ) from e

    if not isinstance(raw, dict):
        raise SpecLoadError(
            phase="yaml",
            path=path,
            issues=["YAML must be a mapping at the top level"],
            exit_code=1,
        )

    # Phase 3 -- SCHEMA
    schema = _get_schema()
    validator = Draft7Validator(schema)
    errors = sorted(validator.iter_errors(raw), key=lambda e: list(e.path))
    if errors:
        issues = [
            f"{'.'.join(str(p) for p in e.path) or '<root>'}: {e.message}"
            for e in errors
        ]
        raise SpecLoadError(phase="schema", path=path, issues=issues, exit_code=1)

    # Phase 4 -- MODEL (only reached if schema is clean)
    try:
        return CovenantSpec.model_validate(raw)
    except ValidationError as e:
        issues = [f"{err['loc']}: {err['msg']}" for err in e.errors()]
        raise SpecLoadError(
            phase="model", path=path, issues=issues, exit_code=1
        ) from e
