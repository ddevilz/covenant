from __future__ import annotations

import pytest
from app.services.diff import diff_specs, check_semver_bump


def spec(tools=None, deny_tools=None, budget=1.0, egress=None, calls=None, invariants=None, svcs=None):
    s = {
        "covenant": "1.0",
        "agent": {"name": "a", "version": "1.0.0", "runtime": "python"},
        "capabilities": {"tools": tools or ["read_file"]},
        "constraints": {"budget": {"max_cost_usd": budget}},
    }
    if deny_tools is not None:
        s["constraints"]["deny_tools"] = deny_tools
    if egress is not None:
        s["constraints"]["network"] = {"egress": egress}
    if calls is not None:
        s["constraints"]["scope"] = {"max_calls_per_invocation": calls}
    if invariants is not None:
        s["invariants"] = invariants
    if svcs is not None:
        s["capabilities"]["external_services"] = svcs
    return s


# ── Breaking changes ──────────────────────────────────────────────────────────

def test_tool_added_is_breaking():
    result = diff_specs(spec(), spec(tools=["read_file", "bash"]))
    assert result.breaking
    assert any("bash" in c for c in result.breaking_changes)


def test_deny_tool_removed_is_breaking():
    result = diff_specs(spec(deny_tools=["bash"]), spec(deny_tools=[]))
    assert result.breaking
    assert any("bash" in c for c in result.breaking_changes)


def test_budget_increased_is_breaking():
    result = diff_specs(spec(budget=1.0), spec(budget=2.0))
    assert result.breaking


def test_egress_loosened_is_breaking():
    result = diff_specs(spec(egress=False), spec(egress=True))
    assert result.breaking


def test_calls_increased_is_breaking():
    result = diff_specs(spec(calls=5), spec(calls=10))
    assert result.breaking


def test_invariant_removed_is_breaking():
    inv = [{"id": "I-1", "assert": "True", "severity": "error"}]
    result = diff_specs(spec(invariants=inv), spec(invariants=[]))
    assert result.breaking


def test_invariant_severity_downgraded_is_breaking():
    old_inv = [{"id": "I-1", "assert": "True", "severity": "error"}]
    new_inv = [{"id": "I-1", "assert": "True", "severity": "warn"}]
    result = diff_specs(spec(invariants=old_inv), spec(invariants=new_inv))
    assert result.breaking


def test_external_service_added_is_breaking():
    result = diff_specs(spec(), spec(svcs=["stripe.com"]))
    assert result.breaking


# ── Non-breaking changes ──────────────────────────────────────────────────────

def test_deny_tool_added_is_non_breaking():
    result = diff_specs(spec(), spec(deny_tools=["bash"]))
    assert not result.breaking
    assert any("bash" in c for c in result.non_breaking_changes)


def test_invariant_added_is_non_breaking():
    new_inv = [{"id": "I-1", "assert": "True", "severity": "error"}]
    result = diff_specs(spec(), spec(invariants=new_inv))
    assert not result.breaking
    assert any("I-1" in c for c in result.non_breaking_changes)


def test_budget_tightened_is_non_breaking():
    result = diff_specs(spec(budget=2.0), spec(budget=1.0))
    assert not result.breaking


def test_no_changes_is_none_verdict():
    result = diff_specs(spec(), spec())
    assert result.semver_verdict == "none"
    assert not result.breaking


# ── check_semver_bump ─────────────────────────────────────────────────────────

def test_major_bump_satisfies_breaking():
    assert check_semver_bump("1.2.0", "2.0.0", breaking=True) is True


def test_minor_bump_does_not_satisfy_breaking():
    assert check_semver_bump("1.2.0", "1.3.0", breaking=True) is False


def test_any_bump_satisfies_non_breaking():
    assert check_semver_bump("1.2.0", "1.3.0", breaking=False) is True
