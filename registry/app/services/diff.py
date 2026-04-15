from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DiffResult:
    """Result of comparing two contract versions.

    Args:
        breaking: True if any breaking change is detected.
        semver_verdict: Required semver increment (major/minor/patch/none).
        breaking_changes: Human-readable descriptions of breaking changes.
        non_breaking_changes: Human-readable descriptions of non-breaking changes.
    """

    breaking: bool
    semver_verdict: str  # major | minor | patch | none
    breaking_changes: list[str] = field(default_factory=list)
    non_breaking_changes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "breaking": self.breaking,
            "semver_verdict": self.semver_verdict,
            "breaking_changes": self.breaking_changes,
            "non_breaking_changes": self.non_breaking_changes,
        }


def diff_specs(old: dict[str, Any], new: dict[str, Any]) -> DiffResult:
    """Detect breaking and non-breaking changes between two parsed specs.

    Args:
        old: Previously published spec (parsed YAML dict).
        new: Incoming spec (parsed YAML dict).

    Returns:
        DiffResult with full change classification.
    """
    breaking: list[str] = []
    non_breaking: list[str] = []

    old_caps = old.get("capabilities", {})
    new_caps = new.get("capabilities", {})
    old_con = old.get("constraints", {})
    new_con = new.get("constraints", {})

    # ── BREAKING: tool added to capabilities.tools ────────────────────────────
    old_tools = set(old_caps.get("tools", []))
    new_tools = set(new_caps.get("tools", []))
    for tool in sorted(new_tools - old_tools):
        breaking.append(f"Tool added to capabilities.tools: '{tool}'")
    for tool in sorted(old_tools - new_tools):
        non_breaking.append(f"Tool removed from capabilities.tools: '{tool}'")

    # ── BREAKING: service added to capabilities.external_services ────────────
    old_svcs = set(old_caps.get("external_services") or [])
    new_svcs = set(new_caps.get("external_services") or [])
    for svc in sorted(new_svcs - old_svcs):
        breaking.append(f"External service added: '{svc}'")

    # ── BREAKING: deny_tool removed ───────────────────────────────────────────
    old_deny = set(old_con.get("deny_tools") or [])
    new_deny = set(new_con.get("deny_tools") or [])
    for tool in sorted(old_deny - new_deny):
        breaking.append(f"deny_tools removal (loosened): '{tool}'")
    for tool in sorted(new_deny - old_deny):
        non_breaking.append(f"deny_tools addition (tightened): '{tool}'")

    # ── BREAKING: network egress loosened ────────────────────────────────────
    old_egress = (old_con.get("network") or {}).get("egress")
    new_egress = (new_con.get("network") or {}).get("egress")
    if old_egress is not None and new_egress is not None:
        if _egress_looser(old_egress, new_egress):
            breaking.append(
                f"network.egress loosened: {old_egress!r} -> {new_egress!r}"
            )

    # ── BREAKING: budget increased ────────────────────────────────────────────
    old_budget = (old_con.get("budget") or {}).get("max_cost_usd")
    new_budget = (new_con.get("budget") or {}).get("max_cost_usd")
    if old_budget is not None and new_budget is not None:
        if new_budget > old_budget:
            breaking.append(
                f"budget.max_cost_usd increased: {old_budget} -> {new_budget}"
            )
        elif new_budget < old_budget:
            non_breaking.append(
                f"budget.max_cost_usd tightened: {old_budget} -> {new_budget}"
            )

    # ── BREAKING: scope.max_calls_per_invocation increased ───────────────────
    old_calls = (old_con.get("scope") or {}).get("max_calls_per_invocation")
    new_calls = (new_con.get("scope") or {}).get("max_calls_per_invocation")
    if old_calls is not None and new_calls is not None:
        if new_calls > old_calls:
            breaking.append(
                f"scope.max_calls_per_invocation increased: {old_calls} -> {new_calls}"
            )
        elif new_calls < old_calls:
            non_breaking.append(
                f"scope.max_calls_per_invocation tightened: {old_calls} -> {new_calls}"
            )

    # ── BREAKING: invariant removed ──────────────────────────────────────────
    old_invs = {i["id"]: i for i in (old.get("invariants") or [])}
    new_invs = {i["id"]: i for i in (new.get("invariants") or [])}
    for inv_id in sorted(old_invs.keys() - new_invs.keys()):
        breaking.append(f"Invariant removed: '{inv_id}'")
    for inv_id in sorted(new_invs.keys() - old_invs.keys()):
        non_breaking.append(f"Invariant added: '{inv_id}'")

    # ── BREAKING: invariant severity downgraded (error -> warn) ──────────────
    for inv_id, old_inv in old_invs.items():
        if inv_id in new_invs:
            old_sev = old_inv.get("severity")
            new_sev = new_invs[inv_id].get("severity")
            if old_sev == "error" and new_sev == "warn":
                breaking.append(
                    f"Invariant '{inv_id}' severity downgraded: error -> warn"
                )

    is_breaking = len(breaking) > 0
    verdict = "major" if is_breaking else ("minor" if non_breaking else "none")
    return DiffResult(
        breaking=is_breaking,
        semver_verdict=verdict,
        breaking_changes=breaking,
        non_breaking_changes=non_breaking,
    )


def _egress_looser(old: Any, new: Any) -> bool:
    """Return True if the new egress value is more permissive than old."""
    # false < scoped < true
    rank = {False: 0, "scoped": 1, True: 2}
    return rank.get(new, 0) > rank.get(old, 0)


def check_semver_bump(
    current_version: str, incoming_version: str, breaking: bool
) -> bool:
    """Return True if the semver bump is sufficient for the change type.

    Args:
        current_version: Latest published version (e.g. "1.2.0").
        incoming_version: Proposed new version (e.g. "1.3.0").
        breaking: Whether any breaking change was detected.

    Returns:
        True if the bump is valid, False if a major bump is required but missing.
    """
    if not breaking:
        return True
    try:
        cur_major = int(current_version.split(".")[0])
        inc_major = int(incoming_version.split(".")[0])
        return inc_major > cur_major
    except (ValueError, IndexError):
        return False
