import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import Ajv from "ajv";
import addFormats from "ajv-formats";
import { CovenantViolationError } from "./errors.js";

const _schemaCache = new Map<string, ReturnType<Ajv["compile"]>>();
const _ajv = new Ajv({ allErrors: true, strict: false });
addFormats(_ajv);

function getValidator(schemaPath: string): ReturnType<Ajv["compile"]> {
  const cached = _schemaCache.get(schemaPath);
  if (cached) return cached;
  const schema = JSON.parse(readFileSync(schemaPath, "utf-8")) as object;
  const fn = _ajv.compile(schema);
  _schemaCache.set(schemaPath, fn);
  return fn;
}

/**
 * Validate input data against the protocols.input.schema JSON Schema.
 *
 * @param data - Input value to validate
 * @param schemaPath - Relative path to schema file, or undefined to skip
 * @param specDir - Directory containing the .covenant.yaml
 * @throws CovenantViolationError INPUT_SCHEMA_MISMATCH on failure
 */
export function validateInput(
  data: unknown,
  schemaPath: string | undefined,
  specDir: string
): void {
  if (!schemaPath) return;
  const full = resolve(specDir, schemaPath);
  const validate = getValidator(full);
  if (!validate(data) && validate.errors) {
    throw new CovenantViolationError("INPUT_SCHEMA_MISMATCH", {
      errors: validate.errors.map((e) => e.message ?? "invalid"),
    });
  }
}

/**
 * Validate output data against the protocols.output.schema JSON Schema.
 *
 * @param data - Output value to validate
 * @param schemaPath - Relative path to schema file, or undefined to skip
 * @param specDir - Directory containing the .covenant.yaml
 * @throws CovenantViolationError OUTPUT_SCHEMA_MISMATCH on failure
 */
export function validateOutput(
  data: unknown,
  schemaPath: string | undefined,
  specDir: string
): void {
  if (!schemaPath) return;
  const full = resolve(specDir, schemaPath);
  const validate = getValidator(full);
  if (!validate(data) && validate.errors) {
    throw new CovenantViolationError("OUTPUT_SCHEMA_MISMATCH", {
      errors: validate.errors.map((e) => e.message ?? "invalid"),
    });
  }
}
