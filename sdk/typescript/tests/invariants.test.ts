import { describe, it, expect } from "vitest";
import { safeEval, evaluateInvariants } from "../src/invariants.js";
import { CovenantViolationError } from "../src/errors.js";
import type { InvariantContext } from "../src/invariants.js";
import type { InvariantSpec } from "../src/spec.js";

const baseCtx: InvariantContext = {
  input: {},
  output: "hello",
  toolCalls: [],
  durationMs: 100,
  costUsd: 0.01,
  modelUsed: "gpt-4o-mini",
};

describe("safeEval", () => {
  it("evaluates true expression", () => {
    expect(safeEval("output.length > 0", baseCtx)).toBe(true);
  });

  it("evaluates false expression", () => {
    expect(safeEval("output.length === 0", baseCtx)).toBe(false);
  });

  it("has access to all context fields", () => {
    expect(safeEval("durationMs === 100", baseCtx)).toBe(true);
    expect(safeEval("costUsd === 0.01", baseCtx)).toBe(true);
    expect(safeEval("modelUsed === 'gpt-4o-mini'", baseCtx)).toBe(true);
    expect(safeEval("toolCalls.length === 0", baseCtx)).toBe(true);
  });

  it("wraps runtime errors as INVARIANT_FAILED", () => {
    expect(() => safeEval("output.nonexistent.property", baseCtx)).toThrow(
      CovenantViolationError
    );
    try {
      safeEval("output.nonexistent.property", { ...baseCtx, output: null });
    } catch (err) {
      expect((err as CovenantViolationError).code).toBe("INVARIANT_FAILED");
      expect((err as CovenantViolationError).detail["error"]).toBeDefined();
    }
  });

  it("wraps syntax errors as INVARIANT_FAILED", () => {
    expect(() => safeEval("{{{{", baseCtx)).toThrow(CovenantViolationError);
  });
});

describe("evaluateInvariants", () => {
  function inv(
    id: string,
    assertExpr: string,
    severity: "error" | "warn" = "error"
  ): InvariantSpec {
    return { id, assert: assertExpr, severity };
  }

  it("passes when all invariants are true", () => {
    evaluateInvariants(
      [inv("I-1", "output.length > 0"), inv("I-2", "costUsd < 1")],
      baseCtx
    );
  });

  it("raises INVARIANT_FAILED for false error severity", () => {
    expect(() =>
      evaluateInvariants([inv("I-1", "false", "error")], baseCtx)
    ).toThrow(CovenantViolationError);
    try {
      evaluateInvariants([inv("I-1", "false", "error")], baseCtx);
    } catch (err) {
      expect((err as CovenantViolationError).code).toBe("INVARIANT_FAILED");
      expect((err as CovenantViolationError).detail["id"]).toBe("I-1");
    }
  });

  it("does NOT raise for false warn severity", () => {
    // Should not throw
    evaluateInvariants([inv("I-1", "false", "warn")], baseCtx);
  });

  it("stops at first error-severity failure", () => {
    const called: string[] = [];
    try {
      evaluateInvariants(
        [
          inv("FIRST", "false", "error"),
          { id: "SECOND", assert: "called.push('SECOND') || true", severity: "error" },
        ],
        { ...baseCtx, output: {} }
      );
    } catch {
      // expected
    }
    expect(called).toHaveLength(0); // SECOND never evaluated
  });
});
