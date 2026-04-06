from __future__ import annotations

import pytest

from covenant.errors import CovenantViolationError
from covenant.invariants import InvariantEvaluator, safe_eval
from covenant.models import InvariantSpec


def _inv(id: str, expr: str, severity: str = "error") -> InvariantSpec:
    return InvariantSpec.model_validate(
        {"id": id, "assert": expr, "severity": severity}
    )


# --- safe_eval ---

def test_safe_eval_true():
    assert safe_eval("len(output) > 0", {"output": [1, 2, 3]}) is True


def test_safe_eval_false():
    assert safe_eval("len(output) > 0", {"output": []}) is False


def test_safe_eval_allowed_builtins():
    assert safe_eval("isinstance(output, list)", {"output": []}) is True
    assert safe_eval("any([True, False])", {}) is True
    assert safe_eval("all([True, True])", {}) is True


def test_safe_eval_exception_becomes_violation():
    with pytest.raises(CovenantViolationError) as exc_info:
        safe_eval("1 / 0", {})
    assert exc_info.value.code == "INVARIANT_FAILED"
    assert "error" in exc_info.value.detail


def test_safe_eval_blocks_import():
    with pytest.raises(CovenantViolationError) as exc_info:
        safe_eval("__import__('os')", {})
    assert exc_info.value.code == "INVARIANT_FAILED"


def test_safe_eval_blocks_open():
    with pytest.raises(CovenantViolationError) as exc_info:
        safe_eval("open('/etc/passwd')", {})
    assert exc_info.value.code == "INVARIANT_FAILED"


# --- InvariantEvaluator ---

def test_evaluator_passes_on_true():
    evaluator = InvariantEvaluator([_inv("INV-001", "len(output) > 0")])
    evaluator.evaluate({"output": "hello", "input": {}, "tool_calls": [],
                        "duration_ms": 10, "cost_usd": 0, "model_used": None})


def test_evaluator_raises_on_false_error_severity():
    evaluator = InvariantEvaluator([_inv("INV-001", "False", severity="error")])
    with pytest.raises(CovenantViolationError) as exc_info:
        evaluator.evaluate({"output": "", "input": {}, "tool_calls": [],
                            "duration_ms": 10, "cost_usd": 0, "model_used": None})
    assert exc_info.value.code == "INVARIANT_FAILED"
    assert exc_info.value.detail["id"] == "INV-001"


def test_evaluator_does_not_raise_on_false_warn_severity():
    evaluator = InvariantEvaluator([_inv("INV-001", "False", severity="warn")])
    # Should not raise
    evaluator.evaluate({"output": "", "input": {}, "tool_calls": [],
                        "duration_ms": 10, "cost_usd": 0, "model_used": None})


def test_evaluator_multiple_invariants_first_failure_stops():
    evaluator = InvariantEvaluator([
        _inv("INV-001", "False", severity="error"),
        _inv("INV-002", "True", severity="error"),
    ])
    with pytest.raises(CovenantViolationError) as exc_info:
        evaluator.evaluate({"output": "", "input": {}, "tool_calls": [],
                            "duration_ms": 10, "cost_usd": 0, "model_used": None})
    assert exc_info.value.detail["id"] == "INV-001"
