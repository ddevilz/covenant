from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.conftest import MINIMAL_SPEC, SPEC_V2_BREAKING, SPEC_V2_NONBREAKING


async def test_publish_first_version(client: AsyncClient):
    resp = await client.post("/contracts", json={"spec_raw": MINIMAL_SPEC})
    assert resp.status_code == 201
    data = resp.json()
    assert data["agent_name"] == "test-agent"
    assert data["version"] == "0.1.0"
    assert data["breaking"] is False


async def test_publish_non_breaking_bump(client: AsyncClient):
    await client.post("/contracts", json={"spec_raw": MINIMAL_SPEC})
    resp = await client.post("/contracts", json={"spec_raw": SPEC_V2_NONBREAKING})
    assert resp.status_code == 201
    data = resp.json()
    assert data["version"] == "0.2.0"
    assert data["breaking"] is False


async def test_publish_breaking_without_major_bump_rejected(client: AsyncClient):
    await client.post("/contracts", json={"spec_raw": MINIMAL_SPEC})
    # SPEC_V2_BREAKING adds a tool but bumps 0.1.0 -> 1.0.0 (major) - should pass
    resp = await client.post("/contracts", json={"spec_raw": SPEC_V2_BREAKING})
    assert resp.status_code == 201
    assert resp.json()["breaking"] is True


async def test_publish_breaking_same_major_rejected(client: AsyncClient):
    await client.post("/contracts", json={"spec_raw": MINIMAL_SPEC})
    # Bump to 0.2.0 but add a new tool (breaking) — should be rejected
    bad_spec = MINIMAL_SPEC.replace("version: 0.1.0", "version: 0.2.0").replace(
        "tools:\n    - read_file", "tools:\n    - read_file\n    - bash"
    )
    resp = await client.post("/contracts", json={"spec_raw": bad_spec})
    assert resp.status_code == 422
    data = resp.json()
    assert data["error"] == "BREAKING_CHANGE_REQUIRES_MAJOR_BUMP"
    assert "breaking_changes" in data["detail"]


async def test_publish_invalid_yaml_rejected(client: AsyncClient):
    resp = await client.post("/contracts", json={"spec_raw": "{ invalid: [yaml"})
    assert resp.status_code == 422


async def test_get_latest_after_publish(client: AsyncClient):
    await client.post("/contracts", json={"spec_raw": MINIMAL_SPEC})
    resp = await client.get("/contracts/test-agent")
    assert resp.status_code == 200
    data = resp.json()
    assert data["agent_name"] == "test-agent"
    assert data["version"] == "0.1.0"


async def test_get_specific_version(client: AsyncClient):
    await client.post("/contracts", json={"spec_raw": MINIMAL_SPEC})
    resp = await client.get("/contracts/test-agent/0.1.0")
    assert resp.status_code == 200
    assert resp.json()["version"] == "0.1.0"


async def test_get_unknown_contract_returns_404(client: AsyncClient):
    resp = await client.get("/contracts/does-not-exist")
    assert resp.status_code == 404
    assert resp.json()["error"] == "CONTRACT_NOT_FOUND"


async def test_list_versions(client: AsyncClient):
    await client.post("/contracts", json={"spec_raw": MINIMAL_SPEC})
    await client.post("/contracts", json={"spec_raw": SPEC_V2_NONBREAKING})
    resp = await client.get("/contracts/test-agent/versions")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["versions"]) == 2
    assert data["versions"][0]["version"] == "0.1.0"
    assert data["versions"][1]["version"] == "0.2.0"
