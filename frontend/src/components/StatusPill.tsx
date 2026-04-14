import React from "react";
import type { DocumentStatus } from "@/lib/api";

interface StatusPillProps {
  status: DocumentStatus | null;
}

const STATUS_LABELS: Record<DocumentStatus, string> = {
  pending_classification: "Classifying",
  pending_review: "Pending Review",
  approved: "Approved",
  rejected: "Rejected",
};

const STATUS_CLASSES: Record<DocumentStatus, string> = {
  pending_classification:
    "bg-[rgba(184,145,78,0.12)] text-[#9A7639] border border-[rgba(184,145,78,0.20)]",
  pending_review:
    "bg-[rgba(184,145,78,0.12)] text-[#9A7639] border border-[rgba(184,145,78,0.20)]",
  approved:
    "bg-[rgba(31,122,77,0.12)] text-data-positive border border-[rgba(31,122,77,0.20)]",
  rejected:
    "bg-[rgba(178,58,46,0.12)] text-data-negative border border-[rgba(178,58,46,0.20)]",
};

/**
 * Status pill: pending/approved/rejected states with tonal color coding.
 */
export function StatusPill({ status }: StatusPillProps) {
  // Defensive normalizer
  if (!status) {
    return (
      <span className="inline-flex items-center rounded-full px-2.5 py-0.5 font-interface text-xs font-medium bg-[rgba(140,149,163,0.15)] text-fg-muted">
        Unknown
      </span>
    );
  }

  const label = STATUS_LABELS[status] ?? status;
  const classes = STATUS_CLASSES[status] ?? STATUS_CLASSES.pending_review;

  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 font-interface text-xs font-medium ${classes}`}
    >
      {label}
    </span>
  );
}
