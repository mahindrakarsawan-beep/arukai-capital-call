import React from "react";
import Link from "next/link";
import type { DocumentSummary } from "@/lib/api";
import { ClassificationBadge } from "./ClassificationBadge";
import { StatusPill } from "./StatusPill";
import { formatDate } from "@/lib/format";

interface DocumentCardProps {
  document: DocumentSummary;
}

/**
 * Table row component for a document in the document list.
 */
export function DocumentCard({ document: doc }: DocumentCardProps) {
  // Defensive normalizer — guard against missing fields
  const id = doc?.id ?? "";
  const filename = doc?.filename ?? "—";
  const uploadedAt = doc?.uploaded_at ? formatDate(doc.uploaded_at) : "—";

  return (
    <tr className="border-b border-border-hairline hover:bg-bg-parchment transition-colors duration-fast">
      <td className="px-4 py-3 font-interface text-sm text-fg-obsidian font-medium">
        <Link
          href={`/documents/${id}`}
          className="hover:underline underline-offset-2 decoration-fg-muted"
        >
          {filename}
        </Link>
      </td>
      <td className="px-4 py-3">
        <ClassificationBadge docType={doc?.doc_type ?? null} />
      </td>
      <td className="px-4 py-3 font-interface text-sm text-fg-slate tabular-nums">
        {uploadedAt}
      </td>
      <td className="px-4 py-3">
        <StatusPill status={doc?.status ?? null} confidence={doc?.confidence ?? null} />
      </td>
      <td className="px-4 py-3">
        <Link
          href={`/documents/${id}`}
          className="font-interface text-sm text-fg-slate hover:text-fg-obsidian transition-colors duration-fast"
          aria-label={`View details for ${filename}`}
        >
          View →
        </Link>
      </td>
    </tr>
  );
}
