import { z } from "zod";

// ── Primitives ───────────────────────────────────────────────────────────────

const SemverPattern = /^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$/;
const KebabCasePattern = /^[a-z0-9-]+$/;

// ── Agent ────────────────────────────────────────────────────────────────────

export const AgentSpec = z.object({
  name: z.string().regex(KebabCasePattern, "agent.name must be kebab-case"),
  version: z.string().regex(SemverPattern, "agent.version must be semver"),
  runtime: z.enum(["python", "typescript", "any"]),
  display_name: z.string().optional(),
  entrypoint: z.string().optional(),
});
export type AgentSpec = z.infer<typeof AgentSpec>;

// ── Capabilities ─────────────────────────────────────────────────────────────

export const ModelAllowSpec = z.object({
  provider: z.string(),
  model: z.string(),
  max_tokens: z.number().int().positive().optional(),
});
export type ModelAllowSpec = z.infer<typeof ModelAllowSpec>;

export const CapabilitiesSpec = z.object({
  tools: z.array(z.string()),
  models: z.array(ModelAllowSpec).optional(),
  external_services: z.array(z.string()).optional(),
});
export type CapabilitiesSpec = z.infer<typeof CapabilitiesSpec>;

// ── Constraints ──────────────────────────────────────────────────────────────

export const NetworkSpec = z.object({
  egress: z.union([z.boolean(), z.literal("scoped")]),
  allowed_domains: z.array(z.string()).optional(),
});
export type NetworkSpec = z.infer<typeof NetworkSpec>;

export const FilesystemSpec = z.object({
  read: z.array(z.string()).optional(),
  write: z.array(z.string()).optional(),
});
export type FilesystemSpec = z.infer<typeof FilesystemSpec>;

export const ScopeSpec = z.object({
  file_patterns: z.array(z.string()).optional(),
  max_file_size_kb: z.number().int().positive().optional(),
  max_calls_per_invocation: z.number().int().positive().optional(),
});
export type ScopeSpec = z.infer<typeof ScopeSpec>;

export const BudgetSpec = z.object({
  max_cost_usd: z.number().positive(),
});
export type BudgetSpec = z.infer<typeof BudgetSpec>;

export const ConstraintsSpec = z.object({
  deny_tools: z.array(z.string()).optional(),
  network: NetworkSpec.optional(),
  filesystem: FilesystemSpec.optional(),
  scope: ScopeSpec.optional(),
  budget: BudgetSpec.optional(),
});
export type ConstraintsSpec = z.infer<typeof ConstraintsSpec>;

// ── Invariants ───────────────────────────────────────────────────────────────

export const InvariantSpec = z.object({
  id: z.string(),
  description: z.string().optional(),
  assert: z.string(),
  severity: z.enum(["error", "warn"]),
});
export type InvariantSpec = z.infer<typeof InvariantSpec>;

// ── Protocols ────────────────────────────────────────────────────────────────

export const ProtocolEndpointSpec = z.object({
  schema: z.string(),
  required: z.boolean().default(true),
});
export type ProtocolEndpointSpec = z.infer<typeof ProtocolEndpointSpec>;

export const ProtocolErrorSpec = z.object({
  schema: z.string(),
});
export type ProtocolErrorSpec = z.infer<typeof ProtocolErrorSpec>;

export const ProtocolsSpec = z.object({
  input: ProtocolEndpointSpec.optional(),
  output: ProtocolEndpointSpec.optional(),
  errors: ProtocolErrorSpec.optional(),
});
export type ProtocolsSpec = z.infer<typeof ProtocolsSpec>;

// ── SLO ──────────────────────────────────────────────────────────────────────

export const SloSpec = z.object({
  latency_p95_ms: z.number().int().positive().optional(),
  latency_p99_ms: z.number().int().positive().optional(),
  cost_per_call_usd_max: z.number().positive().optional(),
  error_rate_max_pct: z.number().min(0).max(100).optional(),
  calls_per_minute_max: z.number().int().positive().optional(),
});
export type SloSpec = z.infer<typeof SloSpec>;

// ── Provenance ───────────────────────────────────────────────────────────────

export const ProvenanceSpec = z.object({
  author: z.string().optional(),
  signed_at: z.string().optional(),
  algorithm: z.literal("Ed25519").optional(),
  public_key: z.string().optional(),
  signature: z.string().optional(),
});
export type ProvenanceSpec = z.infer<typeof ProvenanceSpec>;

// ── Metadata ─────────────────────────────────────────────────────────────────

export const MetadataSpec = z.object({
  description: z.string().optional(),
  tags: z.array(z.string()).optional(),
  homepage: z.string().url().optional(),
  license: z.string().optional(),
  created_at: z.string().optional(),
  updated_at: z.string().optional(),
  llm_enhanced: z.boolean().optional(),
});
export type MetadataSpec = z.infer<typeof MetadataSpec>;

// ── Root ─────────────────────────────────────────────────────────────────────

export const CovenantSpec = z.object({
  covenant: z.literal("1.0"),
  agent: AgentSpec,
  capabilities: CapabilitiesSpec,
  constraints: ConstraintsSpec,
  invariants: z.array(InvariantSpec).optional(),
  protocols: ProtocolsSpec.optional(),
  slo: SloSpec.optional(),
  provenance: ProvenanceSpec.optional(),
  metadata: MetadataSpec.optional(),
});
export type CovenantSpec = z.infer<typeof CovenantSpec>;
