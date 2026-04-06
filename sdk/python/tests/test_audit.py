from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from covenant.audit import AuditEmitter, AuditEvent


def _make_event(**kwargs) -> AuditEvent:
    defaults = dict(
        contract="test-agent@0.1.0",
        outcome="pass",
        tool_calls=[],
        cost_usd=0.01,
        duration_ms=123.4,
        occurred_at=datetime.now(timezone.utc),
        violation_code=None,
        model_used="gpt-4o-mini",
    )
    defaults.update(kwargs)
    return AuditEvent(**defaults)


def test_emit_no_op_when_no_url(monkeypatch):
    monkeypatch.delenv("COVENANT_REGISTRY_URL", raising=False)
    emitter = AuditEmitter()
    # Should not raise
    emitter.emit(_make_event())


def test_emit_no_op_when_url_empty(monkeypatch):
    monkeypatch.setenv("COVENANT_REGISTRY_URL", "")
    emitter = AuditEmitter()
    emitter.emit(_make_event())  # no-op, url is falsy


def test_audit_event_fields():
    event = _make_event(outcome="violation", violation_code="DENIED_TOOL")
    assert event.contract == "test-agent@0.1.0"
    assert event.outcome == "violation"
    assert event.violation_code == "DENIED_TOOL"
    assert event.tool_calls == []
    assert event.model_used == "gpt-4o-mini"


def test_audit_event_serializes():
    event = _make_event()
    data = event.model_dump(mode="json")
    assert data["contract"] == "test-agent@0.1.0"
    assert data["outcome"] == "pass"
    assert isinstance(data["occurred_at"], str)


async def test_emit_creates_task_when_url_set(monkeypatch):
    monkeypatch.setenv("COVENANT_REGISTRY_URL", "http://localhost:8000")
    monkeypatch.setenv("COVENANT_API_KEY", "test-key")

    emitter = AuditEmitter()
    event = _make_event()

    posted = []

    async def mock_post(self_inner, *args, **kwargs):
        posted.append(kwargs)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        return mock_resp

    with patch("httpx.AsyncClient.post", new=mock_post):
        await emitter._post(event)

    # _post was called — event was serialized
    assert len(posted) == 1
    body = posted[0]
    assert body["json"]["contract"] == "test-agent@0.1.0"


async def test_post_swallows_network_error(monkeypatch):
    monkeypatch.setenv("COVENANT_REGISTRY_URL", "http://localhost:9999")

    emitter = AuditEmitter()
    event = _make_event()

    async def failing_post(*args, **kwargs):
        raise ConnectionRefusedError("no server")

    with patch("httpx.AsyncClient.post", new=failing_post):
        # Should not raise
        await emitter._post(event)
