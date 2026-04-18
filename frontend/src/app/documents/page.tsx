/**
 * Operations console — /documents (spec §5)
 * Five sections in strict order: Exceptions · Pending approval · Needs review · Active packages · Recent decisions
 *
 * Per Holden's Figma synthesis (A1):
 *  - Each section: heading + count + max 5 rows + "Show all N" expander when count > 5
 *  - Empty states per section with Arukai-language copy
 *  - "Begin intake" primary button in Active packages section header
 *  - Responsive: desktop (lg:) / tablet (md:) / mobile (default)
 *
 * Server component: fetches /documents using JWT from cookie.
 */

import React from "react";
import Link from "next/link";
import { redirect } from "next/navigation";
import { getToken } from "@/lib/auth";
import { getMe, listPackages } from "@/lib/api";
import { TopNav } from "@/components/TopNav";
import { StaleBanner } from "@/components/StaleBanner";
import { Button } from "@/components/Button";
import { PackageRow } from "@/components/PackageRow";
import { resolvePackageState } from "@/lib/state";
import type { PackageListOut, User } from "@/lib/api";
import type { PackageRowPkg } from "@/components/PackageRow";

/** Convert a PackageListOut (v0.2) to the PackageRowPkg shape. */
function toRowPkg(pkg: PackageListOut): PackageRowPkg {
  return {
    id: pkg.id,
    // Use the human-readable title — not the bare filename
    title: pkg.title,
    state: pkg.state,
    confidence: pkg.confidence,
    // Wire classification badge from eagerly-loaded doc_type
    docType: pkg.doc_type,
    lastMovement: pkg.uploaded_at,
    // claimStatus: Phase B — Drummer will add claimed_by_user_id; default null here
    claimStatus: null,
  };
}

const MAX_VISIBLE = 5;

interface SectionProps {
  title: string;
  count: number;
  useBrassCount?: boolean;
  emptyState: string;
  docs: PackageListOut[];
  action?: React.ReactNode;
  /** If true, sticky section header on mobile */
  stickyHeader?: boolean;
  /**
   * Role-specific callout rendered above the rows (e.g. approver attestation callout).
   * Only rendered when count > 0.
   */
  callout?: React.ReactNode;
  /**
   * Per-row claim toggle handler — passed to PackageRow for reviewer claim CTAs.
   */
  onClaimToggle?: (id: string, action: "claim" | "release") => void;
}

/**
 * ConsoleSection — renders a titled section with rows, cap at MAX_VISIBLE.
 * "Show all N" link appears when count > MAX_VISIBLE.
 *
 * Responsive:
 *  - Mobile: section header is sticky (stickyHeader=true on first section)
 *  - All sizes: same 5-section structure, tighter padding at md
 */
function ConsoleSection({
  title,
  count,
  useBrassCount,
  emptyState,
  docs,
  action,
  stickyHeader,
  callout,
  onClaimToggle,
}: SectionProps) {
  const visible = docs.slice(0, MAX_VISIBLE);
  const hasMore = count > MAX_VISIBLE;

  return (
    <section className="mb-10 md:mb-12">
      {/* Section header — sticky on mobile for long lists */}
      <div
        className={[
          "flex items-center gap-3 mb-3 bg-bg-bone",
          stickyHeader
            ? "sticky top-[53px] z-[5] py-2 -mx-4 px-4 border-b border-border-hairline md:static md:border-none md:mx-0 md:px-0 md:py-0"
            : "",
        ]
          .filter(Boolean)
          .join(" ")}
      >
        <h2 className="font-display text-lg md:text-xl font-light text-fg-obsidian tracking-tight">
          {title}
        </h2>
        <span
          className={[
            "inline-flex items-center justify-center rounded-full px-2 py-0.5 font-interface text-xs tabular-nums min-w-[1.5rem]",
            useBrassCount && count > 0
              ? "bg-[rgba(184,145,78,0.15)] text-[#9A7639] font-medium"
              : "bg-[rgba(140,149,163,0.12)] text-fg-muted font-normal",
          ].join(" ")}
        >
          {count}
        </span>
        <span className="flex-1 border-t border-border-hairline" aria-hidden="true" />
        {action && <span className="flex-shrink-0">{action}</span>}
      </div>

      {/* Role-specific callout — shown above rows when section has content */}
      {callout && count > 0 && (
        <div className="mb-2">{callout}</div>
      )}

      {/* Row container */}
      <div className="rounded-lg border border-border-hairline bg-bg-bone overflow-hidden">
        {docs.length === 0 ? (
          <p className="px-4 py-4 font-interface text-sm text-fg-muted italic">
            {emptyState}
          </p>
        ) : (
          <>
            {visible.map((doc) => (
              <PackageRow
                key={doc.id}
                pkg={toRowPkg(doc)}
                onClaimToggle={onClaimToggle}
              />
            ))}
            {/* "Show all N" expander — appears when section has more than MAX_VISIBLE items */}
            {hasMore && (
              <div className="px-4 py-2 border-t border-border-hairline bg-bg-parchment">
                <Link
                  href={`/documents?filter=${encodeURIComponent(title.toLowerCase().replace(/\s+/g, "_"))}`}
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

export default async function DocumentsPage() {
  const token = await getToken();

  if (!token) {
    redirect("/");
  }

  let packages: PackageListOut[] = [];
  let user: User | null = null;
  let fetchError: string | null = null;

  try {
    [user, packages] = await Promise.all([
      getMe(token),
      listPackages(token),
    ]);
  } catch (err) {
    fetchError =
      err instanceof Error ? err.message : "Failed to load packages.";
  }

  // ─── Single-pass partition into sections ────────────────────────────────
  // Resolve state once per document, then bucket — avoids 5× resolvePackageState calls per doc.
  // Strict section order per spec §5.1:
  //   1. Exceptions  2. Pending approval  3. Needs review  4. Active packages  5. Recent decisions

  const exceptions: PackageListOut[] = [];
  const pendingApproval: PackageListOut[] = [];
  const needsReview: PackageListOut[] = [];
  const activePackages: PackageListOut[] = [];
  const recentDecisions: PackageListOut[] = [];

  for (const pkg of packages) {
    // Use v0.2 state field natively — resolvePackageState handles it as first-class.
    const { uiState } = resolvePackageState(pkg.state, pkg.confidence);
    const isTerminal =
      uiState === "decision_recorded_approved" || uiState === "decision_recorded_rejected";

    if (isTerminal) {
      // Terminal packages go ONLY to recentDecisions — NOT activePackages (no double-count)
      recentDecisions.push(pkg);
    } else {
      // All non-terminal packages appear in activePackages
      activePackages.push(pkg);
      // Then route into exactly ONE priority section (exceptions > pendingApproval > needsReview)
      if (uiState === "exception_surfaced") {
        exceptions.push(pkg);
      } else if (uiState === "routed_for_approval") {
        pendingApproval.push(pkg);
      } else if (
        uiState === "intake_complete" ||
        uiState === "under_review" ||
        uiState === "unclaimed"
      ) {
        needsReview.push(pkg);
      }
      // "submitted" state: non-terminal but no priority section — only activePackages
    }
  }

  const activeCount = activePackages.length;
  const pendingAttestationCount = pendingApproval.length;
  const role = user?.role ?? "admin";

  // ─── Role-specific helpers ──────────────────────────────────────────────────
  const isReviewer = role === "reviewer";
  const isApprover = role === "approver";
  // Admin sees everything; reviewer and approver cannot upload
  const canUpload = role === "admin" || role === "operator";

  // "Begin intake" CTA — only shown to roles that can upload
  const beginIntakeCTA = canUpload ? (
    <Link href="/documents/upload">
      <Button variant="primary" className="text-xs px-3 py-1.5">
        Begin intake
      </Button>
    </Link>
  ) : null;

  // Approver attestation callout — brass highlight when pending > 0
  const approverCallout =
    isApprover && pendingAttestationCount > 0 ? (
      <div
        className="flex items-center gap-2 px-3 py-2 rounded border border-[rgba(184,145,78,0.30)] bg-[rgba(184,145,78,0.08)]"
        role="status"
        aria-label={`${pendingAttestationCount} package${pendingAttestationCount !== 1 ? "s" : ""} awaiting your attestation`}
      >
        <span
          className="inline-flex items-center rounded-full px-2.5 py-0.5 font-interface text-xs font-semibold tabular-nums bg-[rgba(184,145,78,0.20)] text-[#B8914E] border border-[rgba(184,145,78,0.30)]"
          aria-hidden="true"
        >
          {pendingAttestationCount}
        </span>
        <span className="font-interface text-sm text-[#9A7639]">
          Pending your attestation
        </span>
      </div>
    ) : null;

  // ─── Section ordering per role ──────────────────────────────────────────────
  // Reviewer: Needs review first (their primary action)
  // Approver: Pending approval first
  // Admin/operator: standard spec order (Exceptions → Pending → Needs → Active → Recent)

  const sections = (() => {
    const exceptionsSection = (
      <ConsoleSection
        key="exceptions"
        title="Exceptions"
        count={exceptions.length}
        emptyState="No exceptions surfaced. All packages within confidence thresholds."
        docs={exceptions}
        stickyHeader={!isReviewer && !isApprover}
      />
    );

    const pendingApprovalSection = (
      <ConsoleSection
        key="pending_approval"
        title="Pending approval"
        count={pendingApproval.length}
        useBrassCount
        emptyState="No packages routed for attestation."
        docs={pendingApproval}
        callout={approverCallout}
        // Approvers can attest but cannot claim; no claim toggle here
      />
    );

    const needsReviewSection = (
      <ConsoleSection
        key="needs_review"
        title="Needs review"
        count={needsReview.length}
        emptyState="Nothing awaiting your review. Reviewer queue is clear."
        docs={needsReview}
        stickyHeader={isReviewer}
        // Reviewers get claim CTAs via onClaimToggle; approvers do not
        onClaimToggle={
          isReviewer
            ? (_id: string, _action: "claim" | "release") => {
                // Phase B: wire to claimPackage / releasePackage API calls
                // For now, the claim CTA is shown via PackageRow's claimStatus logic
              }
            : undefined
        }
      />
    );

    const activePackagesSection = (
      <ConsoleSection
        key="active_packages"
        title="Active packages"
        count={activeCount}
        emptyState="No packages in flight. Begin an intake to open the first record."
        docs={activePackages}
        action={beginIntakeCTA ?? undefined}
      />
    );

    const recentDecisionsSection = (
      <ConsoleSection
        key="recent_decisions"
        title="Recent decisions"
        count={recentDecisions.length}
        emptyState="No decisions recorded in the last 30 days."
        docs={recentDecisions}
      />
    );

    if (isReviewer) {
      // Reviewer view: Needs review first (primary action), then rest
      return [
        needsReviewSection,
        exceptionsSection,
        activePackagesSection,
        recentDecisionsSection,
      ];
    }

    if (isApprover) {
      // Approver view: Pending approval first (primary action)
      return [
        pendingApprovalSection,
        exceptionsSection,
        recentDecisionsSection,
        activePackagesSection,
      ];
    }

    // Admin / operator: standard spec order
    return [
      exceptionsSection,
      pendingApprovalSection,
      needsReviewSection,
      activePackagesSection,
      recentDecisionsSection,
    ];
  })();

  return (
    <div className="flex min-h-screen flex-col bg-bg-bone">
      <TopNav user={user} pendingAttestationCount={pendingAttestationCount} />

      {fetchError && (
        <StaleBanner message="Workflow state could not be refreshed. The information shown may be stale." />
      )}

      {/*
        Main content:
          Mobile (default):    px-4, single-column, full width
          Tablet (md: 768px):  tighter max-width, same single-column sections
          Desktop (lg: 1280px): max-w-6xl centred, same 5-section layout
      */}
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8 md:py-12">
        {/* Page header */}
        <div className="mb-8 md:mb-10">
          <h1 className="font-display text-xl md:text-2xl font-light text-fg-obsidian tracking-tight">
            Operations console
          </h1>
          <p className="mt-0.5 font-interface text-sm text-fg-muted">
            {activeCount > 0
              ? `${activeCount} active package${activeCount !== 1 ? "s" : ""} across your desk`
              : "No packages in flight. Begin an intake to open the first record."}
          </p>
        </div>

        {sections}
      </main>

      {/*
        Mobile sticky bottom CTA — "Begin intake" pinned to viewport bottom on xs screens.
        Hidden from md upwards (button is in Active packages header instead).
        Only shown to roles that can upload.
      */}
      {canUpload && (
        <>
          <div className="md:hidden fixed bottom-0 inset-x-0 z-20 p-4 bg-bg-bone border-t border-border-hairline">
            <Link href="/documents/upload" className="block w-full">
              <Button variant="primary" className="w-full justify-center">
                Begin intake
              </Button>
            </Link>
          </div>
          {/* Spacer so content isn't hidden under the sticky CTA on mobile */}
          <div className="md:hidden h-20" aria-hidden="true" />
        </>
      )}
    </div>
  );
}
