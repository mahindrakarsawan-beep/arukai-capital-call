"use client";

/**
 * NeedsReviewSection — client component for the "Needs review" console section.
 *
 * This is a client component so it can handle claim/release button clicks
 * from PackageRow without requiring a full server round-trip on every action.
 *
 * Roles that see claim CTAs: reviewer, admin.
 * On success: router.refresh() re-fetches the page from the server.
 */

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { PackageRow } from "@/components/PackageRow";
import { claimPackage, releasePackage } from "@/lib/api";
import type { PackageListOut } from "@/lib/api";
import type { PackageRowPkg } from "@/components/PackageRow";
import type { ClaimState } from "@/lib/state";
import Link from "next/link";

const MAX_VISIBLE = 5;

async function getToken(): Promise<string | null> {
  const res = await fetch("/api/token");
  const data = await res.json();
  return data.token ?? null;
}

interface NeedsReviewSectionProps {
  docs: PackageListOut[];
  /** Whether the current user can claim packages (reviewer or admin). */
  canClaim: boolean;
  /** User ID of the current user — used to determine claimed_by_you vs claimed_by_other. */
  currentUserId?: string | null;
}

/**
 * Map a PackageListOut to the PackageRowPkg shape, computing claimStatus
 * from the package state and current user.
 */
function toRowPkg(
  pkg: PackageListOut,
  currentUserId?: string | null
): PackageRowPkg {
  let claimStatus: ClaimState | null = null;

  if (pkg.state === "intake_complete" || pkg.state === "exception_surfaced") {
    // These states mean no claim yet — any reviewer/admin can claim.
    claimStatus = "unclaimed";
  } else if (pkg.state === "under_review") {
    // under_review: check if the current user holds the claim.
    // PackageListOut doesn't carry claimed_by_user_id — treat as unclaimed
    // until backend adds that field. For now, show unclaimed so the CTA appears.
    claimStatus = "unclaimed";
  }

  return {
    id: pkg.id,
    title: pkg.title,
    state: pkg.state,
    confidence: pkg.confidence,
    docType: pkg.doc_type,
    lastMovement: pkg.uploaded_at,
    claimStatus,
    aiSummary: pkg.ai_summary,
  };
}

export function NeedsReviewSection({
  docs,
  canClaim,
  currentUserId,
}: NeedsReviewSectionProps) {
  const router = useRouter();
  const [actionError, setActionError] = useState<string | null>(null);
  const [loadingId, setLoadingId] = useState<string | null>(null);

  const count = docs.length;
  const visible = docs.slice(0, MAX_VISIBLE);
  const hasMore = count > MAX_VISIBLE;

  async function handleClaimToggle(id: string, action: "claim" | "release") {
    setLoadingId(id);
    setActionError(null);
    try {
      const token = await getToken();
      if (!token) {
        setActionError("Not authenticated.");
        return;
      }
      if (action === "claim") {
        await claimPackage(id, token);
      } else {
        await releasePackage(id, token);
      }
      router.refresh();
    } catch (err) {
      setActionError(
        err instanceof Error
          ? err.message
          : `${action === "claim" ? "Claim" : "Release"} failed.`
      );
    } finally {
      setLoadingId(null);
    }
  }

  return (
    <section className="mb-10 lg:mb-12">
      <div className="flex items-center gap-3 mb-3 bg-bg-bone sticky top-[53px] z-[5] py-2 -mx-4 px-4 border-b border-border-hairline md:static md:border-none md:mx-0 md:px-0 md:py-0">
        <h2 className="font-display text-xl md:text-2xl font-light text-fg-obsidian tracking-tight">
          Needs review
        </h2>
        <span
          className="inline-flex items-center justify-center rounded-full px-2 py-0.5 font-interface text-xs tabular-nums min-w-[1.5rem] bg-[rgba(140,149,163,0.12)] text-fg-muted font-normal"
        >
          {count}
        </span>
        <span className="flex-1 border-t border-border-hairline" aria-hidden="true" />
      </div>

      {actionError && (
        <div
          role="alert"
          className="mb-2 rounded-md bg-[rgba(178,58,46,0.08)] px-3 py-2 font-interface text-sm text-data-negative"
        >
          {actionError}
        </div>
      )}

      <div className="rounded-lg border border-border-hairline bg-bg-parchment overflow-hidden">
        {docs.length === 0 ? (
          <p className="px-4 py-4 font-interface text-sm text-fg-muted italic">
            Nothing awaiting your review. Reviewer queue is clear.
          </p>
        ) : (
          <>
            {visible.map((doc) => {
              const rowPkg = toRowPkg(doc, currentUserId);
              // While an action is in-flight, suppress the CTA for that row
              const effectivePkg =
                loadingId === doc.id
                  ? { ...rowPkg, claimStatus: null as ClaimState | null }
                  : rowPkg;
              return (
                <PackageRow
                  key={doc.id}
                  pkg={effectivePkg}
                  onClaimToggle={canClaim ? handleClaimToggle : undefined}
                />
              );
            })}
            {hasMore && (
              <div className="px-4 py-2 border-t border-border-hairline bg-bg-parchment">
                <Link
                  href={`/documents?filter=needs_review`}
                  className="font-interface text-xs text-fg-slate hover:text-fg-obsidian transition-colors duration-fast focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-fg-slate rounded"
                >
                  Show all {count} →
                </Link>
              </div>
            )}
          </>
        )}
      </div>
    </section>
  );
}
