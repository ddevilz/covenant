import { describe, it, expect } from "vitest";
import { contract, callTool } from "../src/enforcer.js";
import { CovenantViolationError } from "../src/errors.js";
import { interceptorStorage } from "../src/interceptor.js";
import {
  MINIMAL_SPEC,
  SPEC_WITH_DENY,
  SPEC_WITH_INVARIANT,
  SPEC_WITH_WARN_INVARIANT,
  writeSpec,
} from "./helpers.js";

// ── contract() happy paths ────────────────────────────────────────────────────

describe("contract() - happy path", () => {
  it("returns output unchanged", async () => {
    const run = contract(writeSpec(MINIMAL_SPEC))(async (_input: unknown) => ({
      result: "ok",
    }));
    const result = await run({ query: "hello" });
    expect(result).toEqual({ result: "ok" });
  });

  it("passes through array output", async () => {
    const run = contract(writeSpec(MINIMAL_SPEC))(
      async (_input: unknown) => [1, 2, 3]
    );
    expect(await run({})).toEqual([1, 2, 3]);
  });

  it("warn invariant does not raise", async () => {
    const run = contract(writeSpec(SPEC_WITH_WARN_INVARIANT))(
      async (_input: unknown) => "output"
    );
    await expect(run({})).resolves.toBe("output");
  });
});

// ── contract() violations ─────────────────────────────────────────────────────

describe("contract() - violations", () => {
  it("propagates CovenantViolationError from agent body", async () => {
    const run = contract(writeSpec(MINIMAL_SPEC))(
      async (_input: unknown): Promise<unknown> => {
        throw new CovenantViolationError("DENIED_TOOL", { tool: "bash" });
      }
    );
    await expect(run({})).rejects.toMatchObject({
      code: "DENIED_TOOL",
    });
  });

  it("raises INVARIANT_FAILED when error-severity invariant fails", async () => {
    const run = contract(writeSpec(SPEC_WITH_INVARIANT))(
      async (_input: unknown) => "" // empty string fails length > 0
    );
    await expect(run({})).rejects.toMatchObject({
      code: "INVARIANT_FAILED",
    });
  });
});

// ── AsyncLocalStorage isolation ───────────────────────────────────────────────

describe("contract() - AsyncLocalStorage isolation", () => {
  it("interceptor is active inside contract invocation", async () => {
    let capturedInterceptor: unknown = undefined;
    const run = contract(writeSpec(MINIMAL_SPEC))(
      async (_input: unknown): Promise<unknown> => {
        capturedInterceptor = interceptorStorage.getStore();
        return {};
      }
    );
    await run({});
    expect(capturedInterceptor).not.toBeUndefined();
  });

  it("interceptor is undefined outside contract invocation", () => {
    expect(interceptorStorage.getStore()).toBeUndefined();
  });

  it("concurrent invocations get independent interceptors", async () => {
    const interceptors: unknown[] = [];
    const run = contract(writeSpec(MINIMAL_SPEC))(
      async (_input: unknown): Promise<unknown> => {
        interceptors.push(interceptorStorage.getStore());
        await new Promise((r) => setTimeout(r, 10));
        return {};
      }
    );
    await Promise.all([run({}), run({})]);
    expect(interceptors).toHaveLength(2);
    expect(interceptors[0]).not.toBe(interceptors[1]);
  });
});

// ── callTool() ────────────────────────────────────────────────────────────────

describe("callTool()", () => {
  it("executes fn directly when outside contract", async () => {
    const result = await callTool("read_file", async (path: string) => `content:${path}`, "data.csv");
    expect(result).toBe("content:data.csv");
  });

  it("allows declared tool inside contract", async () => {
    const run = contract(writeSpec(MINIMAL_SPEC))(
      async (_input: unknown): Promise<unknown> => {
        return callTool(
          "read_file",
          async (path: string) => `data:${path}`,
          "x.csv"
        );
      }
    );
    const result = await run({});
    expect(result).toBe("data:x.csv");
  });

  it("raises DENIED_TOOL for denied tool inside contract", async () => {
    const run = contract(writeSpec(SPEC_WITH_DENY))(
      async (_input: unknown): Promise<unknown> => {
        return callTool("write_file", async () => null);
      }
    );
    await expect(run({})).rejects.toMatchObject({ code: "DENIED_TOOL" });
  });

  it("raises UNDECLARED_TOOL for undeclared tool inside contract", async () => {
    const run = contract(writeSpec(MINIMAL_SPEC))(
      async (_input: unknown): Promise<unknown> => {
        return callTool("bash", async () => "");
      }
    );
    await expect(run({})).rejects.toMatchObject({ code: "UNDECLARED_TOOL" });
  });

  it("records call in interceptor toolCalls", async () => {
    let seenCalls: unknown[] = [];
    const run = contract(writeSpec(MINIMAL_SPEC))(
      async (_input: unknown): Promise<unknown> => {
        await callTool("read_file", async () => "data");
        seenCalls = interceptorStorage.getStore()?.toolCalls ?? [];
        return {};
      }
    );
    await run({});
    expect(seenCalls).toHaveLength(1);
    expect((seenCalls[0] as { name: string }).name).toBe("read_file");
  });
});

// ── audit.ts (AuditEmitter) ───────────────────────────────────────────────────

describe("AuditEmitter", () => {
  it("is a no-op when COVENANT_REGISTRY_URL is not set", async () => {
    delete process.env["COVENANT_REGISTRY_URL"];
    const { AuditEmitter } = await import("../src/audit.js");
    const emitter = new AuditEmitter();
    // Should not throw
    emitter.emit({
      contract: "test-agent@0.1.0",
      outcome: "pass",
      toolCalls: [],
      costUsd: 0,
      durationMs: 10,
      occurredAt: new Date().toISOString(),
      violationCode: null,
      modelUsed: null,
    });
  });
});
