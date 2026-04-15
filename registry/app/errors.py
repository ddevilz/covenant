from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import uuid


@dataclass
class RegistryError(Exception):
    """Base for all structured registry errors.

    Args:
        error: Machine-readable error code.
        detail: Structured dict with context.
        status_code: HTTP status to return.
    """

    error: str
    detail: dict[str, Any]
    status_code: int = 422

    def to_response(self) -> dict[str, Any]:
        return {
            "error": self.error,
            "detail": self.detail,
            "request_id": str(uuid.uuid4()),
        }


class ContractNotFound(RegistryError):
    def __init__(self, name: str, version: str | None = None) -> None:
        detail = {"name": name}
        if version:
            detail["version"] = version
        super().__init__(
            error="CONTRACT_NOT_FOUND",
            detail=detail,
            status_code=404,
        )


class BreakingChangeError(RegistryError):
    def __init__(
        self,
        current_version: str,
        incoming_version: str,
        breaking_changes: list[str],
    ) -> None:
        super().__init__(
            error="BREAKING_CHANGE_REQUIRES_MAJOR_BUMP",
            detail={
                "current_version": current_version,
                "incoming_version": incoming_version,
                "breaking_changes": breaking_changes,
            },
            status_code=422,
        )


class AuthError(RegistryError):
    def __init__(self, message: str = "Invalid or missing API key") -> None:
        super().__init__(
            error="UNAUTHORIZED",
            detail={"message": message},
            status_code=401,
        )


class ValidationError(RegistryError):
    def __init__(self, issues: list[str]) -> None:
        super().__init__(
            error="SPEC_INVALID",
            detail={"issues": issues},
            status_code=422,
        )
