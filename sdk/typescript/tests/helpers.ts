import { writeFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";

export const MINIMAL_SPEC = `
covenant: "1.0"
agent:
  name: test-agent
  version: 0.1.0
  runtime: typescript
capabilities:
  tools:
    - read_file
    - write_file
constraints:
  budget:
    max_cost_usd: 1.0
`.trim();

export const SPEC_WITH_DENY = `
covenant: "1.0"
agent:
  name: test-agent
  version: 0.1.0
  runtime: typescript
capabilities:
  tools:
    - read_file
constraints:
  deny_tools:
    - write_file
  budget:
    max_cost_usd: 1.0
`.trim();

export const SPEC_WITH_CALL_LIMIT = `
covenant: "1.0"
agent:
  name: test-agent
  version: 0.1.0
  runtime: typescript
capabilities:
  tools:
    - read_file
constraints:
  budget:
    max_cost_usd: 1.0
  scope:
    max_calls_per_invocation: 1
`.trim();

export const SPEC_WITH_INVARIANT = `
covenant: "1.0"
agent:
  name: test-agent
  version: 0.1.0
  runtime: typescript
capabilities:
  tools:
    - read_file
constraints:
  budget:
    max_cost_usd: 1.0
invariants:
  - id: INV-001
    description: output must be non-empty string
    assert: "typeof output === 'string' && output.length > 0"
    severity: error
`.trim();

export const SPEC_WITH_WARN_INVARIANT = `
covenant: "1.0"
agent:
  name: test-agent
  version: 0.1.0
  runtime: typescript
capabilities:
  tools:
    - read_file
constraints:
  budget:
    max_cost_usd: 1.0
invariants:
  - id: INV-002
    assert: "false"
    severity: warn
`.trim();

let _tmpDir: string | null = null;

function getTmpDir(): string {
  if (!_tmpDir) {
    _tmpDir = join(tmpdir(), `covenant-ts-test-${Date.now()}`);
    mkdirSync(_tmpDir, { recursive: true });
  }
  return _tmpDir;
}

export function writeSpec(content: string, name = "test.covenant.yaml"): string {
  const path = join(getTmpDir(), name);
  writeFileSync(path, content, "utf-8");
  return path;
}

/** Build a fake OpenAI ChatCompletion response. */
export function makeResponse(opts: {
  toolNames?: string[];
  promptTokens?: number;
  completionTokens?: number;
} = {}): Record<string, unknown> {
  const { toolNames = [], promptTokens = 100, completionTokens = 50 } = opts;

  const toolCalls = toolNames.map((name) => ({
    function: { name, arguments: "{}" },
  }));

  return {
    choices: [
      {
        message: {
          tool_calls: toolCalls,
        },
      },
    ],
    usage: {
      prompt_tokens: promptTokens,
      completion_tokens: completionTokens,
    },
  };
}
