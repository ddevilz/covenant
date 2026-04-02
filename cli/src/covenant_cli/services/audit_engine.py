from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Literal

from pydantic import BaseModel

from covenant_cli.models.spec import CovenantSpec


class AuditEvent(BaseModel):
    """A single audit event emitted by the SDK runtime."""

    contract: str  # "name@version"
    outcome: Literal["ok", "violation", "slo_breach", "invariant_warn"]
    tool_calls: list[str]
    cost_usd: float
    duration_ms: int
    occurred_at: datetime
    violation_code: str | None = None
    model_used: str | None = None


@dataclass
class VersionReport:
    """Per-version declared-vs-observed analysis."""

    contract: str
    total_events: int
    first_seen: datetime
    last_seen: datetime

    # Tool analysis
    declared_tools: set[str] | None  # None when no spec is available
    observed_tools: set[str]
    undeclared_tools: set[str]
    unused_tools: set[str]

    # Cost analysis
    declared_max_cost: float | None
    actual_p50_cost: float
    actual_p95_cost: float
    actual_p99_cost: float

    # Latency analysis
    actual_p50_ms: float
    actual_p95_ms: float
    actual_p99_ms: float
    declared_p95_ms: int | None
    declared_p99_ms: int | None

    # Violations
    violation_count: int
    violation_breakdown: dict[str, int]
    slo_breaches: list[str]


@dataclass
class AuditReport:
    """Aggregate report across all contract versions seen in the log."""

    versions: dict[str, VersionReport]
    total_events: int
    specless_versions: list[str]


def _percentile(values: list[float], p: float) -> float:
    """Compute percentile using sorted-list approach (no numpy).

    Args:
        values: List of numeric values.
        p: Percentile fraction, e.g. 0.95 for p95.

    Returns:
        The percentile value, or 0.0 for an empty list.
    """
    if not values:
        return 0.0
    s = sorted(values)
    idx = min(int(p * len(s)), len(s) - 1)
    return s[idx]


def analyze(
    events: Iterable[AuditEvent], spec: CovenantSpec | None
) -> AuditReport:
    """Compute declared-vs-observed analysis from audit events.

    Groups events by contract field ("name@version"). Computes declared-vs-observed
    gap per version separately. When spec is None, produces observed-only report.

    Args:
        events: Iterable of AuditEvent objects.
        spec: Optional CovenantSpec for declared comparison.
              None = specless mode (declared columns are empty).

    Returns:
        AuditReport grouped by contract version.
    """
    by_version: dict[str, list[AuditEvent]] = {}
    for ev in events:
        by_version.setdefault(ev.contract, []).append(ev)

    declared_tools = set(spec.capabilities.tools) if spec else None
    declared_max_cost = (
        spec.constraints.budget.max_cost_usd
        if spec and spec.constraints.budget
        else None
    )
    declared_p95_ms = spec.slo.latency_p95_ms if spec and spec.slo else None
    declared_p99_ms = spec.slo.latency_p99_ms if spec and spec.slo else None

    versions: dict[str, VersionReport] = {}
    specless: list[str] = []

    for version_key, evs in by_version.items():
        if spec is None:
            specless.append(version_key)

        observed: set[str] = set()
        for ev in evs:
            observed.update(ev.tool_calls)

        undeclared = observed - declared_tools if declared_tools is not None else set()
        unused = declared_tools - observed if declared_tools is not None else set()

        costs = [ev.cost_usd for ev in evs]
        durations = [float(ev.duration_ms) for ev in evs]
        timestamps = [ev.occurred_at for ev in evs]

        violations = [ev for ev in evs if ev.outcome == "violation"]
        breakdown: dict[str, int] = {}
        for ev in violations:
            if ev.violation_code:
                breakdown[ev.violation_code] = breakdown.get(ev.violation_code, 0) + 1

        versions[version_key] = VersionReport(
            contract=version_key,
            total_events=len(evs),
            first_seen=min(timestamps),
            last_seen=max(timestamps),
            declared_tools=declared_tools,
            observed_tools=observed,
            undeclared_tools=undeclared,
            unused_tools=unused,
            declared_max_cost=declared_max_cost,
            actual_p50_cost=_percentile(costs, 0.50),
            actual_p95_cost=_percentile(costs, 0.95),
            actual_p99_cost=_percentile(costs, 0.99),
            actual_p50_ms=_percentile(durations, 0.50),
            actual_p95_ms=_percentile(durations, 0.95),
            actual_p99_ms=_percentile(durations, 0.99),
            declared_p95_ms=declared_p95_ms,
            declared_p99_ms=declared_p99_ms,
            violation_count=len(violations),
            violation_breakdown=breakdown,
            slo_breaches=[],
        )

    return AuditReport(
        versions=versions,
        total_events=sum(len(v) for v in by_version.values()),
        specless_versions=specless,
    )
