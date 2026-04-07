import { describe, it, expect } from "vitest";
import { ToolCallInterceptor } from "../src/interceptor.js";
import { CovenantViolationError } from "../src/errors.js";
import { loadSpec } from "../src/loader.js";
import {
  MINIMAL_SPEC,
  SPEC_WITH_DENY,
  SPEC_WITH_CALL_LIMIT,
  writeSpec,
  makeResponse,
} from "./helpers.js";

describe("ToolCallInterceptor", () => {
  it("happy path — no tool calls", () => {
    const spec = loadSpec(writeSpec(MINIMAL_SPEC));
    const interceptor = new ToolCallInterceptor(spec);
    interceptor.recordCompletion(makeResponse(), "gpt-4o-mini");
    expect(interceptor.modelUsed).toBe("gpt-4o-mini");
    expect(interceptor.toolCalls).toHaveLength(0);
  });

  it("records declared tool call", () => {
    const spec = loadSpec(writeSpec(MINIMAL_SPEC));
    const interceptor = new ToolCallInterceptor(spec);
    interceptor.recordCompletion(
      makeResponse({ toolNames: ["read_file"] }),
      "gpt-4o-mini"
    );
    expect(interceptor.toolCalls).toHaveLength(1);
    expect(interceptor.toolCalls[0]!.name).toBe("read_file");
  });

  it("raises UNDECLARED_TOOL for unknown tool", () => {
    const spec = loadSpec(writeSpec(MINIMAL_SPEC));
    const interceptor = new ToolCallInterceptor(spec);
    expect(() =>
      interceptor.recordCompletion(
        makeResponse({ toolNames: ["bash"] }),
        "gpt-4o-mini"
      )
    ).toThrow(CovenantViolationError);

    try {
      interceptor.recordCompletion(
        makeResponse({ toolNames: ["bash"] }),
        "gpt-4o-mini"
      );
    } catch (err) {
      expect((err as CovenantViolationError).code).toBe("UNDECLARED_TOOL");
      expect((err as CovenantViolationError).detail["tool"]).toBe("bash");
    }
  });

  it("raises DENIED_TOOL for denied tool", () => {
    const spec = loadSpec(writeSpec(SPEC_WITH_DENY));
    const interceptor = new ToolCallInterceptor(spec);
    try {
      interceptor.recordCompletion(
        makeResponse({ toolNames: ["write_file"] }),
        "gpt-4o-mini"
      );
    } catch (err) {
      expect((err as CovenantViolationError).code).toBe("DENIED_TOOL");
      expect((err as CovenantViolationError).detail["tool"]).toBe("write_file");
    }
  });

  it("raises BUDGET_EXCEEDED when cost overflows", () => {
    const spec = loadSpec(writeSpec(MINIMAL_SPEC));
    const interceptor = new ToolCallInterceptor(spec);
    interceptor.totalCostUsd = 0.999; // seed near limit
    expect(() =>
      interceptor.recordCompletion(
        makeResponse({ promptTokens: 10000, completionTokens: 5000 }),
        "gpt-4o-mini"
      )
    ).toThrow(CovenantViolationError);
    try {
      interceptor.recordCompletion(
        makeResponse({ promptTokens: 10000, completionTokens: 5000 }),
        "gpt-4o-mini"
      );
    } catch (err) {
      expect((err as CovenantViolationError).code).toBe("BUDGET_EXCEEDED");
    }
  });

  it("raises CALL_LIMIT_EXCEEDED beyond max_calls_per_invocation", () => {
    const spec = loadSpec(writeSpec(SPEC_WITH_CALL_LIMIT));
    const interceptor = new ToolCallInterceptor(spec);
    // First call: OK (reaches limit of 1)
    interceptor.recordCompletion(
      makeResponse({ toolNames: ["read_file"] }),
      "gpt-4o-mini"
    );
    expect(interceptor.toolCalls).toHaveLength(1);
    // Second call: exceeds limit
    expect(() =>
      interceptor.recordCompletion(
        makeResponse({ toolNames: ["read_file"] }),
        "gpt-4o-mini"
      )
    ).toThrow(CovenantViolationError);
    try {
      interceptor.recordCompletion(
        makeResponse({ toolNames: ["read_file"] }),
        "gpt-4o-mini"
      );
    } catch (err) {
      expect((err as CovenantViolationError).code).toBe("CALL_LIMIT_EXCEEDED");
    }
  });
});
