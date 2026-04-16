/**
 * State façade — maps v0.1 backend states to v0.2 UI states.
 * Phase A: backend is still v0.1. This layer translates without backend changes.
 * Phase B: Drummer will add native v0.2 states; this façade becomes a passthrough.
 */

export type BackendStatus =
  | "pending_classification"
  | "pending_review"
  | "approved"
  | "rejected";

export type UIState =
  | "submitted"
  | "intake_complete"
  | "routed_for_approval"
  | "decision_recorded_approved"
  | "decision_recorded_rejected"
  | "exception_surfaced"
  | "under_review";

export interface PackageStateInfo {
  uiState: UIState;
  pillLabel: string;
  pillTone: "neutral" | "brass" | "positive" | "negative" | "amber";
  nextOwnerText: string;
  nextOwnerDot: "neutral" | "brass" | "amber";
}

/**
 * Maps a v0.1 backend status + optional confidence to a v0.2 UI state.
 * Decision call: pending_review without confidence is treated as intake_complete
 * (awaiting reviewer); with confidence < 0.5 → exception_surfaced.
 */
export function resolvePackageState(
  backendStatus: BackendStatus | string | null,
  confidence?: number | null,
  approver?: string | null,
  decisionDate?: string | null,
  reviewerName?: string | null
): PackageStateInfo {
  switch (backendStatus) {
    case "pending_classification":
      return {
        uiState: "submitted",
        pillLabel: "Submitted · awaiting intake",
        pillTone: "neutral",
        nextOwnerText: "Awaiting system intake",
        nextOwnerDot: "neutral",
      };

    case "pending_review": {
      // Low-confidence → exception_surfaced
      if (typeof confidence === "number" && confidence < 0.5) {
        return {
          uiState: "exception_surfaced",
          pillLabel: "Exception surfaced · needs operator",
          pillTone: "amber",
          nextOwnerText: "Awaiting operator — low confidence",
          nextOwnerDot: "amber",
        };
      }
      // Has classification, needs reviewer → intake_complete
      return {
        uiState: "intake_complete",
        pillLabel: "Intake complete · awaiting reviewer",
        pillTone: "neutral",
        nextOwnerText: reviewerName ? `With ${reviewerName}` : "Awaiting reviewer",
        nextOwnerDot: "neutral",
      };
    }

    case "approved": {
      const actor = approver ?? "approver";
      const date = decisionDate ?? "";
      return {
        uiState: "decision_recorded_approved",
        pillLabel: `Approved · ${actor}${date ? ` · ${date}` : ""}`,
        pillTone: "positive",
        nextOwnerText: `Decision recorded — ${actor} attested${date ? ` on ${date}` : ""}`,
        nextOwnerDot: "neutral",
      };
    }

    case "rejected": {
      const actor = approver ?? "approver";
      const date = decisionDate ?? "";
      return {
        uiState: "decision_recorded_rejected",
        pillLabel: `Rejected · ${actor}${date ? ` · ${date}` : ""}`,
        pillTone: "negative",
        nextOwnerText: `Decision recorded — ${actor} rejected${date ? ` on ${date}` : ""}`,
        nextOwnerDot: "neutral",
      };
    }

    default:
      return {
        uiState: "submitted",
        pillLabel: "Submitted · awaiting intake",
        pillTone: "neutral",
        nextOwnerText: "Awaiting system intake",
        nextOwnerDot: "neutral",
      };
  }
}

/**
 * Role display mapping: drop DB values at display layer.
 */
export function displayRole(role: string): string {
  switch (role) {
    case "admin":
      return "Approver";
    case "reviewer":
      return "Reviewer";
    case "operator":
      return "Operator";
    default:
      return role.charAt(0).toUpperCase() + role.slice(1);
  }
}
