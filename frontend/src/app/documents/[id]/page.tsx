/**
 * Document detail page — /documents/[id]
 * Server component: fetches /documents/{id} using JWT from cookie.
 * Shows: filename, uploaded info, classification result (doc_type, confidence, extracted fields).
 * Admin + pending_review: shows Approve / Reject buttons.
 * Shows download link.
 */

import React from "react";
import Link from "next/link";
import { redirect, notFound } from "next/navigation";
import { getToken } from "@/lib/auth";
import { getDocument, getDocumentDownloadUrl, getMe } from "@/lib/api";
import { ClassificationBadge } from "@/components/ClassificationBadge";
import { StatusPill } from "@/components/StatusPill";
import { TopNav } from "@/components/TopNav";
import { ApprovalActions } from "./ApprovalActions";
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
    // Re-throw other errors
    throw err;
  }

  if (!doc) notFound();

  const canApprove =
    user?.role === "admin" && doc.status === "pending_review";

  return (
    <div className="flex min-h-screen flex-col">
      <TopNav user={user} />

      <main className="mx-auto w-full max-w-4xl flex-1 px-4 py-8">
        {/* Breadcrumb */}
        <nav className="mb-6 flex items-center gap-2 font-interface text-sm text-fg-muted">
          <Link href="/documents" className="hover:text-fg-obsidian transition-colors">
            Documents
          </Link>
          <span>/</span>
          <span className="text-fg-obsidian truncate max-w-xs">
            {doc.filename}
          </span>
        </nav>

        {/* Header */}
        <div className="mb-6 flex items-start justify-between gap-4">
          <div>
            <h1 className="font-display text-2xl font-light text-fg-obsidian tracking-tight break-all">
              {doc.filename}
            </h1>
            <p className="mt-1 font-interface text-sm text-fg-muted">
              Uploaded {doc.uploaded_at ? formatDateTime(doc.uploaded_at) : "—"}
              {doc.uploaded_by ? ` by ${doc.uploaded_by}` : ""}
            </p>
          </div>
          <StatusPill status={doc.status} />
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          {/* Classification card */}
          <div className="rounded-lg border border-border-hairline bg-bg-bone p-5 shadow-sm">
            <h2 className="mb-4 font-interface text-xs font-medium uppercase tracking-widest text-fg-muted">
              Classification
            </h2>

            {doc.classification ? (
              <div className="flex flex-col gap-3">
                <div className="flex items-center justify-between">
                  <span className="font-interface text-sm text-fg-slate">
                    Document type
                  </span>
                  <ClassificationBadge docType={doc.classification.doc_type} />
                </div>

                <div className="flex items-center justify-between">
                  <span className="font-interface text-sm text-fg-slate">
                    Confidence
                  </span>
                  <span
                    className={[
                      "font-interface text-sm font-medium tabular-nums",
                      doc.classification.confidence >= 0.8
                        ? "text-data-positive"
                        : doc.classification.confidence >= 0.5
                          ? "text-[#9A7639]"
                          : "text-data-negative",
                    ].join(" ")}
                  >
                    {(doc.classification.confidence * 100).toFixed(0)}%
                  </span>
                </div>

                {doc.classification.key_indicators?.length > 0 && (
                  <div>
                    <p className="mb-2 font-interface text-xs font-medium uppercase tracking-widest text-fg-muted">
                      Key indicators
                    </p>
                    <ul className="flex flex-col gap-1">
                      {doc.classification.key_indicators.map((indicator, i) => (
                        <li
                          key={i}
                          className="flex items-start gap-2 font-interface text-sm text-fg-slate"
                        >
                          <span className="mt-0.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-fg-muted" />
                          {indicator}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ) : (
              <p className="font-interface text-sm text-fg-muted italic">
                {doc.status === "pending_classification"
                  ? "Classification in progress…"
                  : "No classification data available."}
              </p>
            )}
          </div>

          {/* Document info card */}
          <div className="rounded-lg border border-border-hairline bg-bg-bone p-5 shadow-sm">
            <h2 className="mb-4 font-interface text-xs font-medium uppercase tracking-widest text-fg-muted">
              Document info
            </h2>

            <div className="flex flex-col gap-3">
              <div className="flex items-center justify-between">
                <span className="font-interface text-sm text-fg-slate">
                  Status
                </span>
                <StatusPill status={doc.status} />
              </div>
              <div className="flex items-center justify-between">
                <span className="font-interface text-sm text-fg-slate">
                  Document ID
                </span>
                <span className="font-interface text-xs text-fg-muted tabular-nums font-mono">
                  {doc.id}
                </span>
              </div>
            </div>

            {/* Download */}
            <div className="mt-5 pt-4 border-t border-border-hairline">
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
                    d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3"
                  />
                </svg>
                Download PDF
              </a>
            </div>
          </div>
        </div>

        {/* Admin approval panel — brass signal (admin CTAs only) */}
        {canApprove && (
          <div className="mt-6">
            <ApprovalActions documentId={doc.id} />
          </div>
        )}
      </main>
    </div>
  );
}
