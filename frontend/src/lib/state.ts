/**
 * State façade — maps v0.1 backend states to v0.2 UI states.
 * Phase A: backend is still v0.1. This layer translates without backend changes.
 * Phase B: Drummer will add native v0.2 states; this façade becomes a passthrough.
 *
 * Claim model (S1): reviewer claims a package before editing.
 *   - Unclaimed: "Unclaimed · awaiting claim"
 *   - Claimed by the current user: "Under review (claimed by you)"
 *   - Claimed by someone else: "Under review · with {name}"
 *
 * Rejection (S4): rejection is a distinct decision type, not a note.
 *   - "Decision recorded · Rejected by {actor}"
 *   - "Decision recorded · Approved by {actor}"
 *
 * Audit ledger visibility (S5): admin + approver only; reviewers cannot see global audit.
 *   - canViewAuditLedger() helper guards nav link and route.
 */

export type BackendStatus =
  | "pending_classification"
  | "pending_review"
  | "approved"
  | "rejected";

/** v0.2 state machine values emitted by the backend PackageListOut. */
export type V2State =
  | "submitted"
  | "intake_complete"
  | "under_review"
  | "routed_for_approval"
  | "decision_recorded"
  | "exception_surfaced";

export type UIState =
  | "submitted"
  | "intake_complete"
  | "routed_for_approval"
  | "decision_recorded_approved"
  | "decision_recorded_rejected"
  | "exception_surfaced"
  | "under_review"
  | "unclaimed";

export type ClaimState = "unclaimed" | "claimed_by_you" | "claimed_by_other";

export interface PackageStateInfo {
  uiState: UIState;
  pillLabel: string;
  pillTone: "neutral" | "brass" | "positive" | "negative" | "amber";
  nextOwnerText: string;
  nextOwnerDot: "neutral" | "brass" | "amber";
  claimState?: ClaimState;
}

/**
 * Maps a backend status/state + optional metadata to a v0.2 UI state.
 *
 * Handles both v0.2 native states (from PackageListOut.state) and the
 * legacy v0.1 status strings (from DocumentSummary.status) so that
 * components remain compatible regardless of which API shape they receive.
 *
 * v0.2 states take priority over v0.1 legacy mappings.
 *
 * @param backendStatus  v0.2 state or v0.1 legacy status string from the API
 * @param confidence     classification confidence (0–1); drives exception_surfaced
 * @param approver       name/email of approver (for decision_recorded states)
 * @param decisionDate   ISO date of decision
 * @param reviewerName   name/email of reviewer currently holding the package
 * @param claimState     claim model state: unclaimed | claimed_by_you | claimed_by_other
 */
export function resolvePackageState(
  backendStatus: BackendStatus | V2State | string | null,
  confidence?: number | null,
  approver?: string | null,
  decisionDate?: string | null,
  reviewerName?: string | null,
  claimState?: ClaimState | null
): PackageStateInfo {
  switch (backendStatus) {
    // ── v0.2 native states ─────────────────────────────────────────────────

    case "submitted":
      return {
        uiState: "submitted",
        pillLabel: "Package submitted",
        pillTone: "neutral",
        nextOwnerText: "Awaiting system intake",
        nextOwnerDot: "neutral",
      };

    case "intake_complete":
      return {
        uiState: "intake_complete",
        pillLabel: "Intake complete · awaiting reviewer",
        pillTone: "neutral",
        nextOwnerText: reviewerName ? `With ${reviewerName}` : "Awaiting reviewer",
        nextOwnerDot: "neutral",
      };

    case "under_review": {
      // Claim model (S1): drive pill copy from claim state when available
      if (claimState === "unclaimed") {
        return {
          uiState: "unclaimed",
          pillLabel: "Unclaimed · awaiting claim",
          pillTone: "neutral",
          nextOwnerText: "Unclaimed · awaiting claim",
          nextOwnerDot: "neutral",
          claimState: "unclaimed",
        };
      }
      if (claimState === "claimed_by_you") {
        return {
          uiState: "under_review",
          pillLabel: "Under review · claimed by you",
          pillTone: "neutral",
          nextOwnerText: "Under review (claimed by you)",
          nextOwnerDot: "neutral",
          claimState: "claimed_by_you",
        };
      }
      if (claimState === "claimed_by_other") {
        const holder = reviewerName ?? "reviewer";
        return {
          uiState: "under_review",
          pillLabel: `Under review · with ${holder}`,
          pillTone: "neutral",
          nextOwnerText: `Under review · with ${holder}`,
          nextOwnerDot: "neutral",
          claimState: "claimed_by_other",
        };
      }
      // No claim state provided: generic under_review
      const holder = reviewerName ?? "reviewer";
      return {
        uiState: "under_review",
        pillLabel: `Under review (claimed by ${holder})`,
        pillTone: "neutral",
        nextOwnerText: `Under review · with ${holder}`,
        nextOwnerDot: "neutral",
      };
    }

    case "routed_for_approval":
      return {
        uiState: "routed_for_approval",
        pillLabel: "Routed for approval",
        pillTone: "brass",
        nextOwnerText: "Awaiting approver",
        nextOwnerDot: "brass",
      };

    case "decision_recorded": {
      // Backend sends a unified "decision_recorded" state; approver field carries the actor.
      // We infer approved vs rejected from the presence/value of approver or fall back to approved.
      const actor = approver ?? "approver";
      const date = decisionDate ?? "";
      // The `decision` field on PackageListOut carries "approved" | "rejected" — passed via approver arg
      // when the caller maps pkg.decision → approver. Detect "Rejected" prefix as a convention.
      const isRejected = actor.startsWith("Rejected:");
      const cleanActor = isRejected ? actor.slice("Rejected:".length).trim() : actor;
      if (isRejected) {
        return {
          uiState: "decision_recorded_rejected",
          pillLabel: `Rejected · ${cleanActor}${date ? ` · ${date}` : ""}`,
          pillTone: "negative",
          nextOwnerText: `Decision recorded · Rejected by ${cleanActor}${date ? ` on ${date}` : ""}`,
          nextOwnerDot: "neutral",
        };
      }
      return {
        uiState: "decision_recorded_approved",
        pillLabel: `Decision recorded · Approved by ${cleanActor}${date ? ` · ${date}` : ""}`,
        pillTone: "positive",
        nextOwnerText: `Decision recorded · Approved by ${cleanActor}${date ? ` on ${date}` : ""}`,
        nextOwnerDot: "neutral",
      };
    }

    case "exception_surfaced":
      return {
        uiState: "exception_surfaced",
        pillLabel: "Exception surfaced · review required",
        pillTone: "amber",
        nextOwnerText: "Awaiting reviewer — exception flagged",
        nextOwnerDot: "amber",
      };

    // ── v0.1 legacy states (Phase A fallback) ─────────────────────────────

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

      // Claim model (S1): drive pill and chip copy from claim state
      if (claimState === "unclaimed") {
        return {
          uiState: "unclaimed",
          pillLabel: "Unclaimed · awaiting claim",
          pillTone: "neutral",
          nextOwnerText: "Unclaimed · awaiting claim",
          nextOwnerDot: "neutral",
          claimState: "unclaimed",
        };
      }

      if (claimState === "claimed_by_you") {
        return {
          uiState: "under_review",
          pillLabel: "Under review · claimed by you",
          pillTone: "neutral",
          nextOwnerText: "Under review (claimed by you)",
          nextOwnerDot: "neutral",
          claimState: "claimed_by_you",
        };
      }

      if (claimState === "claimed_by_other") {
        const holder = reviewerName ?? "reviewer";
        return {
          uiState: "under_review",
          pillLabel: `Under review · with ${holder}`,
          pillTone: "neutral",
          nextOwnerText: `Under review · with ${holder}`,
          nextOwnerDot: "neutral",
          claimState: "claimed_by_other",
        };
      }

      // No claim state provided: Phase A fallback (intake_complete awaiting reviewer)
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
        nextOwnerText: `Decision recorded · Approved by ${actor}${date ? ` on ${date}` : ""}`,
        nextOwnerDot: "neutral",
      };
    }

    case "rejected": {
      // S4: rejection is a distinct decision type.
      const actor = approver ?? "approver";
      const date = decisionDate ?? "";
      return {
        uiState: "decision_recorded_rejected",
        pillLabel: `Rejected · ${actor}${date ? ` · ${date}` : ""}`,
        pillTone: "negative",
        nextOwnerText: `Decision recorded · Rejected by ${actor}${date ? ` on ${date}` : ""}`,
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
 * S2: dedicated approver role enum value ("admin" → "Approver" for legacy compat).
 */
export function displayRole(role: string): string {
  switch (role) {
    case "admin":
    case "approver":
      return "Approver";
    case "reviewer":
      return "Reviewer";
    case "operator":
      return "Operator";
    default:
      return role.charAt(0).toUpperCase() + role.slice(1);
  }
}

/**
 * S5: Audit ledger is visible to admin + approver only.
 * Reviewers see per-package audit trail on the Package Detail page only.
 */
export function canViewAuditLedger(role: string | null | undefined): boolean {
  return role === "admin" || role === "approver";
}
