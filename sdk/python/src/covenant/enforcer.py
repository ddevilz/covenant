from __future__ import annotations

import time
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from typing import Any, Awaitable, Callable

from covenant.audit import AuditEmitter, AuditEvent
from covenant.errors import CovenantViolationError
from covenant.interceptor import ToolCall, ToolCallInterceptor, _active_interceptor
from covenant.invariants import InvariantEvaluator
from covenant.loader import load_spec
from covenant.models import CovenantSpec
from covenant.validator import validate_input, validate_output

_emitter = AuditEmitter()


class ContractEnforcer:
    """Stateless enforcer loaded once per @contract decoration.

    Args:
        spec: Fully-validated CovenantSpec.
        spec_path: Path to the .covenant.yaml (used to resolve protocol schema paths).
    """

    def __init__(self, spec: CovenantSpec, spec_path: Path) -> None:
        self._spec = spec
        self._spec_dir = spec_path.parent

    async def enforce(
        self, fn: Callable[..., Awaitable[Any]], *args: Any, **kwargs: Any
    ) -> Any:
        """Run the full enforcement flow around a single agent invocation.

        Enforcement sequence:
            1. Validate input against protocols.input.schema
            2. Set ContextVar to activate the OpenAI SDK interceptor
            3. Await the wrapped agent function
            4. Validate output against protocols.output.schema
            5. Run invariant assertions
            6. Emit audit event (fire-and-forget)
            7. Return output

        Args:
            fn: The wrapped async agent function.
            *args: Positional arguments forwarded to fn.
            **kwargs: Keyword arguments forwarded to fn.

        Returns:
            Whatever fn returns.

        Raises:
            CovenantViolationError: On any constraint or invariant breach.
        """
        start = time.monotonic()

        # 1. Input validation
        input_data = args[0] if args else kwargs
        input_schema = (
            self._spec.protocols.input.schema_path
            if self._spec.protocols and self._spec.protocols.input
            else None
        )
        validate_input(input_data, input_schema, self._spec_dir)

        # 2. Install per-invocation interceptor via ContextVar
        interceptor = ToolCallInterceptor(self._spec)
        token = _active_interceptor.set(interceptor)

        outcome = "pass"
        violation_code: str | None = None
        output: Any = None

        try:
            output = await fn(*args, **kwargs)
        except CovenantViolationError as exc:
            outcome = "violation"
            violation_code = exc.code
            raise
        finally:
            _active_interceptor.reset(token)

        # 3. Output validation
        output_schema = (
            self._spec.protocols.output.schema_path
            if self._spec.protocols and self._spec.protocols.output
            else None
        )
        validate_output(output, output_schema, self._spec_dir)

        # 4. Invariant evaluation
        duration_ms = (time.monotonic() - start) * 1000
        if self._spec.invariants:
            evaluator = InvariantEvaluator(self._spec.invariants)
            try:
                evaluator.evaluate(
                    {
                        "input": input_data,
                        "output": output,
                        "tool_calls": interceptor.tool_calls,
                        "duration_ms": duration_ms,
                        "cost_usd": interceptor.total_cost_usd,
                        "model_used": interceptor.model_used,
                    }
                )
            except CovenantViolationError as exc:
                outcome = "violation"
                violation_code = exc.code
                raise

        # 5. Emit audit event (fire-and-forget)
        _emitter.emit(
            AuditEvent(
                contract=f"{self._spec.agent.name}@{self._spec.agent.version}",
                outcome=outcome,
                tool_calls=[
                    {"name": tc.name, "args": tc.args}
                    for tc in interceptor.tool_calls
                ],
                cost_usd=interceptor.total_cost_usd,
                duration_ms=duration_ms,
                occurred_at=datetime.now(timezone.utc),
                violation_code=violation_code,
                model_used=interceptor.model_used,
            )
        )

        return output


def contract(spec_path: str | Path) -> Callable:
    """Decorator factory that wraps an async agent function with contract enforcement.

    The spec is loaded once at decoration time (import time). Any spec parse error
    raises immediately — not at call time.

    Args:
        spec_path: Path to the .covenant.yaml file.

    Returns:
        Decorator that wraps an async function with enforcement.

    Example:
        @contract("./my-agent.covenant.yaml")
        async def run(input: dict) -> dict:
            ...
    """
    path = Path(spec_path)
    spec = load_spec(path)
    enforcer = ContractEnforcer(spec, path)

    def decorator(fn: Callable[..., Awaitable[Any]]) -> Callable:
        @wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            return await enforcer.enforce(fn, *args, **kwargs)

        return wrapper

    return decorator


async def call_tool(
    name: str, fn: Callable[..., Awaitable[Any]], /, *args: Any, **kwargs: Any
) -> Any:
    """Explicit enforcement layer for non-LLM tool calls.

    Use this to enforce tool constraints for filesystem, HTTP, subprocess, or any
    other I/O that doesn't go through the OpenAI SDK interceptor.

    If called outside a @contract invocation (no active interceptor), the function
    executes directly with no enforcement applied.

    Args:
        name: Tool name to check against capabilities.tools and constraints.deny_tools.
        fn: Async callable to invoke if the tool is permitted.
        *args: Positional arguments forwarded to fn.
        **kwargs: Keyword arguments forwarded to fn.

    Returns:
        Whatever fn returns.

    Raises:
        CovenantViolationError: UNDECLARED_TOOL or DENIED_TOOL if the tool is not allowed.

    Example:
        result = await call_tool("read_file", read_file_async, path="./data.csv")
    """
    interceptor = _active_interceptor.get()
    if interceptor is not None:
        interceptor._check_tool(name)

    result = await fn(*args, **kwargs)

    if interceptor is not None:
        interceptor.tool_calls.append(
            ToolCall(
                name=name,
                args=kwargs,
                result=result,
                cost_usd=0.0,
            )
        )

    return result
