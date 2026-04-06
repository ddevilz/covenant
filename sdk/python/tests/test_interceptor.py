from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from covenant.errors import CovenantViolationError
from covenant.interceptor import ToolCall, ToolCallInterceptor
from covenant.loader import load_spec


def _make_response(
    tool_names: list[str] | None = None,
    prompt_tokens: int = 100,
    completion_tokens: int = 50,
    model: str = "gpt-4o-mini",
) -> MagicMock:
    """Build a fake OpenAI ChatCompletion response."""
    response = MagicMock()
    response.usage.prompt_tokens = prompt_tokens
    response.usage.completion_tokens = completion_tokens

    if tool_names:
        tool_calls = []
        for name in tool_names:
            tc = MagicMock()
            tc.function.name = name
            tc.function.arguments = "{}"
            tool_calls.append(tc)
        response.choices[0].message.tool_calls = tool_calls
    else:
        response.choices[0].message.tool_calls = []

    return response


def test_happy_path_no_tool_calls(spec_file):
    spec = load_spec(spec_file)
    interceptor = ToolCallInterceptor(spec)
    response = _make_response()
    interceptor.record_completion(response, "gpt-4o-mini")
    assert interceptor.model_used == "gpt-4o-mini"
    assert len(interceptor.tool_calls) == 0


def test_declared_tool_accepted(spec_file):
    spec = load_spec(spec_file)
    interceptor = ToolCallInterceptor(spec)
    response = _make_response(tool_names=["read_file"])
    interceptor.record_completion(response, "gpt-4o-mini")
    assert len(interceptor.tool_calls) == 1
    assert interceptor.tool_calls[0].name == "read_file"


def test_undeclared_tool_raises(spec_file):
    spec = load_spec(spec_file)
    interceptor = ToolCallInterceptor(spec)
    response = _make_response(tool_names=["bash"])
    with pytest.raises(CovenantViolationError) as exc_info:
        interceptor.record_completion(response, "gpt-4o-mini")
    assert exc_info.value.code == "UNDECLARED_TOOL"
    assert exc_info.value.detail["tool"] == "bash"


def test_denied_tool_raises(spec_deny_file):
    spec = load_spec(spec_deny_file)
    interceptor = ToolCallInterceptor(spec)
    response = _make_response(tool_names=["write_file"])
    with pytest.raises(CovenantViolationError) as exc_info:
        interceptor.record_completion(response, "gpt-4o-mini")
    assert exc_info.value.code == "DENIED_TOOL"
    assert exc_info.value.detail["tool"] == "write_file"


def test_budget_exceeded_raises(spec_file):
    spec = load_spec(spec_file)
    interceptor = ToolCallInterceptor(spec)
    # gpt-4o-mini: 0.00015/1k input, 0.0006/1k output
    # 1M input tokens = 1000 * 0.00015 = $0.15 per 1k... need many calls
    # Force budget exceeded by manually setting total_cost_usd
    interceptor.total_cost_usd = 0.999
    response = _make_response(prompt_tokens=10_000, completion_tokens=5_000)
    with pytest.raises(CovenantViolationError) as exc_info:
        interceptor.record_completion(response, "gpt-4o-mini")
    assert exc_info.value.code == "BUDGET_EXCEEDED"
    assert "max_cost_usd" in exc_info.value.detail


def test_call_limit_exceeded_raises(spec_call_limit_file):
    spec = load_spec(spec_call_limit_file)
    interceptor = ToolCallInterceptor(spec)
    # First call: allowed (1 tool call = limit)
    response1 = _make_response(tool_names=["read_file"])
    interceptor.record_completion(response1, "gpt-4o-mini")
    assert len(interceptor.tool_calls) == 1
    # Second call: exceeds limit of 1
    response2 = _make_response(tool_names=["read_file"])
    with pytest.raises(CovenantViolationError) as exc_info:
        interceptor.record_completion(response2, "gpt-4o-mini")
    assert exc_info.value.code == "CALL_LIMIT_EXCEEDED"


def test_tool_call_dataclass_fields():
    tc = ToolCall(name="read_file", args={"path": "x"}, result="content", cost_usd=0.01)
    assert tc.name == "read_file"
    assert tc.args == {"path": "x"}
    assert tc.result == "content"
    assert tc.cost_usd == 0.01
    assert tc.timestamp is not None
