from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import AnyUrl, BaseModel, ConfigDict, Field


class AgentSpec(BaseModel):
    """Agent identity and runtime metadata."""

    model_config = ConfigDict(extra="forbid")

    name: str
    version: str
    runtime: Literal["python", "typescript", "any"]
    display_name: str | None = None
    entrypoint: str | None = None


class ModelAllowSpec(BaseModel):
    """A single allowed model entry in capabilities.models."""

    model_config = ConfigDict(extra="forbid")

    provider: str
    model: str
    max_tokens: int | None = None


class CapabilitiesSpec(BaseModel):
    """Allowlist of tools and models the agent may use."""

    model_config = ConfigDict(extra="forbid")

    tools: list[str]
    models: list[ModelAllowSpec] | None = None
    external_services: list[str] | None = None


class NetworkSpec(BaseModel):
    """Network egress constraints."""

    model_config = ConfigDict(extra="forbid")

    egress: bool | Literal["scoped"]
    allowed_domains: list[str] | None = None


class FilesystemSpec(BaseModel):
    """Filesystem read/write glob constraints."""

    model_config = ConfigDict(extra="forbid")

    read: list[str] | None = None
    write: list[str] | None = None


class ScopeSpec(BaseModel):
    """Scope limits: file patterns, file size, call count."""

    model_config = ConfigDict(extra="forbid")

    file_patterns: list[str] | None = None
    max_file_size_kb: int | None = None
    max_calls_per_invocation: int | None = None


class BudgetSpec(BaseModel):
    """Cost ceiling constraint."""

    model_config = ConfigDict(extra="forbid")

    max_cost_usd: float


class ConstraintsSpec(BaseModel):
    """All enforcement constraints."""

    model_config = ConfigDict(extra="forbid")

    deny_tools: list[str] | None = None
    network: NetworkSpec | None = None
    filesystem: FilesystemSpec | None = None
    scope: ScopeSpec | None = None
    budget: BudgetSpec | None = None


class InvariantSpec(BaseModel):
    """A single behavioral invariant assertion.

    Uses Field(alias="assert") so the YAML key `assert` maps to
    the Python attribute `assert_expr` (avoiding the keyword conflict).
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str
    description: str | None = None
    assert_expr: str = Field(alias="assert")
    severity: Literal["error", "warn"]


class ProtocolEndpointSpec(BaseModel):
    """Input or output protocol schema reference."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_path: str = Field(alias="schema")
    required: bool = True


class ProtocolErrorSpec(BaseModel):
    """Error envelope schema reference."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_path: str = Field(alias="schema")


class ProtocolsSpec(BaseModel):
    """Input/output/error schema protocol declarations."""

    model_config = ConfigDict(extra="forbid")

    input: ProtocolEndpointSpec | None = None
    output: ProtocolEndpointSpec | None = None
    errors: ProtocolErrorSpec | None = None


class SloSpec(BaseModel):
    """Service level objective declarations."""

    model_config = ConfigDict(extra="forbid")

    latency_p95_ms: int | None = None
    latency_p99_ms: int | None = None
    cost_per_call_usd_max: float | None = None
    error_rate_max_pct: float | None = None
    calls_per_minute_max: int | None = None


class ProvenanceSpec(BaseModel):
    """Ed25519 signing provenance block."""

    model_config = ConfigDict(extra="forbid")

    author: str | None = None
    signed_at: datetime | None = None
    algorithm: Literal["Ed25519"] | None = None
    public_key: str | None = None
    signature: str | None = None


class MetadataSpec(BaseModel):
    """Human-readable metadata and publishing information."""

    model_config = ConfigDict(extra="forbid")

    description: str | None = None
    tags: list[str] | None = None
    homepage: AnyUrl | None = None
    license: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    llm_enhanced: bool | None = None


class CovenantSpec(BaseModel):
    """Root model for a .covenant.yaml behavioral contract."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    covenant: Literal["1.0"]
    agent: AgentSpec
    capabilities: CapabilitiesSpec
    constraints: ConstraintsSpec
    invariants: list[InvariantSpec] | None = None
    protocols: ProtocolsSpec | None = None
    slo: SloSpec | None = None
    provenance: ProvenanceSpec | None = None
    metadata: MetadataSpec | None = None
