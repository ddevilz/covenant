from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.db import create_tables
from app.errors import RegistryError
from app.api import contracts, audit, search, verify


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Create DB tables on startup (dev / SQLite). Skipped if tables exist."""
    await create_tables()
    yield


app = FastAPI(
    title="Covenant Registry",
    description="Behavioral contract registry for AI agents",
    version="0.1.0",
    lifespan=lifespan,
)

# ── Routers ───────────────────────────────────────────────────────────────────
# audit and verify are included BEFORE contracts so their specific literal paths
# (/contracts/{name}/audit, /verify) take priority over the wildcard
# /contracts/{name}/{version} route in the contracts router.

app.include_router(audit.router)
app.include_router(search.router)
app.include_router(verify.router)
app.include_router(contracts.router)


# ── Error handlers ────────────────────────────────────────────────────────────

@app.exception_handler(RegistryError)
async def registry_error_handler(request: Request, exc: RegistryError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_response(),
    )


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={
            "error": "INTERNAL_ERROR",
            "detail": {"message": str(exc)},
            "request_id": str(uuid.uuid4()),
        },
    )


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health() -> dict[str, Any]:
    return {"status": "ok", "version": app.version}
