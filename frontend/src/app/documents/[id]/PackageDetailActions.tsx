"use client";

/**
 * PackageDetailActions — bottom action bar for package detail (spec §6.5).
 *
 * Role routing:
 * - Approver (admin/approver role) + routed_for_approval state:
 *     [Attest approval] (brass) + [Record rejection] (secondary)
 * - Reviewer + under_review / intake_complete:
 *     [Claim to review] (unclaimed), [Release claim] (claimed_by_you)
 *     [Route for approval] (claimed_by_you — at least one note must be recorded)
 * - Terminal (approved/rejected): no actions
 *
 * Claim/release: calls claimPackage / releasePackage via api.ts.
 * Route for approval: calls transitionPackage("routed_for_approval") via api.ts.
 * Attest/reject: opens AttestationModal which calls attestPackage.
 *
 * Brass discipline: ONLY the [Attest approval] button uses brass (#B8914E).
 */

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { AttestationModal } from "@/components/AttestationModal";
import { claimPackage, releasePackage, transitionPackage } from "@/lib/api";
import type { ClaimState } from "@/lib/state";

interface PackageDetailActionsProps {
  documentId: string;
  packageTitle: string;
  classification?: string;
  confidence?: number | null;
  /** Current user role — "admin"|"approver" for attestation, "reviewer" for claim/route */
  userRole?: string;
  /** v0.1 backend status string used to drive action visibility */
  packageState?: string;
  /** Claim model state (S1) — drives claim/release buttons */
  claimState?: ClaimState | null;
  /** Reviewer notes on this package (passed to AttestationModal) */
  reviewerNotes?: Array<{ author: string; timestamp: string; body: string }>;
  /** Number of flagged fields for zero-flags / warning panel in AttestationModal */
  flaggedFieldCount?: number;
  /** Flagged field names for warning panel */
  flaggedFields?: string[];
}

async function getToken(): Promise<string | null> {
  const res = await fetch("/api/token");
  const data = await res.json();
  return data.token ?? null;
}

export function PackageDetailActions({
  documentId,
  packageTitle,
  classification,
  confidence,
  userRole,
  packageState,
  claimState,
  reviewerNotes,
  flaggedFieldCount,
  flaggedFields,
}: PackageDetailActionsProps) {
  const router = useRouter();
  const [modal, setModal] = useState<"approve" | "reject" | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  function handleSuccess() {
    setModal(null);
    // Short delay for modal fade (240ms per spec §7.3)
    setTimeout(() => {
      router.refresh();
    }, 240);
  }

  const packageSummary = {
    title: packageTitle,
    classification,
    confidence,
    reviewerNotes,
    flaggedFieldCount,
    flaggedFields,
  };

  // Terminal states: no actions
  const isTerminal =
    packageState === "approved" ||
    packageState === "rejected" ||
    packageState === "decision_recorded";

  if (isTerminal) {
    return null;
  }

  const isApprover = userRole === "approver";
  const isReviewer = userRole === "reviewer";
  const isAdmin = userRole === "admin";

  // States where package awaits attestation (approver/admin action)
  const isAwaitingAttestation =
    packageState === "routed_for_approval";
  // States where package awaits claim / routing (reviewer/admin action)
  // Note: legacy "pending_review" maps to intake_complete in v0.2
  const isAwaitingClaim =
    packageState === "pending_review" ||
    packageState === "under_review" ||
    packageState === "intake_complete" ||
    packageState === "exception_surfaced";

  // Approver sees attest/reject only on routed_for_approval.
  // Admin can attest on routed_for_approval OR claim on earlier states — mutually exclusive.
  const showApproverActions = (isApprover || isAdmin) && isAwaitingAttestation;

  // Reviewer/admin sees claim/release/route on earlier states.
  // Admin only sees claim actions when NOT at routed_for_approval (where attest takes priority).
  const showReviewerActions =
    (isReviewer || isAdmin) && isAwaitingClaim && !isAwaitingAttestation;

  // Effective claim state: when state is intake_complete or exception_surfaced and
  // no claimState provided, treat as unclaimed so buttons appear.
  const effectiveClaimState: ClaimState | null =
    claimState ??
    (packageState === "intake_complete" ||
      packageState === "exception_surfaced" ||
      packageState === "pending_review"
      ? "unclaimed"
      : null);

  async function handleClaim() {
    setActionLoading("claim");
    setActionError(null);
    try {
      const token = await getToken();
      if (!token) return;
      await claimPackage(documentId, token);
      router.refresh();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Claim failed.");
    } finally {
      setActionLoading(null);
    }
  }

  async function handleRelease() {
    setActionLoading("release");
    setActionError(null);
    try {
      const token = await getToken();
      if (!token) return;
      await releasePackage(documentId, token);
      router.refresh();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Release failed.");
    } finally {
      setActionLoading(null);
    }
  }

  async function handleRouteForApproval() {
    setActionLoading("route");
    setActionError(null);
    try {
      const token = await getToken();
      if (!token) return;
      await transitionPackage(documentId, "routed_for_approval", token);
      router.refresh();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Route failed.");
    } finally {
      setActionLoading(null);
    }
  }

  if (!showApproverActions && !showReviewerActions) {
    return null;
  }

  return (
    <>
      <div className="rounded-lg border border-[rgba(184,145,78,0.30)] bg-[rgba(184,145,78,0.04)] p-5">
        {actionError && (
          <div
            role="alert"
            className="mb-3 rounded-md bg-[rgba(178,58,46,0.08)] px-3 py-2 font-interface text-sm text-data-negative"
          >
            {actionError}
          </div>
        )}

        {/* Approver actions */}
        {showApproverActions && (
          <>
            <p className="mb-4 font-interface text-sm text-fg-slate">
              This package is awaiting attestation. Review the extracted facts and reviewer notes before proceeding.
            </p>
            <div className="flex flex-wrap gap-3">
              {/* Brass — Attest approval: the only brass button in the app (spec §9.3) */}
              <button
                type="button"
                onClick={() => setModal("approve")}
                className="inline-flex items-center gap-2 rounded-md px-4 py-2 font-interface text-sm font-semibold text-white transition-colors duration-fast focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-[#B8914E]"
                style={{ backgroundColor: "#B8914E" }}
              >
                Attest approval
              </button>

              {/* Record rejection — secondary, not brass */}
              <button
                type="button"
                onClick={() => setModal("reject")}
                className="inline-flex items-center gap-2 rounded-md px-4 py-2 font-interface text-sm font-semibold text-fg-obsidian border border-border-hairline bg-bg-parchment hover:bg-bg-bone transition-colors duration-fast focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-fg-slate"
              >
                Record rejection
              </button>
            </div>
          </>
        )}

        {/* Reviewer/admin claim actions */}
        {showReviewerActions && (
          <>
            <p className="mb-4 font-interface text-sm text-fg-slate">
              {effectiveClaimState === "unclaimed"
                ? "Claim this package to begin your review."
                : effectiveClaimState === "claimed_by_you"
                ? "You have claimed this package. Record review notes before routing for approval."
                : "This package is under review."}
            </p>
            <div className="flex flex-wrap gap-3">
              {/* Claim to review — shown for unclaimed packages */}
              {(effectiveClaimState === "unclaimed" || effectiveClaimState === null) && (
                <button
                  type="button"
                  onClick={handleClaim}
                  disabled={actionLoading === "claim"}
                  className="inline-flex items-center gap-2 rounded-md px-4 py-2 font-interface text-sm font-semibold text-fg-obsidian border border-border-hairline bg-bg-parchment hover:bg-bg-bone transition-colors duration-fast focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-fg-slate disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {actionLoading === "claim" ? (
                    <>
                      <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" aria-hidden="true" />
                      Claiming…
                    </>
                  ) : (
                    "Claim to review"
                  )}
                </button>
              )}

              {/* Release claim + Route for approval — shown when claimed by current user */}
              {effectiveClaimState === "claimed_by_you" && (
                <>
                  <button
                    type="button"
                    onClick={handleRelease}
                    disabled={actionLoading === "release"}
                    className="inline-flex items-center gap-2 rounded-md px-4 py-2 font-interface text-sm font-semibold text-fg-muted border border-border-hairline bg-bg-bone hover:bg-bg-parchment transition-colors duration-fast focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-fg-slate disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {actionLoading === "release" ? (
                      <>
                        <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" aria-hidden="true" />
                        Releasing…
                      </>
                    ) : (
                      "Release claim"
                    )}
                  </button>

                  {/* Route for approval */}
                  <button
                    type="button"
                    onClick={handleRouteForApproval}
                    disabled={actionLoading === "route"}
                    className="inline-flex items-center gap-2 rounded-md px-4 py-2 font-interface text-sm font-semibold text-fg-obsidian border border-border-hairline bg-bg-parchment hover:bg-bg-bone transition-colors duration-fast focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-fg-slate disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {actionLoading === "route" ? (
                      <>
                        <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" aria-hidden="true" />
                        Routing…
                      </>
                    ) : (
                      "Route for approval"
                    )}
                  </button>
                </>
              )}
            </div>
          </>
        )}
      </div>

      {modal && (
        <AttestationModal
          variant={modal}
          packageSummary={packageSummary}
          documentId={documentId}
          onClose={() => setModal(null)}
          onSuccess={handleSuccess}
        />
      )}
    </>
  );
}
