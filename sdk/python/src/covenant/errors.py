from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal, get_args

ViolationCode = Literal[
    "UNDECLARED_TOOL",
    "DENIED_TOOL",
    "BUDGET_EXCEEDED",
    "CALL_LIMIT_EXCEEDED",
    "INVARIANT_FAILED",
    "INPUT_SCHEMA_MISMATCH",
    "OUTPUT_SCHEMA_MISMATCH",
    "NETWORK_EGRESS_DENIED",
    "FILESYSTEM_SCOPE_VIOLATION",
    "UNDECLARED_MODEL",
]

_ALL_CODES: frozenset[str] = frozenset(get_args(ViolationCode))


@dataclass
class CovenantViolationError(Exception):
    """Raised on any contract violation.

    Args:
        code: Machine-readable violation code.
        detail: Structured dict with violation-specific context.
        timestamp: UTC time of the violation.
    """

    code: str
    detail: dict
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if self.code not in _ALL_CODES:
            raise ValueError(f"Unknown violation code: {self.code!r}")
        super().__init__(self.code, self.detail)
