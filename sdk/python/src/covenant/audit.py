from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class AuditEvent(BaseModel):
    """A single enforcement audit record emitted after each @contract invocation.

    Args:
        contract: "agent_name@version" identifier.
        outcome: "pass" or "violation".
        tool_calls: List of tool call dicts with name/args keys.
        cost_usd: Total LLM cost for the invocation.
        duration_ms: Wall-clock time in milliseconds.
        occurred_at: UTC timestamp of the invocation.
        violation_code: Violation code if outcome is "violation", else None.
        model_used: Last model identifier called, or None.
    """

    contract: str
    outcome: str
    tool_calls: list[dict[str, Any]]
    cost_usd: float
    duration_ms: float
    occurred_at: datetime
    violation_code: str | None = None
    model_used: str | None = None


class AuditEmitter:
    """Emits AuditEvents to the Covenant registry. Fire-and-forget, never blocks.

    If COVENANT_REGISTRY_URL is not set, emit() is a no-op.
    Network failures are logged at DEBUG and silently discarded.
    """

    def __init__(self) -> None:
        self._url = os.environ.get("COVENANT_REGISTRY_URL")
        self._key = os.environ.get("COVENANT_API_KEY", "")

    def emit(self, event: AuditEvent) -> None:
        """Schedule an async POST. Never raises, never blocks the call path.

        Args:
            event: AuditEvent to send.
        """
        if not self._url:
            return
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(self._post(event))
        except RuntimeError:
            pass  # no running loop — skip silently

    async def _post(self, event: AuditEvent) -> None:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(
                    f"{self._url.rstrip('/')}/audit",
                    json=event.model_dump(mode="json"),
                    headers={"Authorization": f"Bearer {self._key}"},
                )
        except Exception:
            logger.debug("Audit emit failed", exc_info=True)
