/**
 * Documents list page — /documents
 * Server component: fetches /documents using JWT from cookie.
 * Table: filename | doc_type | uploaded_at | status | actions
 */

import React from "react";
import Link from "next/link";
import { redirect } from "next/navigation";
import { getToken } from "@/lib/auth";
import { getMe, listDocuments } from "@/lib/api";
import { DocumentCard } from "@/components/DocumentCard";
import { TopNav } from "@/components/TopNav";
import { StaleBanner } from "@/components/StaleBanner";
import { Button } from "@/components/Button";
import type { DocumentSummary, User } from "@/lib/api";

export default async function DocumentsPage() {
  const token = await getToken();

  // Redirect to login if no token
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
      err instanceof Error ? err.message : "Failed to load documents.";
  }

  return (
    <div className="flex min-h-screen flex-col">
      <TopNav user={user} />

      {fetchError && <StaleBanner message={fetchError} />}

      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">
        {/* Header row */}
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="font-display text-2xl font-light text-fg-obsidian tracking-tight">
              Documents
            </h1>
            <p className="mt-0.5 font-interface text-sm text-fg-muted">
              {documents.length > 0
                ? `${documents.length} document${documents.length !== 1 ? "s" : ""}`
                : "No documents yet"}
            </p>
          </div>
          <Link href="/documents/upload">
            <Button variant="primary">Upload new</Button>
          </Link>
        </div>

        {/* Table */}
        {documents.length === 0 && !fetchError ? (
          <div className="rounded-lg border border-border-hairline bg-bg-parchment px-8 py-12 text-center">
            <p className="font-interface text-sm text-fg-muted">
              No documents have been uploaded yet.
            </p>
            <Link href="/documents/upload" className="mt-3 inline-block">
              <Button variant="secondary">Upload your first document</Button>
            </Link>
          </div>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-border-hairline">
            <table className="w-full border-collapse bg-bg-bone">
              <thead>
                <tr className="border-b border-border-hairline">
                  {["Filename", "Type", "Uploaded", "Status", ""].map(
                    (col) => (
                      <th
                        key={col}
                        className="px-4 py-3 text-left font-interface text-xs font-medium uppercase tracking-widest text-fg-muted"
                      >
                        {col}
                      </th>
                    )
                  )}
                </tr>
              </thead>
              <tbody>
                {documents.map((doc) => (
                  <DocumentCard key={doc.id} document={doc} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </main>
    </div>
  );
}
