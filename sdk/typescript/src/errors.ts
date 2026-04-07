export const VIOLATION_CODES = [
  "UNDECLARED_TOOL",
  "DENIED_TOOL",
  "BUDGET_EXCEEDED",
  "CALL_LIMIT_EXCEEDED",
  "INVARIANT_FAILED",
  "INPUT_SCHEMA_MISMATCH",
  "OUTPUT_SCHEMA_MISMATCH",
  "NETWORK_EGRESS_DENIED",
  "FILESYSTEM_SCOPE_VIOLATION",
  "UNDECLARED_MODEL",
] as const;

export type ViolationCode = (typeof VIOLATION_CODES)[number];

const CODE_SET = new Set<string>(VIOLATION_CODES);

export interface ViolationDetail {
  [key: string]: unknown;
}

/**
 * Raised on any contract violation. Always carries code, detail, and timestamp.
 * Never raised with a plain string — always structured.
 */
export class CovenantViolationError extends Error {
  readonly code: ViolationCode;
  readonly detail: ViolationDetail;
  readonly timestamp: Date;

  constructor(code: ViolationCode, detail: ViolationDetail) {
    if (!CODE_SET.has(code)) {
      throw new TypeError(`Unknown violation code: ${code}`);
    }
    super(`CovenantViolationError [${code}]: ${JSON.stringify(detail)}`);
    this.name = "CovenantViolationError";
    this.code = code;
    this.detail = detail;
    this.timestamp = new Date();
  }
}
