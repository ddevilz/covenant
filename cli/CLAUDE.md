# Covenant CLI

Context for working inside the `cli/` directory. Read root `CLAUDE.md` first —
this file is additive, not a replacement.

## What the CLI is

Single binary: `covenant`. Built with Python 3.12 + Typer. Each subcommand maps
to a file in `cli/commands/`. No command does any network I/O except `publish`.

## Commands and their contracts

| Command              | Input                        | Output                         | Side effects     |
|----------------------|------------------------------|--------------------------------|------------------|
| `covenant init`      | interactive prompts          | `.covenant.yaml` scaffolded    | writes file      |
| `covenant validate`  | path to `.covenant.yaml`     | PASS/FAIL + issue list         | none             |
| `covenant sign`      | path to `.covenant.yaml`     | signed `.covenant.yaml`        | overwrites file  |
| `covenant diff`      | two spec paths or versions   | behavioral diff + semver verdict | none           |
| `covenant generate`  | agent source file path       | draft `.covenant.yaml`         | writes file      |
| `covenant publish`   | path to `.covenant.yaml`     | registry contract URL          | registry POST    |
| `covenant audit`     | path to log file             | declared vs observed report    | none             |

## Validation layers in `covenant validate`

Run in this order, stop on first error per layer:

1. File exists and is valid YAML
2. JSON Schema validation against `spec/covenant.schema.json`
3. Principle linting (checks that go beyond schema):
   - `capabilities.tools` is non-empty
   - `constraints.deny_tools` does not overlap with `capabilities.tools`
   - `constraints.budget.max_cost_usd` is present
   - Every invariant has `severity` set
   - `provenance.algorithm` is `Ed25519` if provenance block present

## Signing in `covenant sign`

Uses Ed25519 from the `cryptography` library — same key format as Toolmark.
Private key loaded from `COVENANT_SIGNING_KEY` env var (base64url encoded).
Signs SHA256 of the canonical YAML (keys sorted, no comments).
Writes `provenance.signature` and `provenance.public_key` back into the file.
Never signs a spec that fails `covenant validate`.

## Error output format

All errors print to stderr. Format:

```
[ERROR] constraints.deny_tools: overlaps with capabilities.tools — "write_files" is in both
[WARN]  invariants[0]: missing description field
```

Exit codes: 0 = pass, 1 = validation errors, 2 = file not found, 3 = signing failure.

## Dependencies

```
typer[all]
pyyaml
jsonschema>=4.0
cryptography
rich          # for terminal output formatting
```

## Running

```bash
pip install -e ".[dev]"
covenant validate examples/code-reviewer.covenant.yaml
covenant sign examples/code-reviewer.covenant.yaml
```

## Test structure

```
cli/
└── tests/
    ├── test_validate.py    # happy path + each error code
    ├── test_sign.py        # sign + verify round trip
    ├── test_diff.py        # breaking vs non-breaking cases
    └── fixtures/
        ├── valid.covenant.yaml
        ├── missing_budget.covenant.yaml
        ├── deny_overlap.covenant.yaml
        └── no_invariants.covenant.yaml
```

Every error code from the validator must have a fixture that triggers it and a
test that asserts the correct exit code and stderr message.
