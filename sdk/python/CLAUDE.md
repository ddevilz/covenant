# Covenant SDK — Python

Context for working inside `sdk/python/`. Read root `CLAUDE.md` first.

## What this layer is

The enforcement engine. A `@contract` decorator that wraps any async Python
function and enforces the `.covenant.yaml` spec at call time.

No network dependency at runtime unless audit ingest is enabled via env var.
Works fully offline — the spec file is loaded from disk on decorator init.

## Module responsibilities

| Module           | Responsibility                                                          |
|------------------|-------------------------------------------------------------------------|
| `enforcer.py`    | `ContractEnforcer` class + `@contract` decorator + `call_tool()` fn    |
| `validator.py`   | JSON Schema validation for input/output against protocols block         |
| `interceptor.py` | OpenAI SDK class-level patch — intercepts every completion call         |
| `invariants.py`  | `safe_eval` + `InvariantEvaluator` — post-call assertion runner         |
| `errors.py`      | `CovenantViolationError` dataclass + all error code literals            |
| `audit.py`       | `AuditEmitter` — structured event emission after each invocation        |

## The enforcement flow — exact sequence

```
@contract decorator called
    │
    1. Load + parse spec (CovenantSpec via Pydantic)
    │
    2. Validate input against protocols.input.schema
       -> raises CovenantViolationError(code="INPUT_SCHEMA_MISMATCH") on fail
    │
    3. Set ContextVar token to activate the OpenAI SDK interceptor
    │
    4. Await the wrapped agent function
       │
       ├── Every openai.chat.completions.create call:
       │       a. accumulate cost from response.usage
       │       b. check_budget(cost) -- running total under max_cost_usd?
       │       c. check model against capabilities.models (if declared)
       │       d. extract tool_calls from response.choices[0].message.tool_calls
       │          check_tool(name) -- in capabilities.tools? in deny_tools?
       │       e. check_scope: call count under max_calls_per_invocation?
       │
       └── Any violation -> raises CovenantViolationError immediately
    │
    5. Reset ContextVar (always, even on exception via try/finally)
    │
    6. Validate output against protocols.output.schema
       -> raises CovenantViolationError(code="OUTPUT_SCHEMA_MISMATCH") on fail
    │
    7. Build context dict from collected interceptor state
    │
    8. Run InvariantEvaluator over all invariants
       -> severity=error raises CovenantViolationError(code="INVARIANT_FAILED")
       -> severity=warn does not raise (captured in audit event)
    │
    9. Emit audit event (fire-and-forget via asyncio.create_task, never blocks)
    │
    10. Return output to caller
```

## CovenantViolationError — all valid codes

```python
UNDECLARED_TOOL         # tool called not in capabilities.tools
DENIED_TOOL             # tool called is in constraints.deny_tools
BUDGET_EXCEEDED         # running cost_usd > constraints.budget.max_cost_usd
CALL_LIMIT_EXCEEDED     # call count > constraints.scope.max_calls_per_invocation
INVARIANT_FAILED        # post-call assert expression returned False
INPUT_SCHEMA_MISMATCH   # input failed JSON Schema validation
OUTPUT_SCHEMA_MISMATCH  # output failed JSON Schema validation
NETWORK_EGRESS_DENIED   # HTTP call attempted with egress: false
FILESYSTEM_SCOPE_VIOLATION  # file path outside declared patterns
UNDECLARED_MODEL        # model called not in capabilities.models
```

Every raise site must set `code`, `detail` dict, and `timestamp`. No exceptions.

## OpenAI SDK interception

Two enforcement layers:

**Automatic (OpenAI SDK patch):** `interceptor.py` patches
`openai.resources.chat.completions.completions.Completions.create` and
`AsyncCompletions.create` at class level, once at module import time. The patch
is a no-op when `_active_interceptor.get()` returns None (i.e., outside a
`@contract` invocation). Each invocation sets its own `ContextVar` token —
concurrent async tasks get independent interceptors.

**Explicit (`call_tool()`):** For I/O that bypasses the OpenAI SDK (filesystem,
HTTP via httpx/requests, subprocess), call `call_tool(name, fn, *args, **kwargs)`.
This checks the tool name against capabilities/deny_tools and records the call
in the interceptor's tool_calls list. If called outside a `@contract` invocation,
it executes fn directly with no enforcement.

## safe_eval — what is and isn't allowed

The invariant `assert` expression is evaluated with a restricted builtins dict.

Allowed: `all`, `any`, `len`, `isinstance`, `hasattr`, `getattr`, `list`,
`dict`, `str`, `int`, `float`, `bool`, `None`, `True`, `False`.

Explicitly removed: `__import__`, `open`, `exec`, `eval`, `compile`,
`__builtins__`, `globals`, `locals`, `vars`, `dir`.

Context object fields available in expressions:
- `input` — validated input object
- `output` — validated output object
- `tool_calls` — list of `ToolCall(name, args, result, cost_usd, timestamp)`
- `duration_ms` — wall clock for the full invocation
- `cost_usd` — total cost across all LLM calls
- `model_used` — last model called (string)

If the expression itself raises any exception, convert it to
`CovenantViolationError(code="INVARIANT_FAILED")` with the expression
and original exception in `detail`. Never let a bare exception escape.

## Audit emission

`AuditEmitter.emit()` is fire-and-forget via `asyncio.create_task`. It must
never block the return path. If the registry is unreachable, log at DEBUG level
and discard — never raise.

If `COVENANT_REGISTRY_URL` is not set, audit emission is a no-op.

## Dependencies

```
pydantic>=2.0
pyyaml
jsonschema>=4.0
openai>=1.0
cryptography
httpx          # for async audit ingest
```

## Test philosophy

Every enforcement path needs:
1. A happy-path test (agent complies, no error raised)
2. A violation test (agent violates, correct error code raised)
3. An assertion on `detail` dict content — not just the code

Async tests only for `@contract` decorator tests. Use `pytest-asyncio`.
