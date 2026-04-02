from pathlib import Path

from covenant_cli.services.generator import (
    _merge_llm_result,
    analyze,
    draft_spec,
)

PYTHON_WITH_LLM = """\
import anthropic
import httpx

async def run_agent(query: str) -> str:
    client = anthropic.Anthropic()
    return "result"

async def helper() -> None:
    pass
"""

PYTHON_WITH_FS = """\
import os
from pathlib import Path

async def process() -> str:
    with open("file.txt") as f:
        data = f.read()
    return data
"""

PYTHON_PLAIN = """\
async def simple_agent(x: int) -> int:
    return x + 1
"""


def test_detects_llm_import(tmp_path: Path) -> None:
    p = tmp_path / "agent.py"
    p.write_text(PYTHON_WITH_LLM)
    result = analyze(p)
    assert result.has_llm is True
    assert result.has_network is True
    assert result.detected_runtime == "python"


def test_detects_filesystem(tmp_path: Path) -> None:
    p = tmp_path / "agent.py"
    p.write_text(PYTHON_WITH_FS)
    result = analyze(p)
    assert result.has_filesystem is True


def test_detects_async_functions(tmp_path: Path) -> None:
    p = tmp_path / "agent.py"
    p.write_text(PYTHON_WITH_LLM)
    result = analyze(p)
    assert "run_agent" in result.agent_functions
    assert "helper" in result.agent_functions


def test_plain_agent_no_network_no_llm(tmp_path: Path) -> None:
    p = tmp_path / "agent.py"
    p.write_text(PYTHON_PLAIN)
    result = analyze(p)
    assert result.has_llm is False
    assert result.has_network is False
    assert result.has_filesystem is False


def test_draft_spec_structure(tmp_path: Path) -> None:
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


def test_draft_spec_network_egress(tmp_path: Path) -> None:
    p = tmp_path / "agent.py"
    p.write_text(PYTHON_WITH_LLM)
    result = analyze(p)
    draft = draft_spec(result, "net-agent")
    assert draft["constraints"]["network"]["egress"] is True


def test_draft_spec_filesystem(tmp_path: Path) -> None:
    p = tmp_path / "agent.py"
    p.write_text(PYTHON_WITH_FS)
    result = analyze(p)
    draft = draft_spec(result, "fs-agent")
    assert "filesystem" in draft["constraints"]
    assert "**/*" in draft["constraints"]["filesystem"]["read"]


def test_llm_merge_fills_description() -> None:
    draft: dict = {
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
            {
                "id": "INV-001",
                "description": "cost check",
                "assert": "cost_usd < 0.10",
                "severity": "error",
            }
        ],
    }
    merged = _merge_llm_result(draft, llm_result)
    assert merged["metadata"]["description"] == "Does code review"
    assert "read_files" in merged["capabilities"]["tools"]
    assert merged["metadata"]["llm_enhanced"] is True
    assert len(merged["invariants"]) == 1
