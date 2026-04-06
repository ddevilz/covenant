# Covenant Registry

Context for working inside `registry/`. Read root `CLAUDE.md` first.

## What this layer is

The paid backend. Stores, versions, diffs, and audits behavioral contracts.
FastAPI + PostgreSQL + asyncpg. Deployed to Railway.

The registry is where the OSS spec becomes a network-effect product.
Agents declare → orchestrators require → platforms verify. The registry
is the trust anchor for that chain.

## API surface

| Method | Path                              | Auth     | Description                          |
|--------|-----------------------------------|----------|--------------------------------------|
| POST   | /contracts                        | API key  | Publish a new contract or version    |
| GET    | /contracts/{name}                 | public   | Resolve latest version               |
| GET    | /contracts/{name}/{version}       | public   | Resolve specific version             |
| GET    | /contracts/{name}/versions        | public   | List all versions with diff summaries|
| GET    | /contracts/{name}/diff            | public   | Behavioral diff between two versions |
| POST   | /contracts/{name}/audit           | SDK key  | Ingest audit event from SDK          |
| GET    | /contracts/{name}/audit           | API key  | Query audit log (paid tier)          |
| GET    | /search                           | public   | Full-text + tag search               |
| POST   | /verify                           | public   | Verify Ed25519 signature             |

## Data model

### contracts
```
id              UUID PK
agent_name      VARCHAR NOT NULL
latest_version  VARCHAR NOT NULL
owner_team_id   UUID FK → teams.id
created_at      TIMESTAMPTZ
```

### contract_versions
```
id              UUID PK
contract_id     UUID FK → contracts.id
version         VARCHAR NOT NULL        ← semver
spec            JSONB NOT NULL          ← parsed .covenant.yaml
spec_raw        TEXT NOT NULL           ← original YAML bytes
signature       TEXT                    ← Ed25519 sig
public_key      TEXT
author          VARCHAR
breaking        BOOLEAN NOT NULL        ← auto-computed on publish
diff_summary    JSONB                   ← vs previous version
published_at    TIMESTAMPTZ
downloads       INTEGER DEFAULT 0
UNIQUE (contract_id, version)
```

### audit_events
```
id              UUID PK
contract_id     UUID FK
version         VARCHAR
event_type      ENUM(ok, violation, slo_breach, invariant_warn)
payload         JSONB NOT NULL
occurred_at     TIMESTAMPTZ
PARTITION BY RANGE (occurred_at)        ← partition monthly
```

### teams
```
id              UUID PK
name            VARCHAR UNIQUE
api_key_hash    VARCHAR                 ← bcrypt hash, never store plaintext
plan            ENUM(free, registry, enforce, enterprise)
created_at      TIMESTAMPTZ
```

## Breaking change detection — exact rules

Run on every `POST /contracts` before writing to DB.
Compare incoming spec against the previous version for the same agent_name.

BREAKING (sets `breaking = true`, enforces major semver bump):
- Any tool removed from `constraints.deny_tools`
- Any tool added to `capabilities.tools`
- Any service added to `capabilities.external_services`
- `constraints.network.egress` loosened (false → true or scoped)
- `constraints.budget.max_cost_usd` increased
- `constraints.scope.max_calls_per_invocation` increased
- Any invariant removed
- Any invariant severity downgraded (error → warn)

NON-BREAKING (allowed without major bump):
- New tool added to `constraints.deny_tools`
- New invariant added
- SLO bounds tightened
- Scope narrowed
- metadata/description/tags changes

If `breaking = true` and incoming `version` has same major as previous,
return HTTP 422 with:
```json
{
  "error": "BREAKING_CHANGE_REQUIRES_MAJOR_BUMP",
  "detail": {
    "current_version": "1.2.0",
    "incoming_version": "1.3.0",
    "breaking_changes": [...]
  }
}
```

## Authentication

API key authentication via `Authorization: Bearer <key>` header.
Keys are stored as bcrypt hashes. Never log or return a plaintext key.

Three key types:
- `publish_key` — can POST /contracts and POST /audit (team-scoped)
- `sdk_key` — can POST /audit only (per-agent scoped, low privilege)
- `read_key` — GET only (for private contracts on paid tier)

Public contracts require no key for GET endpoints.

## Error responses

All errors return structured JSON. Never return a bare HTTP 500 with HTML.

```json
{
  "error": "BREAKING_CHANGE_REQUIRES_MAJOR_BUMP",
  "detail": {},
  "request_id": "uuid"
}
```

Error codes live in `app/errors.py`. Every endpoint handler must catch
`RegistryError` and convert to the correct HTTP status + JSON body.

## Audit ingest

`POST /contracts/{name}/audit` is the high-volume endpoint. Accepts the
SDK's `AuditEvent` shape. Write to `audit_events` table asynchronously —
use a background task, never block the response.

Rate limited to 1000 req/min per SDK key (free tier: 100/min).

## Dependencies

```
fastapi
uvicorn[standard]
sqlalchemy[asyncio]>=2.0
asyncpg
pydantic>=2.0
pyyaml
jsonschema>=4.0
cryptography
bcrypt
python-jose    # JWT for session tokens
```

## Running locally

```bash
pip install -e ".[dev]"
# needs a local postgres — docker-compose.yml in registry/ provides one
docker compose up -d db
uvicorn app.main:app --reload
```

## Test structure

```
registry/
└── tests/
    ├── test_publish.py         # publish happy path + breaking change rejection
    ├── test_diff.py            # all breaking/non-breaking cases
    ├── test_audit_ingest.py    # audit event write + query
    ├── test_search.py          # full-text + tag search
    ├── test_verify.py          # Ed25519 signature verification
    └── conftest.py             # async test DB setup + teardown
```

Use `pytest-asyncio` with `asyncio_mode = "auto"`.
Each test gets a fresh schema via `TRUNCATE` — never share state between tests.
