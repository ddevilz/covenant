from __future__ import annotations

import hashlib
import os
import secrets

import bcrypt
from fastapi import Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import AuthError
from app.models.tables import Team


def hash_api_key(plaintext: str) -> str:
    """Bcrypt-hash a plaintext API key for storage."""
    return bcrypt.hashpw(plaintext.encode(), bcrypt.gensalt()).decode()


def verify_api_key(plaintext: str, hashed: str) -> bool:
    """Verify a plaintext API key against its stored bcrypt hash."""
    try:
        return bcrypt.checkpw(plaintext.encode(), hashed.encode())
    except Exception:
        return False


def generate_api_key() -> str:
    """Generate a cryptographically secure random API key."""
    return secrets.token_urlsafe(32)


async def require_publish_key(
    session: AsyncSession,
    authorization: str | None,
) -> Team:
    """Resolve a publish-scoped API key to the owning Team.

    Args:
        session: Active DB session.
        authorization: Value of the Authorization header.

    Returns:
        The authenticated Team row.

    Raises:
        AuthError: If the key is missing, malformed, or invalid.
    """
    token = _extract_bearer(authorization)
    result = await session.execute(select(Team))
    teams = result.scalars().all()
    for team in teams:
        if team.api_key_hash and verify_api_key(token, team.api_key_hash):
            return team
    raise AuthError()


def _extract_bearer(authorization: str | None) -> str:
    if not authorization:
        raise AuthError("Missing Authorization header")
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise AuthError("Authorization must be 'Bearer <token>'")
    return parts[1]


# ── Optional: master key bypass for single-tenant deploys ────────────────────

def check_master_key(authorization: str | None) -> bool:
    """Return True if the request carries the server-level master API key."""
    master = os.environ.get("COVENANT_MASTER_KEY")
    if not master:
        return False
    try:
        token = _extract_bearer(authorization)
        return secrets.compare_digest(token, master)
    except AuthError:
        return False
