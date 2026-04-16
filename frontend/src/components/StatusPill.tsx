import React from "react";
import type { DocumentStatus } from "@/lib/api";
import { resolvePackageState } from "@/lib/state";

interface StatusPillProps {
  status: DocumentStatus | null;
  confidence?: number | null;
  approver?: string | null;
  decisionDate?: string | null;
}

const TONE_CLASSES: Record<string, string> = {
  neutral:
    "bg-[rgba(60,72,88,0.10)] text-fg-slate border border-[rgba(60,72,88,0.16)]",
  // Brass — ONLY routed_for_approval (spec §9.3)
  brass:
    "bg-[rgba(184,145,78,0.12)] text-[#B8914E] border border-[rgba(184,145,78,0.30)]",
  positive:
    "bg-[rgba(31,122,77,0.12)] text-data-positive border border-[rgba(31,122,77,0.20)]",
  negative:
    "bg-[rgba(178,58,46,0.12)] text-data-negative border border-[rgba(178,58,46,0.20)]",
  amber:
    "bg-[rgba(184,145,78,0.12)] text-[#9A7639] border border-[rgba(184,145,78,0.20)]",
};

/**
 * StatusPill — v0.2 state labels per spec §1.4.
 * Brass tone ONLY for routed_for_approval (mapped from pending_review + classification).
 * Amber for exception_surfaced. Positive/negative for decisions.
 *
 * Phase A: maps v0.1 backend statuses through the state façade.
 */
export function StatusPill({
  status,
  confidence,
  approver,
  decisionDate,
}: StatusPillProps) {
  if (!status) {
    return (
      <span className="inline-flex items-center rounded-full px-2.5 py-0.5 font-interface text-xs font-medium bg-[rgba(140,149,163,0.15)] text-fg-muted">
        Unknown
      </span>
    );
  }

  const stateInfo = resolvePackageState(status, confidence, approver, decisionDate);
  const classes = TONE_CLASSES[stateInfo.pillTone] ?? TONE_CLASSES.neutral;

  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 font-interface text-xs font-medium ${classes}`}
    >
      {stateInfo.pillLabel}
    </span>
  );
}
