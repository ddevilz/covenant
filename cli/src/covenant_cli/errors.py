from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

EXIT_OK = 0
EXIT_VALIDATION = 1
EXIT_NOT_FOUND = 2
EXIT_SIGNING = 3
EXIT_NETWORK = 4


@dataclass
class SpecLoadError(Exception):
    """Raised by spec_loader when any load phase fails.

    Args:
        phase: Which phase failed.
        path: Path to the spec file.
        issues: All errors collected during the phase.
        exit_code: Appropriate CLI exit code (2 for file, 1 for others).
    """

    phase: Literal["file", "yaml", "schema", "model"]
    path: Path
    issues: list[str]
    exit_code: int


@dataclass
class CliError(Exception):
    """Raised by command handlers for user-facing errors.

    Args:
        message: Human-readable error description.
        exit_code: Appropriate CLI exit code.
        hint: Optional actionable hint shown below the message.
    """

    message: str
    exit_code: int
    hint: str | None = None
