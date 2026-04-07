import { dirname, resolve } from "node:path";
import { AuditEmitter } from "./audit.js";
import { CovenantViolationError } from "./errors.js";
import {
  ToolCallInterceptor,
  interceptorStorage,
  installPatches,
} from "./interceptor.js";
import { evaluateInvariants } from "./invariants.js";
import { loadSpec } from "./loader.js";
import type { CovenantSpec } from "./spec.js";
import { validateInput, validateOutput } from "./validator.js";

// Install OpenAI SDK patches once at module load time
installPatches();

const _emitter = new AuditEmitter();

// ── Types ─────────────────────────────────────────────────────────────────────

type AsyncFn<A extends unknown[], R> = (...args: A) => Promise<R>;

// ── ContractEnforcer ──────────────────────────────────────────────────────────

export class ContractEnforcer {
  constructor(
    private readonly spec: CovenantSpec,
    private readonly specDir: string
  ) {}

  async enforce<A extends unknown[], R>(
    fn: AsyncFn<A, R>,
    args: A
  ): Promise<R> {
    const start = Date.now();
    const inputData = args[0];

    // 1. Validate input
    validateInput(inputData, this.spec.protocols?.input?.schema, this.specDir);

    // 2. Create per-invocation interceptor and run fn inside AsyncLocalStorage
    const interceptor = new ToolCallInterceptor(this.spec);

    let outcome: "pass" | "violation" = "pass";
    let violationCode: string | null = null;
    let output: R;

    try {
      output = await interceptorStorage.run(interceptor, () => fn(...args));
    } catch (err) {
      if (err instanceof CovenantViolationError) {
        outcome = "violation";
        violationCode = err.code;
      }
      throw err;
    }

    // 3. Validate output
    validateOutput(output, this.spec.protocols?.output?.schema, this.specDir);

    // 4. Evaluate invariants
    const durationMs = Date.now() - start;
    if (this.spec.invariants && this.spec.invariants.length > 0) {
      try {
        evaluateInvariants(this.spec.invariants, {
          input: inputData,
          output,
          toolCalls: interceptor.toolCalls,
          durationMs,
          costUsd: interceptor.totalCostUsd,
          modelUsed: interceptor.modelUsed,
        });
      } catch (err) {
        if (err instanceof CovenantViolationError) {
          outcome = "violation";
          violationCode = err.code;
        }
        throw err;
      }
    }

    // 5. Emit audit event (fire-and-forget)
    _emitter.emit({
      contract: `${this.spec.agent.name}@${this.spec.agent.version}`,
      outcome,
      toolCalls: interceptor.toolCalls.map((tc) => ({
        name: tc.name,
        args: tc.args,
      })),
      costUsd: interceptor.totalCostUsd,
      durationMs,
      occurredAt: new Date().toISOString(),
      violationCode,
      modelUsed: interceptor.modelUsed,
    });

    return output;
  }
}

// ── contract() decorator factory ──────────────────────────────────────────────

/**
 * Wraps an async function with Covenant contract enforcement.
 * The spec is loaded synchronously at call time (typically module load).
 *
 * @param specPath - Path to the .covenant.yaml file
 * @returns Decorator that wraps an async function with full enforcement
 *
 * @example
 * const run = contract("./my-agent.covenant.yaml")(
 *   async (input: Input): Promise<Output> => { ... }
 * );
 */
export function contract(
  specPath: string
): <A extends unknown[], R>(fn: AsyncFn<A, R>) => AsyncFn<A, R> {
  const absPath = resolve(specPath);
  const spec = loadSpec(absPath);
  const specDir = dirname(absPath);
  const enforcer = new ContractEnforcer(spec, specDir);

  return function <A extends unknown[], R>(fn: AsyncFn<A, R>): AsyncFn<A, R> {
    return async (...args: A): Promise<R> => {
      return enforcer.enforce(fn, args);
    };
  };
}

// ── callTool() ────────────────────────────────────────────────────────────────

/**
 * Explicit enforcement layer for non-LLM tool calls (filesystem, HTTP, subprocess).
 *
 * Checks the tool name against capabilities.tools and constraints.deny_tools.
 * If called outside a contract() invocation, executes fn directly (no enforcement).
 *
 * @param name - Tool name to check against the spec
 * @param fn - Async function to invoke if the tool is permitted
 * @param args - Arguments forwarded to fn
 *
 * @example
 * const data = await callTool("read_file", readFileAsync, "./data.csv");
 */
export async function callTool<A extends unknown[], R>(
  name: string,
  fn: (...args: A) => Promise<R>,
  ...args: A
): Promise<R> {
  const interceptor = interceptorStorage.getStore();
  if (interceptor !== undefined) {
    interceptor.checkTool(name);
  }

  const result = await fn(...args);

  if (interceptor !== undefined) {
    interceptor.toolCalls.push({
      name,
      args: args[0] !== undefined ? (args[0] as Record<string, unknown>) : {},
      result,
      costUsd: 0,
      timestamp: new Date(),
    });
  }

  return result;
}
