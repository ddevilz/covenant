from __future__ import annotations

from pathlib import Path
from typing import Any

import jsonschema
import yaml

from covenant.errors import CovenantViolationError


def _load_schema(spec_dir: Path, schema_path: str) -> dict[str, Any]:
    full = (spec_dir / schema_path).resolve()
    return yaml.safe_load(full.read_text(encoding="utf-8"))


def validate_input(data: Any, schema_path: str | None, spec_dir: Path) -> None:
    """Validate input data against the protocols.input.schema JSON Schema.

    Args:
        data: Input value to validate.
        schema_path: Relative path to the JSON Schema file, or None to skip.
        spec_dir: Directory containing the .covenant.yaml (schema path is relative to this).

    Raises:
        CovenantViolationError: INPUT_SCHEMA_MISMATCH if validation fails.
    """
    if not schema_path:
        return
    schema = _load_schema(spec_dir, schema_path)
    errors = list(jsonschema.Draft7Validator(schema).iter_errors(data))
    if errors:
        raise CovenantViolationError(
            code="INPUT_SCHEMA_MISMATCH",
            detail={"errors": [e.message for e in errors]},
        )


def validate_output(data: Any, schema_path: str | None, spec_dir: Path) -> None:
    """Validate output data against the protocols.output.schema JSON Schema.

    Args:
        data: Output value to validate.
        schema_path: Relative path to the JSON Schema file, or None to skip.
        spec_dir: Directory containing the .covenant.yaml (schema path is relative to this).

    Raises:
        CovenantViolationError: OUTPUT_SCHEMA_MISMATCH if validation fails.
    """
    if not schema_path:
        return
    schema = _load_schema(spec_dir, schema_path)
    errors = list(jsonschema.Draft7Validator(schema).iter_errors(data))
    if errors:
        raise CovenantViolationError(
            code="OUTPUT_SCHEMA_MISMATCH",
            detail={"errors": [e.message for e in errors]},
        )
