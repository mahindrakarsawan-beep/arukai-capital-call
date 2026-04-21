/**
 * Package detail page — /documents/[id] (spec §6)
 * 4-block layout: Source document | Extracted facts | Review notes | Audit trail
 * Header: package title, state pill + next-owner chip, "Package submitted {date} by {actor}"
 *
 * v0.2 API contract fix (POR-same-class-as-146):
 *   - GET /packages/{id} returns `state` not `status`
 *   - classification lives at doc.documents[0].classification
 *   - AI data (extracted_fields, classification_reasoning, model_used,
 *     classification_duration_ms) is top-level on PackageDetail
 */

import React from "react";
import Link from "next/link";
import { redirect, notFound } from "next/navigation";
import { getToken } from "@/lib/auth";
import { getPackage, getMe } from "@/lib/api";
import { ClassificationBadge } from "@/components/ClassificationBadge";
import { StatusPill } from "@/components/StatusPill";
import { NextOwnerChip } from "@/components/NextOwnerChip";
import { TopNav } from "@/components/TopNav";
import { ConfidenceBadge } from "@/components/ConfidenceBadge";
import { PackageDetailActions } from "./PackageDetailActions";
import { SourceViewer } from "@/components/SourceViewer";
import { AIAnalysisBlock } from "@/components/AIAnalysisBlock";
import { resolvePackageState } from "@/lib/state";
import type { PackageDetail, User } from "@/lib/api";

interface Props {
  params: Promise<{ id: string }>;
}

/**
 * POR-161 #1: derive a display name for the "Package submitted by …" subtitle
 * from a user's email local-part. Falls back through email → uuid → "Someone".
 * Example: "naomi.ito@arukai.example" → "Naomi Ito". UUID inputs pass through
 * unchanged so the subtitle still degrades gracefully if the server didn't join.
 */
function formatUploaderName(email: string | null | undefined, uuid: string | null | undefined): string {
  if (email) {
    const local = email.split("@")[0] ?? email;
    return local
      .split(/[._-]+/)
      .filter(Boolean)
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
      .join(" ") || email;
  }
  return uuid ?? "Someone";
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

  let doc: PackageDetail | null = null;
  let user: User | null = null;

  try {
    [user, doc] = await Promise.all([getMe(token), getPackage(id, token)]);
  } catch (err) {
    if (err instanceof Error && err.message.includes("404")) {
      notFound();
    }
    throw err;
  }

  if (!doc) notFound();

  // v0.2: classification lives at documents[0].classification (not top-level).
  const classification = doc.documents?.[0]?.classification ?? null;

  // v0.2: confidence comes from the nested classification; top-level extracted_fields
  // and AI metadata come directly from PackageDetail.
  const confidence = classification?.confidence ?? null;

  // v0.2: use doc.state (not doc.status which is undefined on PackageDetailOut).
  const stateInfo = resolvePackageState(
    doc.state,
    confidence,
    undefined,
    undefined
  );

  // Show action bar per role × state matrix (spec §6.5).
  const isApproverRole = user?.role === "approver";
  const isAdminRole = user?.role === "admin";
  const isReviewerRole = user?.role === "reviewer";

  // Approver / admin attest on routed_for_approval (or legacy pending_review)
  const canAttest = (isApproverRole || isAdminRole) && (
    doc.state === "routed_for_approval" || doc.legacy_status === "pending_review"
  );
  // Reviewer / admin can claim on intake_complete, under_review, exception_surfaced
  const canClaim =
    (isReviewerRole || isAdminRole) &&
    (doc.state === "intake_complete" ||
      doc.state === "under_review" ||
      doc.state === "exception_surfaced" ||
      doc.state === "pending_review");

  const showActions = canAttest || canClaim;

  // Derive claimState from package fields when available.
  // claimed_by_user_id comes from PackageDetail when backend has shipped it.
  const claimState = (() => {
    if (!canClaim) return undefined;
    if (doc.claimed_by_user_id && user?.id) {
      if (doc.claimed_by_user_id === user.id) return "claimed_by_you" as const;
      return "claimed_by_other" as const;
    }
    // No claimant: treat as unclaimed for intake_complete and exception_surfaced
    if (
      doc.state === "intake_complete" ||
      doc.state === "exception_surfaced" ||
      doc.state === "pending_review"
    ) {
      return "unclaimed" as const;
    }
    return undefined;
  })();

  return (
    <div className="flex min-h-screen flex-col">
      <TopNav user={user} />

      <main className="mx-auto w-full max-w-4xl flex-1 px-4 py-12 md:py-16 lg:py-16">
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
        <div className="mb-8">
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <h1 className="font-display text-[28px] md:text-[32px] font-light text-fg-obsidian tracking-tight break-all">
              {doc.filename}
            </h1>
            <div className="flex items-center gap-2 flex-shrink-0">
              <StatusPill status={doc.state as import("@/lib/api").DocumentStatus} confidence={confidence} />
              <NextOwnerChip stateInfo={stateInfo} />
            </div>
          </div>
          <p className="mt-1 font-interface text-sm text-fg-muted">
            Package submitted {doc.uploaded_at ? formatDateTime(doc.uploaded_at) : "—"}
            {/* POR-161 #1: prefer the email-derived display name over the raw
                UUID. Falls back to email, then UUID, then nothing — the UUID
                path should rarely trigger in practice (users always have email). */}
            {doc.uploaded_by_email || doc.uploaded_by
              ? ` by ${formatUploaderName(doc.uploaded_by_email, doc.uploaded_by)}`
              : ""}
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

        {/* 5-block grid: 2×2 ≥lg (AI Analysis spans full width), stacked on narrow */}
        <div className="grid gap-8 lg:grid-cols-2">
          {/* Block 1: Source document */}
          <div className="rounded-lg border border-border-hairline bg-bg-parchment p-6 lg:p-8 shadow-sm">
            <h2 className="mb-6 font-display text-xl font-light tracking-tight text-fg-obsidian">
              Source document
            </h2>
            {/* A3: blob-URL auth fix — SourceViewer fetches PDF with Authorization header */}
            <SourceViewer
              documentId={doc.id}
              filename={doc.filename}
              sizeBytes={0}
              uploadedAt={doc.uploaded_at ?? ""}
            />
          </div>

          {/* Block 2: Extracted facts */}
          <div className="rounded-lg border border-border-hairline bg-bg-parchment p-6 lg:p-8 shadow-sm">
            <h2 className="mb-6 font-display text-xl font-light tracking-tight text-fg-obsidian">
              Extracted facts
            </h2>

            {classification ? (
              <div className="flex flex-col gap-3">
                {(classification.model_version ?? doc.model_used) && (
                  <p className="font-interface text-[10px] text-fg-muted">
                    Extracted by {classification.model_version ?? doc.model_used}
                    {/* POR-161 #3: drop the " on —" trailing em-dash when we
                        don't have a date. Only render the "on <date>" clause
                        when uploaded_at is present. */}
                    {doc.uploaded_at ? ` on ${formatDateTime(doc.uploaded_at)}` : ""}
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

                {/* Key indicators — guard against null (old API responses) */}
                {Array.isArray(classification.key_indicators) && classification.key_indicators.length > 0 && (
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
                {doc.state === "submitted" || doc.legacy_status === "pending_classification"
                  ? "Intake in progress…"
                  : "No extracted facts available."}
              </p>
            )}
          </div>

          {/* Block 3: AI Analysis (POR-148) — full width across both columns.
              POR-159 19d.3: gate on either nested classification OR top-level AI
              fields. POR-151 moved fields top-level; existing seed packages have
              `classification: null` in the response, which was hiding this block
              entirely despite the AI data being present. Miller caught this. */}
          {(classification ||
            doc.extracted_fields ||
            doc.classification_reasoning ||
            doc.model_used) && (
            <div className="lg:col-span-2">
              <AIAnalysisBlock
                classification={
                  classification ?? {
                    // Synthesize a minimal Classification stub from top-level AI
                    // data so AIAnalysisBlock's prop contract holds when the
                    // nested classification is null. doc_type/confidence aren't
                    // available at top-level on PackageDetail — AIAnalysisBlock
                    // will fall through to its overall-confidence fallback.
                    doc_type: "other",
                    confidence: 0,
                    key_indicators: [],
                    extracted_fields: doc.extracted_fields ?? undefined,
                    classification_reasoning: doc.classification_reasoning ?? null,
                    model_version: doc.model_used ?? undefined,
                    duration_ms: doc.classification_duration_ms ?? undefined,
                  }
                }
                analysedAt={doc.uploaded_at ?? new Date().toISOString()}
                extractedFields={doc.extracted_fields ?? undefined}
                reasoning={doc.classification_reasoning ?? undefined}
                modelUsed={doc.model_used ?? undefined}
                durationMs={doc.classification_duration_ms ?? undefined}
              />
            </div>
          )}

          {/* Block 4: Review notes */}
          <div className="rounded-lg border border-border-hairline bg-bg-bone p-6 lg:p-8 shadow-sm">
            <h2 className="mb-6 font-display text-xl font-light tracking-tight text-fg-obsidian">
              Review notes
            </h2>
            <p className="font-interface text-sm text-fg-muted italic">
              No review notes recorded. Reviewers will annotate here before routing for approval.
            </p>
            {/* Phase B: review notes input will be wired here by Drummer (B1) */}
          </div>

          {/* Block 5: Audit trail */}
          <div className="rounded-lg border border-border-hairline bg-bg-bone p-6 lg:p-8 shadow-sm">
            <h2 className="mb-6 font-display text-xl font-light tracking-tight text-fg-obsidian">
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

        {/* Bottom action bar — role-routed actions (spec §6.5) */}
        {showActions && (
          <div className="mt-6">
            <PackageDetailActions
              documentId={doc.id}
              packageTitle={doc.filename}
              classification={classification?.doc_type ?? undefined}
              confidence={classification?.confidence ?? undefined}
              userRole={user?.role}
              packageState={doc.state}
              claimState={claimState}
            />
          </div>
        )}

        {/* Terminal state banner */}
        {(doc.state === "decision_recorded" || doc.legacy_status === "approved" || doc.legacy_status === "rejected") && (
          <div className="mt-6 rounded-lg border border-border-hairline bg-bg-parchment px-5 py-4">
            <p className="font-interface text-sm text-fg-slate">
              Package closed. Decision recorded
              {doc.legacy_status === "rejected" ? " — Rejected" : " — Approved"}.
            </p>
          </div>
        )}
      </main>
    </div>
  );
}
