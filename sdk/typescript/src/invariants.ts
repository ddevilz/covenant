import { CovenantViolationError } from "./errors.js";
import type { InvariantSpec } from "./spec.js";

// Context fields available in invariant expressions
export interface InvariantContext {
  input: unknown;
  output: unknown;
  toolCalls: unknown[];
  durationMs: number;
  costUsd: number;
  modelUsed: string | null;
}

/**
 * Evaluate a single invariant expression in a restricted sandbox.
 *
 * The expression is a JavaScript boolean expression that has access to
 * the InvariantContext fields. Uses Function constructor with explicit
 * parameter names — no access to outer scope.
 *
 * @param expression - JS boolean expression from invariant.assert
 * @param ctx - Context variables available in the expression
 * @returns Result of the expression
 * @throws CovenantViolationError INVARIANT_FAILED if expression throws
 */
export function safeEval(expression: string, ctx: InvariantContext): unknown {
  try {
    // Construct a function with only the context variables in scope.
    // "use strict" blocks access to global via this, arguments, etc.
    const fn = new Function(
      "input",
      "output",
      "toolCalls",
      "durationMs",
      "costUsd",
      "modelUsed",
      `"use strict"; return (${expression});`
    );
    return fn(
      ctx.input,
      ctx.output,
      ctx.toolCalls,
      ctx.durationMs,
      ctx.costUsd,
      ctx.modelUsed
    );
  } catch (err) {
    if (err instanceof CovenantViolationError) throw err;
    throw new CovenantViolationError("INVARIANT_FAILED", {
      expression,
      error: err instanceof Error ? err.message : String(err),
    });
  }
}

/**
 * Evaluates all invariants in sequence against the enforcement context.
 * severity=error raises CovenantViolationError on first falsy result.
 * severity=warn does not raise (caller may record in audit event).
 */
export function evaluateInvariants(
  invariants: InvariantSpec[],
  ctx: InvariantContext
): void {
  for (const inv of invariants) {
    const result = safeEval(inv.assert, ctx);
    if (!result) {
      if (inv.severity === "error") {
        throw new CovenantViolationError("INVARIANT_FAILED", {
          id: inv.id,
          expression: inv.assert,
        });
      }
      // severity=warn — no throw
    }
  }
}
