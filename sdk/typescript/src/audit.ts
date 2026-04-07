export interface AuditEvent {
  contract: string;
  outcome: "pass" | "violation";
  toolCalls: Array<{ name: string; args: Record<string, unknown> }>;
  costUsd: number;
  durationMs: number;
  occurredAt: string; // ISO 8601
  violationCode: string | null;
  modelUsed: string | null;
}

/**
 * Fire-and-forget audit emitter.
 * Never blocks the return path. Network failures are logged at debug and discarded.
 * If COVENANT_REGISTRY_URL is not set, emit() is a no-op.
 */
export class AuditEmitter {
  private readonly url: string | undefined;
  private readonly key: string;

  constructor() {
    this.url = process.env["COVENANT_REGISTRY_URL"];
    this.key = process.env["COVENANT_API_KEY"] ?? "";
  }

  emit(event: AuditEvent): void {
    if (!this.url) return;
    // Fire-and-forget — intentionally not awaited
    void this._post(event);
  }

  private async _post(event: AuditEvent): Promise<void> {
    try {
      await fetch(`${this.url!.replace(/\/$/, "")}/audit`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${this.key}`,
        },
        body: JSON.stringify(event),
      });
    } catch {
      // Silently discard — registry unreachable is non-fatal
    }
  }
}
