from __future__ import annotations

import contextvars
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from covenant.errors import CovenantViolationError

if TYPE_CHECKING:
    from covenant.models import CovenantSpec

# Per-invocation interceptor — set by ContractEnforcer before awaiting the agent fn.
# Each asyncio task gets its own value; concurrent invocations are fully isolated.
_active_interceptor: contextvars.ContextVar[ToolCallInterceptor | None] = (
    contextvars.ContextVar("_active_interceptor", default=None)
)

# Best-effort price table (input $/1k tokens, output $/1k tokens)
_PRICE_TABLE: dict[str, tuple[float, float]] = {
    "gpt-4o": (0.005, 0.015),
    "gpt-4o-mini": (0.00015, 0.0006),
    "gpt-4-turbo": (0.01, 0.03),
    "gpt-3.5-turbo": (0.0005, 0.0015),
    "claude-opus-4-6": (0.015, 0.075),
    "claude-sonnet-4-6": (0.003, 0.015),
    "claude-haiku-4-5-20251001": (0.00025, 0.00125),
}


@dataclass
class ToolCall:
    """A single tool call observed during an agent invocation.

    Args:
        name: Tool function name.
        args: Arguments passed to the tool.
        result: Return value from the tool (None if not yet resolved).
        cost_usd: LLM cost attributed to this call.
        timestamp: UTC time the call was observed.
    """

    name: str
    args: dict
    result: Any
    cost_usd: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class ToolCallInterceptor:
    """Stateful per-invocation enforcer installed via ContextVar.

    Tracks all tool calls and cumulative cost for a single @contract invocation.
    Raises CovenantViolationError immediately on any constraint breach.
    """

    def __init__(self, spec: CovenantSpec) -> None:
        self._spec = spec
        self.tool_calls: list[ToolCall] = []
        self.total_cost_usd: float = 0.0
        self.model_used: str | None = None

    def record_completion(self, response: Any, model: str) -> None:
        """Called after each OpenAI completion response.

        Extracts usage, computes cost, checks model declaration, checks tool calls
        in the response, and enforces budget + call limits.

        Args:
            response: OpenAI ChatCompletion response object.
            model: Model identifier string from the request kwargs.

        Raises:
            CovenantViolationError: On BUDGET_EXCEEDED, UNDECLARED_MODEL,
                UNDECLARED_TOOL, DENIED_TOOL, or CALL_LIMIT_EXCEEDED.
        """
        self.model_used = model

        # Accumulate cost from usage
        usage = getattr(response, "usage", None)
        if usage:
            in_tok = getattr(usage, "prompt_tokens", 0) or 0
            out_tok = getattr(usage, "completion_tokens", 0) or 0
            in_price, out_price = _PRICE_TABLE.get(model, (0.0, 0.0))
            self.total_cost_usd += (in_tok / 1000 * in_price) + (out_tok / 1000 * out_price)

        # Budget check
        budget = self._spec.constraints.budget
        if budget and self.total_cost_usd > budget.max_cost_usd:
            raise CovenantViolationError(
                code="BUDGET_EXCEEDED",
                detail={
                    "max_cost_usd": budget.max_cost_usd,
                    "actual_cost_usd": round(self.total_cost_usd, 6),
                },
            )

        # Model check (capabilities.models is a list of ModelAllowSpec)
        declared_models = self._spec.capabilities.models
        if declared_models is not None:
            allowed_model_ids = {m.model for m in declared_models}
            if model not in allowed_model_ids:
                raise CovenantViolationError(
                    code="UNDECLARED_MODEL",
                    detail={"model": model, "declared": sorted(allowed_model_ids)},
                )

        # Extract tool calls from response choices
        choices = getattr(response, "choices", None) or []
        if choices:
            msg = getattr(choices[0], "message", None)
            response_tool_calls = getattr(msg, "tool_calls", None) or []
            for tc in response_tool_calls:
                fn = getattr(tc, "function", None)
                if not fn:
                    continue
                tool_name = fn.name
                args = json.loads(fn.arguments) if fn.arguments else {}
                self._check_tool(tool_name)
                self.tool_calls.append(
                    ToolCall(name=tool_name, args=args, result=None, cost_usd=0.0)
                )

        # Call limit check
        scope = self._spec.constraints.scope
        if scope and scope.max_calls_per_invocation is not None:
            if len(self.tool_calls) > scope.max_calls_per_invocation:
                raise CovenantViolationError(
                    code="CALL_LIMIT_EXCEEDED",
                    detail={
                        "max_calls": scope.max_calls_per_invocation,
                        "actual_calls": len(self.tool_calls),
                    },
                )

    def _check_tool(self, name: str) -> None:
        """Verify tool name against capabilities and deny list.

        Raises:
            CovenantViolationError: DENIED_TOOL or UNDECLARED_TOOL.
        """
        allowed = set(self._spec.capabilities.tools)
        denied = set(self._spec.constraints.deny_tools or [])

        if name in denied:
            raise CovenantViolationError(
                code="DENIED_TOOL",
                detail={"tool": name},
            )
        if name not in allowed:
            raise CovenantViolationError(
                code="UNDECLARED_TOOL",
                detail={"tool": name, "declared": sorted(allowed)},
            )


# ---------------------------------------------------------------------------
# OpenAI SDK class-level patch — installed once at module import time.
# The patch is a no-op when no interceptor is active in the current context.
# ---------------------------------------------------------------------------

def _install_patches() -> None:
    """Monkey-patch OpenAI Completions at class level. Idempotent."""
    try:
        import openai.resources.chat.completions.completions as _mod
    except ImportError:
        # openai not installed — skip patching (SDK still usable without LLM interception)
        return

    Completions = _mod.Completions
    AsyncCompletions = _mod.AsyncCompletions

    if getattr(Completions, "_covenant_patched", False):
        return

    _orig_create = Completions.create
    _orig_async_create = AsyncCompletions.create

    def _patched_create(self_inner, *args, **kwargs):
        response = _orig_create(self_inner, *args, **kwargs)
        interceptor = _active_interceptor.get()
        if interceptor is not None:
            interceptor.record_completion(response, kwargs.get("model", ""))
        return response

    async def _patched_async_create(self_inner, *args, **kwargs):
        response = await _orig_async_create(self_inner, *args, **kwargs)
        interceptor = _active_interceptor.get()
        if interceptor is not None:
            interceptor.record_completion(response, kwargs.get("model", ""))
        return response

    Completions.create = _patched_create
    AsyncCompletions.create = _patched_async_create
    Completions._covenant_patched = True
    AsyncCompletions._covenant_patched = True


_install_patches()
