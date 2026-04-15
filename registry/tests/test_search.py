from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.conftest import MINIMAL_SPEC

SPEC_WITH_META = """\
covenant: "1.0"
agent:
  name: code-reviewer
  version: 1.0.0
  runtime: python
capabilities:
  tools:
    - read_file
constraints:
  budget:
    max_cost_usd: 2.0
metadata:
  description: Reviews code for quality and security issues
  tags:
    - code
    - review
    - security
"""


async def test_search_by_name(client: AsyncClient):
    await client.post("/contracts", json={"spec_raw": MINIMAL_SPEC})
    await client.post("/contracts", json={"spec_raw": SPEC_WITH_META})
    resp = await client.get("/search?q=code")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    names = [r["agent_name"] for r in data["results"]]
    assert "code-reviewer" in names


async def test_search_by_tag(client: AsyncClient):
    await client.post("/contracts", json={"spec_raw": SPEC_WITH_META})
    resp = await client.get("/search?tag=security")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["results"][0]["agent_name"] == "code-reviewer"


async def test_search_no_query_returns_all(client: AsyncClient):
    await client.post("/contracts", json={"spec_raw": MINIMAL_SPEC})
    await client.post("/contracts", json={"spec_raw": SPEC_WITH_META})
    resp = await client.get("/search")
    assert resp.status_code == 200
    assert resp.json()["total"] == 2


async def test_search_no_match_returns_empty(client: AsyncClient):
    await client.post("/contracts", json={"spec_raw": MINIMAL_SPEC})
    resp = await client.get("/search?q=zzz-nonexistent")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0
    assert resp.json()["results"] == []


async def test_search_result_has_expected_fields(client: AsyncClient):
    await client.post("/contracts", json={"spec_raw": SPEC_WITH_META})
    resp = await client.get("/search?q=code-reviewer")
    assert resp.status_code == 200
    result = resp.json()["results"][0]
    assert "agent_name" in result
    assert "latest_version" in result
    assert "tags" in result
    assert "downloads" in result
