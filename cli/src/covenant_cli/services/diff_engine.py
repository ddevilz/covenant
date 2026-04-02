from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from covenant_cli.models.spec import CovenantSpec


@dataclass
class Change:
    """A single detected change between two spec versions.

    Args:
        rule: Machine-readable rule code.
        field: Dotted spec path affected.
        description: Human-readable description.
        detail: Raw old/new values for programmatic inspection.
    """

    rule: str
    field: str
    description: str
    detail: dict


@dataclass
class DiffResult:
    """Result of comparing two CovenantSpec versions.

    Args:
        breaking: Changes that require a major semver bump.
        non_breaking: Changes that require minor or patch bumps.
        semver_verdict: Overall semver implication.
        old_version: Version string from the old spec.
        new_version: Version string from the new spec.
    """

    breaking: list[Change]
    non_breaking: list[Change]
    semver_verdict: Literal["major", "minor", "patch", "none"]
    old_version: str
    new_version: str


def diff(old: CovenantSpec, new: CovenantSpec) -> DiffResult:
    """Compute behavioral diff between two CovenantSpec versions.

    Pure function -- no I/O. Takes CovenantSpec objects, not file paths.

    Args:
        old: Previous spec version.
        new: Incoming spec version.

    Returns:
        DiffResult with classified changes and semver verdict.
    """
    breaking: list[Change] = []
    non_breaking: list[Change] = []

    # --- capabilities.tools ---
    old_tools = set(old.capabilities.tools)
    new_tools = set(new.capabilities.tools)
    for added in sorted(new_tools - old_tools):
        breaking.append(
            Change(
                rule="TOOL_ADDED_TO_CAPABILITIES",
                field="capabilities.tools",
                description=f'Tool "{added}" added to capabilities allowlist',
                detail={"added": added},
            )
        )

    # --- constraints.deny_tools ---
    old_deny = set(old.constraints.deny_tools or [])
    new_deny = set(new.constraints.deny_tools or [])
    for removed in sorted(old_deny - new_deny):
        breaking.append(
            Change(
                rule="DENY_TOOL_REMOVED",
                field="constraints.deny_tools",
                description=f'Deny rule for "{removed}" removed',
                detail={"removed": removed},
            )
        )
    for added in sorted(new_deny - old_deny):
        non_breaking.append(
            Change(
                rule="DENY_TOOL_ADDED",
                field="constraints.deny_tools",
                description=f'Deny rule for "{added}" added',
                detail={"added": added},
            )
        )

    # --- capabilities.external_services ---
    old_svc = set(old.capabilities.external_services or [])
    new_svc = set(new.capabilities.external_services or [])
    for added in sorted(new_svc - old_svc):
        breaking.append(
            Change(
                rule="EXTERNAL_SERVICE_ADDED",
                field="capabilities.external_services",
                description=f'External service "{added}" added',
                detail={"added": added},
            )
        )

    # --- constraints.network.egress ---
    old_egress = old.constraints.network.egress if old.constraints.network else None
    new_egress = new.constraints.network.egress if new.constraints.network else None
    if old_egress != new_egress and old_egress is not None and new_egress is not None:
        loosened = (
            (old_egress is False and new_egress is True)
            or (old_egress is False and new_egress == "scoped")
            or (old_egress == "scoped" and new_egress is True)
        )
        tightened = (
            (old_egress is True and new_egress is False)
            or (old_egress is True and new_egress == "scoped")
            or (old_egress == "scoped" and new_egress is False)
        )
        if loosened:
            breaking.append(
                Change(
                    rule="EGRESS_LOOSENED",
                    field="constraints.network.egress",
                    description=f"Network egress loosened from {old_egress!r} to {new_egress!r}",
                    detail={"old": old_egress, "new": new_egress},
                )
            )
        elif tightened:
            non_breaking.append(
                Change(
                    rule="EGRESS_TIGHTENED",
                    field="constraints.network.egress",
                    description=f"Network egress tightened from {old_egress!r} to {new_egress!r}",
                    detail={"old": old_egress, "new": new_egress},
                )
            )

    # --- constraints.budget.max_cost_usd ---
    old_cost = old.constraints.budget.max_cost_usd if old.constraints.budget else None
    new_cost = new.constraints.budget.max_cost_usd if new.constraints.budget else None
    if old_cost is not None and new_cost is not None and old_cost != new_cost:
        if new_cost > old_cost:
            breaking.append(
                Change(
                    rule="BUDGET_INCREASED",
                    field="constraints.budget.max_cost_usd",
                    description=f"Budget ceiling raised from ${old_cost} to ${new_cost}",
                    detail={"old": old_cost, "new": new_cost},
                )
            )
        else:
            non_breaking.append(
                Change(
                    rule="BUDGET_DECREASED",
                    field="constraints.budget.max_cost_usd",
                    description=f"Budget ceiling lowered from ${old_cost} to ${new_cost}",
                    detail={"old": old_cost, "new": new_cost},
                )
            )

    # --- constraints.scope.max_calls_per_invocation ---
    old_calls = (
        old.constraints.scope.max_calls_per_invocation
        if old.constraints.scope
        else None
    )
    new_calls = (
        new.constraints.scope.max_calls_per_invocation
        if new.constraints.scope
        else None
    )
    if old_calls is not None and new_calls is not None and old_calls != new_calls:
        if new_calls > old_calls:
            breaking.append(
                Change(
                    rule="CALL_LIMIT_INCREASED",
                    field="constraints.scope.max_calls_per_invocation",
                    description=f"Call limit raised from {old_calls} to {new_calls}",
                    detail={"old": old_calls, "new": new_calls},
                )
            )
        else:
            non_breaking.append(
                Change(
                    rule="CALL_LIMIT_DECREASED",
                    field="constraints.scope.max_calls_per_invocation",
                    description=f"Call limit lowered from {old_calls} to {new_calls}",
                    detail={"old": old_calls, "new": new_calls},
                )
            )

    # --- invariants ---
    old_invs = {inv.id: inv for inv in (old.invariants or [])}
    new_invs = {inv.id: inv for inv in (new.invariants or [])}

    for inv_id in sorted(old_invs.keys() - new_invs.keys()):
        breaking.append(
            Change(
                rule="INVARIANT_REMOVED",
                field="invariants",
                description=f"Invariant {inv_id} removed",
                detail={"removed": inv_id},
            )
        )
    for inv_id in sorted(new_invs.keys() - old_invs.keys()):
        non_breaking.append(
            Change(
                rule="INVARIANT_ADDED",
                field="invariants",
                description=f"Invariant {inv_id} added",
                detail={"added": inv_id},
            )
        )
    for inv_id in sorted(old_invs.keys() & new_invs.keys()):
        old_sev = old_invs[inv_id].severity
        new_sev = new_invs[inv_id].severity
        if old_sev == "error" and new_sev == "warn":
            breaking.append(
                Change(
                    rule="INVARIANT_SEVERITY_DOWNGRADED",
                    field=f"invariants[{inv_id}].severity",
                    description=(
                        f"Invariant {inv_id} severity downgraded from error to warn"
                    ),
                    detail={"old": old_sev, "new": new_sev},
                )
            )

    # --- semver verdict ---
    _minor_rules = {
        "DENY_TOOL_ADDED",
        "INVARIANT_ADDED",
        "SLO_TIGHTENED",
        "EGRESS_TIGHTENED",
        "BUDGET_DECREASED",
        "CALL_LIMIT_DECREASED",
    }
    if breaking:
        verdict: Literal["major", "minor", "patch", "none"] = "major"
    elif non_breaking:
        has_minor = any(c.rule in _minor_rules for c in non_breaking)
        verdict = "minor" if has_minor else "patch"
    else:
        verdict = "none"

    return DiffResult(
        breaking=breaking,
        non_breaking=non_breaking,
        semver_verdict=verdict,
        old_version=old.agent.version,
        new_version=new.agent.version,
    )
