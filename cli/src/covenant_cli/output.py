from __future__ import annotations

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# stdout -- reports, success panels
console = Console()
# stderr -- errors, warnings (allows `covenant validate spec.yaml | grep X` to work)
err_console = Console(stderr=True)


def success_panel(title: str, body_lines: list[str] | None = None) -> None:
    """Render a green success panel to stdout.

    Args:
        title: Panel title text.
        body_lines: Optional lines shown inside the panel.
    """
    body = "\n".join(body_lines) if body_lines else ""
    console.print(Panel(body, title=f"[bold green]{title}[/]", border_style="green"))


def error_panel(message: str, hint: str | None = None) -> None:
    """Render a red error panel to stderr.

    Args:
        message: Error description.
        hint: Optional actionable hint shown in dim style below the message.
    """
    body = message
    if hint:
        body += f"\n[dim]{hint}[/dim]"
    err_console.print(Panel(body, title="[bold red]Error[/]", border_style="red"))


def issues_table(issues: list) -> None:  # list[LintIssue] -- avoid circular import
    """Render a LintIssue list as a table to stderr.

    Args:
        issues: List of LintIssue objects.
    """
    table = Table(box=box.SIMPLE, show_header=True)
    table.add_column("level", style="bold")
    table.add_column("code")
    table.add_column("field")
    table.add_column("message")

    errors = 0
    warns = 0
    for issue in issues:
        level_style = "red" if issue.level == "error" else "yellow"
        table.add_row(
            f"[{level_style}]{issue.level}[/{level_style}]",
            issue.code,
            issue.field or "--",
            issue.message,
        )
        if issue.level == "error":
            errors += 1
        else:
            warns += 1

    err_console.print(table)
    err_console.print(f"[dim]{errors} error(s)  {warns} warning(s)[/dim]")


def diff_renderer(result: object) -> None:
    """Render a DiffResult to stdout. Called from diff command and publish 422 handler.

    Args:
        result: A DiffResult instance.
    """
    from covenant_cli.services.diff_engine import DiffResult  # avoid module-level circular

    assert isinstance(result, DiffResult)

    verdict_colors = {
        "major": "red",
        "minor": "yellow",
        "patch": "blue",
        "none": "green",
    }
    color = verdict_colors[result.semver_verdict]
    console.print(
        Panel(
            f"[bold {color}]{result.semver_verdict.upper()} change[/]"
            f"  {result.old_version} -> {result.new_version}",
            border_style=color,
        )
    )

    if result.breaking:
        t = Table(title="Breaking changes", box=box.SIMPLE)
        t.add_column("rule")
        t.add_column("field")
        t.add_column("description")
        for c in result.breaking:
            t.add_row(c.rule, c.field, c.description)
        console.print(t)

    if result.non_breaking:
        t = Table(title="Non-breaking changes", box=box.SIMPLE)
        t.add_column("rule")
        t.add_column("field")
        t.add_column("description")
        for c in result.non_breaking:
            t.add_row(c.rule, c.field, c.description)
        console.print(t)

    console.print(
        f"[dim]{len(result.breaking)} breaking  |  {len(result.non_breaking)} non-breaking[/dim]"
    )


def audit_renderer(report: object) -> None:
    """Render an AuditReport to console/err_console.

    Args:
        report: An AuditReport instance.
    """
    from covenant_cli.services.audit_engine import AuditReport, VersionReport  # avoid circular

    assert isinstance(report, AuditReport)

    for version_key, vr in report.versions.items():
        assert isinstance(vr, VersionReport)
        console.rule(
            f"{version_key}  |  {vr.total_events} invocations"
            f"  |  {vr.first_seen.date()} to {vr.last_seen.date()}"
        )

        # Tools table
        t = Table(title="Tools", box=box.SIMPLE)
        t.add_column("declared")
        t.add_column("observed")
        t.add_column("status")

        all_tools = (vr.declared_tools or set()) | vr.observed_tools
        for tool in sorted(all_tools):
            declared_col = tool if (vr.declared_tools and tool in vr.declared_tools) else "--"
            observed_col = tool if tool in vr.observed_tools else "--"
            if vr.declared_tools is None:
                status = "[dim]no spec[/dim]"
            elif tool in vr.undeclared_tools:
                status = "[yellow]! undeclared[/yellow]"
            elif tool in (vr.unused_tools or set()):
                status = "[dim]unused[/dim]"
            else:
                status = "[green]ok[/green]"
            t.add_row(declared_col, observed_col, status)
        console.print(t)

        # Cost
        max_label = (
            f"declared max: ${vr.declared_max_cost:.2f}"
            if vr.declared_max_cost
            else "no limit declared"
        )
        console.print(f"\n[bold]Cost[/bold] ({max_label})")
        console.print(f"  p50  ${vr.actual_p50_cost:.3f}")
        console.print(f"  p95  ${vr.actual_p95_cost:.3f}")
        console.print(f"  p99  ${vr.actual_p99_cost:.3f}")

        # Latency
        slo_parts = []
        if vr.declared_p95_ms:
            slo_parts.append(f"p95 ≤ {vr.declared_p95_ms}ms")
        if vr.declared_p99_ms:
            slo_parts.append(f"p99 ≤ {vr.declared_p99_ms}ms")
        slo_label = f"SLO: {' | '.join(slo_parts)}" if slo_parts else "no SLO declared"
        console.print(f"\n[bold]Latency[/bold] ({slo_label})")
        console.print(f"  p95  {vr.actual_p95_ms:.0f}ms")
        console.print(f"  p99  {vr.actual_p99_ms:.0f}ms")

        # Violations
        if vr.violation_count:
            breakdown = "  |  ".join(
                f"{k}: {v}" for k, v in vr.violation_breakdown.items()
            )
            console.print(f"\n[red]Violations: {vr.violation_count}[/red]  ({breakdown})")
        else:
            console.print("\n[green]No violations[/green]")

    if report.specless_versions:
        err_console.print(
            f"[yellow]! {len(report.specless_versions)} version(s) observed without a"
            " matching spec -- pass --spec to compare[/yellow]"
        )
