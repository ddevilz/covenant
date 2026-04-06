from __future__ import annotations

import textwrap
from pathlib import Path

import pytest


MINIMAL_SPEC = textwrap.dedent("""\
    covenant: "1.0"
    agent:
      name: test-agent
      version: 0.1.0
      runtime: python
    capabilities:
      tools:
        - read_file
        - write_file
    constraints:
      budget:
        max_cost_usd: 1.0
""")

SPEC_WITH_DENY = textwrap.dedent("""\
    covenant: "1.0"
    agent:
      name: test-agent
      version: 0.1.0
      runtime: python
    capabilities:
      tools:
        - read_file
    constraints:
      deny_tools:
        - write_file
      budget:
        max_cost_usd: 1.0
""")

SPEC_WITH_CALL_LIMIT = textwrap.dedent("""\
    covenant: "1.0"
    agent:
      name: test-agent
      version: 0.1.0
      runtime: python
    capabilities:
      tools:
        - read_file
    constraints:
      budget:
        max_cost_usd: 1.0
      scope:
        max_calls_per_invocation: 1
""")

SPEC_WITH_INVARIANT = textwrap.dedent("""\
    covenant: "1.0"
    agent:
      name: test-agent
      version: 0.1.0
      runtime: python
    capabilities:
      tools:
        - read_file
    constraints:
      budget:
        max_cost_usd: 1.0
    invariants:
      - id: INV-001
        description: output must be non-empty
        assert: "len(output) > 0"
        severity: error
""")

SPEC_WITH_WARN_INVARIANT = textwrap.dedent("""\
    covenant: "1.0"
    agent:
      name: test-agent
      version: 0.1.0
      runtime: python
    capabilities:
      tools:
        - read_file
    constraints:
      budget:
        max_cost_usd: 1.0
    invariants:
      - id: INV-002
        description: warn only
        assert: "False"
        severity: warn
""")


@pytest.fixture
def spec_file(tmp_path: Path) -> Path:
    p = tmp_path / "test.covenant.yaml"
    p.write_text(MINIMAL_SPEC, encoding="utf-8")
    return p


@pytest.fixture
def spec_deny_file(tmp_path: Path) -> Path:
    p = tmp_path / "deny.covenant.yaml"
    p.write_text(SPEC_WITH_DENY, encoding="utf-8")
    return p


@pytest.fixture
def spec_call_limit_file(tmp_path: Path) -> Path:
    p = tmp_path / "call_limit.covenant.yaml"
    p.write_text(SPEC_WITH_CALL_LIMIT, encoding="utf-8")
    return p


@pytest.fixture
def spec_invariant_file(tmp_path: Path) -> Path:
    p = tmp_path / "invariant.covenant.yaml"
    p.write_text(SPEC_WITH_INVARIANT, encoding="utf-8")
    return p


@pytest.fixture
def spec_warn_invariant_file(tmp_path: Path) -> Path:
    p = tmp_path / "warn_invariant.covenant.yaml"
    p.write_text(SPEC_WITH_WARN_INVARIANT, encoding="utf-8")
    return p
