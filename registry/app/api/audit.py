from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import check_master_key, require_publish_key
from app.db import get_session
from app.errors import ContractNotFound
from app.models.schemas import AuditEventResponse, AuditIngestRequest, AuditQueryResponse
from app.models.tables import AuditEvent, Contract

router = APIRouter(tags=["audit"])


# ── POST /contracts/{name}/audit ──────────────────────────────────────────────

@router.post("/contracts/{name}/audit", status_code=202)
async def ingest_audit_event(
    name: str,
    body: AuditIngestRequest,
    background_tasks: BackgroundTasks,
    authorization: Annotated[str | None, Header()] = None,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Ingest an audit event from the SDK. Written asynchronously."""
    # Allow SDK key OR master key — no team check needed for ingest
    # In production, validate sdk_key against a per-agent key table.
    # For now: master key or any bearer token is accepted (rate limiting in proxy).
    result = await session.execute(
        select(Contract).where(Contract.agent_name == name)
    )
    contract = result.scalar_one_or_none()
    if contract is None:
        raise ContractNotFound(name)

    # Determine event_type from outcome
    event_type = _outcome_to_event_type(body.outcome, body.violation_code)

    background_tasks.add_task(
        _write_audit_event,
        session=session,
        contract_id=contract.id,
        body=body,
        event_type=event_type,
    )

    return {"accepted": True}


# ── GET /contracts/{name}/audit ───────────────────────────────────────────────

@router.get("/contracts/{name}/audit", response_model=AuditQueryResponse)
async def query_audit_events(
    name: str,
    authorization: Annotated[str | None, Header()] = None,
    limit: int = Query(50, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> AuditQueryResponse:
    """Query audit log for a contract. Requires publish key or master key."""
    if not check_master_key(authorization):
        await require_publish_key(session, authorization)

    result = await session.execute(
        select(Contract).where(Contract.agent_name == name)
    )
    contract = result.scalar_one_or_none()
    if contract is None:
        raise ContractNotFound(name)

    count_result = await session.execute(
        select(func.count()).select_from(AuditEvent).where(
            AuditEvent.contract_id == contract.id
        )
    )
    total = count_result.scalar_one()

    events_result = await session.execute(
        select(AuditEvent)
        .where(AuditEvent.contract_id == contract.id)
        .order_by(AuditEvent.occurred_at.desc())
        .limit(limit)
        .offset(offset)
    )
    events = events_result.scalars().all()

    return AuditQueryResponse(
        total=total,
        events=[
            AuditEventResponse(
                id=e.id,
                version=e.version,
                event_type=e.event_type,
                payload=e.payload,
                occurred_at=e.occurred_at,
            )
            for e in events
        ],
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _outcome_to_event_type(outcome: str, violation_code: str | None) -> str:
    if outcome == "violation":
        if violation_code and "INVARIANT" in violation_code:
            return "invariant_warn"
        return "violation"
    return "ok"


async def _write_audit_event(
    session: AsyncSession,
    contract_id,
    body: AuditIngestRequest,
    event_type: str,
) -> None:
    """Background task: write audit event row."""
    # Need a fresh session for background tasks
    from app.db import async_session_factory
    async with async_session_factory() as bg_session:
        event = AuditEvent(
            contract_id=contract_id,
            version=body.contract.split("@")[-1] if "@" in body.contract else None,
            event_type=event_type,
            payload={
                "outcome": body.outcome,
                "tool_calls": body.tool_calls,
                "cost_usd": body.cost_usd,
                "duration_ms": body.duration_ms,
                "violation_code": body.violation_code,
                "model_used": body.model_used,
            },
            occurred_at=body.occurred_at,
        )
        bg_session.add(event)
        await bg_session.commit()
