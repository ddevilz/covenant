import { AsyncLocalStorage } from "node:async_hooks";
import { CovenantViolationError } from "./errors.js";
import type { CovenantSpec } from "./spec.js";

// ── Price table (input $/1k tokens, output $/1k tokens) ──────────────────────

const PRICE_TABLE: Record<string, [number, number]> = {
  "gpt-4o": [0.005, 0.015],
  "gpt-4o-mini": [0.00015, 0.0006],
  "gpt-4-turbo": [0.01, 0.03],
  "gpt-3.5-turbo": [0.0005, 0.0015],
  "claude-opus-4-6": [0.015, 0.075],
  "claude-sonnet-4-6": [0.003, 0.015],
  "claude-haiku-4-5-20251001": [0.00025, 0.00125],
};

// ── ToolCall record ───────────────────────────────────────────────────────────

export interface ToolCall {
  name: string;
  args: Record<string, unknown>;
  result: unknown;
  costUsd: number;
  timestamp: Date;
}

// ── Interceptor ───────────────────────────────────────────────────────────────

export class ToolCallInterceptor {
  readonly toolCalls: ToolCall[] = [];
  totalCostUsd = 0;
  modelUsed: string | null = null;

  constructor(private readonly spec: CovenantSpec) {}

  /**
   * Called after each OpenAI completion response.
   * Accumulates cost, checks model declaration, extracts + validates tool calls,
   * enforces budget and call limits.
   */
  recordCompletion(response: unknown, model: string): void {
    this.modelUsed = model;

    // Accumulate cost
    const usage = (response as Record<string, unknown>)["usage"] as
      | Record<string, number>
      | undefined;
    if (usage) {
      const inTok = usage["prompt_tokens"] ?? 0;
      const outTok = usage["completion_tokens"] ?? 0;
      const [inPrice, outPrice] = PRICE_TABLE[model] ?? [0, 0];
      this.totalCostUsd += (inTok / 1000) * inPrice + (outTok / 1000) * outPrice;
    }

    // Budget check
    const budget = this.spec.constraints.budget;
    if (budget && this.totalCostUsd > budget.max_cost_usd) {
      throw new CovenantViolationError("BUDGET_EXCEEDED", {
        max_cost_usd: budget.max_cost_usd,
        actual_cost_usd: Math.round(this.totalCostUsd * 1e6) / 1e6,
      });
    }

    // Model check
    const declaredModels = this.spec.capabilities.models;
    if (declaredModels !== undefined) {
      const allowed = new Set(declaredModels.map((m) => m.model));
      if (!allowed.has(model)) {
        throw new CovenantViolationError("UNDECLARED_MODEL", {
          model,
          declared: [...allowed].sort(),
        });
      }
    }

    // Extract tool calls from response
    const choices = (response as Record<string, unknown>)["choices"] as
      | unknown[]
      | undefined;
    if (choices && choices.length > 0) {
      const msg = (choices[0] as Record<string, unknown>)["message"] as
        | Record<string, unknown>
        | undefined;
      const tcs = (msg?.["tool_calls"] as unknown[] | undefined) ?? [];
      for (const tc of tcs) {
        const fn = (tc as Record<string, unknown>)["function"] as
          | Record<string, unknown>
          | undefined;
        if (!fn) continue;
        const toolName = fn["name"] as string;
        let args: Record<string, unknown> = {};
        try {
          args = JSON.parse((fn["arguments"] as string) ?? "{}") as Record<
            string,
            unknown
          >;
        } catch {
          // malformed args — keep empty
        }
        this.checkTool(toolName);
        this.toolCalls.push({
          name: toolName,
          args,
          result: null,
          costUsd: 0,
          timestamp: new Date(),
        });
      }
    }

    // Call limit check
    const maxCalls = this.spec.constraints.scope?.max_calls_per_invocation;
    if (maxCalls !== undefined && this.toolCalls.length > maxCalls) {
      throw new CovenantViolationError("CALL_LIMIT_EXCEEDED", {
        max_calls: maxCalls,
        actual_calls: this.toolCalls.length,
      });
    }
  }

  checkTool(name: string): void {
    const allowed = new Set(this.spec.capabilities.tools);
    const denied = new Set(this.spec.constraints.deny_tools ?? []);

    if (denied.has(name)) {
      throw new CovenantViolationError("DENIED_TOOL", { tool: name });
    }
    if (!allowed.has(name)) {
      throw new CovenantViolationError("UNDECLARED_TOOL", {
        tool: name,
        declared: [...allowed].sort(),
      });
    }
  }
}

// ── AsyncLocalStorage context ─────────────────────────────────────────────────

/**
 * Per-invocation storage. Each async call chain (one @contract invocation)
 * gets its own interceptor instance — concurrent calls are fully isolated.
 */
export const interceptorStorage = new AsyncLocalStorage<ToolCallInterceptor>();

// ── OpenAI SDK class-level patch ──────────────────────────────────────────────

let _patched = false;

export function installPatches(): void {
  if (_patched) return;
  try {
    // Dynamic require to avoid hard dep — if openai isn't installed, skip
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const openaiModule = require("openai/resources/chat/completions") as {
      Completions: { prototype: { create: (...args: unknown[]) => unknown } };
    };
    const Completions = openaiModule.Completions;
    const origCreate = Completions.prototype.create.bind(
      Completions.prototype
    ) as (...args: unknown[]) => unknown;

    Completions.prototype.create = function (
      this: unknown,
      ...args: unknown[]
    ): unknown {
      const interceptor = interceptorStorage.getStore();
      const result = origCreate.apply(this, args);

      // Handle both sync and async results
      if (result instanceof Promise) {
        return result.then((response) => {
          interceptor?.recordCompletion(
            response,
            (args[0] as Record<string, unknown>)?.["model"] as string ?? ""
          );
          return response;
        });
      }
      interceptor?.recordCompletion(
        result,
        (args[0] as Record<string, unknown>)?.["model"] as string ?? ""
      );
      return result;
    };

    _patched = true;
  } catch {
    // openai not installed — interception is no-op
  }
}
