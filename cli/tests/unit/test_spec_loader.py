from pathlib import Path

import pytest

from covenant_cli.errors import SpecLoadError
from covenant_cli.models.spec_loader import load_spec

FIXTURES = Path(__file__).parent.parent / "integration" / "fixtures"


def test_load_valid_spec(tmp_path: Path) -> None:
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


def test_load_missing_file(tmp_path: Path) -> None:
    with pytest.raises(SpecLoadError) as exc_info:
        load_spec(tmp_path / "nonexistent.yaml")
    assert exc_info.value.phase == "file"
    assert exc_info.value.exit_code == 2


def test_load_invalid_yaml(tmp_path: Path) -> None:
    p = tmp_path / "bad.yaml"
    p.write_text("covenant: [\nbroken yaml")
    with pytest.raises(SpecLoadError) as exc_info:
        load_spec(p)
    assert exc_info.value.phase == "yaml"
    assert exc_info.value.exit_code == 1


def test_load_schema_violation(tmp_path: Path) -> None:
    # Missing required 'constraints' key
    p = tmp_path / "no_constraints.yaml"
    p.write_text(
        """
covenant: "1.0"
agent:
  name: test-agent
  version: "1.0.0"
  runtime: python
capabilities:
  tools: [read_files]
"""
    )
    with pytest.raises(SpecLoadError) as exc_info:
        load_spec(p)
    assert exc_info.value.phase == "schema"
    assert len(exc_info.value.issues) >= 1


def test_schema_collects_all_errors(tmp_path: Path) -> None:
    # Both 'agent' and 'constraints' missing — should report both
    p = tmp_path / "multi_err.yaml"
    p.write_text(
        """
covenant: "1.0"
capabilities:
  tools: [read_files]
"""
    )
    with pytest.raises(SpecLoadError) as exc_info:
        load_spec(p)
    assert exc_info.value.phase == "schema"
    assert len(exc_info.value.issues) >= 2


def test_load_invalid_agent_name(tmp_path: Path) -> None:
    p = tmp_path / "bad_name.yaml"
    p.write_text(
        """
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
"""
    )
    with pytest.raises(SpecLoadError) as exc_info:
        load_spec(p)
    assert exc_info.value.phase == "schema"


def test_assert_field_alias(tmp_path: Path) -> None:
    """InvariantSpec.assert_expr must parse from the 'assert' YAML key."""
    p = tmp_path / "with_inv.yaml"
    p.write_text(
        """
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
"""
    )
    spec = load_spec(p)
    assert spec.invariants is not None
    assert spec.invariants[0].assert_expr == "cost_usd < 0.10"
    assert spec.invariants[0].id == "INV-001"
