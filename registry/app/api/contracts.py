from __future__ import annotations

import json
from typing import Annotated, Any

import yaml
from fastapi import APIRouter, BackgroundTasks, Depends, Header, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth import check_master_key, require_publish_key
from app.db import get_session
from app.errors import BreakingChangeError, ContractNotFound, ValidationError
from app.models.schemas import (
    ContractResponse,
    ContractVersionResponse,
    DiffResponse,
    PublishRequest,
    PublishResponse,
    VersionSummary,
)
from app.models.tables import Contract, ContractVersion
from app.services.diff import check_semver_bump, diff_specs

router = APIRouter(prefix="/contracts", tags=["contracts"])


# ── POST /contracts ───────────────────────────────────────────────────────────

@router.post("", response_model=PublishResponse, status_code=201)
async def publish_contract(
    body: PublishRequest,
    authorization: Annotated[str | None, Header()] = None,
    session: AsyncSession = Depends(get_session),
) -> PublishResponse:
    """Publish a new contract or version.

    Auth: requires publish API key or master key.
    If COVENANT_MASTER_KEY is not set the endpoint is open (single-tenant / dev mode).
    """
    import os
    master_configured = bool(os.environ.get("COVENANT_MASTER_KEY"))
    if master_configured and not check_master_key(authorization):
        await require_publish_key(session, authorization)

    # Parse + validate the raw YAML
    try:
        spec_dict: Any = yaml.safe_load(body.spec_raw)
    except yaml.YAMLError as e:
        raise ValidationError([f"YAML parse error: {e}"])

    if not isinstance(spec_dict, dict):
        raise ValidationError(["Spec must be a YAML mapping"])

    agent_name: str = (spec_dict.get("agent") or {}).get("name", "")
    incoming_version: str = (spec_dict.get("agent") or {}).get("version", "")
    if not agent_name or not incoming_version:
        raise ValidationError(["agent.name and agent.version are required"])

    # Extract provenance fields
    prov = spec_dict.get("provenance") or {}
    signature = prov.get("signature")
    public_key = prov.get("public_key")
    author = prov.get("author")

    # Load or create Contract row
    result = await session.execute(
        select(Contract)
        .where(Contract.agent_name == agent_name)
        .options(selectinload(Contract.versions))
    )
    contract = result.scalar_one_or_none()

    diff_summary = None
    is_breaking = False

    if contract is not None:
        # Find previous version spec for diff
        prev_versions = sorted(contract.versions, key=lambda v: v.published_at)
        if prev_versions:
            prev_spec = prev_versions[-1].spec
            diff_result = diff_specs(prev_spec, spec_dict)
            is_breaking = diff_result.breaking
            diff_summary = diff_result.to_dict()

            if not check_semver_bump(contract.latest_version, incoming_version, is_breaking):
                raise BreakingChangeError(
                    current_version=contract.latest_version,
                    incoming_version=incoming_version,
                    breaking_changes=diff_result.breaking_changes,
                )
        contract.latest_version = incoming_version
    else:
        contract = Contract(agent_name=agent_name, latest_version=incoming_version)
        session.add(contract)
        await session.flush()  # get contract.id

    version_row = ContractVersion(
        contract_id=contract.id,
        version=incoming_version,
        spec=spec_dict,
        spec_raw=body.spec_raw,
        signature=signature,
        public_key=public_key,
        author=author,
        breaking=is_breaking,
        diff_summary=diff_summary,
    )
    session.add(version_row)
    await session.commit()
    await session.refresh(contract)
    await session.refresh(version_row)

    return PublishResponse(
        contract_id=contract.id,
        version_id=version_row.id,
        agent_name=agent_name,
        version=incoming_version,
        breaking=is_breaking,
        message="published" if not is_breaking else "published (breaking change)",
    )


# ── GET /contracts/{name}/versions ────────────────────────────────────────────
# NOTE: specific literal sub-paths must be registered BEFORE /{name}/{version}

@router.get("/{name}/versions", response_model=ContractResponse)
async def list_versions(
    name: str,
    session: AsyncSession = Depends(get_session),
) -> ContractResponse:
    """List all versions of a contract with diff summaries."""
    contract = await _get_contract(session, name)
    versions = sorted(contract.versions, key=lambda v: v.published_at)
    return ContractResponse(
        id=contract.id,
        agent_name=contract.agent_name,
        latest_version=contract.latest_version,
        created_at=contract.created_at,
        versions=[
            VersionSummary(
                version=v.version,
                breaking=v.breaking,
                published_at=v.published_at,
                downloads=v.downloads,
                author=v.author,
            )
            for v in versions
        ],
    )


# ── GET /contracts/{name}/diff ────────────────────────────────────────────────

@router.get("/{name}/diff", response_model=DiffResponse)
async def get_diff(
    name: str,
    from_version: str = Query(..., description="Base version"),
    to_version: str = Query(..., description="Target version"),
    session: AsyncSession = Depends(get_session),
) -> DiffResponse:
    """Compute behavioral diff between two versions of a contract."""
    contract = await _get_contract(session, name)
    version_map = {v.version: v for v in contract.versions}

    if from_version not in version_map:
        raise ContractNotFound(name, from_version)
    if to_version not in version_map:
        raise ContractNotFound(name, to_version)

    result = diff_specs(version_map[from_version].spec, version_map[to_version].spec)
    return DiffResponse(
        from_version=from_version,
        to_version=to_version,
        breaking=result.breaking,
        semver_verdict=result.semver_verdict,
        breaking_changes=result.breaking_changes,
        non_breaking_changes=result.non_breaking_changes,
    )


# ── GET /contracts/{name} ─────────────────────────────────────────────────────
# Registered after /versions and /diff so they take priority

@router.get("/{name}", response_model=ContractVersionResponse)
async def get_latest(
    name: str,
    session: AsyncSession = Depends(get_session),
) -> ContractVersionResponse:
    """Resolve latest version of a contract by agent name."""
    contract = await _get_contract(session, name)
    versions = sorted(contract.versions, key=lambda v: v.published_at, reverse=True)
    if not versions:
        raise ContractNotFound(name)
    v = versions[0]
    return _version_response(name, v)


# ── GET /contracts/{name}/{version} ──────────────────────────────────────────

@router.get("/{name}/{version}", response_model=ContractVersionResponse)
async def get_version(
    name: str,
    version: str,
    session: AsyncSession = Depends(get_session),
) -> ContractVersionResponse:
    """Resolve a specific version of a contract."""
    contract = await _get_contract(session, name)
    for v in contract.versions:
        if v.version == version:
            v.downloads += 1
            await session.commit()
            return _version_response(name, v)
    raise ContractNotFound(name, version)


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_contract(session: AsyncSession, name: str) -> Contract:
    result = await session.execute(
        select(Contract)
        .where(Contract.agent_name == name)
        .options(selectinload(Contract.versions))
    )
    contract = result.scalar_one_or_none()
    if contract is None:
        raise ContractNotFound(name)
    return contract


def _version_response(name: str, v: ContractVersion) -> ContractVersionResponse:
    return ContractVersionResponse(
        id=v.id,
        agent_name=name,
        version=v.version,
        spec=v.spec,
        spec_raw=v.spec_raw,
        signature=v.signature,
        public_key=v.public_key,
        author=v.author,
        breaking=v.breaking,
        diff_summary=v.diff_summary,
        published_at=v.published_at,
        downloads=v.downloads,
    )
