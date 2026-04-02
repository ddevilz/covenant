from datetime import datetime, timezone

from covenant_cli.models.spec import (
    AgentSpec,
    BudgetSpec,
    CapabilitiesSpec,
    ConstraintsSpec,
    CovenantSpec,
    SloSpec,
)
from covenant_cli.services.audit_engine import AuditEvent, analyze


def _event(
    contract: str = "agent@1.0.0",
    outcome: str = "ok",
    tools: list[str] | None = None,
    cost: float = 0.05,
    duration: int = 1000,
    code: str | None = None,
    model: str | None = None,
) -> AuditEvent:
    return AuditEvent(
        contract=contract,
        outcome=outcome,  # type: ignore[arg-type]
        tool_calls=tools or ["read_files"],
        cost_usd=cost,
        duration_ms=duration,
        occurred_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        violation_code=code,
        model_used=model,
    )


def _spec() -> CovenantSpec:
    return CovenantSpec(
        covenant="1.0",
        agent=AgentSpec(name="agent", version="1.0.0", runtime="python"),
        capabilities=CapabilitiesSpec(tools=["read_files", "call_llm"]),
        constraints=ConstraintsSpec(budget=BudgetSpec(max_cost_usd=0.10)),
        slo=SloSpec(latency_p95_ms=2000, latency_p99_ms=5000),
    )


def test_basic_report() -> None:
    events = [_event(), _event()]
    report = analyze(events, _spec())
    assert "agent@1.0.0" in report.versions
    vr = report.versions["agent@1.0.0"]
    assert vr.total_events == 2
    assert "read_files" in vr.observed_tools


def test_undeclared_tool_detected() -> None:
    events = [_event(tools=["read_files", "write_files"])]
    report = analyze(events, _spec())
    vr = report.versions["agent@1.0.0"]
    assert "write_files" in vr.undeclared_tools


def test_unused_tool_detected() -> None:
    events = [_event(tools=["read_files"])]  # call_llm never used
    report = analyze(events, _spec())
    vr = report.versions["agent@1.0.0"]
    assert "call_llm" in vr.unused_tools


def test_specless_mode() -> None:
    events = [_event()]
    report = analyze(events, None)
    vr = report.versions["agent@1.0.0"]
    assert vr.declared_tools is None
    assert "agent@1.0.0" in report.specless_versions


def test_violation_breakdown() -> None:
    events = [
        _event(outcome="violation", code="BUDGET_EXCEEDED"),
        _event(outcome="violation", code="BUDGET_EXCEEDED"),
        _event(outcome="violation", code="UNDECLARED_TOOL"),
    ]
    report = analyze(events, _spec())
    vr = report.versions["agent@1.0.0"]
    assert vr.violation_count == 3
    assert vr.violation_breakdown["BUDGET_EXCEEDED"] == 2
    assert vr.violation_breakdown["UNDECLARED_TOOL"] == 1


def test_percentile_computation() -> None:
    # 100 events with ascending costs
    events = [_event(cost=i * 0.001, duration=i * 10) for i in range(1, 101)]
    report = analyze(events, _spec())
    vr = report.versions["agent@1.0.0"]
    assert 0.045 < vr.actual_p50_cost < 0.055
    assert 0.090 < vr.actual_p95_cost < 0.100
