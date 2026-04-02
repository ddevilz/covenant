from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from covenant_cli.models.spec import CovenantSpec


@dataclass
class LintIssue:
    """A single linting finding.

    Args:
        level: Severity -- "error" blocks signing/publishing, "warn" does not.
        code: Machine-readable rule identifier.
        field: Dotted spec path that triggered the issue, or None.
        message: Human-readable description.
    """

    level: Literal["error", "warn"]
    code: str
    field: str | None
    message: str


def lint(spec: CovenantSpec) -> list[LintIssue]:
    """Run principle linting rules against a loaded CovenantSpec.

    These rules go beyond JSON Schema validation -- they check semantic
    correctness and best practices.

    Args:
        spec: A fully-validated CovenantSpec.

    Returns:
        List of LintIssues. Empty list means the spec is clean.
    """
    issues: list[LintIssue] = []

    # EMPTY_TOOLS_LIST -- capabilities.tools must be non-empty
    if not spec.capabilities.tools:
        issues.append(
            LintIssue(
                level="error",
                code="EMPTY_TOOLS_LIST",
                field="capabilities.tools",
                message="capabilities.tools must be non-empty",
            )
        )

    # DENY_OVERLAP + UNDECLARED_DENY
    if spec.constraints.deny_tools:
        tools_set = set(spec.capabilities.tools)
        deny_set = set(spec.constraints.deny_tools)

        overlap = deny_set & tools_set
        for tool in sorted(overlap):
            issues.append(
                LintIssue(
                    level="error",
                    code="DENY_OVERLAP",
                    field="constraints.deny_tools",
                    message=(
                        f'"{tool}" is in both capabilities.tools and'
                        " constraints.deny_tools"
                    ),
                )
            )

        undeclared = deny_set - tools_set
        for tool in sorted(undeclared):
            issues.append(
                LintIssue(
                    level="warn",
                    code="UNDECLARED_DENY",
                    field="constraints.deny_tools",
                    message=f'"{tool}" in deny_tools is not in capabilities.tools',
                )
            )

    # MISSING_BUDGET -- constraints.budget is required
    if spec.constraints.budget is None:
        issues.append(
            LintIssue(
                level="error",
                code="MISSING_BUDGET",
                field="constraints.budget",
                message="constraints.budget.max_cost_usd is required",
            )
        )

    # INVARIANT_MISSING_SEV -- belt-and-suspenders over schema
    if spec.invariants:
        for i, inv in enumerate(spec.invariants):
            if not inv.severity:
                issues.append(
                    LintIssue(
                        level="error",
                        code="INVARIANT_MISSING_SEV",
                        field=f"invariants[{i}].severity",
                        message=f"invariant {inv.id} is missing severity",
                    )
                )

    # PROVENANCE_ALGO_INVALID -- provenance present but algorithm not Ed25519
    if spec.provenance is not None and spec.provenance.algorithm != "Ed25519":
        issues.append(
            LintIssue(
                level="warn",
                code="PROVENANCE_ALGO_INVALID",
                field="provenance.algorithm",
                message='provenance block present but algorithm is not "Ed25519"',
            )
        )

    return issues
