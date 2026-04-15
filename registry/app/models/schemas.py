from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ── Publish ───────────────────────────────────────────────────────────────────

class PublishRequest(BaseModel):
    spec_raw: str = Field(..., description="Raw YAML bytes of the .covenant.yaml")


class PublishResponse(BaseModel):
    contract_id: uuid.UUID
    version_id: uuid.UUID
    agent_name: str
    version: str
    breaking: bool
    message: str


# ── Contract ──────────────────────────────────────────────────────────────────

class VersionSummary(BaseModel):
    version: str
    breaking: bool
    published_at: datetime
    downloads: int
    author: str | None


class ContractResponse(BaseModel):
    id: uuid.UUID
    agent_name: str
    latest_version: str
    created_at: datetime
    versions: list[VersionSummary] = []


class ContractVersionResponse(BaseModel):
    id: uuid.UUID
    agent_name: str
    version: str
    spec: dict[str, Any]
    spec_raw: str
    signature: str | None
    public_key: str | None
    author: str | None
    breaking: bool
    diff_summary: dict[str, Any] | None
    published_at: datetime
    downloads: int


# ── Diff ─────────────────────────────────────────────────────────────────────

class DiffResponse(BaseModel):
    from_version: str
    to_version: str
    breaking: bool
    semver_verdict: str
    breaking_changes: list[str]
    non_breaking_changes: list[str]


# ── Audit ─────────────────────────────────────────────────────────────────────

class AuditIngestRequest(BaseModel):
    contract: str
    outcome: str
    tool_calls: list[dict[str, Any]] = []
    cost_usd: float = 0.0
    duration_ms: float = 0.0
    occurred_at: datetime
    violation_code: str | None = None
    model_used: str | None = None


class AuditEventResponse(BaseModel):
    id: uuid.UUID
    version: str | None
    event_type: str
    payload: dict[str, Any]
    occurred_at: datetime


class AuditQueryResponse(BaseModel):
    total: int
    events: list[AuditEventResponse]


# ── Search ────────────────────────────────────────────────────────────────────

class SearchResult(BaseModel):
    agent_name: str
    latest_version: str
    description: str | None
    tags: list[str]
    downloads: int


class SearchResponse(BaseModel):
    total: int
    results: list[SearchResult]


# ── Verify ────────────────────────────────────────────────────────────────────

class VerifyRequest(BaseModel):
    spec_raw: str
    public_key: str
    signature: str


class VerifyResponse(BaseModel):
    valid: bool
    message: str
