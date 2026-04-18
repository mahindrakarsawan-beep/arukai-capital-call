/**
 * PackageRow — extracted from documents/page.tsx for reuse across console sections.
 *
 * Variants (per Figma node 34:2 unclaimed, 34:16 claimed-by-you):
 *   - Unclaimed: "Claim to review" CTA button shown
 *   - Claimed by you: "Release claim" CTA button shown
 *   - Claimed by other / no claim state: no CTA
 *
 * Responsive:
 *   - Mobile (<768px): stacked card layout (flex-col)
 *   - Tablet (768–1279px): 2-line collapse (title+classification row, then status+time row)
 *   - Desktop (1280px+): single row with full column set
 */

import React from "react";
import Link from "next/link";
import { StatusPill } from "@/components/StatusPill";
import { NextOwnerChip } from "@/components/NextOwnerChip";
import { ClassificationBadge } from "@/components/ClassificationBadge";
import { ConfidenceBadge } from "@/components/ConfidenceBadge";
import { resolvePackageState } from "@/lib/state";
import { formatRelative } from "@/lib/format";
import type { DocType, DocumentStatus } from "@/lib/api";
import type { ClaimState } from "@/lib/state";

/**
 * Converts a snake_case doc_type string to readable title case.
 * e.g. "capital_call_notice" → "Capital Call Notice"
 */
export function formatDocType(docType: string): string {
  return docType
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

export interface PackageRowPkg {
  id: string;
  /** Display title (e.g. fund name or pkg.title from API). */
  title: string;
  /** Subtitle — typically the raw filename, shown in fgMuted below title. */
  subtitle?: string | null;
  state: DocumentStatus | string;
  confidence?: number | null;
  docType?: DocType | null;
  nextOwner?: string | null;
  lastMovement?: string | null;
  claimStatus?: ClaimState | null;
  approver?: string | null;
  decisionDate?: string | null;
}

interface PackageRowProps {
  pkg: PackageRowPkg;
  /** Called when user clicks "Claim to review" or "Release claim" */
  onClaimToggle?: (id: string, action: "claim" | "release") => void;
}

/**
 * PackageRow — a single package entry in a console section list.
 *
 * Desktop: one row, title | classification | state pill + next-owner | timestamp
 * Tablet (md): title + classification stack on line 1; state + time on line 2
 * Mobile (sm and below): card layout with all fields stacked
 */
export function PackageRow({ pkg, onClaimToggle }: PackageRowProps) {
  const stateInfo = resolvePackageState(
    pkg.state,
    pkg.confidence,
    pkg.approver,
    pkg.decisionDate,
    pkg.nextOwner,
    pkg.claimStatus
  );

  const showClaimCTA =
    stateInfo.claimState === "unclaimed" || stateInfo.claimState === "claimed_by_you";

  const claimLabel =
    stateInfo.claimState === "unclaimed" ? "Claim to review" : "Release claim";
  const claimAction: "claim" | "release" =
    stateInfo.claimState === "unclaimed" ? "claim" : "release";

  const relativeTime = pkg.lastMovement ? formatRelative(pkg.lastMovement) : "—";

  return (
    /* Mobile: card (flex-col), Tablet+: row (flex-row) */
    <div className="group relative border-b border-border-hairline last:border-0">
      {/* Row link covers the whole cell — CTA buttons intercept clicks via stopPropagation */}
      <Link
        href={`/documents/${pkg.id}`}
        className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4 px-4 py-3 hover:bg-bg-parchment transition-colors duration-fast focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-fg-slate"
        aria-label={`Open package ${pkg.title}`}
      >
        {/* Identity column: doc type title + classification badge + subtitle — stacks on mobile */}
        <span className="flex flex-col gap-0.5 flex-1 min-w-0">
          {/* Title line: formatted doc type (or raw title) + classification badge + confidence inline */}
          <span className="flex flex-row items-center gap-2 min-w-0">
            <span className="font-display text-base font-normal text-fg-obsidian truncate leading-snug">
              {pkg.docType ? formatDocType(pkg.docType) : pkg.title}
            </span>
            {pkg.docType && (
              <span className="flex-shrink-0">
                <ClassificationBadge docType={pkg.docType} />
              </span>
            )}
            {typeof pkg.confidence === "number" && pkg.confidence > 0 && (
              <span className="flex-shrink-0">
                <ConfidenceBadge confidence={pkg.confidence} value={`${(pkg.confidence * 100).toFixed(0)}%`} />
              </span>
            )}
          </span>
          {/* Subtitle: raw filename in muted tone */}
          {pkg.subtitle && (
            <span className="font-interface text-xs text-fg-muted truncate">
              {pkg.subtitle}
            </span>
          )}
          {/* Received timestamp */}
          {pkg.lastMovement && (
            <span className="font-interface text-xs text-fg-muted">
              Received {formatRelative(pkg.lastMovement)}
            </span>
          )}
        </span>

        {/* Status + next-owner + timestamp — collapse to line 2 on tablet */}
        <span className="flex items-center gap-2 flex-shrink-0 flex-wrap">
          <StatusPill
            status={pkg.state as DocumentStatus}
            confidence={pkg.confidence}
            approver={pkg.approver}
            decisionDate={pkg.decisionDate}
          />
          <NextOwnerChip stateInfo={stateInfo} />
        </span>
      </Link>

      {/* Claim CTA — floats to right edge, only when relevant */}
      {showClaimCTA && onClaimToggle && (
        <div className="absolute right-4 top-1/2 -translate-y-1/2">
          <button
            type="button"
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              onClaimToggle(pkg.id, claimAction);
            }}
            className="font-interface text-xs font-semibold text-fg-slate border border-border-hairline rounded px-2.5 py-1 bg-bg-bone hover:bg-bg-parchment hover:text-fg-obsidian transition-colors duration-fast focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-fg-slate"
            aria-label={`${claimLabel} for package ${pkg.title}`}
          >
            {claimLabel}
          </button>
        </div>
      )}
    </div>
  );
}
