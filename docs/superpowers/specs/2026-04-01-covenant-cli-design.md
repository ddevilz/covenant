# Covenant CLI — Design Spec

**Date:** 2026-04-01
**Scope:** `cli/` package only. SDK, Registry, and UI are out of scope for this build cycle.
**Status:** Approved — ready for implementation planning.

---

## What we are building

A single binary, `covenant`, with seven subcommands for working with `.covenant.yaml` behavioral contract files. The CLI is the primary developer interface for Covenant — it is what a developer runs first, what CI pipelines call, and what creates the "Show HN moment" when `covenant validate` passes on a real spec.

**Commands in scope (all seven):**

| Command | Input | Output | Side effects |
|---|---|---|---|
| `covenant init` | interactive prompts | `.covenant.yaml` scaffolded | writes file |
| `covenant validate` | path to `.covenant.yaml` | PASS/FAIL + issue table | none |
| `covenant sign` | path to `.covenant.yaml` | signed `.covenant.yaml` | overwrites provenance block |
| `covenant diff` | two spec paths | behavioral diff + semver verdict | none |
| `covenant generate` | agent source file | draft `.covenant.yaml` | writes file |
| `covenant publish` | path to `.covenant.yaml` | registry contract URL | HTTP POST |
| `covenant audit` | path to NDJSON events file | declared vs observed report | none |

**Build order:** `validate` fully working end-to-end first. That is the Show HN moment — everything else follows.

---

## Architecture decision

**Approach B — standalone CLI with `uv init`, thin commands + service layer.**

- `cd cli && uv init --lib .` creates one self-contained `pyproject.toml`
- Commands are thin: parse args → call service → format output with rich
- All business logic lives in `services/` — pure Python, no I/O, unit testable without Typer
- `CovenantSpec` Pydantic model lives in `models/` within the CLI package
- When the SDK is built later, extract `CovenantSpec` into a shared package at that point — not now
- No LiteLLM anywhere. The `generate` command uses the OpenAI SDK directly. The SDK enforcement layer (a later build) will intercept Anthropic SDK calls directly.

---

## Package layout

```
cli/
├── pyproject.toml
├── uv.lock
└── src/
    └── covenant_cli/
        ├── __init__.py
        ├── main.py                  # Typer app, registers all seven commands
        ├── commands/
        │   ├── __init__.py
        │   ├── init.py
        │   ├── validate.py
        │   ├── sign.py
        │   ├── diff.py
        │   ├── generate.py
        │   ├── publish.py
        │   └── audit.py
        ├── services/
        │   ├── __init__.py
        │   ├── linter.py            # principle linting beyond JSON Schema
        │   ├── diff_engine.py       # breaking change detection + semver verdict
        │   ├── audit_engine.py      # declared vs observed analysis
        │   └── generator.py         # static analysis + optional LLM enhancement
        ├── models/
        │   ├── __init__.py
        │   ├── spec.py              # CovenantSpec and all sub-models (Pydantic)
        │   └── spec_loader.py       # YAML → schema validation → CovenantSpec
        ├── data/
        │   └── covenant.schema.json # bundled copy of spec/covenant.schema.json
        ├── output.py                # rich Console instances + all shared renderers
        └── errors.py                # exit code constants + CliError dataclass
```

---

## `pyproject.toml`

```toml
[project]
name = "covenant-cli"
version = "0.1.0"
description = "Behavioral contract CLI for AI agents"
requires-python = ">=3.12"
dependencies = [
    "typer[all]>=0.12",
    "pyyaml>=6.0",
    "jsonschema>=4.0",
    "pydantic>=2.0",
    "cryptography>=42.0",
    "rich>=13.0",
    "httpx>=0.27",
    "openai>=1.30",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "mypy>=1.9",
    "ruff>=0.4",
]

[project.scripts]
covenant = "covenant_cli.main:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/covenant_cli"]

[tool.ruff]
target-version = "py312"
line-length = 88

[tool.mypy]
strict = true
python_version = "3.12"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

**Dependency notes:**
- `openai>=1.30` — used only in `services/generator.py` for the optional LLM enhancement pass. Provider-agnostic via `COVENANT_LLM_BASE_URL`. Not `anthropic` — the OpenAI SDK interface is the de facto standard and every major provider (Anthropic, Gemini, Groq, Mistral, Ollama) exposes an OpenAI-compatible endpoint.
- `openai` is a hard dependency, not optional. The CLI is a developer tool — the extra package weight is trivial and conditional import machinery for a single command is complexity for no gain. The feature is gated by env var, not install-time optionals.
- The bundled `data/covenant.schema.json` is a copy of `spec/covenant.schema.json`. The CLI must work standalone after install without the repo on disk. Loaded via `importlib.resources`.

---

## `models/spec.py` — CovenantSpec hierarchy

All models use `model_config = ConfigDict(extra="forbid")` — mirrors `additionalProperties: false` in the schema. Unknown fields raise at parse time.

```
CovenantSpec
├── covenant: Literal["1.0"]
├── agent: AgentSpec
│   ├── name: str                          # kebab-case pattern validated
│   ├── version: str                       # semver pattern validated
│   ├── runtime: Literal["python","typescript","any"]
│   ├── display_name: str | None
│   └── entrypoint: str | None
├── capabilities: CapabilitiesSpec
│   ├── tools: list[str]                   # required, allowlist
│   ├── models: list[ModelAllowSpec] | None
│   │   ├── provider: str
│   │   ├── model: str                     # exact id or glob
│   │   └── max_tokens: int | None
│   └── external_services: list[str] | None
├── constraints: ConstraintsSpec
│   ├── deny_tools: list[str] | None
│   ├── network: NetworkSpec | None
│   │   ├── egress: bool | Literal["scoped"]
│   │   └── allowed_domains: list[str] | None
│   ├── filesystem: FilesystemSpec | None
│   │   ├── read: list[str] | None         # glob patterns
│   │   └── write: list[str] | None
│   ├── scope: ScopeSpec | None
│   │   ├── file_patterns: list[str] | None
│   │   ├── max_file_size_kb: int | None
│   │   └── max_calls_per_invocation: int | None
│   └── budget: BudgetSpec | None
│       └── max_cost_usd: float            # > 0, required inside block
├── invariants: list[InvariantSpec] | None
│   ├── id: str                            # pattern: INV-\d{3,}
│   ├── description: str | None
│   ├── assert_expr: str                   # Field(alias="assert") — Python keyword
│   └── severity: Literal["error","warn"]
├── protocols: ProtocolsSpec | None
│   ├── input: ProtocolEndpointSpec | None
│   │   ├── schema: str                    # relative path to JSON Schema file
│   │   └── required: bool = True
│   ├── output: ProtocolEndpointSpec | None
│   └── errors: ProtocolErrorSpec | None
│       └── schema: str
├── slo: SloSpec | None
│   ├── latency_p95_ms: int | None
│   ├── latency_p99_ms: int | None
│   ├── cost_per_call_usd_max: float | None
│   ├── error_rate_max_pct: float | None   # 0–100
│   └── calls_per_minute_max: int | None
├── provenance: ProvenanceSpec | None
│   ├── author: str | None
│   ├── signed_at: datetime | None
│   ├── algorithm: Literal["Ed25519"] | None
│   ├── public_key: str | None             # base64url Ed25519 public key
│   └── signature: str | None             # base64url Ed25519 signature
└── metadata: MetadataSpec | None
    ├── description: str | None
    ├── tags: list[str] | None
    ├── homepage: AnyUrl | None
    ├── license: str | None
    ├── created_at: datetime | None
    ├── updated_at: datetime | None
    └── llm_enhanced: bool | None      # set by covenant generate when LLM phase ran
```

`llm_enhanced` must be declared in both `MetadataSpec` and in `data/covenant.schema.json`'s `metadata.properties` block. Without this, a generated spec would immediately fail `covenant validate` because `extra="forbid"` rejects undeclared fields.

**`InvariantSpec.assert_expr`** uses `Field(alias="assert")` with `model_config = ConfigDict(populate_by_name=True)` so both `assert` (in YAML) and `assert_expr` (in Python) work.

---

## `models/spec_loader.py` — four-phase loader

```
load_spec(path: Path) -> CovenantSpec
```

Four sequential phases. Failure at any phase raises `SpecLoadError` immediately with all issues collected for that phase. Never returns a partial result.

```
Phase 1 — FILE       path.exists()? readable?
Phase 2 — YAML       yaml.safe_load(text)
Phase 3 — SCHEMA     Draft7Validator.iter_errors() — collects ALL errors, not just first
Phase 4 — MODEL      CovenantSpec.model_validate(raw_dict)
```

**Guard:** if Phase 3 produces any errors, Phase 4 is skipped entirely. Pydantic would re-catch schema violations and produce duplicate noise. Phase 4 runs only on a schema-clean dict.

**Schema loading:** bundled `covenant.schema.json` loaded once at import time via `importlib.resources.files("covenant_cli.data").joinpath("covenant.schema.json")`.

**`SpecLoadError`** carries:
- `phase: Literal["file", "yaml", "schema", "model"]`
- `path: Path`
- `issues: list[str]`
- `exit_code: int` — 2 for file phase, 1 for all others

---

## `services/linter.py` — principle linting

Runs only when explicitly called. `diff` and `audit` do not call it. `validate`, `sign`, and `publish` do.

```
lint(spec: CovenantSpec) -> list[LintIssue]
```

**`LintIssue`** carries: `level: Literal["error","warn"]`, `code: str`, `field: str | None`, `message: str`.
The `field` attribute points to the spec path that triggered the issue (e.g. `"constraints.deny_tools"`). Renders as a dash in the issues table when `None`.

**Rules:**

| Level | Code | Field | Trigger |
|---|---|---|---|
| error | `EMPTY_TOOLS_LIST` | `capabilities.tools` | list is empty |
| error | `DENY_OVERLAP` | `constraints.deny_tools` | deny_tools ∩ capabilities.tools is non-empty |
| error | `MISSING_BUDGET` | `constraints.budget` | `constraints.budget` block absent |
| error | `INVARIANT_MISSING_SEV` | `invariants[n].severity` | invariant has no severity (belt-and-suspenders over schema) |
| warn | `UNDECLARED_DENY` | `constraints.deny_tools` | deny_tools contains a tool not in capabilities.tools |
| warn | `PROVENANCE_ALGO_INVALID` | `provenance.algorithm` | provenance block present but algorithm ≠ "Ed25519" |

Returns a list (never raises). Empty list = clean.

**Distinction:** `spec_loader.py` answers "is this a valid spec?" The linter answers "is this a good spec?" They are different questions with different callers.

---

## `services/diff_engine.py`

```
diff(old: CovenantSpec, new: CovenantSpec) -> DiffResult
```

Pure function. No I/O. Takes two `CovenantSpec` objects — never file paths.

**`DiffResult`:**
```
breaking: list[Change]
non_breaking: list[Change]
semver_verdict: Literal["major", "minor", "patch", "none"]
old_version: str
new_version: str

Change:
  rule: str        # rule code
  field: str       # spec path
  description: str # human-readable
  detail: dict     # {"old": ..., "new": ...}
```

**Breaking rules** — any one triggers `semver_verdict = "major"`:

| Rule | Field | Trigger |
|---|---|---|
| `TOOL_ADDED_TO_CAPABILITIES` | `capabilities.tools` | tool added to allowlist |
| `DENY_TOOL_REMOVED` | `constraints.deny_tools` | tool removed from deny list |
| `EXTERNAL_SERVICE_ADDED` | `capabilities.external_services` | new service added |
| `EGRESS_LOOSENED` | `constraints.network.egress` | false→true, false→scoped, scoped→true |
| `BUDGET_INCREASED` | `constraints.budget.max_cost_usd` | limit raised |
| `CALL_LIMIT_INCREASED` | `constraints.scope.max_calls_per_invocation` | limit raised |
| `INVARIANT_REMOVED` | `invariants` | invariant removed by id |
| `INVARIANT_SEVERITY_DOWNGRADED` | `invariants[id].severity` | error→warn |

**Non-breaking rules:**

| Rule | Verdict contribution |
|---|---|
| `DENY_TOOL_ADDED` | minor |
| `INVARIANT_ADDED` | minor |
| `SLO_TIGHTENED` | minor |
| `EGRESS_TIGHTENED` | minor |
| `BUDGET_DECREASED` | minor |
| `CALL_LIMIT_DECREASED` | minor |
| `METADATA_CHANGED` | patch |

**Semver verdict logic:** any breaking → `"major"`. Any minor-group non-breaking → `"minor"`. Only patch-group changes → `"patch"`. Zero changes → `"none"`.

**Null-safety:** all optional fields treated as empty/None on either side without erroring. **Asymmetric case is explicit:** if `old` has a block and `new` drops it entirely (e.g. `old.constraints.deny_tools = ["write_files"]`, `new.constraints.deny_tools = None`), every tool in the old list is treated as removed — `DENY_TOOL_REMOVED` fires once per tool. Both-None is a no-op — not a change.

---

## `services/audit_engine.py`

```
analyze(events: Iterable[AuditEvent], spec: CovenantSpec | None) -> AuditReport
```

Stateless. Groups events by `contract` field ("name@version"), computes declared-vs-observed gap per version separately.

**`AuditEvent`** (Pydantic model — mirrors what the SDK will emit):
```
contract: str           # "name@version"
outcome: Literal["ok","violation","slo_breach","invariant_warn"]
tool_calls: list[str]
cost_usd: float
duration_ms: int
occurred_at: datetime
violation_code: str | None
model_used: str | None
```

**`VersionReport`:**
```
contract: str
total_events: int
first_seen: datetime        # min(occurred_at)
last_seen: datetime         # max(occurred_at)

# Tool analysis
declared_tools: set[str]    # from spec.capabilities.tools — None if no spec
observed_tools: set[str]    # union of tool_calls across all events
undeclared_tools: set[str]  # observed − declared
unused_tools: set[str]      # declared − observed

# Cost analysis
declared_max_cost: float | None
actual_p50_cost: float
actual_p95_cost: float
actual_p99_cost: float

# Latency analysis
actual_p50_ms: float
actual_p95_ms: float
actual_p99_ms: float
declared_p95_ms: int | None   # from spec.slo
declared_p99_ms: int | None

# Violations
violation_count: int
violation_breakdown: dict[str, int]   # code → count
slo_breaches: list[str]
```

**`AuditReport`:**
```
versions: dict[str, VersionReport]   # keyed by "name@version"
total_events: int
specless_versions: list[str]         # versions with no spec available
```

**Spec resolution (when `--spec` is not passed):**
1. Look for `.covenant.yaml` in cwd
2. If found: use it for all versions. If version in log ≠ spec version: **warn but continue** — produce the report against the available spec and flag the mismatch prominently in the output. Do not abort.
3. If not found: produce observed-only report (declared columns empty/N/A, flagged in output)

**Percentile computation:** sorted-list approach, no numpy. `p95 = sorted_values[int(0.95 * N)]`.

---

## `services/generator.py`

Two-phase generation. Phase 2 runs only when `COVENANT_LLM_KEY` is set (and `--no-llm` is not passed).

### Phase 1 — Static analysis

```
analyze(path: Path) -> StaticAnalysisResult

StaticAnalysisResult:
  detected_runtime: Literal["python","typescript","any"]
  agent_functions: list[str]     # top-level async def names
  detected_tools: list[str]      # calls to known tool-shaped functions
  has_network: bool              # requests/httpx/urllib/aiohttp import detected
  has_filesystem: bool           # open() / pathlib / os.path detected
  has_llm: bool                  # anthropic/openai import detected
  imported_modules: list[str]    # all top-level imports
  source_path: Path
```

**Python:** full AST analysis via `ast` module.
**TypeScript:** regex-based (import statement patterns) — no full AST.

Patterns detected:
- `import anthropic` / `import openai` → `has_llm = True`
- `import requests` / `import httpx` / `import aiohttp` / `import urllib` → `has_network = True`
- `open()` / `Path.read_text()` / `Path.write_text()` / `os.path.*` → `has_filesystem = True`
- `async def *` at module level → `agent_functions`

### Draft spec from static analysis

```
draft_spec(result: StaticAnalysisResult, name: str) -> dict
```

Produces a raw spec dict:

```yaml
covenant: "1.0"
agent:
  name: <filename-kebab-case>
  version: "0.1.0"
  runtime: python
capabilities:
  tools: []            # intentionally empty — user must fill in
constraints:
  network:
    egress: true/false  # from has_network
  filesystem:
    read: ["**/*"]       # only if has_filesystem
    write: []
  budget:
    max_cost_usd: 0.10  # conservative default
metadata:
  description: "Generated by covenant generate — review before publishing"
  llm_enhanced: false
```

`capabilities.tools` is left empty with a `# TODO: fill in your tool names` comment. Static analysis can detect that tools are called but not reliably what the contract names should be. Forcing the user to fill this in manually is a feature — it forces intentional review of the most important field in the spec.

**Always-warn if `has_llm = True` and `capabilities.models` is empty** — users consistently forget this field alongside `capabilities.tools`.

### Phase 2 — LLM enhancement

```
enhance_with_llm(draft: dict, source_text: str) -> dict
```

Env vars:
- `COVENANT_LLM_KEY` — passed as-is to OpenAI client
- `COVENANT_LLM_BASE_URL` — optional, defaults to `api.openai.com`
- `COVENANT_LLM_MODEL` — optional, defaults to `gpt-4o-mini`

The LLM is asked to return **only JSON, no preamble, no markdown fences.** Implementation strips any accidental fences before `json.loads()` — belt and suspenders.

The model returns a JSON object with exactly three fields:
```json
{
  "description": "one-sentence agent description",
  "tools": ["tool_name_1", "tool_name_2"],
  "invariants": [
    {"id": "INV-001", "description": "...", "assert": "...", "severity": "error"}
  ]
}
```

The LLM result **merges** into the static draft — it never replaces fields that static analysis set with confidence (runtime, has_network, has_filesystem). It fills in fields static analysis cannot determine. Individual LLM-suggested invariants are annotated with `# llm-suggested` comments in the YAML output.

**`metadata.llm_enhanced: true`** is set in the output spec when Phase 2 runs. Greppable across a repo: `grep -r "llm_enhanced: true" .` identifies specs that still need human review before publish.

---

## Command interfaces

### Universal rules across all commands

- `SpecLoadError` and `CliError` are the **only** exception types command handlers catch. Anything else surfacing is a bug — the traceback is the correct output.
- Never `sys.exit()`. Always `raise typer.Exit(code)` so Typer's cleanup runs.
- All success messages print the **absolute path**, never the relative path passed in.
- All file-writing commands (`init`, `sign`, `generate`) prompt before overwriting an existing file.

### Error-handling pattern (identical across all commands)

```python
def validate_cmd(path: Path, no_lint: bool = False) -> None:
    try:
        spec = spec_loader.load_spec(path)
        issues = [] if no_lint else linter.lint(spec)
        if issues:
            output.issues_table(issues)
            raise typer.Exit(EXIT_VALIDATION)
        output.success_panel(f"PASS  {spec.agent.name} {spec.agent.version}")
    except SpecLoadError as e:
        output.error_panel(
            message=f"[{e.phase.upper()}] {'; '.join(e.issues)}",
            hint=None
        )
        raise typer.Exit(e.exit_code)
    except CliError as e:
        output.error_panel(e.message, hint=e.hint)
        raise typer.Exit(e.exit_code)
```

---

### `covenant init [PATH]`

```
PATH   output path, default: .covenant.yaml

Interactive prompts (in order):
  1. Agent name        — kebab-case, re-prompt on pattern failure
  2. Version           — semver, default "0.1.0"
  3. Runtime           — choice: python / typescript / any
  4. Allowed tools     — comma-separated, at least one required
  5. Max cost USD      — float > 0
  6. Deny tools        — optional, comma-separated
  7. Add invariant?    — y/n loop; each asks: id, description, expression, severity
  8. Description       — optional free text

Pre-write:
  If PATH exists: prompt "Overwrite existing contract? [y/N]" — abort if no.
  Write only on full completion. Partial wizard → nothing written.

Output:
  Success panel + "Run `covenant validate <abs-path>` to check it."

Exit: 0 = written, 1 = user aborted
```

---

### `covenant validate PATH`

```
PATH         path to .covenant.yaml
--no-lint    skip principle linting (JSON Schema check only)

Preconditions:
  1. spec_loader.load_spec(PATH)
  2. linter.lint(spec)   [skipped if --no-lint]

Output (clean):   green PASS panel with agent name + version
Output (errors):  issues table to err_console, footer with counts

Exit: 0 = pass, 1 = validation/lint errors, 2 = file not found
```

---

### `covenant sign PATH`

```
PATH   path to .covenant.yaml
COVENANT_SIGNING_KEY   base64url Ed25519 private key (required env var)

Preconditions:
  1. spec_loader.load_spec(PATH)
  2. linter.lint(spec) → filter to errors only: abort if any errors, warn is ok
     (issues table shows all issues including warns, but only errors block signing)
  3. COVENANT_SIGNING_KEY set?

If spec already has provenance.signature: overwrite silently. Re-signing is valid.

Signing:
  4. Decode private key from base64url
  5. Strip existing provenance block from the spec dict (avoids circular signing)
  6. Canonical YAML of provenance-free dict: keys sorted recursively, comments stripped
  7. SHA256(canonical) → Ed25519 sign
  8. Write provenance block back: algorithm, public_key, signature, signed_at
     (provenance block is appended after signing, never included in signed content)

**Key order note:** the provenance block is always written at the end of the file,
regardless of where it appeared in the original. Implementation must not attempt to
preserve provenance key position — that path introduces bugs and the trade-off is
not worth it. Document this in the command's help text.

Output:
  Success panel with public key fingerprint (first 16 chars of base64url)
  "Provenance written to <abs-path>"

Exit: 0 = signed, 1 = validation failure, 2 = file not found, 3 = signing failure
```

---

### `covenant diff OLD NEW`

```
OLD              path to old .covenant.yaml
NEW              path to new .covenant.yaml
--fail-on-breaking   exit 1 if any breaking change (for CI)

Preconditions:
  spec_loader.load_spec(OLD) and spec_loader.load_spec(NEW)
  Load independently. If both fail, report both — label errors "OLD spec:" / "NEW spec:".

Core: diff_engine.diff(old_spec, new_spec) → DiffResult

Output:
  Verdict banner (major=red, minor=yellow, patch=blue, none=green)
  Breaking changes table (if any)
  Non-breaking changes table (if any)
  Footer: "<n> breaking  ·  <m> non-breaking"

Exit: 0 = diff complete, 1 = spec load error, 2 = file not found
      With --fail-on-breaking: 1 if any breaking change
```

The diff engine takes `CovenantSpec` objects — not file paths. The command handler does the loading. This separation means adding registry-aware resolution later (CLI-009, blocked on REG-001) is a one-line change to the loading step.

---

### `covenant generate SOURCE`

```
SOURCE           path to agent source file (.py or .ts)
--output PATH    output path, default: <source-stem>.covenant.yaml
--no-llm         skip LLM even if COVENANT_LLM_KEY is set

Environment (all optional):
  COVENANT_LLM_KEY        OpenAI-compatible API key
  COVENANT_LLM_BASE_URL   provider base URL (default: api.openai.com)
  COVENANT_LLM_MODEL      model id (default: gpt-4o-mini)

Flow:
  1. Detect runtime from file extension
  2. generator.analyze(SOURCE) → StaticAnalysisResult
  3. generator.draft_spec(result) → raw dict
  4. If COVENANT_LLM_KEY set and not --no-llm:
       generator.enhance_with_llm(draft, source_text) → merged dict
  5. If --output path exists: prompt to overwrite
  6. Write YAML to --output

Output:
  Success panel: "Draft written to <abs-path>"
  If LLM-enhanced: "  ✦ LLM-enhanced (llm_enhanced: true set in metadata)"
  Always:         "  ⚠ capabilities.tools is empty — fill in before publishing"
  If has_llm but no models block: "  ⚠ capabilities.models is empty — LLM usage detected"

Exit: 0 = written, 1 = generation error, 2 = source file not found
```

`--no-llm` is the escape hatch for reproducible generation in scripts. LLM runs automatically when the key is present — no flag needed for the common case.

---

### `covenant publish PATH`

```
PATH   path to .covenant.yaml

Environment:
  COVENANT_REGISTRY_URL   registry base URL (required)
  COVENANT_API_KEY        publish key (required)

Preconditions (in order — fail fast locally before any network call):
  1. spec_loader.load_spec(PATH)
  2. linter.lint(spec) → filter to errors only — abort if any errors, warn is ok
  3. spec.provenance.signature present?
       → CliError("Spec must be signed before publishing.", hint="Run `covenant sign <abs-path>`")
  4. COVENANT_REGISTRY_URL set?
       → CliError("COVENANT_REGISTRY_URL is not set.")
  5. COVENANT_API_KEY set?
       → CliError("COVENANT_API_KEY is not set.")

HTTP:
  POST {COVENANT_REGISTRY_URL}/contracts
  Headers: Authorization: Bearer {COVENANT_API_KEY}
           Content-Type: application/yaml
  Body: raw YAML bytes

Response handling:
  201  → success panel with contract URL from response
  422 BREAKING_CHANGE_REQUIRES_MAJOR_BUMP
       → attempt to deserialize response body's breaking_changes into DiffResult
         → if deserialization succeeds: output.diff_renderer(diff_result)
         → if deserialization fails (registry version mismatch, unexpected shape):
              fall back to printing raw detail array as JSON, never crash
         → exit 1 in both cases
  409  → "Version {v} already published. Bump the version and re-sign."
  401/403 → "Authentication failed. Check COVENANT_API_KEY."
  ConnectionError → "Registry unreachable at {url}. Is COVENANT_REGISTRY_URL correct?"

Exit: 0 = published, 1 = validation/registry rejection, 2 = file not found,
      3 = unsigned spec, 4 = publish/network failure
```

The 422 handler deserializes the response body to a `DiffResult` before passing to `output.diff_renderer`. The renderer never touches HTTP response shapes directly.

---

### `covenant audit EVENTS`

```
EVENTS        path to NDJSON audit events file (.jsonl)
--spec PATH   explicit spec file (overrides auto-resolution)

Flow:
  1. Parse NDJSON line by line:
       valid lines → list[AuditEvent]
       malformed lines → skip, count tracked
     Zero valid events → exit 1

  2. Spec resolution:
       a. --spec set → spec_loader.load_spec(spec)
       b. .covenant.yaml in cwd → load it
          If log version ≠ spec version: warn but continue, flag mismatch prominently
       c. Neither → observed-only report (declared columns show "—")

  3. audit_engine.analyze(events, spec) → AuditReport
  4. output.audit_renderer(report)

Exit: 0 = report produced, 1 = zero valid events or critical parse failure
```

---

## `output.py` — rendering layer

Two `Console` instances at module level:

```python
console     = Console()              # stdout — reports, success panels
err_console = Console(stderr=True)   # stderr — errors, warnings
```

The split is intentional: `covenant validate spec.yaml | grep ERROR` works correctly.

### Shared renderers

**`success_panel(title, body_lines)`** — green border, stdout.

**`error_panel(message, hint=None)`** — red border, stderr. `hint` rendered in dim style. Used for both `CliError` and `SpecLoadError` (caller formats the phase + issues into `message` before passing in).

**`issues_table(issues: list[LintIssue])`** — stderr. Columns: level (error=red, warn=yellow), code, field (dash if None), message. Footer: `"<n> error(s)  <m> warning(s)"`.

**`diff_renderer(result: DiffResult)`** — stdout. Verdict banner, breaking changes table, non-breaking changes table, footer. Called from both `diff` command and `publish` 422 handler with identical call signature.

**`audit_renderer(report: AuditReport)`** — mixed: report tables to stdout, warnings (specless versions, malformed lines) to stderr.

### Output format for audit (per version)

```
code-reviewer @ 2.1.0  ·  47 invocations  ·  2026-03-01 → 2026-03-29

Tools
─────────────────────────────────────────
declared    observed    status
read_files  read_files  ✓
call_llm    call_llm    ✓
—           write_files ⚠ undeclared

Cost (declared max: $0.10)
──────────────────────────
p50   $0.031
p95   $0.078  ✓ within limit
p99   $0.094  ✓ within limit

Latency (SLO: p95 ≤ 2000ms · p99 ≤ 5000ms)
────────────────────────────────────────────
p95   1243ms  ✓
p99   3891ms  ✓

Violations: 3  (BUDGET_EXCEEDED: 2  ·  UNDECLARED_TOOL: 1)
```

Warnings go to stderr:
- `"⚠ 2 version(s) observed without a matching spec — pass --spec to compare"` (if `specless_versions` non-empty)
- `"⚠ 2 malformed line(s) skipped"` (if any)

---

## `errors.py` — exit codes and CliError

```python
EXIT_OK         = 0   # success
EXIT_VALIDATION = 1   # spec invalid, lint failed, no events, generation error
EXIT_NOT_FOUND  = 2   # input file does not exist
EXIT_SIGNING    = 3   # signing failed, or spec unsigned on publish
EXIT_NETWORK    = 4   # registry unreachable, HTTP error on publish

@dataclass
class CliError(Exception):
    message: str
    exit_code: int
    hint: str | None = None   # "Run `covenant sign <path>` first."
```

---

## Test structure

```
cli/tests/
├── conftest.py                  # temp dirs, sample spec fixtures
├── unit/
│   ├── test_spec_loader.py      # all four phases, happy path + each error
│   ├── test_linter.py           # each lint rule, clean spec
│   ├── test_diff_engine.py      # each breaking rule, each non-breaking rule,
│   │                            # asymmetric None cases, semver verdict logic
│   ├── test_audit_engine.py     # declared vs observed scenarios, specless mode,
│   │                            # version mismatch warning
│   └── test_generator.py        # static analysis patterns, LLM merge logic
└── integration/
    ├── fixtures/
    │   ├── valid.covenant.yaml
    │   ├── missing_budget.covenant.yaml
    │   ├── deny_overlap.covenant.yaml
    │   ├── no_tools.covenant.yaml
    │   └── unsigned.covenant.yaml
    ├── test_validate.py          # CLI end-to-end, each exit code
    ├── test_sign.py              # sign + verify round trip
    ├── test_diff.py              # CLI diff output, --fail-on-breaking
    └── test_audit.py             # CLI audit output, --spec flag
                                  # must cover BOTH paths to exit 1:
                                  # (a) zero valid events and (b) all-malformed input
                                  # so they can't be accidentally split into separate codes later
```

**Test rules (from CLAUDE.md):**
- Every error code from spec_loader and linter must have a fixture + test asserting exit code and stderr message.
- Every breaking/non-breaking rule in diff_engine must have a test.
- Unit tests never invoke Typer. They call service functions directly.
- Integration tests invoke the CLI via Typer's test client.

---

## Tickets affected by this design

**In scope (this build):**
- CVN-001 — `covenant.schema.json` is done (already exists)
- CLI-001 — `covenant init`
- CLI-002 — `covenant validate`
- CLI-003 — `covenant sign`
- CLI-004 — `covenant diff` (local file only)
- CLI-005 — `covenant publish` (client-side only)

**New tickets from this design:**
- CLI-006 — `covenant generate` (static analysis + optional LLM)
- CLI-007 — `covenant audit` (NDJSON report)
- CLI-008 — `output.py` + `errors.py` (shared rendering layer, built first)
- CLI-009 — `covenant diff` registry-aware resolution (blocked on REG-001)

---

## Design principles enforced by this CLI

1. **Contract-first** — `spec_loader.py` is the boundary. Every service receives a valid `CovenantSpec`, never a raw dict.
2. **Explicit failure** — `CliError` and `SpecLoadError` carry structured payloads. No silent fallbacks.
3. **Layered enforcement** — loader answers "valid?", linter answers "good?", they are separate callers.
4. **Declared vs observed** — `audit` is the command that makes this gap visible.
5. **Semver enforcement** — `diff` surfaces breaking changes before they reach the registry.
6. **Minimal surface area** — one binary, seven commands, no sprawl.
7. **Zero-friction adoption** — `uv init`, `pip install covenant-cli`, `covenant validate ./spec.yaml`. Works in under five minutes.
