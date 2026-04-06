# Covenant

> OpenAPI for agent behavior. Define what your agent does. Prove it.

## What this is

Covenant is a behavioral contract standard for AI agents. A `.covenant.yaml` file
declares what an agent can do, what it cannot do, what its outputs must satisfy, and
what it costs. The SDK enforces the contract at runtime. The registry stores and
versions contracts. The CLI validates and signs them.

Three-layer system:
- **Spec** — `.covenant.yaml` (OSS, JSON Schema validated)
- **SDK** — `@contract` decorator for Python agents, Zod-based TypeScript SDK
- **Registry** — FastAPI backend + React UI (paid tier)

## Repository layout

```
covenant/
├── spec/               # JSON Schema for .covenant.yaml
│   └── covenant.schema.json
├── cli/                # covenant CLI (Python + Typer)
│   ├── commands/
│   │   ├── init.py
│   │   ├── validate.py
│   │   ├── sign.py
│   │   ├── diff.py
│   │   ├── generate.py
│   │   ├── publish.py
│   │   └── audit.py
│   └── main.py
├── sdk/
│   ├── python/         # @contract decorator + enforcement engine
│   │   ├── covenant/
│   │   │   ├── enforcer.py
│   │   │   ├── validator.py
│   │   │   ├── interceptor.py
│   │   │   ├── invariants.py
│   │   │   ├── errors.py
│   │   │   └── audit.py
│   │   └── pyproject.toml
│   └── typescript/     # Zod-based SDK
│       ├── src/
│       └── package.json
├── registry/           # FastAPI backend
│   ├── app/
│   │   ├── api/
│   │   │   ├── contracts.py
│   │   │   ├── audit.py
│   │   │   └── search.py
│   │   ├── models/
│   │   │   ├── contract.py
│   │   │   └── audit_event.py
│   │   ├── services/
│   │   │   ├── diff.py
│   │   │   └── verify.py
│   │   └── main.py
│   └── pyproject.toml
├── ui/                 # React + Tailwind registry UI
│   ├── src/
│   │   ├── pages/
│   │   ├── components/
│   │   └── main.tsx
│   └── package.json
└── examples/           # example .covenant.yaml files
    ├── code-reviewer.covenant.yaml
    └── data-pipeline.covenant.yaml
```

## Design principles — never violate these

1. **Contract-first** — the `.covenant.yaml` spec is the source of truth for everything.
   Code conforms to the spec, not the other way around.

2. **Explicit failure** — violations always raise `CovenantViolationError` with a
   structured payload. Never silently degrade, log-and-continue, or swallow errors.

3. **Layered enforcement** — static (validate), runtime (SDK), audit (registry).
   All three layers must exist. No layer substitutes for another.

4. **Declared vs observed** — the spec is a promise. Audit events prove whether the
   promise was kept. This gap is the core product value.

5. **Semver enforcement** — loosening a constraint (removing a deny, adding a capability)
   requires a major semver bump. The registry enforces this on publish.

6. **Structured errors** — `CovenantViolationError` always carries `code`, `detail`,
   and `timestamp`. Never raise a plain string exception from enforcement code.

7. **Minimal surface area** — one decorator (`@contract`), one CLI binary (`covenant`),
   one registry REST API. No sprawl.

8. **Open spec, paid ops** — the `.covenant.yaml` format and JSON Schema are OSS.
   The registry, enforcement dashboard, and audit trail are the paid moat.

9. **Zero-friction adoption** — `@contract("./spec.yaml")` wrapping any async function
   must work in under five minutes with no infrastructure dependency.

10. **Composable, not competing** — integrates with Toolmark (skills embed Covenant
    specs), TokenGuard (constraints feed the proxy), Loom (graph generates specs).

## Stack

| Layer       | Tech                                     |
|-------------|------------------------------------------|
| Spec        | YAML + JSON Schema (jsonschema 4.x)      |
| CLI         | Python 3.12, Typer, PyYAML, jsonschema   |
| SDK Python  | Python 3.12, Pydantic v2, OpenAI SDK (provider-agnostic via base_url) |
| Signing     | Ed25519 (cryptography lib) — same as Toolmark |
| Registry    | FastAPI, SQLAlchemy 2, PostgreSQL, asyncpg |
| UI          | React 18, Tailwind, React Router         |
| Infra       | Railway (API + DB), Cloudflare Pages (UI) |

## Ticket prefixes

- `CVN-` — spec schema work
- `CLI-` — covenant CLI commands
- `SDK-` — Python SDK enforcement engine
- `TSS-` — TypeScript SDK
- `REG-` — registry API
- `UI-`  — registry React UI
- `INF-` — infra, deploy, CI

## Current focus

Week 1: spec JSON Schema + `covenant validate` + `covenant sign` → Show HN moment.

Tickets in flight: CVN-001 (JSON Schema draft), CLI-001 (init), CLI-002 (validate),
CLI-003 (sign).

## Code conventions

- Python: `ruff` for linting, `mypy --strict`, `pytest` for tests
- All enforcement code: explicit over implicit, no silent fallbacks
- Pydantic models for all spec parsing — never raw dict access
- Every public function has a docstring with Args/Returns/Raises
- `CovenantViolationError` is the only exception type raised from enforcement code
- Async throughout the registry and SDK — no blocking I/O

## Running locally

```bash
# CLI
cd cli && pip install -e ".[dev]"
covenant validate examples/code-reviewer.covenant.yaml

# SDK
cd sdk/python && pip install -e ".[dev]"
pytest

# Registry
cd registry && pip install -e ".[dev]"
uvicorn app.main:app --reload

# UI
cd ui && npm install && npm run dev
```

## Environment variables

```
# Registry
DATABASE_URL=postgresql+asyncpg://...
JWT_SECRET=...
REGISTRY_SIGNING_KEY=...   # Ed25519 private key for registry-level signing

# SDK (optional — for audit ingest)
COVENANT_REGISTRY_URL=https://registry.covenant.dev
COVENANT_API_KEY=...
```
