# Covenant CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `covenant` CLI binary — seven subcommands for working with `.covenant.yaml` behavioral contract files, starting with `validate` as the Show HN moment.

**Architecture:** Thin Typer commands + pure-Python service layer in `services/`. All business logic is in `services/` (unit-testable without Typer). Pydantic `CovenantSpec` models in `models/`. Shared rich rendering in `output.py`.

**Tech Stack:** Python 3.12, Typer, PyYAML, jsonschema 4.x, Pydantic v2, cryptography (Ed25519), rich, httpx, openai SDK

---

## File Map

| File | Purpose |
|---|---|
| `cli/pyproject.toml` | Package config, deps, `covenant` entry point |
| `cli/src/covenant_cli/__init__.py` | Package marker |
| `cli/src/covenant_cli/main.py` | Typer app, registers all commands |
| `cli/src/covenant_cli/errors.py` | Exit code constants + `CliError` dataclass |
| `cli/src/covenant_cli/output.py` | rich Console + all shared renderers |
| `cli/src/covenant_cli/models/__init__.py` | Package marker |
| `cli/src/covenant_cli/models/spec.py` | All Pydantic models for CovenantSpec |
| `cli/src/covenant_cli/models/spec_loader.py` | 4-phase YAML→schema→Pydantic loader |
| `cli/src/covenant_cli/data/covenant.schema.json` | Bundled copy of spec/covenant.schema.json |
| `cli/src/covenant_cli/services/__init__.py` | Package marker |
| `cli/src/covenant_cli/services/linter.py` | Principle linting rules |
| `cli/src/covenant_cli/services/diff_engine.py` | Breaking change detection + semver verdict |
| `cli/src/covenant_cli/services/audit_engine.py` | Declared vs observed analysis |
| `cli/src/covenant_cli/services/generator.py` | Static analysis + optional LLM enhancement |
| `cli/src/covenant_cli/commands/__init__.py` | Package marker |
| `cli/src/covenant_cli/commands/validate.py` | `covenant validate` command |
| `cli/src/covenant_cli/commands/init.py` | `covenant init` command |
| `cli/src/covenant_cli/commands/sign.py` | `covenant sign` command |
| `cli/src/covenant_cli/commands/diff.py` | `covenant diff` command |
| `cli/src/covenant_cli/commands/generate.py` | `covenant generate` command |
| `cli/src/covenant_cli/commands/publish.py` | `covenant publish` command |
| `cli/src/covenant_cli/commands/audit.py` | `covenant audit` command |
| `cli/tests/conftest.py` | Temp dirs + spec fixtures |
| `cli/tests/unit/test_spec_loader.py` | Unit tests: loader 4 phases |
| `cli/tests/unit/test_linter.py` | Unit tests: each lint rule |
| `cli/tests/unit/test_diff_engine.py` | Unit tests: each diff rule |
| `cli/tests/unit/test_audit_engine.py` | Unit tests: declared vs observed |
| `cli/tests/unit/test_generator.py` | Unit tests: static analysis + LLM merge |
| `cli/tests/integration/fixtures/valid.covenant.yaml` | Valid spec for integration tests |
| `cli/tests/integration/fixtures/missing_budget.covenant.yaml` | Triggers MISSING_BUDGET lint error |
| `cli/tests/integration/fixtures/deny_overlap.covenant.yaml` | Triggers DENY_OVERLAP lint error |
| `cli/tests/integration/fixtures/no_tools.covenant.yaml` | Triggers EMPTY_TOOLS_LIST lint error |
| `cli/tests/integration/fixtures/unsigned.covenant.yaml` | Valid spec without provenance block |
| `cli/tests/integration/test_validate.py` | CLI end-to-end validate tests |
| `cli/tests/integration/test_sign.py` | CLI sign + verify round trip |
| `cli/tests/integration/test_diff.py` | CLI diff output + --fail-on-breaking |
| `cli/tests/integration/test_audit.py` | CLI audit output + --spec flag |

---

## Task 1: Project scaffold + errors.py + output.py

**Files:**
- Create: `cli/pyproject.toml`
- Create: `cli/src/covenant_cli/__init__.py`
- Create: `cli/src/covenant_cli/main.py`
- Create: `cli/src/covenant_cli/errors.py`
- Create: `cli/src/covenant_cli/output.py`
- Create: `cli/src/covenant_cli/commands/__init__.py`
- Create: `cli/src/covenant_cli/models/__init__.py`
- Create: `cli/src/covenant_cli/services/__init__.py`
- Create: `cli/src/covenant_cli/data/covenant.schema.json` (copy)

- [ ] **Step 1: Create pyproject.toml**

```toml
[project]
name = "covenant-cli"
version = "0.1.0"
description = "Behavioral contract CLI for AI agents"
requires-python = ">=3.12"
dependencies = [
    "typer[all]>=0.12",
    "pyyaml>=6.0",
    "jsonschema>=4.0",
    "pydantic>=2.0",
    "cryptography>=42.0",
    "rich>=13.0",
    "httpx>=0.27",
    "openai>=1.30",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "mypy>=1.9",
    "ruff>=0.4",
]

[project.scripts]
covenant = "covenant_cli.main:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/covenant_cli"]

[tool.ruff]
target-version = "py312"
line-length = 88

[tool.mypy]
strict = true
python_version = "3.12"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

Save as `cli/pyproject.toml`.

- [ ] **Step 2: Create package markers and data directory**

```bash
mkdir -p cli/src/covenant_cli/commands
mkdir -p cli/src/covenant_cli/models
mkdir -p cli/src/covenant_cli/services
mkdir -p cli/src/covenant_cli/data
mkdir -p cli/tests/unit
mkdir -p cli/tests/integration/fixtures
touch cli/src/covenant_cli/__init__.py
touch cli/src/covenant_cli/commands/__init__.py
touch cli/src/covenant_cli/models/__init__.py
touch cli/src/covenant_cli/services/__init__.py
touch cli/tests/__init__.py
touch cli/tests/unit/__init__.py
touch cli/tests/integration/__init__.py
```

- [ ] **Step 3: Copy covenant.schema.json**

```bash
cp spec/covenant.schema.json cli/src/covenant_cli/data/covenant.schema.json
```

Then add `llm_enhanced` to the `metadata.properties` block in `cli/src/covenant_cli/data/covenant.schema.json`:

```json
"llm_enhanced": {
  "type": "boolean",
  "description": "Set by covenant generate when LLM enhancement phase ran"
}
```

(Add this entry inside `"metadata": { "properties": { ... } }`)

- [ ] **Step 4: Write errors.py**

```python
# cli/src/covenant_cli/errors.py
from dataclasses import dataclass
from typing import Literal

EXIT_OK = 0
EXIT_VALIDATION = 1
EXIT_NOT_FOUND = 2
EXIT_SIGNING = 3
EXIT_NETWORK = 4


@dataclass
class SpecLoadError(Exception):
    """Raised by spec_loader when any load phase fails."""
    phase: Literal["file", "yaml", "schema", "model"]
    path: object  # Path
    issues: list[str]
    exit_code: int


@dataclass
class CliError(Exception):
    """Raised by command handlers for user-facing errors."""
    message: str
    exit_code: int
    hint: str | None = None
```

- [ ] **Step 5: Write output.py**

```python
# cli/src/covenant_cli/output.py
from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

console = Console()
err_console = Console(stderr=True)


def success_panel(title: str, body_lines: list[str] | None = None) -> None:
    body = "\n".join(body_lines) if body_lines else ""
    console.print(Panel(body, title=f"[bold green]{title}[/]", border_style="green"))


def error_panel(message: str, hint: str | None = None) -> None:
    body = message
    if hint:
        body += f"\n[dim]{hint}[/dim]"
    err_console.print(Panel(body, title="[bold red]Error[/]", border_style="red"))


def issues_table(issues: list) -> None:
    """Render LintIssue list to stderr."""
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
            issue.field or "—",
            issue.message,
        )
        if issue.level == "error":
            errors += 1
        else:
            warns += 1

    err_console.print(table)
    err_console.print(f"[dim]{errors} error(s)  {warns} warning(s)[/dim]")


def diff_renderer(result: object) -> None:
    """Render DiffResult. Called from diff command and publish 422 handler."""
    from covenant_cli.services.diff_engine import DiffResult  # avoid circular

    assert isinstance(result, DiffResult)

    verdict_colors = {"major": "red", "minor": "yellow", "patch": "blue", "none": "green"}
    color = verdict_colors[result.semver_verdict]
    console.print(
        Panel(
            f"[bold {color}]{result.semver_verdict.upper()} change[/]"
            f"  {result.old_version} → {result.new_version}",
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
        f"[dim]{len(result.breaking)} breaking  ·  {len(result.non_breaking)} non-breaking[/dim]"
    )


def audit_renderer(report: object) -> None:
    """Render AuditReport to console/err_console."""
    from covenant_cli.services.audit_engine import AuditReport, VersionReport

    assert isinstance(report, AuditReport)

    for version_key, vr in report.versions.items():
        assert isinstance(vr, VersionReport)
        console.rule(
            f"{version_key}  ·  {vr.total_events} invocations"
            f"  ·  {vr.first_seen.date()} → {vr.last_seen.date()}"
        )

        # Tools table
        t = Table(title="Tools", box=box.SIMPLE)
        t.add_column("declared")
        t.add_column("observed")
        t.add_column("status")

        all_tools = (vr.declared_tools or set()) | vr.observed_tools
        for tool in sorted(all_tools):
            declared = tool if (vr.declared_tools and tool in vr.declared_tools) else "—"
            observed = tool if tool in vr.observed_tools else "—"
            if vr.declared_tools is None:
                status = "[dim]no spec[/dim]"
            elif tool in vr.undeclared_tools:
                status = "[yellow]⚠ undeclared[/yellow]"
            elif tool in (vr.unused_tools or set()):
                status = "[dim]unused[/dim]"
            else:
                status = "[green]✓[/green]"
            t.add_row(declared, observed, status)
        console.print(t)

        # Cost
        max_label = f"declared max: ${vr.declared_max_cost:.2f}" if vr.declared_max_cost else "no limit declared"
        console.print(f"\n[bold]Cost[/bold] ({max_label})")
        console.print(f"  p50  ${vr.actual_p50_cost:.3f}")
        console.print(f"  p95  ${vr.actual_p95_cost:.3f}")
        console.print(f"  p99  ${vr.actual_p99_cost:.3f}")

        # Latency
        slo_label = (
            f"SLO: p95 ≤ {vr.declared_p95_ms}ms · p99 ≤ {vr.declared_p99_ms}ms"
            if vr.declared_p95_ms or vr.declared_p99_ms
            else "no SLO declared"
        )
        console.print(f"\n[bold]Latency[/bold] ({slo_label})")
        console.print(f"  p95  {vr.actual_p95_ms:.0f}ms")
        console.print(f"  p99  {vr.actual_p99_ms:.0f}ms")

        # Violations
        if vr.violation_count:
            breakdown = "  ·  ".join(f"{k}: {v}" for k, v in vr.violation_breakdown.items())
            console.print(f"\n[red]Violations: {vr.violation_count}[/red]  ({breakdown})")
        else:
            console.print("\n[green]No violations[/green]")

    if report.specless_versions:
        err_console.print(
            f"[yellow]⚠ {len(report.specless_versions)} version(s) observed without a matching spec — pass --spec to compare[/yellow]"
        )
```

- [ ] **Step 6: Write main.py**

```python
# cli/src/covenant_cli/main.py
import typer

app = typer.Typer(name="covenant", help="Behavioral contract CLI for AI agents.")


def _register_commands() -> None:
    from covenant_cli.commands import (
        init, validate, sign, diff, generate, publish, audit
    )
    app.command("init")(init.init_cmd)
    app.command("validate")(validate.validate_cmd)
    app.command("sign")(sign.sign_cmd)
    app.command("diff")(diff.diff_cmd)
    app.command("generate")(generate.generate_cmd)
    app.command("publish")(publish.publish_cmd)
    app.command("audit")(audit.audit_cmd)


_register_commands()


if __name__ == "__main__":
    app()
```

- [ ] **Step 7: Install in dev mode and verify entry point works**

```bash
cd cli && pip install -e ".[dev]"
covenant --help
```

Expected output: help text listing all seven subcommands.

- [ ] **Step 8: Commit**

```bash
git add cli/
git commit -m "feat(cli): scaffold package, errors.py, output.py, main.py"
```

---

## Task 2: CovenantSpec models (models/spec.py + models/spec_loader.py)

**Files:**
- Create: `cli/src/covenant_cli/models/spec.py`
- Create: `cli/src/covenant_cli/models/spec_loader.py`
- Test: `cli/tests/unit/test_spec_loader.py`

- [ ] **Step 1: Write failing tests for spec_loader**

```python
# cli/tests/unit/test_spec_loader.py
import pytest
from pathlib import Path
from covenant_cli.models.spec_loader import load_spec
from covenant_cli.errors import SpecLoadError

FIXTURES = Path(__file__).parent.parent / "integration" / "fixtures"

def test_load_valid_spec(tmp_path):
    yaml_text = """
covenant: "1.0"
agent:
  name: code-reviewer
  version: "1.0.0"
  runtime: python
capabilities:
  tools:
    - read_files
constraints:
  budget:
    max_cost_usd: 0.10
"""
    p = tmp_path / "valid.covenant.yaml"
    p.write_text(yaml_text)
    spec = load_spec(p)
    assert spec.agent.name == "code-reviewer"
    assert spec.agent.version == "1.0.0"
    assert spec.capabilities.tools == ["read_files"]

def test_load_missing_file(tmp_path):
    with pytest.raises(SpecLoadError) as exc_info:
        load_spec(tmp_path / "nonexistent.yaml")
    assert exc_info.value.phase == "file"
    assert exc_info.value.exit_code == 2

def test_load_invalid_yaml(tmp_path):
    p = tmp_path / "bad.yaml"
    p.write_text("covenant: [\nbroken yaml")
    with pytest.raises(SpecLoadError) as exc_info:
        load_spec(p)
    assert exc_info.value.phase == "yaml"
    assert exc_info.value.exit_code == 1

def test_load_schema_violation(tmp_path):
    # missing required 'constraints' key
    p = tmp_path / "no_constraints.yaml"
    p.write_text("""
covenant: "1.0"
agent:
  name: test-agent
  version: "1.0.0"
  runtime: python
capabilities:
  tools: [read_files]
""")
    with pytest.raises(SpecLoadError) as exc_info:
        load_spec(p)
    assert exc_info.value.phase == "schema"
    assert len(exc_info.value.issues) >= 1

def test_schema_collects_all_errors(tmp_path):
    # both 'agent' and 'constraints' missing — should report both, not just first
    p = tmp_path / "multi_err.yaml"
    p.write_text("""
covenant: "1.0"
capabilities:
  tools: [read_files]
""")
    with pytest.raises(SpecLoadError) as exc_info:
        load_spec(p)
    assert exc_info.value.phase == "schema"
    assert len(exc_info.value.issues) >= 2

def test_load_invalid_agent_name(tmp_path):
    p = tmp_path / "bad_name.yaml"
    p.write_text("""
covenant: "1.0"
agent:
  name: "Bad Name With Spaces"
  version: "1.0.0"
  runtime: python
capabilities:
  tools: [read_files]
constraints:
  budget:
    max_cost_usd: 0.10
""")
    with pytest.raises(SpecLoadError) as exc_info:
        load_spec(p)
    assert exc_info.value.phase == "schema"

def test_assert_field_alias(tmp_path):
    """InvariantSpec.assert_expr must parse from 'assert' key in YAML."""
    p = tmp_path / "with_inv.yaml"
    p.write_text("""
covenant: "1.0"
agent:
  name: test-agent
  version: "1.0.0"
  runtime: python
capabilities:
  tools: [read_files]
constraints:
  budget:
    max_cost_usd: 0.10
invariants:
  - id: INV-001
    description: cost check
    assert: cost_usd < 0.10
    severity: error
""")
    spec = load_spec(p)
    assert spec.invariants is not None
    assert spec.invariants[0].assert_expr == "cost_usd < 0.10"
    assert spec.invariants[0].id == "INV-001"
```

- [ ] **Step 2: Run tests — confirm they fail**

```bash
cd cli && pytest tests/unit/test_spec_loader.py -v
```

Expected: `ModuleNotFoundError` or similar — spec_loader not yet written.

- [ ] **Step 3: Write models/spec.py**

```python
# cli/src/covenant_cli/models/spec.py
from __future__ import annotations
from typing import Literal
from datetime import datetime
from pydantic import AnyUrl, BaseModel, ConfigDict, Field


class AgentSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    version: str
    runtime: Literal["python", "typescript", "any"]
    display_name: str | None = None
    entrypoint: str | None = None


class ModelAllowSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: str
    model: str
    max_tokens: int | None = None


class CapabilitiesSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tools: list[str]
    models: list[ModelAllowSpec] | None = None
    external_services: list[str] | None = None


class NetworkSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    egress: bool | Literal["scoped"]
    allowed_domains: list[str] | None = None


class FilesystemSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    read: list[str] | None = None
    write: list[str] | None = None


class ScopeSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    file_patterns: list[str] | None = None
    max_file_size_kb: int | None = None
    max_calls_per_invocation: int | None = None


class BudgetSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    max_cost_usd: float


class ConstraintsSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    deny_tools: list[str] | None = None
    network: NetworkSpec | None = None
    filesystem: FilesystemSpec | None = None
    scope: ScopeSpec | None = None
    budget: BudgetSpec | None = None


class InvariantSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    id: str
    description: str | None = None
    assert_expr: str = Field(alias="assert")
    severity: Literal["error", "warn"]


class ProtocolEndpointSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema: str
    required: bool = True


class ProtocolErrorSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema: str


class ProtocolsSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    input: ProtocolEndpointSpec | None = None
    output: ProtocolEndpointSpec | None = None
    errors: ProtocolErrorSpec | None = None


class SloSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    latency_p95_ms: int | None = None
    latency_p99_ms: int | None = None
    cost_per_call_usd_max: float | None = None
    error_rate_max_pct: float | None = None
    calls_per_minute_max: int | None = None


class ProvenanceSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    author: str | None = None
    signed_at: datetime | None = None
    algorithm: Literal["Ed25519"] | None = None
    public_key: str | None = None
    signature: str | None = None


class MetadataSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    description: str | None = None
    tags: list[str] | None = None
    homepage: AnyUrl | None = None
    license: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    llm_enhanced: bool | None = None


class CovenantSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    covenant: Literal["1.0"]
    agent: AgentSpec
    capabilities: CapabilitiesSpec
    constraints: ConstraintsSpec
    invariants: list[InvariantSpec] | None = None
    protocols: ProtocolsSpec | None = None
    slo: SloSpec | None = None
    provenance: ProvenanceSpec | None = None
    metadata: MetadataSpec | None = None
```

- [ ] **Step 4: Write models/spec_loader.py**

```python
# cli/src/covenant_cli/models/spec_loader.py
from __future__ import annotations

import importlib.resources
import json
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft7Validator
from pydantic import ValidationError

from covenant_cli.errors import SpecLoadError
from covenant_cli.models.spec import CovenantSpec

_schema: dict[str, Any] | None = None


def _get_schema() -> dict[str, Any]:
    global _schema
    if _schema is None:
        data = importlib.resources.files("covenant_cli.data").joinpath("covenant.schema.json")
        _schema = json.loads(data.read_text(encoding="utf-8"))
    return _schema


def load_spec(path: Path) -> CovenantSpec:
    """Load and validate a .covenant.yaml file through four sequential phases.

    Args:
        path: Path to the .covenant.yaml file.

    Returns:
        A fully-validated CovenantSpec instance.

    Raises:
        SpecLoadError: On any phase failure, with all issues collected for that phase.
    """
    # Phase 1 — FILE
    if not path.exists():
        raise SpecLoadError(phase="file", path=path, issues=[f"File not found: {path}"], exit_code=2)
    if not path.is_file():
        raise SpecLoadError(phase="file", path=path, issues=[f"Not a file: {path}"], exit_code=2)

    text = path.read_text(encoding="utf-8")

    # Phase 2 — YAML
    try:
        raw: Any = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise SpecLoadError(phase="yaml", path=path, issues=[str(e)], exit_code=1) from e

    if not isinstance(raw, dict):
        raise SpecLoadError(
            phase="yaml", path=path,
            issues=["YAML must be a mapping at the top level"],
            exit_code=1,
        )

    # Phase 3 — SCHEMA
    schema = _get_schema()
    validator = Draft7Validator(schema)
    errors = sorted(validator.iter_errors(raw), key=lambda e: list(e.path))
    if errors:
        issues = [f"{'.'.join(str(p) for p in e.path) or '<root>'}: {e.message}" for e in errors]
        raise SpecLoadError(phase="schema", path=path, issues=issues, exit_code=1)

    # Phase 4 — MODEL
    try:
        return CovenantSpec.model_validate(raw)
    except ValidationError as e:
        issues = [f"{err['loc']}: {err['msg']}" for err in e.errors()]
        raise SpecLoadError(phase="model", path=path, issues=issues, exit_code=1) from e
```

- [ ] **Step 5: Run tests — confirm they pass**

```bash
cd cli && pytest tests/unit/test_spec_loader.py -v
```

Expected: all 7 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add cli/src/covenant_cli/models/ cli/tests/unit/test_spec_loader.py
git commit -m "feat(cli): CovenantSpec pydantic models + 4-phase spec_loader"
```

---

## Task 3: services/linter.py

**Files:**
- Create: `cli/src/covenant_cli/services/linter.py`
- Test: `cli/tests/unit/test_linter.py`

- [ ] **Step 1: Write failing tests**

```python
# cli/tests/unit/test_linter.py
import pytest
from covenant_cli.models.spec import (
    CovenantSpec, AgentSpec, CapabilitiesSpec, ConstraintsSpec, BudgetSpec,
    InvariantSpec, ProvenanceSpec
)
from covenant_cli.services.linter import lint, LintIssue


def _base_spec(**overrides) -> CovenantSpec:
    defaults = dict(
        covenant="1.0",
        agent=AgentSpec(name="test-agent", version="1.0.0", runtime="python"),
        capabilities=CapabilitiesSpec(tools=["read_files"]),
        constraints=ConstraintsSpec(budget=BudgetSpec(max_cost_usd=0.10)),
    )
    defaults.update(overrides)
    return CovenantSpec(**defaults)


def test_clean_spec_returns_empty():
    assert lint(_base_spec()) == []


def test_empty_tools_list():
    spec = _base_spec(capabilities=CapabilitiesSpec(tools=[]))
    issues = lint(spec)
    codes = [i.code for i in issues]
    assert "EMPTY_TOOLS_LIST" in codes
    assert any(i.level == "error" for i in issues if i.code == "EMPTY_TOOLS_LIST")


def test_deny_overlap():
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


def test_missing_budget():
    spec = _base_spec(constraints=ConstraintsSpec())
    issues = lint(spec)
    codes = [i.code for i in issues]
    assert "MISSING_BUDGET" in codes
    assert any(i.level == "error" for i in issues if i.code == "MISSING_BUDGET")


def test_provenance_algo_invalid():
    from covenant_cli.models.spec import ProvenanceSpec
    # Use model_construct to bypass Literal validation for test purposes
    prov = ProvenanceSpec.model_construct(algorithm=None, author="test")
    # Actually test via a spec where provenance block is present but algorithm missing
    # We test the lint rule: provenance present but algorithm != "Ed25519"
    # Since schema enforces Ed25519, we test the belt-and-suspenders path via model_construct
    prov2 = ProvenanceSpec.model_construct(author="test", algorithm=None)
    spec = _base_spec()
    spec = spec.model_copy(update={"provenance": prov2})
    issues = lint(spec)
    # provenance present but no algorithm set — should warn
    codes = [i.code for i in issues]
    assert "PROVENANCE_ALGO_INVALID" in codes
    assert any(i.level == "warn" for i in issues if i.code == "PROVENANCE_ALGO_INVALID")


def test_undeclared_deny_warns():
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


def test_lint_issue_has_field():
    spec = _base_spec(capabilities=CapabilitiesSpec(tools=[]))
    issues = lint(spec)
    assert any(i.field == "capabilities.tools" for i in issues)
```

- [ ] **Step 2: Run tests — confirm they fail**

```bash
cd cli && pytest tests/unit/test_linter.py -v
```

Expected: `ModuleNotFoundError` — linter not yet written.

- [ ] **Step 3: Write services/linter.py**

```python
# cli/src/covenant_cli/services/linter.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from covenant_cli.models.spec import CovenantSpec


@dataclass
class LintIssue:
    """A single linting finding."""
    level: Literal["error", "warn"]
    code: str
    field: str | None
    message: str


def lint(spec: CovenantSpec) -> list[LintIssue]:
    """Run principle linting rules against a loaded CovenantSpec.

    Args:
        spec: A fully-validated CovenantSpec.

    Returns:
        List of LintIssues. Empty list means the spec is clean.
    """
    issues: list[LintIssue] = []

    # EMPTY_TOOLS_LIST
    if not spec.capabilities.tools:
        issues.append(LintIssue(
            level="error",
            code="EMPTY_TOOLS_LIST",
            field="capabilities.tools",
            message="capabilities.tools must be non-empty",
        ))

    # DENY_OVERLAP + UNDECLARED_DENY
    if spec.constraints.deny_tools:
        tools_set = set(spec.capabilities.tools)
        deny_set = set(spec.constraints.deny_tools)

        overlap = deny_set & tools_set
        for tool in sorted(overlap):
            issues.append(LintIssue(
                level="error",
                code="DENY_OVERLAP",
                field="constraints.deny_tools",
                message=f'"{tool}" is in both capabilities.tools and constraints.deny_tools',
            ))

        undeclared = deny_set - tools_set
        for tool in sorted(undeclared):
            issues.append(LintIssue(
                level="warn",
                code="UNDECLARED_DENY",
                field="constraints.deny_tools",
                message=f'"{tool}" in deny_tools is not in capabilities.tools',
            ))

    # MISSING_BUDGET
    if spec.constraints.budget is None:
        issues.append(LintIssue(
            level="error",
            code="MISSING_BUDGET",
            field="constraints.budget",
            message="constraints.budget.max_cost_usd is required",
        ))

    # INVARIANT_MISSING_SEV (belt-and-suspenders over schema)
    if spec.invariants:
        for i, inv in enumerate(spec.invariants):
            if not inv.severity:
                issues.append(LintIssue(
                    level="error",
                    code="INVARIANT_MISSING_SEV",
                    field=f"invariants[{i}].severity",
                    message=f'invariant {inv.id} is missing severity',
                ))

    # PROVENANCE_ALGO_INVALID
    if spec.provenance is not None and spec.provenance.algorithm != "Ed25519":
        issues.append(LintIssue(
            level="warn",
            code="PROVENANCE_ALGO_INVALID",
            field="provenance.algorithm",
            message='provenance block present but algorithm is not "Ed25519"',
        ))

    return issues
```

- [ ] **Step 4: Run tests — confirm they pass**

```bash
cd cli && pytest tests/unit/test_linter.py -v
```

Expected: all 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add cli/src/covenant_cli/services/linter.py cli/tests/unit/test_linter.py
git commit -m "feat(cli): linter service with 5 rules"
```

---

## Task 4: covenant validate command (Show HN moment)

**Files:**
- Create: `cli/src/covenant_cli/commands/validate.py`
- Create: `cli/tests/integration/fixtures/valid.covenant.yaml`
- Create: `cli/tests/integration/fixtures/missing_budget.covenant.yaml`
- Create: `cli/tests/integration/fixtures/deny_overlap.covenant.yaml`
- Create: `cli/tests/integration/fixtures/no_tools.covenant.yaml`
- Test: `cli/tests/integration/test_validate.py`

- [ ] **Step 1: Write integration test fixtures**

`cli/tests/integration/fixtures/valid.covenant.yaml`:
```yaml
covenant: "1.0"
agent:
  name: code-reviewer
  version: "1.0.0"
  runtime: python
capabilities:
  tools:
    - read_files
    - call_llm
constraints:
  budget:
    max_cost_usd: 0.10
metadata:
  description: Reviews code for correctness and style
```

`cli/tests/integration/fixtures/missing_budget.covenant.yaml`:
```yaml
covenant: "1.0"
agent:
  name: code-reviewer
  version: "1.0.0"
  runtime: python
capabilities:
  tools:
    - read_files
constraints: {}
```

`cli/tests/integration/fixtures/deny_overlap.covenant.yaml`:
```yaml
covenant: "1.0"
agent:
  name: code-reviewer
  version: "1.0.0"
  runtime: python
capabilities:
  tools:
    - read_files
    - write_files
constraints:
  deny_tools:
    - write_files
  budget:
    max_cost_usd: 0.10
```

`cli/tests/integration/fixtures/no_tools.covenant.yaml`:
```yaml
covenant: "1.0"
agent:
  name: code-reviewer
  version: "1.0.0"
  runtime: python
capabilities:
  tools: []
constraints:
  budget:
    max_cost_usd: 0.10
```

`cli/tests/integration/fixtures/unsigned.covenant.yaml`:
```yaml
covenant: "1.0"
agent:
  name: code-reviewer
  version: "1.0.0"
  runtime: python
capabilities:
  tools:
    - read_files
constraints:
  budget:
    max_cost_usd: 0.10
```

- [ ] **Step 2: Write failing integration tests**

```python
# cli/tests/integration/test_validate.py
from pathlib import Path
from typer.testing import CliRunner
from covenant_cli.main import app

runner = CliRunner()
FIXTURES = Path(__file__).parent / "fixtures"


def test_validate_valid_spec():
    result = runner.invoke(app, ["validate", str(FIXTURES / "valid.covenant.yaml")])
    assert result.exit_code == 0
    assert "PASS" in result.output


def test_validate_missing_file():
    result = runner.invoke(app, ["validate", "/nonexistent/path.yaml"])
    assert result.exit_code == 2


def test_validate_missing_budget():
    result = runner.invoke(app, ["validate", str(FIXTURES / "missing_budget.covenant.yaml")])
    assert result.exit_code == 1
    assert "MISSING_BUDGET" in result.output


def test_validate_deny_overlap():
    result = runner.invoke(app, ["validate", str(FIXTURES / "deny_overlap.covenant.yaml")])
    assert result.exit_code == 1
    assert "DENY_OVERLAP" in result.output


def test_validate_no_tools():
    result = runner.invoke(app, ["validate", str(FIXTURES / "no_tools.covenant.yaml")])
    assert result.exit_code == 1
    assert "EMPTY_TOOLS_LIST" in result.output


def test_validate_no_lint_flag():
    """--no-lint skips linter; missing_budget should pass schema but fail lint.
    With --no-lint it should pass (schema is valid, just lint rule missing)."""
    result = runner.invoke(
        app, ["validate", "--no-lint", str(FIXTURES / "missing_budget.covenant.yaml")]
    )
    # missing_budget.covenant.yaml passes JSON Schema (constraints: {} is valid per schema)
    assert result.exit_code == 0
```

- [ ] **Step 3: Run tests — confirm they fail**

```bash
cd cli && pytest tests/integration/test_validate.py -v
```

Expected: failures because `validate.py` command is not yet written.

- [ ] **Step 4: Write commands/validate.py**

```python
# cli/src/covenant_cli/commands/validate.py
from __future__ import annotations

from pathlib import Path

import typer

from covenant_cli.errors import EXIT_VALIDATION, CliError, SpecLoadError
from covenant_cli.models import spec_loader
from covenant_cli.services import linter
from covenant_cli import output


def validate_cmd(
    path: Path = typer.Argument(..., help="Path to .covenant.yaml"),
    no_lint: bool = typer.Option(False, "--no-lint", help="Skip principle linting"),
) -> None:
    """Validate a .covenant.yaml against the JSON Schema and lint rules."""
    try:
        spec = spec_loader.load_spec(path)
        issues = [] if no_lint else linter.lint(spec)
        if issues:
            output.issues_table(issues)
            raise typer.Exit(EXIT_VALIDATION)
        output.success_panel(f"PASS  {spec.agent.name} {spec.agent.version}")
    except SpecLoadError as e:
        output.error_panel(
            message=f"[{e.phase.upper()}] {'; '.join(e.issues)}",
            hint=None,
        )
        raise typer.Exit(e.exit_code)
    except CliError as e:
        output.error_panel(e.message, hint=e.hint)
        raise typer.Exit(e.exit_code)
```

- [ ] **Step 5: Wire up placeholder commands** (so main.py doesn't crash on import)

Create stub files for all other commands so `_register_commands()` in main.py doesn't fail:

```python
# cli/src/covenant_cli/commands/init.py
import typer
def init_cmd(path: str = typer.Argument(".covenant.yaml")) -> None:
    typer.echo("init: not yet implemented")

# cli/src/covenant_cli/commands/sign.py
import typer
from pathlib import Path
def sign_cmd(path: Path = typer.Argument(...)) -> None:
    typer.echo("sign: not yet implemented")

# cli/src/covenant_cli/commands/diff.py
import typer
from pathlib import Path
def diff_cmd(old: Path = typer.Argument(...), new: Path = typer.Argument(...), fail_on_breaking: bool = False) -> None:
    typer.echo("diff: not yet implemented")

# cli/src/covenant_cli/commands/generate.py
import typer
from pathlib import Path
def generate_cmd(source: Path = typer.Argument(...), output: str | None = None, no_llm: bool = False) -> None:
    typer.echo("generate: not yet implemented")

# cli/src/covenant_cli/commands/publish.py
import typer
from pathlib import Path
def publish_cmd(path: Path = typer.Argument(...)) -> None:
    typer.echo("publish: not yet implemented")

# cli/src/covenant_cli/commands/audit.py
import typer
from pathlib import Path
def audit_cmd(events: Path = typer.Argument(...), spec: Path | None = None) -> None:
    typer.echo("audit: not yet implemented")
```

- [ ] **Step 6: Run integration tests — confirm they pass**

```bash
cd cli && pytest tests/integration/test_validate.py -v
```

Expected: all 6 tests PASS.

- [ ] **Step 7: Manual smoke test**

```bash
cd cli
covenant validate tests/integration/fixtures/valid.covenant.yaml
# Expected: green PASS panel

covenant validate tests/integration/fixtures/missing_budget.covenant.yaml
# Expected: exit 1, issues table with MISSING_BUDGET

covenant validate /nonexistent.yaml
# Expected: exit 2, error panel "File not found"
```

- [ ] **Step 8: Commit**

```bash
git add cli/src/covenant_cli/commands/ cli/tests/integration/
git commit -m "feat(cli): covenant validate — Show HN moment"
```

---

## Task 5: services/diff_engine.py + covenant diff

**Files:**
- Create: `cli/src/covenant_cli/services/diff_engine.py`
- Modify: `cli/src/covenant_cli/commands/diff.py`
- Test: `cli/tests/unit/test_diff_engine.py`
- Test: `cli/tests/integration/test_diff.py`

- [ ] **Step 1: Write failing unit tests for diff_engine**

```python
# cli/tests/unit/test_diff_engine.py
import pytest
from covenant_cli.models.spec import (
    CovenantSpec, AgentSpec, CapabilitiesSpec, ConstraintsSpec, BudgetSpec,
    NetworkSpec, ScopeSpec, InvariantSpec, SloSpec
)
from covenant_cli.services.diff_engine import diff, DiffResult


def _spec(version="1.0.0", tools=None, deny_tools=None, external_services=None,
          egress=None, max_cost=0.10, max_calls=None, invariants=None, slo=None) -> CovenantSpec:
    network = NetworkSpec(egress=egress) if egress is not None else None
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
        slo=slo,
    )


def test_no_changes():
    old = _spec("1.0.0")
    new = _spec("1.0.1")
    result = diff(old, new)
    assert result.semver_verdict == "none"
    assert result.breaking == []
    assert result.non_breaking == []


def test_tool_added_is_breaking():
    old = _spec("1.0.0", tools=["read_files"])
    new = _spec("2.0.0", tools=["read_files", "write_files"])
    result = diff(old, new)
    rules = [c.rule for c in result.breaking]
    assert "TOOL_ADDED_TO_CAPABILITIES" in rules
    assert result.semver_verdict == "major"


def test_deny_tool_removed_is_breaking():
    old = _spec("1.0.0", deny_tools=["delete_files"])
    new = _spec("2.0.0", deny_tools=None)
    result = diff(old, new)
    rules = [c.rule for c in result.breaking]
    assert "DENY_TOOL_REMOVED" in rules
    assert result.semver_verdict == "major"


def test_deny_tool_added_is_non_breaking():
    old = _spec("1.0.0", deny_tools=None)
    new = _spec("1.1.0", deny_tools=["delete_files"])
    result = diff(old, new)
    rules = [c.rule for c in result.non_breaking]
    assert "DENY_TOOL_ADDED" in rules
    assert result.semver_verdict == "minor"


def test_external_service_added_is_breaking():
    old = _spec("1.0.0", external_services=None)
    new = _spec("2.0.0", external_services=["github.com"])
    result = diff(old, new)
    rules = [c.rule for c in result.breaking]
    assert "EXTERNAL_SERVICE_ADDED" in rules


def test_egress_false_to_true_is_breaking():
    old = _spec("1.0.0", egress=False)
    new = _spec("2.0.0", egress=True)
    result = diff(old, new)
    rules = [c.rule for c in result.breaking]
    assert "EGRESS_LOOSENED" in rules


def test_egress_true_to_false_is_non_breaking():
    old = _spec("1.0.0", egress=True)
    new = _spec("1.1.0", egress=False)
    result = diff(old, new)
    rules = [c.rule for c in result.non_breaking]
    assert "EGRESS_TIGHTENED" in rules


def test_budget_increased_is_breaking():
    old = _spec("1.0.0", max_cost=0.10)
    new = _spec("2.0.0", max_cost=0.20)
    result = diff(old, new)
    rules = [c.rule for c in result.breaking]
    assert "BUDGET_INCREASED" in rules


def test_budget_decreased_is_non_breaking():
    old = _spec("1.0.0", max_cost=0.20)
    new = _spec("1.1.0", max_cost=0.10)
    result = diff(old, new)
    rules = [c.rule for c in result.non_breaking]
    assert "BUDGET_DECREASED" in rules


def test_call_limit_increased_is_breaking():
    old = _spec("1.0.0", max_calls=10)
    new = _spec("2.0.0", max_calls=20)
    result = diff(old, new)
    rules = [c.rule for c in result.breaking]
    assert "CALL_LIMIT_INCREASED" in rules


def test_invariant_removed_is_breaking():
    inv = [InvariantSpec(**{"id": "INV-001", "assert": "cost_usd < 0.10", "severity": "error"})]
    old = _spec("1.0.0", invariants=inv)
    new = _spec("2.0.0", invariants=None)
    result = diff(old, new)
    rules = [c.rule for c in result.breaking]
    assert "INVARIANT_REMOVED" in rules


def test_invariant_severity_downgraded_is_breaking():
    old_inv = [InvariantSpec(**{"id": "INV-001", "assert": "cost_usd < 0.10", "severity": "error"})]
    new_inv = [InvariantSpec(**{"id": "INV-001", "assert": "cost_usd < 0.10", "severity": "warn"})]
    old = _spec("1.0.0", invariants=old_inv)
    new = _spec("2.0.0", invariants=new_inv)
    result = diff(old, new)
    rules = [c.rule for c in result.breaking]
    assert "INVARIANT_SEVERITY_DOWNGRADED" in rules


def test_invariant_added_is_non_breaking():
    inv = [InvariantSpec(**{"id": "INV-001", "assert": "cost_usd < 0.10", "severity": "error"})]
    old = _spec("1.0.0", invariants=None)
    new = _spec("1.1.0", invariants=inv)
    result = diff(old, new)
    rules = [c.rule for c in result.non_breaking]
    assert "INVARIANT_ADDED" in rules


def test_both_deny_none_is_noop():
    old = _spec("1.0.0", deny_tools=None)
    new = _spec("1.0.1", deny_tools=None)
    result = diff(old, new)
    assert result.semver_verdict == "none"


def test_semver_verdict_major_beats_minor():
    old = _spec("1.0.0", tools=["read_files"], deny_tools=None)
    new = _spec("2.0.0", tools=["read_files", "write_files"], deny_tools=["delete_files"])
    result = diff(old, new)
    assert result.semver_verdict == "major"
```

- [ ] **Step 2: Run tests — confirm they fail**

```bash
cd cli && pytest tests/unit/test_diff_engine.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Write services/diff_engine.py**

```python
# cli/src/covenant_cli/services/diff_engine.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from covenant_cli.models.spec import CovenantSpec


@dataclass
class Change:
    rule: str
    field: str
    description: str
    detail: dict


@dataclass
class DiffResult:
    breaking: list[Change]
    non_breaking: list[Change]
    semver_verdict: Literal["major", "minor", "patch", "none"]
    old_version: str
    new_version: str


def diff(old: CovenantSpec, new: CovenantSpec) -> DiffResult:
    """Compute behavioral diff between two CovenantSpec versions.

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
        breaking.append(Change(
            rule="TOOL_ADDED_TO_CAPABILITIES",
            field="capabilities.tools",
            description=f'Tool "{added}" added to capabilities allowlist',
            detail={"added": added},
        ))

    # --- constraints.deny_tools ---
    old_deny = set(old.constraints.deny_tools or [])
    new_deny = set(new.constraints.deny_tools or [])
    for removed in sorted(old_deny - new_deny):
        breaking.append(Change(
            rule="DENY_TOOL_REMOVED",
            field="constraints.deny_tools",
            description=f'Deny rule for "{removed}" removed',
            detail={"removed": removed},
        ))
    for added in sorted(new_deny - old_deny):
        non_breaking.append(Change(
            rule="DENY_TOOL_ADDED",
            field="constraints.deny_tools",
            description=f'Deny rule for "{added}" added',
            detail={"added": added},
        ))

    # --- capabilities.external_services ---
    old_svc = set(old.capabilities.external_services or [])
    new_svc = set(new.capabilities.external_services or [])
    for added in sorted(new_svc - old_svc):
        breaking.append(Change(
            rule="EXTERNAL_SERVICE_ADDED",
            field="capabilities.external_services",
            description=f'External service "{added}" added',
            detail={"added": added},
        ))

    # --- constraints.network.egress ---
    old_egress = old.constraints.network.egress if old.constraints.network else None
    new_egress = new.constraints.network.egress if new.constraints.network else None
    if old_egress != new_egress and old_egress is not None and new_egress is not None:
        # Loosened: false→true, false→scoped, scoped→true
        loosened = (
            (old_egress is False and new_egress is True) or
            (old_egress is False and new_egress == "scoped") or
            (old_egress == "scoped" and new_egress is True)
        )
        tightened = (
            (old_egress is True and new_egress is False) or
            (old_egress is True and new_egress == "scoped") or
            (old_egress == "scoped" and new_egress is False)
        )
        if loosened:
            breaking.append(Change(
                rule="EGRESS_LOOSENED",
                field="constraints.network.egress",
                description=f"Network egress loosened from {old_egress!r} to {new_egress!r}",
                detail={"old": old_egress, "new": new_egress},
            ))
        elif tightened:
            non_breaking.append(Change(
                rule="EGRESS_TIGHTENED",
                field="constraints.network.egress",
                description=f"Network egress tightened from {old_egress!r} to {new_egress!r}",
                detail={"old": old_egress, "new": new_egress},
            ))

    # --- constraints.budget.max_cost_usd ---
    old_cost = old.constraints.budget.max_cost_usd if old.constraints.budget else None
    new_cost = new.constraints.budget.max_cost_usd if new.constraints.budget else None
    if old_cost is not None and new_cost is not None and old_cost != new_cost:
        if new_cost > old_cost:
            breaking.append(Change(
                rule="BUDGET_INCREASED",
                field="constraints.budget.max_cost_usd",
                description=f"Budget ceiling raised from ${old_cost} to ${new_cost}",
                detail={"old": old_cost, "new": new_cost},
            ))
        else:
            non_breaking.append(Change(
                rule="BUDGET_DECREASED",
                field="constraints.budget.max_cost_usd",
                description=f"Budget ceiling lowered from ${old_cost} to ${new_cost}",
                detail={"old": old_cost, "new": new_cost},
            ))

    # --- constraints.scope.max_calls_per_invocation ---
    old_calls = (
        old.constraints.scope.max_calls_per_invocation
        if old.constraints.scope else None
    )
    new_calls = (
        new.constraints.scope.max_calls_per_invocation
        if new.constraints.scope else None
    )
    if old_calls is not None and new_calls is not None and old_calls != new_calls:
        if new_calls > old_calls:
            breaking.append(Change(
                rule="CALL_LIMIT_INCREASED",
                field="constraints.scope.max_calls_per_invocation",
                description=f"Call limit raised from {old_calls} to {new_calls}",
                detail={"old": old_calls, "new": new_calls},
            ))
        else:
            non_breaking.append(Change(
                rule="CALL_LIMIT_DECREASED",
                field="constraints.scope.max_calls_per_invocation",
                description=f"Call limit lowered from {old_calls} to {new_calls}",
                detail={"old": old_calls, "new": new_calls},
            ))

    # --- invariants ---
    old_invs = {inv.id: inv for inv in (old.invariants or [])}
    new_invs = {inv.id: inv for inv in (new.invariants or [])}

    for inv_id in sorted(old_invs.keys() - new_invs.keys()):
        breaking.append(Change(
            rule="INVARIANT_REMOVED",
            field="invariants",
            description=f'Invariant {inv_id} removed',
            detail={"removed": inv_id},
        ))
    for inv_id in sorted(new_invs.keys() - old_invs.keys()):
        non_breaking.append(Change(
            rule="INVARIANT_ADDED",
            field="invariants",
            description=f'Invariant {inv_id} added',
            detail={"added": inv_id},
        ))
    for inv_id in sorted(old_invs.keys() & new_invs.keys()):
        old_sev = old_invs[inv_id].severity
        new_sev = new_invs[inv_id].severity
        if old_sev == "error" and new_sev == "warn":
            breaking.append(Change(
                rule="INVARIANT_SEVERITY_DOWNGRADED",
                field=f"invariants[{inv_id}].severity",
                description=f'Invariant {inv_id} severity downgraded from error to warn',
                detail={"old": old_sev, "new": new_sev},
            ))

    # --- semver verdict ---
    if breaking:
        verdict: Literal["major", "minor", "patch", "none"] = "major"
    elif non_breaking:
        # Check if any non-breaking changes are patch-level
        minor_rules = {
            "DENY_TOOL_ADDED", "INVARIANT_ADDED", "SLO_TIGHTENED",
            "EGRESS_TIGHTENED", "BUDGET_DECREASED", "CALL_LIMIT_DECREASED",
        }
        has_minor = any(c.rule in minor_rules for c in non_breaking)
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
```

- [ ] **Step 4: Run unit tests — confirm they pass**

```bash
cd cli && pytest tests/unit/test_diff_engine.py -v
```

Expected: all 15 tests PASS.

- [ ] **Step 5: Write commands/diff.py**

```python
# cli/src/covenant_cli/commands/diff.py
from __future__ import annotations

from pathlib import Path

import typer

from covenant_cli.errors import EXIT_NOT_FOUND, EXIT_VALIDATION, SpecLoadError, CliError
from covenant_cli.models import spec_loader
from covenant_cli.services import diff_engine
from covenant_cli import output


def diff_cmd(
    old: Path = typer.Argument(..., help="Path to old .covenant.yaml"),
    new: Path = typer.Argument(..., help="Path to new .covenant.yaml"),
    fail_on_breaking: bool = typer.Option(
        False, "--fail-on-breaking", help="Exit 1 if any breaking changes (for CI)"
    ),
) -> None:
    """Show behavioral diff between two .covenant.yaml versions."""
    old_spec = None
    new_spec = None
    errors = []

    try:
        old_spec = spec_loader.load_spec(old)
    except SpecLoadError as e:
        errors.append(f"OLD spec: [{e.phase.upper()}] {'; '.join(e.issues)}")

    try:
        new_spec = spec_loader.load_spec(new)
    except SpecLoadError as e:
        errors.append(f"NEW spec: [{e.phase.upper()}] {'; '.join(e.issues)}")

    if errors:
        for err in errors:
            output.error_panel(err)
        raise typer.Exit(EXIT_NOT_FOUND if "not found" in " ".join(errors).lower() else EXIT_VALIDATION)

    assert old_spec is not None and new_spec is not None
    result = diff_engine.diff(old_spec, new_spec)
    output.diff_renderer(result)

    if fail_on_breaking and result.breaking:
        raise typer.Exit(EXIT_VALIDATION)
```

- [ ] **Step 6: Write integration tests for diff**

```python
# cli/tests/integration/test_diff.py
from pathlib import Path
from typer.testing import CliRunner
from covenant_cli.main import app

runner = CliRunner()
FIXTURES = Path(__file__).parent / "fixtures"


def test_diff_same_spec_shows_none(tmp_path):
    result = runner.invoke(
        app, ["diff", str(FIXTURES / "valid.covenant.yaml"), str(FIXTURES / "valid.covenant.yaml")]
    )
    assert result.exit_code == 0
    assert "none" in result.output.lower()


def test_diff_fail_on_breaking(tmp_path):
    import yaml
    old_path = FIXTURES / "valid.covenant.yaml"
    # Create a new spec with an extra tool (breaking change)
    with open(old_path) as f:
        data = yaml.safe_load(f)
    data["agent"]["version"] = "2.0.0"
    data["capabilities"]["tools"].append("write_files")
    new_path = tmp_path / "new.covenant.yaml"
    with open(new_path, "w") as f:
        yaml.dump(data, f)

    result = runner.invoke(app, ["diff", "--fail-on-breaking", str(old_path), str(new_path)])
    assert result.exit_code == 1


def test_diff_nonexistent_file():
    result = runner.invoke(app, ["diff", "/no/such/old.yaml", str(FIXTURES / "valid.covenant.yaml")])
    assert result.exit_code != 0
```

- [ ] **Step 7: Run all diff tests**

```bash
cd cli && pytest tests/unit/test_diff_engine.py tests/integration/test_diff.py -v
```

Expected: all tests PASS.

- [ ] **Step 8: Commit**

```bash
git add cli/src/covenant_cli/services/diff_engine.py cli/src/covenant_cli/commands/diff.py cli/tests/
git commit -m "feat(cli): diff_engine service + covenant diff command"
```

---

## Task 6: covenant sign

**Files:**
- Modify: `cli/src/covenant_cli/commands/sign.py`
- Test: `cli/tests/integration/test_sign.py`

- [ ] **Step 1: Write failing sign tests**

```python
# cli/tests/integration/test_sign.py
import base64
import os
from pathlib import Path
import yaml
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from typer.testing import CliRunner
from covenant_cli.main import app

runner = CliRunner()
FIXTURES = Path(__file__).parent / "fixtures"


def _make_key() -> tuple[str, str]:
    """Returns (private_key_b64url, public_key_b64url)."""
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key()
    priv_bytes = priv.private_bytes_raw()
    pub_bytes = pub.public_bytes_raw()
    return (
        base64.urlsafe_b64encode(priv_bytes).decode(),
        base64.urlsafe_b64encode(pub_bytes).decode(),
    )


def test_sign_round_trip(tmp_path):
    priv_b64, pub_b64 = _make_key()
    src = FIXTURES / "unsigned.covenant.yaml"
    dest = tmp_path / "signed.covenant.yaml"
    import shutil
    shutil.copy(src, dest)

    result = runner.invoke(
        app, ["sign", str(dest)],
        env={"COVENANT_SIGNING_KEY": priv_b64},
    )
    assert result.exit_code == 0, result.output

    with open(dest) as f:
        data = yaml.safe_load(f)

    assert "provenance" in data
    assert data["provenance"]["algorithm"] == "Ed25519"
    assert "signature" in data["provenance"]
    assert "public_key" in data["provenance"]


def test_sign_verify_signature(tmp_path):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    import hashlib

    priv_b64, pub_b64 = _make_key()
    src = FIXTURES / "unsigned.covenant.yaml"
    dest = tmp_path / "signed.covenant.yaml"
    import shutil
    shutil.copy(src, dest)

    runner.invoke(app, ["sign", str(dest)], env={"COVENANT_SIGNING_KEY": priv_b64})

    with open(dest) as f:
        data = yaml.safe_load(f)

    sig = base64.urlsafe_b64decode(data["provenance"]["signature"])
    pub_key_bytes = base64.urlsafe_b64decode(data["provenance"]["public_key"])
    pub_key = Ed25519PublicKey.from_public_bytes(pub_key_bytes)

    # Reconstruct canonical: spec without provenance block
    data_no_prov = {k: v for k, v in data.items() if k != "provenance"}
    canonical = yaml.dump(data_no_prov, sort_keys=True, allow_unicode=True).encode()
    digest = hashlib.sha256(canonical).digest()

    # Should not raise
    pub_key.verify(sig, digest)


def test_sign_missing_key_env(tmp_path):
    src = FIXTURES / "unsigned.covenant.yaml"
    dest = tmp_path / "spec.yaml"
    import shutil
    shutil.copy(src, dest)

    env = {k: v for k, v in os.environ.items() if k != "COVENANT_SIGNING_KEY"}
    result = runner.invoke(app, ["sign", str(dest)], env=env)
    assert result.exit_code == 3


def test_sign_invalid_spec_aborts(tmp_path):
    priv_b64, _ = _make_key()
    # Use a spec that fails linting (missing budget)
    src = FIXTURES / "missing_budget.covenant.yaml"
    dest = tmp_path / "spec.yaml"
    import shutil
    shutil.copy(src, dest)

    result = runner.invoke(app, ["sign", str(dest)], env={"COVENANT_SIGNING_KEY": priv_b64})
    assert result.exit_code == 1
```

- [ ] **Step 2: Run tests — confirm they fail**

```bash
cd cli && pytest tests/integration/test_sign.py -v
```

- [ ] **Step 3: Write commands/sign.py**

```python
# cli/src/covenant_cli/commands/sign.py
from __future__ import annotations

import base64
import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path

import typer
import yaml

from covenant_cli.errors import EXIT_SIGNING, EXIT_VALIDATION, CliError, SpecLoadError
from covenant_cli.models import spec_loader
from covenant_cli.services import linter
from covenant_cli import output


def sign_cmd(
    path: Path = typer.Argument(..., help="Path to .covenant.yaml"),
) -> None:
    """Sign a .covenant.yaml with an Ed25519 key, writing provenance block."""
    try:
        spec = spec_loader.load_spec(path)
    except SpecLoadError as e:
        output.error_panel(f"[{e.phase.upper()}] {'; '.join(e.issues)}")
        raise typer.Exit(e.exit_code)

    # Lint — block on errors only
    issues = linter.lint(spec)
    error_issues = [i for i in issues if i.level == "error"]
    if issues:
        output.issues_table(issues)
    if error_issues:
        output.error_panel("Spec has lint errors — fix them before signing.")
        raise typer.Exit(EXIT_VALIDATION)

    signing_key_b64 = os.environ.get("COVENANT_SIGNING_KEY")
    if not signing_key_b64:
        output.error_panel(
            "COVENANT_SIGNING_KEY is not set.",
            hint="Export a base64url-encoded Ed25519 private key.",
        )
        raise typer.Exit(EXIT_SIGNING)

    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

        priv_bytes = base64.urlsafe_b64decode(signing_key_b64)
        private_key = Ed25519PrivateKey.from_private_bytes(priv_bytes)
        public_key = private_key.public_key()
        pub_b64 = base64.urlsafe_b64encode(public_key.public_bytes_raw()).decode()
    except Exception as e:
        output.error_panel(f"Failed to load signing key: {e}")
        raise typer.Exit(EXIT_SIGNING)

    try:
        raw_text = path.read_text(encoding="utf-8")
        raw_dict = yaml.safe_load(raw_text)

        # Strip existing provenance to avoid circular signing
        raw_no_prov = {k: v for k, v in raw_dict.items() if k != "provenance"}

        # Canonical YAML: keys sorted, no comments
        canonical = yaml.dump(raw_no_prov, sort_keys=True, allow_unicode=True).encode()
        digest = hashlib.sha256(canonical).digest()

        sig_bytes = private_key.sign(digest)
        sig_b64 = base64.urlsafe_b64encode(sig_bytes).decode()

        raw_dict["provenance"] = {
            "algorithm": "Ed25519",
            "public_key": pub_b64,
            "signature": sig_b64,
            "signed_at": datetime.now(tz=timezone.utc).isoformat(),
        }

        path.write_text(yaml.dump(raw_dict, sort_keys=False, allow_unicode=True), encoding="utf-8")

    except Exception as e:
        output.error_panel(f"Signing failed: {e}")
        raise typer.Exit(EXIT_SIGNING)

    fingerprint = pub_b64[:16]
    output.success_panel(
        f"Signed  {spec.agent.name} {spec.agent.version}",
        body_lines=[
            f"Key fingerprint: {fingerprint}...",
            f"Provenance written to {path.absolute()}",
        ],
    )
```

- [ ] **Step 4: Run sign tests — confirm they pass**

```bash
cd cli && pytest tests/integration/test_sign.py -v
```

Expected: all 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add cli/src/covenant_cli/commands/sign.py cli/tests/integration/test_sign.py
git commit -m "feat(cli): covenant sign with Ed25519 + verify round-trip tests"
```

---

## Task 7: services/audit_engine.py + covenant audit

**Files:**
- Create: `cli/src/covenant_cli/services/audit_engine.py`
- Modify: `cli/src/covenant_cli/commands/audit.py`
- Test: `cli/tests/unit/test_audit_engine.py`
- Test: `cli/tests/integration/test_audit.py`

- [ ] **Step 1: Write failing unit tests**

```python
# cli/tests/unit/test_audit_engine.py
import pytest
from datetime import datetime, timezone
from covenant_cli.services.audit_engine import analyze, AuditEvent, AuditReport, VersionReport
from covenant_cli.models.spec import (
    CovenantSpec, AgentSpec, CapabilitiesSpec, ConstraintsSpec, BudgetSpec, SloSpec
)


def _event(contract="agent@1.0.0", outcome="ok", tools=None, cost=0.05,
           duration=1000, code=None, model=None):
    return AuditEvent(
        contract=contract,
        outcome=outcome,
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


def test_basic_report():
    events = [_event(), _event()]
    report = analyze(events, _spec())
    assert "agent@1.0.0" in report.versions
    vr = report.versions["agent@1.0.0"]
    assert vr.total_events == 2
    assert "read_files" in vr.observed_tools


def test_undeclared_tool_detected():
    events = [_event(tools=["read_files", "write_files"])]
    report = analyze(events, _spec())
    vr = report.versions["agent@1.0.0"]
    assert "write_files" in vr.undeclared_tools


def test_unused_tool_detected():
    events = [_event(tools=["read_files"])]  # call_llm never used
    report = analyze(events, _spec())
    vr = report.versions["agent@1.0.0"]
    assert "call_llm" in vr.unused_tools


def test_specless_mode():
    events = [_event()]
    report = analyze(events, None)
    vr = report.versions["agent@1.0.0"]
    assert vr.declared_tools is None
    assert "agent@1.0.0" in report.specless_versions


def test_violation_breakdown():
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


def test_percentile_computation():
    # 100 events with ascending costs
    events = [_event(cost=i * 0.001, duration=i * 10) for i in range(1, 101)]
    report = analyze(events, _spec())
    vr = report.versions["agent@1.0.0"]
    # p50 ≈ 0.050, p95 ≈ 0.095, p99 ≈ 0.099
    assert 0.045 < vr.actual_p50_cost < 0.055
    assert 0.090 < vr.actual_p95_cost < 0.100
```

- [ ] **Step 2: Run tests — confirm they fail**

```bash
cd cli && pytest tests/unit/test_audit_engine.py -v
```

- [ ] **Step 3: Write services/audit_engine.py**

```python
# cli/src/covenant_cli/services/audit_engine.py
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable, Literal

from pydantic import BaseModel

from covenant_cli.models.spec import CovenantSpec


class AuditEvent(BaseModel):
    """A single audit event emitted by the SDK."""
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
    contract: str
    total_events: int
    first_seen: datetime
    last_seen: datetime
    declared_tools: set[str] | None
    observed_tools: set[str]
    undeclared_tools: set[str]
    unused_tools: set[str]
    declared_max_cost: float | None
    actual_p50_cost: float
    actual_p95_cost: float
    actual_p99_cost: float
    actual_p50_ms: float
    actual_p95_ms: float
    actual_p99_ms: float
    declared_p95_ms: int | None
    declared_p99_ms: int | None
    violation_count: int
    violation_breakdown: dict[str, int]
    slo_breaches: list[str]


@dataclass
class AuditReport:
    versions: dict[str, VersionReport]
    total_events: int
    specless_versions: list[str]


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    idx = int(p * len(s))
    idx = min(idx, len(s) - 1)
    return s[idx]


def analyze(events: Iterable[AuditEvent], spec: CovenantSpec | None) -> AuditReport:
    """Compute declared-vs-observed report from audit events.

    Args:
        events: Iterable of AuditEvent objects.
        spec: Optional CovenantSpec for declared comparison. None = observed-only.

    Returns:
        AuditReport grouped by contract version.
    """
    by_version: dict[str, list[AuditEvent]] = {}
    for ev in events:
        by_version.setdefault(ev.contract, []).append(ev)

    declared_tools = set(spec.capabilities.tools) if spec else None
    declared_max_cost = spec.constraints.budget.max_cost_usd if spec and spec.constraints.budget else None
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
```

- [ ] **Step 4: Run unit tests — confirm pass**

```bash
cd cli && pytest tests/unit/test_audit_engine.py -v
```

Expected: all 6 tests PASS.

- [ ] **Step 5: Write commands/audit.py**

```python
# cli/src/covenant_cli/commands/audit.py
from __future__ import annotations

import json
from pathlib import Path

import typer
from pydantic import ValidationError

from covenant_cli.errors import EXIT_VALIDATION, CliError, SpecLoadError
from covenant_cli.models import spec_loader
from covenant_cli.services.audit_engine import AuditEvent, analyze
from covenant_cli import output


def audit_cmd(
    events: Path = typer.Argument(..., help="Path to NDJSON audit events file (.jsonl)"),
    spec: Path | None = typer.Option(None, "--spec", help="Explicit spec file path"),
) -> None:
    """Report declared vs observed behavior from an audit events log."""
    # Parse NDJSON
    valid_events: list[AuditEvent] = []
    malformed = 0

    if not events.exists():
        output.error_panel(f"File not found: {events}")
        raise typer.Exit(2)

    for line in events.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            valid_events.append(AuditEvent.model_validate(data))
        except (json.JSONDecodeError, ValidationError):
            malformed += 1

    if not valid_events:
        output.error_panel("Zero valid events parsed from input file.")
        raise typer.Exit(EXIT_VALIDATION)

    # Spec resolution
    loaded_spec = None
    if spec is not None:
        try:
            loaded_spec = spec_loader.load_spec(spec)
        except SpecLoadError as e:
            output.error_panel(f"[{e.phase.upper()}] {'; '.join(e.issues)}")
            raise typer.Exit(e.exit_code)
    else:
        auto = Path.cwd() / ".covenant.yaml"
        if auto.exists():
            try:
                loaded_spec = spec_loader.load_spec(auto)
            except SpecLoadError:
                pass  # fall through to specless mode

    report = analyze(valid_events, loaded_spec)

    # Warn about malformed lines to stderr
    if malformed:
        output.err_console.print(f"[yellow]⚠ {malformed} malformed line(s) skipped[/yellow]")

    output.audit_renderer(report)
```

- [ ] **Step 6: Write integration tests for audit**

```python
# cli/tests/integration/test_audit.py
import json
from pathlib import Path
from datetime import datetime, timezone
from typer.testing import CliRunner
from covenant_cli.main import app

runner = CliRunner()
FIXTURES = Path(__file__).parent / "fixtures"


def _write_events(path: Path, events: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(e) for e in events))


def _base_event(**overrides) -> dict:
    base = {
        "contract": "code-reviewer@1.0.0",
        "outcome": "ok",
        "tool_calls": ["read_files"],
        "cost_usd": 0.05,
        "duration_ms": 1000,
        "occurred_at": "2026-03-01T00:00:00+00:00",
        "violation_code": None,
        "model_used": None,
    }
    base.update(overrides)
    return base


def test_audit_basic_report(tmp_path):
    evs = tmp_path / "events.jsonl"
    _write_events(evs, [_base_event(), _base_event()])
    result = runner.invoke(
        app, ["audit", str(evs), "--spec", str(FIXTURES / "valid.covenant.yaml")]
    )
    assert result.exit_code == 0
    assert "code-reviewer" in result.output


def test_audit_zero_valid_events(tmp_path):
    evs = tmp_path / "empty.jsonl"
    evs.write_text("")
    result = runner.invoke(app, ["audit", str(evs)])
    assert result.exit_code == 1


def test_audit_all_malformed_is_exit_1(tmp_path):
    evs = tmp_path / "bad.jsonl"
    evs.write_text("not json\nalso not json\n")
    result = runner.invoke(app, ["audit", str(evs)])
    assert result.exit_code == 1


def test_audit_specless_mode(tmp_path):
    evs = tmp_path / "events.jsonl"
    _write_events(evs, [_base_event()])
    # Run from tmp_path where no .covenant.yaml exists
    result = runner.invoke(app, ["audit", str(evs)])
    # Should still produce a report (specless)
    assert result.exit_code == 0
```

- [ ] **Step 7: Run all audit tests**

```bash
cd cli && pytest tests/unit/test_audit_engine.py tests/integration/test_audit.py -v
```

Expected: all tests PASS. Note: `test_audit_all_malformed_is_exit_1` and `test_audit_zero_valid_events` both exit 1 — both paths to exit 1 covered.

- [ ] **Step 8: Commit**

```bash
git add cli/src/covenant_cli/services/audit_engine.py cli/src/covenant_cli/commands/audit.py cli/tests/
git commit -m "feat(cli): audit_engine + covenant audit command"
```

---

## Task 8: services/generator.py + covenant generate

**Files:**
- Create: `cli/src/covenant_cli/services/generator.py`
- Modify: `cli/src/covenant_cli/commands/generate.py`
- Test: `cli/tests/unit/test_generator.py`

- [ ] **Step 1: Write failing unit tests**

```python
# cli/tests/unit/test_generator.py
import ast
from pathlib import Path
import pytest
from covenant_cli.services.generator import analyze, draft_spec, StaticAnalysisResult


PYTHON_WITH_LLM = '''
import anthropic
import httpx

async def run_agent(query: str) -> str:
    client = anthropic.Anthropic()
    return "result"

async def helper():
    pass
'''

PYTHON_WITH_FS = '''
import os
from pathlib import Path

async def process():
    with open("file.txt") as f:
        data = f.read()
    return data
'''

PYTHON_PLAIN = '''
async def simple_agent(x: int) -> int:
    return x + 1
'''


def test_detects_llm_import(tmp_path):
    p = tmp_path / "agent.py"
    p.write_text(PYTHON_WITH_LLM)
    result = analyze(p)
    assert result.has_llm is True
    assert result.has_network is True
    assert result.detected_runtime == "python"


def test_detects_filesystem(tmp_path):
    p = tmp_path / "agent.py"
    p.write_text(PYTHON_WITH_FS)
    result = analyze(p)
    assert result.has_filesystem is True


def test_detects_async_functions(tmp_path):
    p = tmp_path / "agent.py"
    p.write_text(PYTHON_WITH_LLM)
    result = analyze(p)
    assert "run_agent" in result.agent_functions
    assert "helper" in result.agent_functions


def test_plain_agent_no_network_no_llm(tmp_path):
    p = tmp_path / "agent.py"
    p.write_text(PYTHON_PLAIN)
    result = analyze(p)
    assert result.has_llm is False
    assert result.has_network is False
    assert result.has_filesystem is False


def test_draft_spec_structure(tmp_path):
    p = tmp_path / "my_agent.py"
    p.write_text(PYTHON_PLAIN)
    result = analyze(p)
    draft = draft_spec(result, "my-agent")
    assert draft["covenant"] == "1.0"
    assert draft["agent"]["name"] == "my-agent"
    assert draft["agent"]["version"] == "0.1.0"
    assert draft["capabilities"]["tools"] == []
    assert "budget" in draft["constraints"]
    assert draft["metadata"]["llm_enhanced"] is False


def test_draft_spec_network_egress(tmp_path):
    p = tmp_path / "agent.py"
    p.write_text(PYTHON_WITH_LLM)
    result = analyze(p)
    draft = draft_spec(result, "net-agent")
    assert draft["constraints"]["network"]["egress"] is True


def test_draft_spec_filesystem(tmp_path):
    p = tmp_path / "agent.py"
    p.write_text(PYTHON_WITH_FS)
    result = analyze(p)
    draft = draft_spec(result, "fs-agent")
    assert "filesystem" in draft["constraints"]
    assert "**/*" in draft["constraints"]["filesystem"]["read"]


def test_llm_merge_fills_description(tmp_path):
    from covenant_cli.services.generator import _merge_llm_result
    draft = {
        "covenant": "1.0",
        "agent": {"name": "test", "version": "0.1.0", "runtime": "python"},
        "capabilities": {"tools": []},
        "constraints": {"budget": {"max_cost_usd": 0.10}},
        "metadata": {"llm_enhanced": False},
    }
    llm_result = {
        "description": "Does code review",
        "tools": ["read_files", "call_llm"],
        "invariants": [
            {"id": "INV-001", "description": "cost check", "assert": "cost_usd < 0.10", "severity": "error"}
        ],
    }
    merged = _merge_llm_result(draft, llm_result)
    assert merged["metadata"]["description"] == "Does code review"
    assert "read_files" in merged["capabilities"]["tools"]
    assert merged["metadata"]["llm_enhanced"] is True
    assert len(merged["invariants"]) == 1
```

- [ ] **Step 2: Run tests — confirm they fail**

```bash
cd cli && pytest tests/unit/test_generator.py -v
```

- [ ] **Step 3: Write services/generator.py**

```python
# cli/src/covenant_cli/services/generator.py
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class StaticAnalysisResult:
    detected_runtime: str  # "python" | "typescript" | "any"
    agent_functions: list[str]
    detected_tools: list[str]
    has_network: bool
    has_filesystem: bool
    has_llm: bool
    imported_modules: list[str]
    source_path: Path


_NETWORK_MODULES = {"requests", "httpx", "aiohttp", "urllib", "urllib3"}
_LLM_MODULES = {"anthropic", "openai", "litellm"}
_FS_PATTERNS = re.compile(r'\bopen\(|Path\(.*\)\.(read_text|write_text)|os\.path\.')


def analyze(path: Path) -> StaticAnalysisResult:
    """Statically analyze an agent source file.

    Args:
        path: Path to a Python or TypeScript source file.

    Returns:
        StaticAnalysisResult with detected features.
    """
    source = path.read_text(encoding="utf-8")
    ext = path.suffix.lower()

    if ext == ".py":
        return _analyze_python(source, path)
    else:
        return _analyze_typescript(source, path)


def _analyze_python(source: str, path: Path) -> StaticAnalysisResult:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return StaticAnalysisResult(
            detected_runtime="python",
            agent_functions=[],
            detected_tools=[],
            has_network=False,
            has_filesystem=False,
            has_llm=False,
            imported_modules=[],
            source_path=path,
        )

    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module.split(".")[0])

    async_fns = [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef)
        and isinstance(node.col_offset, int) and node.col_offset == 0
    ]

    imports_set = set(imports)
    has_llm = bool(imports_set & _LLM_MODULES)
    has_network = has_llm or bool(imports_set & _NETWORK_MODULES)
    has_filesystem = bool(_FS_PATTERNS.search(source))

    return StaticAnalysisResult(
        detected_runtime="python",
        agent_functions=async_fns,
        detected_tools=[],
        has_network=has_network,
        has_filesystem=has_filesystem,
        has_llm=has_llm,
        imported_modules=list(imports_set),
        source_path=path,
    )


def _analyze_typescript(source: str, path: Path) -> StaticAnalysisResult:
    import_pattern = re.compile(r'import\s+.*?\s+from\s+[\'"]([^\'"]+)[\'"]')
    modules = [m.split("/")[0].lstrip("@").split("/")[0] for m in import_pattern.findall(source)]
    modules_set = set(modules)

    has_llm = bool(modules_set & {"anthropic", "openai"})
    has_network = has_llm or bool(modules_set & {"axios", "node-fetch", "undici"})
    has_filesystem = bool(re.search(r'\bfs\b|\breadFileSync\b|\bwriteFileSync\b', source))

    async_fns = re.findall(r'(?:export\s+)?async\s+function\s+(\w+)', source)

    return StaticAnalysisResult(
        detected_runtime="typescript",
        agent_functions=async_fns,
        detected_tools=[],
        has_network=has_network,
        has_filesystem=has_filesystem,
        has_llm=has_llm,
        imported_modules=list(modules_set),
        source_path=path,
    )


def draft_spec(result: StaticAnalysisResult, name: str) -> dict[str, Any]:
    """Produce a draft spec dict from static analysis.

    Args:
        result: StaticAnalysisResult from analyze().
        name: kebab-case agent name.

    Returns:
        Raw spec dict (not yet a CovenantSpec — user must fill in tools).
    """
    spec: dict[str, Any] = {
        "covenant": "1.0",
        "agent": {
            "name": name,
            "version": "0.1.0",
            "runtime": result.detected_runtime,
        },
        "capabilities": {
            "tools": [],  # user must fill in
        },
        "constraints": {
            "budget": {"max_cost_usd": 0.10},
        },
        "metadata": {
            "description": "Generated by covenant generate — review before publishing",
            "llm_enhanced": False,
        },
    }

    if result.has_network:
        spec["constraints"]["network"] = {"egress": True}

    if result.has_filesystem:
        spec["constraints"]["filesystem"] = {"read": ["**/*"], "write": []}

    return spec


def _merge_llm_result(draft: dict[str, Any], llm_result: dict[str, Any]) -> dict[str, Any]:
    """Merge LLM-suggested fields into a draft spec dict.

    Args:
        draft: Draft spec dict from draft_spec().
        llm_result: Parsed LLM response with description, tools, invariants.

    Returns:
        Merged spec dict with llm_enhanced: true set.
    """
    merged = dict(draft)

    if "description" in llm_result:
        merged.setdefault("metadata", {})["description"] = llm_result["description"]

    if "tools" in llm_result and llm_result["tools"]:
        merged["capabilities"] = dict(merged.get("capabilities", {}))
        merged["capabilities"]["tools"] = llm_result["tools"]

    if "invariants" in llm_result and llm_result["invariants"]:
        merged["invariants"] = llm_result["invariants"]

    merged.setdefault("metadata", {})["llm_enhanced"] = True

    return merged


def enhance_with_llm(draft: dict[str, Any], source_text: str) -> dict[str, Any]:
    """Run LLM enhancement phase (Phase 2).

    Requires COVENANT_LLM_KEY env var. Uses COVENANT_LLM_BASE_URL and
    COVENANT_LLM_MODEL if set; otherwise defaults to OpenAI gpt-4o-mini.

    Args:
        draft: Draft spec dict from draft_spec().
        source_text: Full source code of the agent file.

    Returns:
        Merged spec dict. Falls back to draft on any LLM failure.
    """
    import json
    import os
    from openai import OpenAI

    api_key = os.environ["COVENANT_LLM_KEY"]
    base_url = os.environ.get("COVENANT_LLM_BASE_URL")
    model = os.environ.get("COVENANT_LLM_MODEL", "gpt-4o-mini")

    client = OpenAI(api_key=api_key, base_url=base_url)

    system = (
        "You analyze AI agent source code and return a JSON object describing the agent's contract. "
        "Return ONLY valid JSON — no preamble, no markdown fences. "
        "JSON must have exactly these fields: "
        '{"description": "one sentence", "tools": ["tool_name"], '
        '"invariants": [{"id": "INV-001", "description": "...", "assert": "...", "severity": "error"}]}'
    )
    user = f"Agent source code:\n\n{source_text}"

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        max_tokens=1000,
    )
    raw = response.choices[0].message.content or ""

    # Strip accidental markdown fences
    raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    raw = re.sub(r"\s*```$", "", raw)

    llm_result = json.loads(raw)
    return _merge_llm_result(draft, llm_result)
```

- [ ] **Step 4: Run unit tests — confirm pass**

```bash
cd cli && pytest tests/unit/test_generator.py -v
```

Expected: all 8 tests PASS.

- [ ] **Step 5: Write commands/generate.py**

```python
# cli/src/covenant_cli/commands/generate.py
from __future__ import annotations

import os
import re
from pathlib import Path

import typer
import yaml

from covenant_cli.errors import EXIT_NOT_FOUND, EXIT_VALIDATION, CliError
from covenant_cli.services.generator import analyze, draft_spec, enhance_with_llm
from covenant_cli import output


def generate_cmd(
    source: Path = typer.Argument(..., help="Path to agent source file (.py or .ts)"),
    output_path: str | None = typer.Option(None, "--output", "-o", help="Output path"),
    no_llm: bool = typer.Option(False, "--no-llm", help="Skip LLM even if key is set"),
) -> None:
    """Generate a draft .covenant.yaml from an agent source file."""
    if not source.exists():
        output.error_panel(f"File not found: {source}")
        raise typer.Exit(EXIT_NOT_FOUND)

    stem = source.stem
    agent_name = re.sub(r"[^a-z0-9]+", "-", stem.lower()).strip("-")
    out_path = Path(output_path) if output_path else source.parent / f"{stem}.covenant.yaml"

    if out_path.exists():
        confirmed = typer.confirm(f"Overwrite existing {out_path}?", default=False)
        if not confirmed:
            raise typer.Exit(0)

    try:
        result = analyze(source)
        draft = draft_spec(result, agent_name)

        llm_key = os.environ.get("COVENANT_LLM_KEY")
        llm_enhanced = False
        if llm_key and not no_llm:
            try:
                source_text = source.read_text(encoding="utf-8")
                draft = enhance_with_llm(draft, source_text)
                llm_enhanced = True
            except Exception as e:
                output.err_console.print(f"[yellow]⚠ LLM enhancement failed: {e} — using static analysis only[/yellow]")

        out_path.write_text(yaml.dump(draft, sort_keys=False, allow_unicode=True), encoding="utf-8")

    except Exception as e:
        output.error_panel(f"Generation failed: {e}")
        raise typer.Exit(EXIT_VALIDATION)

    body_lines = [f"Draft written to {out_path.absolute()}"]
    if llm_enhanced:
        body_lines.append("  ✦ LLM-enhanced (llm_enhanced: true set in metadata)")
    body_lines.append("  ⚠ capabilities.tools is empty — fill in before publishing")
    if result.has_llm and not draft.get("capabilities", {}).get("models"):
        body_lines.append("  ⚠ capabilities.models is empty — LLM usage detected")

    output.success_panel(f"Generated  {agent_name}", body_lines=body_lines)
```

- [ ] **Step 6: Commit**

```bash
git add cli/src/covenant_cli/services/generator.py cli/src/covenant_cli/commands/generate.py cli/tests/unit/test_generator.py
git commit -m "feat(cli): generator service + covenant generate command"
```

---

## Task 9: covenant init

**Files:**
- Modify: `cli/src/covenant_cli/commands/init.py`

- [ ] **Step 1: Write commands/init.py**

```python
# cli/src/covenant_cli/commands/init.py
from __future__ import annotations

import re
from pathlib import Path

import typer
import yaml

from covenant_cli.errors import EXIT_VALIDATION
from covenant_cli import output


def init_cmd(
    path: str = typer.Argument(".covenant.yaml", help="Output path"),
) -> None:
    """Interactively scaffold a .covenant.yaml contract file."""
    out_path = Path(path)

    if out_path.exists():
        confirmed = typer.confirm(f"Overwrite existing {out_path}?", default=False)
        if not confirmed:
            raise typer.Exit(0)

    # 1. Agent name
    while True:
        name = typer.prompt("Agent name (kebab-case)").strip()
        if re.match(r"^[a-z0-9-]+$", name):
            break
        typer.echo("[red]Name must be kebab-case (lowercase letters, digits, hyphens only)[/red]")

    # 2. Version
    version = typer.prompt("Version", default="0.1.0").strip()

    # 3. Runtime
    runtime = typer.prompt(
        "Runtime", default="python",
        prompt_suffix=" [python/typescript/any]: "
    ).strip()
    if runtime not in ("python", "typescript", "any"):
        runtime = "python"

    # 4. Allowed tools
    while True:
        tools_raw = typer.prompt("Allowed tools (comma-separated, at least one required)").strip()
        tools = [t.strip() for t in tools_raw.split(",") if t.strip()]
        if tools:
            break
        typer.echo("At least one tool is required.")

    # 5. Max cost USD
    while True:
        cost_raw = typer.prompt("Max cost USD per invocation", default="0.10").strip()
        try:
            max_cost = float(cost_raw)
            if max_cost > 0:
                break
        except ValueError:
            pass
        typer.echo("Must be a positive number.")

    # 6. Deny tools (optional)
    deny_raw = typer.prompt("Deny tools (comma-separated, optional)", default="").strip()
    deny_tools = [t.strip() for t in deny_raw.split(",") if t.strip()]

    # 7. Invariants (optional loop)
    invariants = []
    while typer.confirm("Add an invariant?", default=False):
        inv_id = typer.prompt("  Invariant ID (e.g. INV-001)").strip()
        inv_desc = typer.prompt("  Description").strip()
        inv_expr = typer.prompt("  Assert expression (Python, e.g. cost_usd < 0.10)").strip()
        inv_sev = typer.prompt("  Severity", default="error", prompt_suffix=" [error/warn]: ").strip()
        invariants.append({
            "id": inv_id,
            "description": inv_desc,
            "assert": inv_expr,
            "severity": inv_sev if inv_sev in ("error", "warn") else "error",
        })

    # 8. Description (optional)
    description = typer.prompt("Description (optional)", default="").strip()

    # Build spec dict
    spec: dict = {
        "covenant": "1.0",
        "agent": {"name": name, "version": version, "runtime": runtime},
        "capabilities": {"tools": tools},
        "constraints": {"budget": {"max_cost_usd": max_cost}},
    }
    if deny_tools:
        spec["constraints"]["deny_tools"] = deny_tools
    if invariants:
        spec["invariants"] = invariants
    if description:
        spec["metadata"] = {"description": description}

    out_path.write_text(yaml.dump(spec, sort_keys=False, allow_unicode=True), encoding="utf-8")

    output.success_panel(
        f"Created  {name} {version}",
        body_lines=[
            f"Written to {out_path.absolute()}",
            f"Run `covenant validate {out_path.absolute()}` to check it.",
        ],
    )
```

- [ ] **Step 2: Smoke test init interactively**

```bash
cd cli
echo -e "test-agent\n\npython\nread_files\n0.10\n\nn\n" | covenant init /tmp/test.covenant.yaml
covenant validate /tmp/test.covenant.yaml
```

Expected: PASS panel for the generated spec.

- [ ] **Step 3: Commit**

```bash
git add cli/src/covenant_cli/commands/init.py
git commit -m "feat(cli): covenant init interactive wizard"
```

---

## Task 10: covenant publish

**Files:**
- Modify: `cli/src/covenant_cli/commands/publish.py`

- [ ] **Step 1: Write commands/publish.py**

```python
# cli/src/covenant_cli/commands/publish.py
from __future__ import annotations

import json
import os
from pathlib import Path

import httpx
import typer

from covenant_cli.errors import EXIT_NETWORK, EXIT_NOT_FOUND, EXIT_SIGNING, EXIT_VALIDATION, CliError, SpecLoadError
from covenant_cli.models import spec_loader
from covenant_cli.services import linter
from covenant_cli import output


def publish_cmd(
    path: Path = typer.Argument(..., help="Path to .covenant.yaml"),
) -> None:
    """Publish a signed .covenant.yaml to the registry."""
    # 1. Load and lint
    try:
        spec = spec_loader.load_spec(path)
    except SpecLoadError as e:
        output.error_panel(f"[{e.phase.upper()}] {'; '.join(e.issues)}")
        raise typer.Exit(e.exit_code)

    issues = linter.lint(spec)
    error_issues = [i for i in issues if i.level == "error"]
    if issues:
        output.issues_table(issues)
    if error_issues:
        output.error_panel("Spec has lint errors — fix them before publishing.")
        raise typer.Exit(EXIT_VALIDATION)

    # 2. Must be signed
    if not (spec.provenance and spec.provenance.signature):
        output.error_panel(
            "Spec must be signed before publishing.",
            hint=f"Run `covenant sign {path.absolute()}`",
        )
        raise typer.Exit(EXIT_SIGNING)

    # 3. Env vars
    registry_url = os.environ.get("COVENANT_REGISTRY_URL")
    api_key = os.environ.get("COVENANT_API_KEY")
    if not registry_url:
        output.error_panel("COVENANT_REGISTRY_URL is not set.")
        raise typer.Exit(EXIT_NETWORK)
    if not api_key:
        output.error_panel("COVENANT_API_KEY is not set.")
        raise typer.Exit(EXIT_NETWORK)

    # 4. HTTP POST
    raw_yaml = path.read_bytes()
    try:
        response = httpx.post(
            f"{registry_url.rstrip('/')}/contracts",
            content=raw_yaml,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/yaml",
            },
            timeout=30,
        )
    except httpx.ConnectError:
        output.error_panel(
            f"Registry unreachable at {registry_url}. Is COVENANT_REGISTRY_URL correct?"
        )
        raise typer.Exit(EXIT_NETWORK)

    if response.status_code == 201:
        try:
            body = response.json()
            contract_url = body.get("url", "")
        except Exception:
            contract_url = ""
        output.success_panel(
            f"Published  {spec.agent.name} {spec.agent.version}",
            body_lines=[contract_url] if contract_url else [],
        )

    elif response.status_code == 422:
        try:
            body = response.json()
            detail = body.get("detail", {})
            breaking_raw = detail.get("breaking_changes", [])
            # Try to render as DiffResult
            try:
                from covenant_cli.services.diff_engine import DiffResult, Change
                breaking = [Change(**c) for c in breaking_raw]
                result = DiffResult(
                    breaking=breaking,
                    non_breaking=[],
                    semver_verdict="major",
                    old_version=detail.get("current_version", "?"),
                    new_version=detail.get("incoming_version", "?"),
                )
                output.diff_renderer(result)
            except Exception:
                output.err_console.print(json.dumps(breaking_raw, indent=2))
        except Exception:
            output.error_panel(f"Registry rejected publish (422): {response.text[:200]}")
        raise typer.Exit(EXIT_VALIDATION)

    elif response.status_code == 409:
        output.error_panel(
            f"Version {spec.agent.version} already published. Bump the version and re-sign."
        )
        raise typer.Exit(EXIT_VALIDATION)

    elif response.status_code in (401, 403):
        output.error_panel("Authentication failed. Check COVENANT_API_KEY.")
        raise typer.Exit(EXIT_NETWORK)

    else:
        output.error_panel(f"Unexpected registry response: {response.status_code}\n{response.text[:200]}")
        raise typer.Exit(EXIT_NETWORK)
```

- [ ] **Step 2: Commit**

```bash
git add cli/src/covenant_cli/commands/publish.py
git commit -m "feat(cli): covenant publish command"
```

---

## Task 11: Full test run + ruff/mypy

- [ ] **Step 1: Run full test suite**

```bash
cd cli && pytest -v
```

Expected: all tests PASS.

- [ ] **Step 2: Run ruff**

```bash
cd cli && ruff check src/ tests/
```

Fix any reported issues.

- [ ] **Step 3: Run mypy**

```bash
cd cli && mypy src/covenant_cli/
```

Fix any reported type errors.

- [ ] **Step 4: Smoke test all commands**

```bash
# validate
covenant validate tests/integration/fixtures/valid.covenant.yaml
# Expected: green PASS panel

# diff
covenant diff tests/integration/fixtures/valid.covenant.yaml tests/integration/fixtures/valid.covenant.yaml
# Expected: none verdict

# generate
covenant generate tests/integration/fixtures/valid.covenant.yaml --no-llm
# Expected: draft written

# audit (with a test events file)
echo '{"contract":"agent@1.0.0","outcome":"ok","tool_calls":["read_files"],"cost_usd":0.05,"duration_ms":1000,"occurred_at":"2026-03-01T00:00:00+00:00","violation_code":null,"model_used":null}' > /tmp/events.jsonl
covenant audit /tmp/events.jsonl
# Expected: audit report

covenant --help
# Expected: help with all 7 subcommands listed
```

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "feat(cli): complete covenant CLI — all 7 commands passing"
```

---

## Self-Review

**Spec coverage check:**
- `covenant init` — Task 9 ✓
- `covenant validate` — Task 4 ✓
- `covenant sign` — Task 6 ✓
- `covenant diff` — Task 5 ✓
- `covenant generate` — Task 8 ✓
- `covenant publish` — Task 10 ✓
- `covenant audit` — Task 7 ✓
- `models/spec.py` all fields — Task 2 ✓
- `spec_loader.py` 4-phase load — Task 2 ✓
- `linter.py` all 5 rules — Task 3 ✓
- `diff_engine.py` all 8 breaking + 7 non-breaking — Task 5 ✓
- `audit_engine.py` declared vs observed, specless mode, percentiles — Task 7 ✓
- `generator.py` static analysis + LLM merge — Task 8 ✓
- `output.py` console/err_console split, all renderers — Task 1 ✓
- `errors.py` all exit codes + CliError + SpecLoadError — Task 1 ✓
- `llm_enhanced` in schema — Task 1 Step 3 ✓
- Both paths to audit exit 1 (zero events + all malformed) — Task 7 Step 6 ✓

**Placeholder scan:** None found. All steps contain complete code.

**Type consistency check:**
- `LintIssue.field` used as `str | None` consistently ✓
- `DiffResult` / `Change` defined in Task 5, used in Task 10 publish 422 handler ✓
- `AuditEvent` defined in `audit_engine.py`, used in `commands/audit.py` ✓
- `StaticAnalysisResult` defined and used consistently ✓
