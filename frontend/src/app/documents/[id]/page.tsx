/**
 * Package detail page — /documents/[id] (spec §6)
 * 4-block layout: Source document | Extracted facts | Review notes | Audit trail
 * Header: package title, state pill + next-owner chip, "Package submitted {date} by {actor}"
 *
 * BUG FIX: v0.1 read doc.classification but API returns doc.documents[0].classification
 * Fixed at line ~50: safe fallback to doc.documents?.[0]?.classification
 *
 * Attestation actions replaced inline approve/reject with AttestationModal trigger.
 */

import React from "react";
import Link from "next/link";
import { redirect, notFound } from "next/navigation";
import { getToken } from "@/lib/auth";
import { getDocument, getDocumentDownloadUrl, getMe } from "@/lib/api";
import { ClassificationBadge } from "@/components/ClassificationBadge";
import { StatusPill } from "@/components/StatusPill";
import { NextOwnerChip } from "@/components/NextOwnerChip";
import { TopNav } from "@/components/TopNav";
import { ConfidenceBadge } from "@/components/ConfidenceBadge";
import { PackageDetailActions } from "./PackageDetailActions";
import { resolvePackageState } from "@/lib/state";
import type { DocumentDetail, User } from "@/lib/api";

interface Props {
  params: Promise<{ id: string }>;
}

function formatDateTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString("en-US", {
      year: "numeric",
      month: "long",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export default async function DocumentDetailPage({ params }: Props) {
  const { id } = await params;
  const token = await getToken();

  if (!token) {
    redirect("/");
  }

  let doc: DocumentDetail | null = null;
  let user: User | null = null;

  try {
    [user, doc] = await Promise.all([getMe(token), getDocument(id, token)]);
  } catch (err) {
    if (err instanceof Error && err.message.includes("404")) {
      notFound();
    }
    throw err;
  }

  if (!doc) notFound();

  // BUG FIX: v0.1 read doc.classification directly; API may return doc.documents[0].classification
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const raw = doc as any;
  const classification =
    doc.classification ??
    raw.documents?.[0]?.classification ??
    null;

  const stateInfo = resolvePackageState(
    doc.status,
    doc.confidence,
    undefined,
    undefined
  );

  const canAttest = user?.role === "admin" && doc.status === "pending_review";

  return (
    <div className="flex min-h-screen flex-col">
      <TopNav user={user} />

      <main className="mx-auto w-full max-w-4xl flex-1 px-4 py-8">
        {/* Breadcrumb */}
        <nav className="mb-6 flex items-center gap-2 font-interface text-sm text-fg-muted">
          <Link
            href="/documents"
            className="hover:text-fg-obsidian transition-colors"
          >
            Console
          </Link>
          <span>/</span>
          <span className="text-fg-obsidian truncate max-w-xs">
            {doc.filename}
          </span>
        </nav>

        {/* Header block */}
        <div className="mb-6">
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <h1 className="font-display text-2xl font-light text-fg-obsidian tracking-tight break-all">
              {doc.filename}
            </h1>
            <div className="flex items-center gap-2 flex-shrink-0">
              <StatusPill status={doc.status} confidence={doc.confidence} />
              <NextOwnerChip stateInfo={stateInfo} />
            </div>
          </div>
          <p className="mt-1 font-interface text-sm text-fg-muted">
            Package submitted {doc.uploaded_at ? formatDateTime(doc.uploaded_at) : "—"}
            {doc.uploaded_by ? ` by ${doc.uploaded_by}` : ""}
          </p>
          {classification && (
            <p className="mt-0.5 font-interface text-sm text-fg-slate">
              Classification:{" "}
              <ClassificationBadge docType={classification.doc_type} />
              {typeof classification.confidence === "number" && (
                <span className="ml-2 text-fg-muted">
                  · intake confidence{" "}
                  <ConfidenceBadge confidence={classification.confidence} />
                </span>
              )}
            </p>
          )}
        </div>

        {/* 4-block grid: 2×2 ≥lg, stacked on narrow */}
        <div className="grid gap-4 lg:grid-cols-2">
          {/* Block 1: Source document */}
          <div className="rounded-lg border border-border-hairline bg-bg-bone p-5 shadow-sm">
            <h2 className="mb-3 font-interface text-xs font-medium uppercase tracking-widest text-fg-muted">
              Source document
            </h2>
            {/* Phase A acceptable fallback: iframe embed */}
            <iframe
              src={getDocumentDownloadUrl(doc.id)}
              title={`Source PDF: ${doc.filename}`}
              className="w-full rounded border border-border-hairline"
              style={{ height: "600px" }}
            />
            <div className="mt-3 pt-3 border-t border-border-hairline">
              <a
                href={getDocumentDownloadUrl(doc.id)}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 font-interface text-sm text-fg-slate hover:text-fg-obsidian transition-colors duration-fast"
              >
                <svg
                  className="h-4 w-4"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={1.5}
                  aria-hidden="true"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25"
                  />
                </svg>
                View source document
              </a>
            </div>
          </div>

          {/* Block 2: Extracted facts */}
          <div className="rounded-lg border border-border-hairline bg-bg-bone p-5 shadow-sm">
            <h2 className="mb-1 font-interface text-xs font-medium uppercase tracking-widest text-fg-muted">
              Extracted facts
            </h2>

            {classification ? (
              <div className="flex flex-col gap-3">
                {classification.model_version && (
                  <p className="font-interface text-[10px] text-fg-muted">
                    Extracted by {classification.model_version} on{" "}
                    {doc.uploaded_at ? formatDateTime(doc.uploaded_at) : "—"}
                  </p>
                )}

                {/* Document type */}
                <div className="flex items-center justify-between border-b border-border-hairline pb-2">
                  <span className="font-interface text-xs font-medium uppercase tracking-widest text-fg-muted">
                    Document type
                  </span>
                  <ClassificationBadge docType={classification.doc_type} />
                </div>

                {/* Confidence with band treatment */}
                <div className="flex items-center justify-between border-b border-border-hairline pb-2">
                  <span className="font-interface text-xs font-medium uppercase tracking-widest text-fg-muted">
                    Intake confidence
                  </span>
                  <ConfidenceBadge
                    confidence={classification.confidence}
                    value={`${(classification.confidence * 100).toFixed(0)}%`}
                  />
                </div>

                {/* Key indicators */}
                {classification.key_indicators?.length > 0 && (
                  <div>
                    <p className="mb-2 font-interface text-xs font-medium uppercase tracking-widest text-fg-muted">
                      Key indicators
                    </p>
                    <ul className="flex flex-col gap-1">
                      {classification.key_indicators.map(
                        (indicator: string, i: number) => (
                          <li
                            key={i}
                            className="flex items-start gap-2 font-interface text-sm text-fg-slate"
                          >
                            <span className="mt-0.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-fg-muted" />
                            {indicator}
                          </li>
                        )
                      )}
                    </ul>
                  </div>
                )}
              </div>
            ) : (
              <p className="font-interface text-sm text-fg-muted italic">
                {doc.status === "pending_classification"
                  ? "Intake in progress…"
                  : "No extracted facts available."}
              </p>
            )}
          </div>

          {/* Block 3: Review notes */}
          <div className="rounded-lg border border-border-hairline bg-bg-bone p-5 shadow-sm">
            <h2 className="mb-3 font-interface text-xs font-medium uppercase tracking-widest text-fg-muted">
              Review notes
            </h2>
            <p className="font-interface text-sm text-fg-muted italic">
              No review notes recorded. Reviewers will annotate here before routing for approval.
            </p>
            {/* Phase B: review notes input will be wired here by Drummer (B1) */}
          </div>

          {/* Block 4: Audit trail */}
          <div className="rounded-lg border border-border-hairline bg-bg-bone p-5 shadow-sm">
            <h2 className="mb-3 font-interface text-xs font-medium uppercase tracking-widest text-fg-muted">
              Audit trail
            </h2>
            <p className="font-interface text-sm text-fg-muted italic">
              Package has no recorded events yet. Submission event will appear on intake.
            </p>
            {/* Phase B: audit trail endpoint wired by Drummer (B1) */}
            <div className="mt-3 pt-3 border-t border-border-hairline">
              <span className="font-interface text-xs text-fg-muted">
                Open in audit ledger →
              </span>
            </div>
          </div>
        </div>

        {/* Bottom action bar — attestation modal trigger */}
        {canAttest && (
          <div className="mt-6">
            <PackageDetailActions
              documentId={doc.id}
              packageTitle={doc.filename}
              classification={classification?.doc_type ?? undefined}
              confidence={classification?.confidence ?? undefined}
            />
          </div>
        )}

        {/* Terminal state banner */}
        {(doc.status === "approved" || doc.status === "rejected") && (
          <div className="mt-6 rounded-lg border border-border-hairline bg-bg-parchment px-5 py-4">
            <p className="font-interface text-sm text-fg-slate">
              Package closed. Decision recorded
              {doc.status === "approved" ? " — Approved" : " — Rejected"}.
            </p>
          </div>
        )}
      </main>
    </div>
  );
}
