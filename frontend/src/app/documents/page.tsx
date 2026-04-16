/**
 * Operations console — /documents (spec §5)
 * Five sections in order: Exceptions · Pending approval · Needs review · Active packages · Recent decisions
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
import { StatusPill } from "@/components/StatusPill";
import { NextOwnerChip } from "@/components/NextOwnerChip";
import { ClassificationBadge } from "@/components/ClassificationBadge";
import { resolvePackageState } from "@/lib/state";
import type { DocumentSummary, User } from "@/lib/api";

function formatRelative(iso: string): string {
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

interface ConsoleRowProps {
  doc: DocumentSummary;
}

function ConsoleRow({ doc }: ConsoleRowProps) {
  const stateInfo = resolvePackageState(doc.status, doc.confidence);

  return (
    <Link
      href={`/documents/${doc.id}`}
      className="flex items-center gap-4 px-4 py-3 border-b border-border-hairline last:border-0 hover:bg-bg-parchment transition-colors duration-fast focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-fg-slate"
      aria-label={`Open package ${doc.filename}`}
    >
      {/* Package reference — Cormorant */}
      <span className="flex-1 min-w-0 font-display text-base font-normal text-fg-obsidian truncate">
        {doc.filename}
      </span>

      {/* Classification */}
      <span className="hidden md:block">
        <ClassificationBadge docType={doc.doc_type} />
      </span>

      {/* State pill + next-owner chip */}
      <span className="flex items-center gap-2 flex-shrink-0">
        <StatusPill status={doc.status} confidence={doc.confidence} />
        <NextOwnerChip stateInfo={stateInfo} />
      </span>

      {/* Last movement */}
      <span
        className="hidden lg:block font-interface text-xs text-fg-muted tabular-nums flex-shrink-0"
        title={doc.uploaded_at}
      >
        {doc.uploaded_at ? formatRelative(doc.uploaded_at) : "—"}
      </span>
    </Link>
  );
}

interface SectionProps {
  title: string;
  count: number;
  useBrassCount?: boolean;
  emptyState: string;
  docs: DocumentSummary[];
  action?: React.ReactNode;
}

function ConsoleSection({ title, count, useBrassCount, emptyState, docs, action }: SectionProps) {
  return (
    <section className="mb-8">
      {/* Section header */}
      <div className="flex items-center gap-3 mb-3">
        <h2 className="font-display text-xl font-light text-fg-obsidian tracking-tight">
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

      {/* Rows */}
      <div className="rounded-lg border border-border-hairline bg-bg-bone overflow-hidden">
        {docs.length === 0 ? (
          <p className="px-4 py-4 font-interface text-sm text-fg-muted italic">
            {emptyState}
          </p>
        ) : (
          docs.map((doc) => <ConsoleRow key={doc.id} doc={doc} />)
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

  // Partition into sections using state façade
  const exceptions = documents.filter((d) => {
    const info = resolvePackageState(d.status, d.confidence);
    return info.uiState === "exception_surfaced";
  });

  const pendingApproval = documents.filter((d) => {
    // Phase A: pending_review with confidence ≥ 0.5 is "intake_complete" (awaiting reviewer).
    // There is no v0.1 state that maps to routed_for_approval — section will be empty until Phase B.
    const info = resolvePackageState(d.status, d.confidence);
    return info.uiState === "routed_for_approval";
  });

  const needsReview = documents.filter((d) => {
    const info = resolvePackageState(d.status, d.confidence);
    return info.uiState === "intake_complete" || info.uiState === "under_review";
  });

  const activePackages = documents.filter((d) => {
    const info = resolvePackageState(d.status, d.confidence);
    return (
      info.uiState !== "decision_recorded_approved" &&
      info.uiState !== "decision_recorded_rejected"
    );
  });

  const recentDecisions = documents.filter((d) => {
    const info = resolvePackageState(d.status, d.confidence);
    return (
      info.uiState === "decision_recorded_approved" ||
      info.uiState === "decision_recorded_rejected"
    );
  });

  const activeCount = activePackages.length;

  return (
    <div className="flex min-h-screen flex-col">
      <TopNav user={user} />

      {fetchError && (
        <StaleBanner message="Workflow state could not be refreshed. The information shown may be stale." />
      )}

      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">
        {/* Page header */}
        <div className="mb-8">
          <h1 className="font-display text-2xl font-light text-fg-obsidian tracking-tight">
            Operations console
          </h1>
          <p className="mt-0.5 font-interface text-sm text-fg-muted">
            {activeCount > 0
              ? `${activeCount} active package${activeCount !== 1 ? "s" : ""} across your desk`
              : "No packages in flight. Begin an intake to open the first record."}
          </p>
        </div>

        {/* Section 1: Exceptions */}
        <ConsoleSection
          title="Exceptions"
          count={exceptions.length}
          emptyState="No exceptions surfaced. All packages within confidence thresholds."
          docs={exceptions}
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

        {/* Section 4: Active packages */}
        <ConsoleSection
          title="Active packages"
          count={activeCount}
          emptyState="No packages in flight. Begin an intake to open the first record."
          docs={activePackages}
          action={
            <Link href="/documents/upload">
              <Button variant="primary">Begin intake</Button>
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
    </div>
  );
}
