from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from covenant.enforcer import call_tool, contract
from covenant.errors import CovenantViolationError
from covenant.interceptor import _active_interceptor


# ---------------------------------------------------------------------------
# @contract decorator — happy path
# ---------------------------------------------------------------------------

async def test_contract_happy_path(spec_file):
    @contract(spec_file)
    async def agent(input: dict) -> dict:
        return {"result": "ok"}

    result = await agent({"query": "hello"})
    assert result == {"result": "ok"}


async def test_contract_returns_output_unchanged(spec_file):
    @contract(spec_file)
    async def agent(input: dict) -> list:
        return [1, 2, 3]

    result = await agent({"x": 1})
    assert result == [1, 2, 3]


# ---------------------------------------------------------------------------
# @contract decorator — violations propagate
# ---------------------------------------------------------------------------

async def test_contract_propagates_undeclared_tool(spec_file):
    @contract(spec_file)
    async def agent(input: dict) -> dict:
        # Directly raise from inside the agent (simulates interceptor firing)
        raise CovenantViolationError(code="UNDECLARED_TOOL", detail={"tool": "bash"})

    with pytest.raises(CovenantViolationError) as exc_info:
        await agent({})
    assert exc_info.value.code == "UNDECLARED_TOOL"


async def test_contract_invariant_failure_raises(spec_invariant_file):
    @contract(spec_invariant_file)
    async def agent(input: dict) -> str:
        return ""  # empty string fails len(output) > 0

    with pytest.raises(CovenantViolationError) as exc_info:
        await agent({})
    assert exc_info.value.code == "INVARIANT_FAILED"
    assert exc_info.value.detail["id"] == "INV-001"


async def test_contract_warn_invariant_does_not_raise(spec_warn_invariant_file):
    @contract(spec_warn_invariant_file)
    async def agent(input: dict) -> str:
        return "ok"

    # warn invariant assert=False should not raise
    result = await agent({})
    assert result == "ok"


# ---------------------------------------------------------------------------
# @contract decorator — ContextVar isolation
# ---------------------------------------------------------------------------

async def test_no_active_interceptor_outside_contract():
    assert _active_interceptor.get() is None


async def test_interceptor_active_inside_contract(spec_file):
    captured = []

    @contract(spec_file)
    async def agent(input: dict) -> dict:
        captured.append(_active_interceptor.get())
        return {}

    await agent({})
    assert len(captured) == 1
    assert captured[0] is not None


async def test_interceptor_cleaned_up_after_contract(spec_file):
    @contract(spec_file)
    async def agent(input: dict) -> dict:
        return {}

    await agent({})
    assert _active_interceptor.get() is None


async def test_interceptor_cleaned_up_on_violation(spec_file):
    @contract(spec_file)
    async def agent(input: dict) -> dict:
        raise CovenantViolationError(code="DENIED_TOOL", detail={"tool": "x"})

    with pytest.raises(CovenantViolationError):
        await agent({})
    assert _active_interceptor.get() is None


# ---------------------------------------------------------------------------
# call_tool
# ---------------------------------------------------------------------------

async def test_call_tool_outside_contract_executes_directly():
    async def my_fn(path: str) -> str:
        return f"content of {path}"

    result = await call_tool("read_file", my_fn, path="data.csv")
    assert result == "content of data.csv"


async def test_call_tool_inside_contract_checks_tool(spec_file):
    async def read_file(path: str) -> str:
        return "data"

    @contract(spec_file)
    async def agent(input: dict) -> dict:
        content = await call_tool("read_file", read_file, path="x.csv")
        return {"content": content}

    result = await agent({})
    assert result["content"] == "data"


async def test_call_tool_denied_tool_raises(spec_deny_file):
    async def write_file(path: str, data: str) -> None:
        pass

    @contract(spec_deny_file)
    async def agent(input: dict) -> dict:
        await call_tool("write_file", write_file, path="x.csv", data="y")
        return {}

    with pytest.raises(CovenantViolationError) as exc_info:
        await agent({})
    assert exc_info.value.code == "DENIED_TOOL"


async def test_call_tool_undeclared_tool_raises(spec_file):
    async def bash(cmd: str) -> str:
        return ""

    @contract(spec_file)
    async def agent(input: dict) -> dict:
        await call_tool("bash", bash, cmd="ls")
        return {}

    with pytest.raises(CovenantViolationError) as exc_info:
        await agent({})
    assert exc_info.value.code == "UNDECLARED_TOOL"


async def test_call_tool_records_in_tool_calls(spec_file):
    calls_seen = []

    async def read_file(path: str) -> str:
        return "data"

    @contract(spec_file)
    async def agent(input: dict) -> dict:
        await call_tool("read_file", read_file, path="x.csv")
        interceptor = _active_interceptor.get()
        if interceptor:
            calls_seen.extend(interceptor.tool_calls)
        return {}

    await agent({})
    assert len(calls_seen) == 1
    assert calls_seen[0].name == "read_file"
