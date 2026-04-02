from covenant_cli.models.spec import (
    AgentSpec,
    BudgetSpec,
    CapabilitiesSpec,
    ConstraintsSpec,
    CovenantSpec,
    InvariantSpec,
    NetworkSpec,
    ScopeSpec,
)
from covenant_cli.services.diff_engine import diff


def _spec(
    version: str = "1.0.0",
    tools: list[str] | None = None,
    deny_tools: list[str] | None = None,
    external_services: list[str] | None = None,
    egress: bool | str | None = None,
    max_cost: float = 0.10,
    max_calls: int | None = None,
    invariants: list[InvariantSpec] | None = None,
) -> CovenantSpec:
    network = NetworkSpec(egress=egress) if egress is not None else None  # type: ignore[arg-type]
    scope = ScopeSpec(max_calls_per_invocation=max_calls) if max_calls else None
    return CovenantSpec(
        covenant="1.0",
        agent=AgentSpec(name="test-agent", version=version, runtime="python"),
        capabilities=CapabilitiesSpec(
            tools=tools or ["read_files"],
            external_services=external_services,
        ),
        constraints=ConstraintsSpec(
            deny_tools=deny_tools,
            network=network,
            scope=scope,
            budget=BudgetSpec(max_cost_usd=max_cost),
        ),
        invariants=invariants,
    )


def test_no_changes() -> None:
    result = diff(_spec("1.0.0"), _spec("1.0.1"))
    assert result.semver_verdict == "none"
    assert result.breaking == []
    assert result.non_breaking == []


def test_tool_added_is_breaking() -> None:
    old = _spec("1.0.0", tools=["read_files"])
    new = _spec("2.0.0", tools=["read_files", "write_files"])
    result = diff(old, new)
    assert any(c.rule == "TOOL_ADDED_TO_CAPABILITIES" for c in result.breaking)
    assert result.semver_verdict == "major"


def test_deny_tool_removed_is_breaking() -> None:
    old = _spec("1.0.0", deny_tools=["delete_files"])
    new = _spec("2.0.0", deny_tools=None)
    result = diff(old, new)
    assert any(c.rule == "DENY_TOOL_REMOVED" for c in result.breaking)
    assert result.semver_verdict == "major"


def test_deny_tool_added_is_non_breaking() -> None:
    old = _spec("1.0.0", deny_tools=None)
    new = _spec("1.1.0", deny_tools=["delete_files"])
    result = diff(old, new)
    assert any(c.rule == "DENY_TOOL_ADDED" for c in result.non_breaking)
    assert result.semver_verdict == "minor"


def test_external_service_added_is_breaking() -> None:
    old = _spec("1.0.0", external_services=None)
    new = _spec("2.0.0", external_services=["github.com"])
    result = diff(old, new)
    assert any(c.rule == "EXTERNAL_SERVICE_ADDED" for c in result.breaking)


def test_egress_false_to_true_is_breaking() -> None:
    old = _spec("1.0.0", egress=False)
    new = _spec("2.0.0", egress=True)
    result = diff(old, new)
    assert any(c.rule == "EGRESS_LOOSENED" for c in result.breaking)


def test_egress_true_to_false_is_non_breaking() -> None:
    old = _spec("1.0.0", egress=True)
    new = _spec("1.1.0", egress=False)
    result = diff(old, new)
    assert any(c.rule == "EGRESS_TIGHTENED" for c in result.non_breaking)


def test_budget_increased_is_breaking() -> None:
    old = _spec("1.0.0", max_cost=0.10)
    new = _spec("2.0.0", max_cost=0.20)
    result = diff(old, new)
    assert any(c.rule == "BUDGET_INCREASED" for c in result.breaking)


def test_budget_decreased_is_non_breaking() -> None:
    old = _spec("1.0.0", max_cost=0.20)
    new = _spec("1.1.0", max_cost=0.10)
    result = diff(old, new)
    assert any(c.rule == "BUDGET_DECREASED" for c in result.non_breaking)


def test_call_limit_increased_is_breaking() -> None:
    old = _spec("1.0.0", max_calls=10)
    new = _spec("2.0.0", max_calls=20)
    result = diff(old, new)
    assert any(c.rule == "CALL_LIMIT_INCREASED" for c in result.breaking)


def test_invariant_removed_is_breaking() -> None:
    inv = [InvariantSpec(**{"id": "INV-001", "assert": "cost_usd < 0.10", "severity": "error"})]
    old = _spec("1.0.0", invariants=inv)
    new = _spec("2.0.0", invariants=None)
    result = diff(old, new)
    assert any(c.rule == "INVARIANT_REMOVED" for c in result.breaking)


def test_invariant_severity_downgraded_is_breaking() -> None:
    old_inv = [InvariantSpec(**{"id": "INV-001", "assert": "cost_usd < 0.10", "severity": "error"})]
    new_inv = [InvariantSpec(**{"id": "INV-001", "assert": "cost_usd < 0.10", "severity": "warn"})]
    old = _spec("1.0.0", invariants=old_inv)
    new = _spec("2.0.0", invariants=new_inv)
    result = diff(old, new)
    assert any(c.rule == "INVARIANT_SEVERITY_DOWNGRADED" for c in result.breaking)


def test_invariant_added_is_non_breaking() -> None:
    inv = [InvariantSpec(**{"id": "INV-001", "assert": "cost_usd < 0.10", "severity": "error"})]
    old = _spec("1.0.0", invariants=None)
    new = _spec("1.1.0", invariants=inv)
    result = diff(old, new)
    assert any(c.rule == "INVARIANT_ADDED" for c in result.non_breaking)


def test_both_deny_none_is_noop() -> None:
    old = _spec("1.0.0", deny_tools=None)
    new = _spec("1.0.1", deny_tools=None)
    result = diff(old, new)
    assert result.semver_verdict == "none"


def test_semver_verdict_major_beats_minor() -> None:
    # Has both a breaking change and a non-breaking change
    old = _spec("1.0.0", tools=["read_files"], deny_tools=None)
    new = _spec("2.0.0", tools=["read_files", "write_files"], deny_tools=["delete_files"])
    result = diff(old, new)
    assert result.semver_verdict == "major"
