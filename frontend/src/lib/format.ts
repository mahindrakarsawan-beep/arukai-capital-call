/**
 * Shared formatting utilities — date, time, number, audit actions.
 * Keep pure (no React, no DOM).
 */

/**
 * Format an ISO timestamp as a human-relative string.
 *   < 1h  → "just now"
 *   < 24h → "Xh ago"
 *   < 30d → "Xd ago"
 *   ≥ 30d → "Mon D" (e.g. "Apr 12")
 */
export function formatRelative(iso: string): string {
  try {
    const diff = Date.now() - new Date(iso).getTime();
    const h = Math.floor(diff / 3600000);
    if (h < 1) return "just now";
    if (h < 24) return `${h}h ago`;
    const d = Math.floor(h / 24);
    if (d < 30) return `${d}d ago`;
    return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric" });
  } catch {
    return iso;
  }
}

/**
 * Map raw backend audit action strings to governed display labels.
 * Unmapped actions fall back to underscores-replaced-by-spaces (capitalised).
 */
const AUDIT_ACTION_LABELS: Record<string, string> = {
  // Package lifecycle
  upload_document: "Package received",
  package_received: "Package received",
  classify_document: "Classification recorded",
  classification_recorded: "Classification recorded",
  approve_document: "Decision attested",
  decision_attested: "Decision attested",
  attested_decision: "Decision attested",
  attested_approval: "Approval attested",
  reject_document: "Rejection recorded",
  rejection_recorded: "Rejection recorded",
  recorded_rejection: "Rejection recorded",
  claimed_package: "Review claimed",
  released_claim: "Claim released",
  recorded_review_note: "Review note recorded",
  transitioned_package: "Package transitioned",
};

export function formatAuditAction(action: string): string {
  if (!action) return "—";
  const mapped = AUDIT_ACTION_LABELS[action.toLowerCase()];
  if (mapped) return mapped;
  // Fallback: replace underscores, capitalise first letter
  const words = action.replace(/_/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

/**
 * Format an ISO timestamp as an absolute short date: "Apr 12, 2026".
 */
export function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch {
    return iso;
  }
}
