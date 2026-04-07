import { describe, it, expect } from "vitest";
import { loadSpec, SpecLoadError } from "../src/loader.js";
import { MINIMAL_SPEC, writeSpec } from "./helpers.js";

describe("loadSpec", () => {
  it("loads a valid spec", () => {
    const path = writeSpec(MINIMAL_SPEC);
    const spec = loadSpec(path);
    expect(spec.agent.name).toBe("test-agent");
    expect(spec.agent.version).toBe("0.1.0");
    expect(spec.capabilities.tools).toContain("read_file");
  });

  it("throws SpecLoadError on missing file", () => {
    expect(() => loadSpec("/nonexistent/path/spec.yaml")).toThrow(SpecLoadError);
    try {
      loadSpec("/nonexistent/path/spec.yaml");
    } catch (err) {
      expect(err).toBeInstanceOf(SpecLoadError);
      expect((err as SpecLoadError).phase).toBe("file");
    }
  });

  it("throws SpecLoadError on invalid YAML", () => {
    const path = writeSpec("{ invalid yaml: [", "bad.yaml");
    try {
      loadSpec(path);
    } catch (err) {
      expect(err).toBeInstanceOf(SpecLoadError);
      expect((err as SpecLoadError).phase).toBe("yaml");
    }
  });

  it("throws SpecLoadError on schema violation", () => {
    const path = writeSpec(
      `covenant: "1.0"\nagent:\n  name: test\n  version: "not-semver"\n  runtime: python\ncapabilities:\n  tools: []\nconstraints: {}`,
      "schema-err.yaml"
    );
    try {
      loadSpec(path);
    } catch (err) {
      expect(err).toBeInstanceOf(SpecLoadError);
      expect((err as SpecLoadError).phase).toBe("schema");
    }
  });

  it("SpecLoadError has issues array", () => {
    try {
      loadSpec("/does/not/exist.yaml");
    } catch (err) {
      expect((err as SpecLoadError).issues.length).toBeGreaterThan(0);
    }
  });
});
