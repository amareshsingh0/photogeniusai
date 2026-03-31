/**
 * Shared TypeScript types for PhotoGenius AI
 */

export * from "./user";
export * from "./identity";
export * from "./generation";

// ─────────────────────────────────────────────────────────────
// CONSENT & COMPLIANCE
// ─────────────────────────────────────────────────────────────

export interface ConsentRecord {
  userId: string;
  version: string;
  agreedAt: Date;
  ipAddress?: string;
}

// ─────────────────────────────────────────────────────────────
// SAFETY
// ─────────────────────────────────────────────────────────────

export interface SafetyCheck {
  allowed: boolean;
  blockedReason?: string;
  preCheck: {
    allowed: boolean;
    reason?: string;
    modifiedPrompt: string;
  };
  postCheck?: {
    nsfwScore: number;
    isAdult: boolean;
  };
}
