import React from "react";
import type { DocType } from "@/lib/api";

interface ClassificationBadgeProps {
  docType: DocType | null;
}

const DOC_TYPE_LABELS: Record<DocType, string> = {
  capital_call_notice: "Capital Call",
  subscription_agreement: "Subscription Agmt",
  side_letter: "Side Letter",
  k1: "K-1",
  wire_instructions: "Wire Instructions",
  other: "Other",
};

const DOC_TYPE_CLASSES: Record<DocType, string> = {
  capital_call_notice:
    "bg-[rgba(31,122,77,0.12)] text-data-positive border border-[rgba(31,122,77,0.20)]",
  subscription_agreement:
    "bg-[rgba(60,72,88,0.10)] text-fg-slate border border-[rgba(60,72,88,0.16)]",
  side_letter:
    "bg-[rgba(60,72,88,0.10)] text-fg-slate border border-[rgba(60,72,88,0.16)]",
  k1: "bg-[rgba(60,72,88,0.10)] text-fg-slate border border-[rgba(60,72,88,0.16)]",
  wire_instructions:
    "bg-[rgba(178,58,46,0.12)] text-data-negative border border-[rgba(178,58,46,0.20)]",
  other:
    "bg-[rgba(140,149,163,0.15)] text-fg-muted border border-[rgba(140,149,163,0.20)]",
};

/**
 * Colored badge for document classification type.
 * Capital call = green; wire instructions = red (high-risk signal); others = slate.
 */
export function ClassificationBadge({ docType }: ClassificationBadgeProps) {
  // Defensive: handle null/undefined gracefully
  if (!docType) {
    return (
      <span className="inline-flex items-center rounded-full px-2.5 py-0.5 font-interface text-xs font-medium bg-[rgba(140,149,163,0.15)] text-fg-muted border border-[rgba(140,149,163,0.20)]">
        Unclassified
      </span>
    );
  }

  const label = DOC_TYPE_LABELS[docType] ?? docType;
  const classes = DOC_TYPE_CLASSES[docType] ?? DOC_TYPE_CLASSES.other;

  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 font-interface text-xs font-medium ${classes}`}
    >
      {label}
    </span>
  );
}
