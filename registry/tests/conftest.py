from __future__ import annotations

import os
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Use SQLite in-memory for tests — no Postgres required
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

from app.db import create_tables, drop_tables, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest_asyncio.fixture(autouse=True)
async def reset_db():
    """Recreate all tables before each test for full isolation."""
    await drop_tables()
    await create_tables()
    yield
    await drop_tables()


@pytest_asyncio.fixture
async def client():
    """AsyncClient wired to the FastAPI app via ASGI transport."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


MINIMAL_SPEC = """\
covenant: "1.0"
agent:
  name: test-agent
  version: 0.1.0
  runtime: python
capabilities:
  tools:
    - read_file
constraints:
  budget:
    max_cost_usd: 1.0
"""

SPEC_V2_BREAKING = """\
covenant: "1.0"
agent:
  name: test-agent
  version: 1.0.0
  runtime: python
capabilities:
  tools:
    - read_file
    - write_file
constraints:
  budget:
    max_cost_usd: 1.0
"""

SPEC_V2_NONBREAKING = """\
covenant: "1.0"
agent:
  name: test-agent
  version: 0.2.0
  runtime: python
capabilities:
  tools:
    - read_file
constraints:
  deny_tools:
    - bash
  budget:
    max_cost_usd: 1.0
"""
