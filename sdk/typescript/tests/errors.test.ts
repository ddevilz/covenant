import { describe, it, expect } from "vitest";
import { CovenantViolationError, VIOLATION_CODES } from "../src/errors.js";

describe("CovenantViolationError", () => {
  it("constructs with valid code and detail", () => {
    const err = new CovenantViolationError("UNDECLARED_TOOL", { tool: "bash" });
    expect(err.code).toBe("UNDECLARED_TOOL");
    expect(err.detail).toEqual({ tool: "bash" });
    expect(err.timestamp).toBeInstanceOf(Date);
  });

  it("is an instance of Error", () => {
    const err = new CovenantViolationError("DENIED_TOOL", { tool: "rm" });
    expect(err).toBeInstanceOf(Error);
    expect(err).toBeInstanceOf(CovenantViolationError);
  });

  it("accepts all valid codes", () => {
    for (const code of VIOLATION_CODES) {
      const err = new CovenantViolationError(code, {});
      expect(err.code).toBe(code);
    }
  });

  it("throws TypeError on unknown code", () => {
    expect(
      () => new CovenantViolationError("NOT_REAL" as never, {})
    ).toThrow(TypeError);
  });

  it("message includes code and detail", () => {
    const err = new CovenantViolationError("BUDGET_EXCEEDED", {
      max_cost_usd: 1.0,
    });
    expect(err.message).toContain("BUDGET_EXCEEDED");
    expect(err.message).toContain("max_cost_usd");
  });

  it("name is CovenantViolationError", () => {
    const err = new CovenantViolationError("INVARIANT_FAILED", {});
    expect(err.name).toBe("CovenantViolationError");
  });
});
