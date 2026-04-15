from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_session
from app.models.schemas import SearchResponse, SearchResult
from app.models.tables import Contract, ContractVersion

router = APIRouter(tags=["search"])


@router.get("/search", response_model=SearchResponse)
async def search_contracts(
    q: str | None = Query(None, description="Full-text search query"),
    tag: str | None = Query(None, description="Filter by tag"),
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> SearchResponse:
    """Search contracts by name, description, or tag."""
    result = await session.execute(
        select(Contract).options(selectinload(Contract.versions))
    )
    contracts = result.scalars().all()

    results: list[SearchResult] = []
    for contract in contracts:
        # Get the latest version spec for metadata
        versions = sorted(contract.versions, key=lambda v: v.published_at, reverse=True)
        if not versions:
            continue
        latest = versions[0]
        spec = latest.spec
        metadata = spec.get("metadata") or {}
        description = metadata.get("description")
        tags: list[str] = metadata.get("tags") or []

        # Filter by query (name or description match)
        if q:
            q_lower = q.lower()
            name_match = q_lower in contract.agent_name.lower()
            desc_match = description and q_lower in description.lower()
            if not name_match and not desc_match:
                continue

        # Filter by tag
        if tag and tag not in tags:
            continue

        total_downloads = sum(v.downloads for v in contract.versions)
        results.append(
            SearchResult(
                agent_name=contract.agent_name,
                latest_version=contract.latest_version,
                description=description,
                tags=tags,
                downloads=total_downloads,
            )
        )

    # Sort by downloads desc
    results.sort(key=lambda r: r.downloads, reverse=True)
    total = len(results)
    return SearchResponse(
        total=total,
        results=results[offset : offset + limit],
    )
