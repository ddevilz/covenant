from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from covenant.errors import CovenantViolationError
from covenant.models import InvariantSpec

_SAFE_BUILTINS: dict[str, Any] = {
    "all": all,
    "any": any,
    "len": len,
    "isinstance": isinstance,
    "hasattr": hasattr,
    "getattr": getattr,
    "list": list,
    "dict": dict,
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "None": None,
    "True": True,
    "False": False,
}


def safe_eval(expression: str, context: dict[str, Any]) -> Any:
    """Evaluate an invariant expression in a restricted sandbox.

    Args:
        expression: Python expression string from invariant.assert.
        context: Variables available in the expression (input, output, tool_calls, etc.).

    Returns:
        Result of the expression evaluation.

    Raises:
        CovenantViolationError: INVARIANT_FAILED if the expression raises any exception.
    """
    try:
        return eval(expression, {"__builtins__": _SAFE_BUILTINS}, context)  # noqa: S307
    except CovenantViolationError:
        raise
    except Exception as exc:
        raise CovenantViolationError(
            code="INVARIANT_FAILED",
            detail={"expression": expression, "error": str(exc)},
        ) from exc


@dataclass
class InvariantEvaluator:
    """Runs all invariants against the enforcement context after the agent returns.

    Args:
        invariants: List of InvariantSpec from the loaded CovenantSpec.
    """

    invariants: list[InvariantSpec]

    def evaluate(self, context_dict: dict[str, Any]) -> None:
        """Evaluate every invariant in sequence.

        Args:
            context_dict: Keys: input, output, tool_calls, duration_ms, cost_usd, model_used.

        Raises:
            CovenantViolationError: INVARIANT_FAILED for any severity=error invariant
                whose assert expression returns falsy.
        """
        for inv in self.invariants:
            result = safe_eval(inv.assert_expr, context_dict)
            if not result:
                if inv.severity == "error":
                    raise CovenantViolationError(
                        code="INVARIANT_FAILED",
                        detail={"id": inv.id, "expression": inv.assert_expr},
                    )
                # severity=warn: violation noted but not raised
                # (will be captured in audit event by the enforcer)
