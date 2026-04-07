import { readFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import yaml from "js-yaml";
import Ajv from "ajv";
import addFormats from "ajv-formats";
import { ZodError } from "zod";
import { CovenantSpec } from "./spec.js";

// ── JSON Schema validator (cached) ────────────────────────────────────────────

let _ajv: Ajv | null = null;
let _validateFn: ReturnType<Ajv["compile"]> | null = null;

function getValidator(): ReturnType<Ajv["compile"]> {
  if (_validateFn) return _validateFn;

  const ajv = new Ajv({ allErrors: true, strict: false });
  addFormats(ajv);
  _ajv = ajv;

  const schemaPath = resolve(
    dirname(fileURLToPath(import.meta.url)),
    "../data/covenant.schema.json"
  );
  const schema = JSON.parse(readFileSync(schemaPath, "utf-8")) as object;
  _validateFn = ajv.compile(schema);
  return _validateFn;
}

// ── Error type ────────────────────────────────────────────────────────────────

export class SpecLoadError extends Error {
  constructor(
    readonly phase: "file" | "yaml" | "schema" | "model",
    readonly specPath: string,
    readonly issues: string[]
  ) {
    super(`[${phase.toUpperCase()}] ${issues.join("; ")}`);
    this.name = "SpecLoadError";
  }
}

// ── Loader ────────────────────────────────────────────────────────────────────

/**
 * Load and validate a .covenant.yaml through four sequential phases.
 *
 * Phase 1 -- FILE:   path exists and is readable
 * Phase 2 -- YAML:   valid YAML, top-level object
 * Phase 3 -- SCHEMA: JSON Schema Draft-07 validation (all errors collected)
 * Phase 4 -- MODEL:  Zod parse (skipped if Phase 3 has errors)
 *
 * @param specPath - Absolute or relative path to the .covenant.yaml file.
 * @returns Fully-validated CovenantSpec.
 * @throws SpecLoadError on any phase failure.
 */
export function loadSpec(specPath: string): CovenantSpec {
  const absPath = resolve(specPath);

  // Phase 1 -- FILE
  let text: string;
  try {
    text = readFileSync(absPath, "utf-8");
  } catch {
    throw new SpecLoadError("file", absPath, [`File not found: ${absPath}`]);
  }

  // Phase 2 -- YAML
  let raw: unknown;
  try {
    raw = yaml.load(text);
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    throw new SpecLoadError("yaml", absPath, [msg]);
  }

  if (typeof raw !== "object" || raw === null || Array.isArray(raw)) {
    throw new SpecLoadError("yaml", absPath, [
      "YAML must be a mapping at the top level",
    ]);
  }

  // Phase 3 -- SCHEMA
  const validate = getValidator();
  const valid = validate(raw);
  if (!valid && validate.errors) {
    const issues = validate.errors.map(
      (e) => `${e.instancePath || "<root>"}: ${e.message ?? "invalid"}`
    );
    throw new SpecLoadError("schema", absPath, issues);
  }

  // Phase 4 -- MODEL
  try {
    return CovenantSpec.parse(raw);
  } catch (err) {
    if (err instanceof ZodError) {
      const issues = err.errors.map((e) => `${e.path.join(".")}: ${e.message}`);
      throw new SpecLoadError("model", absPath, issues);
    }
    throw err;
  }
}
