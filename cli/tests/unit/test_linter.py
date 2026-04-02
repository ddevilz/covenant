from covenant_cli.models.spec import (
    AgentSpec,
    BudgetSpec,
    CapabilitiesSpec,
    ConstraintsSpec,
    CovenantSpec,
    ProvenanceSpec,
)
from covenant_cli.services.linter import lint


def _base_spec(**overrides) -> CovenantSpec:  # type: ignore[no-untyped-def]
    defaults: dict = dict(
        covenant="1.0",
        agent=AgentSpec(name="test-agent", version="1.0.0", runtime="python"),
        capabilities=CapabilitiesSpec(tools=["read_files"]),
        constraints=ConstraintsSpec(budget=BudgetSpec(max_cost_usd=0.10)),
    )
    defaults.update(overrides)
    return CovenantSpec(**defaults)


def test_clean_spec_returns_empty() -> None:
    assert lint(_base_spec()) == []


def test_empty_tools_list() -> None:
    spec = _base_spec(capabilities=CapabilitiesSpec(tools=[]))
    issues = lint(spec)
    codes = [i.code for i in issues]
    assert "EMPTY_TOOLS_LIST" in codes
    assert any(i.level == "error" for i in issues if i.code == "EMPTY_TOOLS_LIST")


def test_deny_overlap() -> None:
    spec = _base_spec(
        capabilities=CapabilitiesSpec(tools=["read_files", "write_files"]),
        constraints=ConstraintsSpec(
            deny_tools=["write_files"],
            budget=BudgetSpec(max_cost_usd=0.10),
        ),
    )
    issues = lint(spec)
    codes = [i.code for i in issues]
    assert "DENY_OVERLAP" in codes
    assert any(i.level == "error" for i in issues if i.code == "DENY_OVERLAP")


def test_missing_budget() -> None:
    spec = _base_spec(constraints=ConstraintsSpec())
    issues = lint(spec)
    codes = [i.code for i in issues]
    assert "MISSING_BUDGET" in codes
    assert any(i.level == "error" for i in issues if i.code == "MISSING_BUDGET")


def test_provenance_algo_invalid() -> None:
    # Use model_construct to bypass Literal validation — tests belt-and-suspenders path
    prov = ProvenanceSpec.model_construct(author="test", algorithm=None)
    spec = _base_spec()
    spec = spec.model_copy(update={"provenance": prov})
    issues = lint(spec)
    codes = [i.code for i in issues]
    assert "PROVENANCE_ALGO_INVALID" in codes
    assert any(i.level == "warn" for i in issues if i.code == "PROVENANCE_ALGO_INVALID")


def test_undeclared_deny_warns() -> None:
    spec = _base_spec(
        capabilities=CapabilitiesSpec(tools=["read_files"]),
        constraints=ConstraintsSpec(
            deny_tools=["delete_files"],  # not in capabilities.tools
            budget=BudgetSpec(max_cost_usd=0.10),
        ),
    )
    issues = lint(spec)
    codes = [i.code for i in issues]
    assert "UNDECLARED_DENY" in codes
    assert any(i.level == "warn" for i in issues if i.code == "UNDECLARED_DENY")


def test_lint_issue_has_field() -> None:
    spec = _base_spec(capabilities=CapabilitiesSpec(tools=[]))
    issues = lint(spec)
    assert any(i.field == "capabilities.tools" for i in issues)
