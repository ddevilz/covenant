from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.conftest import MINIMAL_SPEC


async def test_ingest_pass_event(client: AsyncClient):
    await client.post("/contracts", json={"spec_raw": MINIMAL_SPEC})
    resp = await client.post(
        "/contracts/test-agent/audit",
        json={
            "contract": "test-agent@0.1.0",
            "outcome": "pass",
            "tool_calls": [{"name": "read_file", "args": {}}],
            "cost_usd": 0.005,
            "duration_ms": 432.1,
            "occurred_at": "2026-04-10T12:00:00Z",
            "violation_code": None,
            "model_used": "gpt-4o-mini",
        },
    )
    assert resp.status_code == 202
    assert resp.json()["accepted"] is True


async def test_ingest_violation_event(client: AsyncClient):
    await client.post("/contracts", json={"spec_raw": MINIMAL_SPEC})
    resp = await client.post(
        "/contracts/test-agent/audit",
        json={
            "contract": "test-agent@0.1.0",
            "outcome": "violation",
            "tool_calls": [],
            "cost_usd": 0.001,
            "duration_ms": 100.0,
            "occurred_at": "2026-04-10T12:01:00Z",
            "violation_code": "DENIED_TOOL",
            "model_used": "gpt-4o-mini",
        },
    )
    assert resp.status_code == 202


async def test_ingest_unknown_contract_returns_404(client: AsyncClient):
    resp = await client.post(
        "/contracts/nonexistent/audit",
        json={
            "contract": "nonexistent@0.1.0",
            "outcome": "pass",
            "tool_calls": [],
            "cost_usd": 0,
            "duration_ms": 0,
            "occurred_at": "2026-04-10T12:00:00Z",
        },
    )
    assert resp.status_code == 404


async def test_query_audit_without_key_returns_401(client: AsyncClient):
    await client.post("/contracts", json={"spec_raw": MINIMAL_SPEC})
    resp = await client.get("/contracts/test-agent/audit")
    assert resp.status_code == 401


async def test_query_audit_with_master_key(client: AsyncClient, monkeypatch):
    monkeypatch.setenv("COVENANT_MASTER_KEY", "test-master-key")
    await client.post("/contracts", json={"spec_raw": MINIMAL_SPEC})

    resp = await client.get(
        "/contracts/test-agent/audit",
        headers={"Authorization": "Bearer test-master-key"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert "events" in data
