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
import { getMe, listDocuments } from "@/lib/api";
import { TopNav } from "@/components/TopNav";
import { StaleBanner } from "@/components/StaleBanner";
import { Button } from "@/components/Button";
import { PackageRow } from "@/components/PackageRow";
import { resolvePackageState } from "@/lib/state";
import type { DocumentSummary, User } from "@/lib/api";
import type { PackageRowPkg } from "@/components/PackageRow";

/** Convert a DocumentSummary to the PackageRowPkg shape. */
function toRowPkg(doc: DocumentSummary): PackageRowPkg {
  return {
    id: doc.id,
    title: doc.filename,
    state: doc.status,
    confidence: doc.confidence,
    docType: doc.doc_type,
    lastMovement: doc.uploaded_at,
    // claimStatus: Phase B — Drummer will add claimed_by_user_id; default unclaimed here
    claimStatus: null,
  };
}

const MAX_VISIBLE = 5;

interface SectionProps {
  title: string;
  count: number;
  useBrassCount?: boolean;
  emptyState: string;
  docs: DocumentSummary[];
  action?: React.ReactNode;
  /** If true, sticky section header on mobile */
  stickyHeader?: boolean;
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
}: SectionProps) {
  const visible = docs.slice(0, MAX_VISIBLE);
  const hasMore = count > MAX_VISIBLE;

  return (
    <section className="mb-6 md:mb-8">
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
            "font-interface text-sm tabular-nums",
            useBrassCount && count > 0
              ? "text-[#B8914E] font-semibold"
              : "text-fg-muted",
          ].join(" ")}
        >
          {count}
        </span>
        <span className="flex-1 border-t border-border-hairline" aria-hidden="true" />
        {action && <span className="flex-shrink-0">{action}</span>}
      </div>

      {/* Row container */}
      <div className="rounded-lg border border-border-hairline bg-bg-bone overflow-hidden">
        {docs.length === 0 ? (
          <p className="px-4 py-4 font-interface text-sm text-fg-muted italic">
            {emptyState}
          </p>
        ) : (
          <>
            {visible.map((doc) => (
              <PackageRow key={doc.id} pkg={toRowPkg(doc)} />
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

  let documents: DocumentSummary[] = [];
  let user: User | null = null;
  let fetchError: string | null = null;

  try {
    [user, documents] = await Promise.all([
      getMe(token),
      listDocuments(token),
    ]);
  } catch (err) {
    fetchError =
      err instanceof Error ? err.message : "Failed to load packages.";
  }

  // ─── Single-pass partition into sections ────────────────────────────────
  // Resolve state once per document, then bucket — avoids 5× resolvePackageState calls per doc.
  // Strict section order per spec §5.1:
  //   1. Exceptions  2. Pending approval  3. Needs review  4. Active packages  5. Recent decisions

  const exceptions: DocumentSummary[] = [];
  const pendingApproval: DocumentSummary[] = [];
  const needsReview: DocumentSummary[] = [];
  const activePackages: DocumentSummary[] = [];
  const recentDecisions: DocumentSummary[] = [];

  for (const d of documents) {
    const { uiState } = resolvePackageState(d.status, d.confidence);
    const isDecided =
      uiState === "decision_recorded_approved" || uiState === "decision_recorded_rejected";

    if (!isDecided) activePackages.push(d);

    if (uiState === "exception_surfaced") {
      exceptions.push(d);
    } else if (uiState === "routed_for_approval") {
      pendingApproval.push(d);
    } else if (
      uiState === "intake_complete" ||
      uiState === "under_review" ||
      uiState === "unclaimed"
    ) {
      needsReview.push(d);
    } else if (isDecided) {
      recentDecisions.push(d);
    }
  }

  const activeCount = activePackages.length;
  const pendingAttestationCount = pendingApproval.length;

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
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 md:py-8">
        {/* Page header */}
        <div className="mb-6 md:mb-8">
          <h1 className="font-display text-xl md:text-2xl font-light text-fg-obsidian tracking-tight">
            Operations console
          </h1>
          <p className="mt-0.5 font-interface text-sm text-fg-muted">
            {activeCount > 0
              ? `${activeCount} active package${activeCount !== 1 ? "s" : ""} across your desk`
              : "No packages in flight. Begin an intake to open the first record."}
          </p>
        </div>

        {/* Section 1: Exceptions — sticky header on mobile (top of list) */}
        <ConsoleSection
          title="Exceptions"
          count={exceptions.length}
          emptyState="No exceptions surfaced. All packages within confidence thresholds."
          docs={exceptions}
          stickyHeader
        />

        {/* Section 2: Pending approval — brass count when > 0 */}
        <ConsoleSection
          title="Pending approval"
          count={pendingApproval.length}
          useBrassCount
          emptyState="No packages routed for attestation."
          docs={pendingApproval}
        />

        {/* Section 3: Needs review */}
        <ConsoleSection
          title="Needs review"
          count={needsReview.length}
          emptyState="Nothing awaiting your review. Reviewer queue is clear."
          docs={needsReview}
        />

        {/* Section 4: Active packages — "Begin intake" CTA in header */}
        <ConsoleSection
          title="Active packages"
          count={activeCount}
          emptyState="No packages in flight. Begin an intake to open the first record."
          docs={activePackages}
          action={
            <Link href="/documents/upload">
              <Button variant="primary" className="text-xs px-3 py-1.5">
                Begin intake
              </Button>
            </Link>
          }
        />

        {/* Section 5: Recent decisions */}
        <ConsoleSection
          title="Recent decisions"
          count={recentDecisions.length}
          emptyState="No decisions recorded in the last 30 days."
          docs={recentDecisions}
        />
      </main>

      {/*
        Mobile sticky bottom CTA — "Begin intake" pinned to viewport bottom on xs screens.
        Hidden from md upwards (button is in Active packages header instead).
      */}
      <div className="md:hidden fixed bottom-0 inset-x-0 z-20 p-4 bg-bg-bone border-t border-border-hairline">
        <Link href="/documents/upload" className="block w-full">
          <Button variant="primary" className="w-full justify-center">
            Begin intake
          </Button>
        </Link>
      </div>
      {/* Spacer so content isn't hidden under the sticky CTA on mobile */}
      <div className="md:hidden h-20" aria-hidden="true" />
    </div>
  );
}
