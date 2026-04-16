import React from "react";

interface ConfidenceBadgeProps {
  confidence: number | null | undefined;
  value?: string | React.ReactNode;
}

/**
 * ConfidenceBadge — renders a value with confidence treatment per spec §4.
 *
 * Bands:
 *  ≥ 0.90  High       — value only, no marker
 *  0.70–0.89 Confident — hairline right-side marker, hover tooltip
 *  0.50–0.69 Needs review — amber "Needs review" pill
 *  < 0.50  Low confidence — dashed border box + "Low confidence — flag" pill
 *  null/undefined — amber "Missing" pill
 */
export function ConfidenceBadge({ confidence, value }: ConfidenceBadgeProps) {
  // Missing field
  if (confidence === null || confidence === undefined) {
    return (
      <span
        className="inline-flex items-center gap-1.5"
        aria-label={`${value ?? "—"}, missing field`}
      >
        <span className="font-interface text-sm text-fg-slate">—</span>
        <span className="inline-flex items-center rounded px-1.5 py-0.5 font-interface text-[10px] font-medium uppercase tracking-wider bg-[rgba(184,145,78,0.12)] text-[#9A7639]">
          Missing
        </span>
      </span>
    );
  }

  // High confidence ≥ 0.90
  if (confidence >= 0.9) {
    return (
      <span
        className="font-interface text-sm text-fg-obsidian"
        aria-label={value ? String(value) : `${(confidence * 100).toFixed(0)}% confidence`}
      >
        {value ?? `${(confidence * 100).toFixed(0)}%`}
      </span>
    );
  }

  // Confident 0.70–0.89
  if (confidence >= 0.7) {
    return (
      <span
        className="inline-flex items-center gap-1"
        title={`Extracted with high confidence (${(confidence * 100).toFixed(0)}%)`}
        aria-label={`${value ?? ""}, extracted with high confidence`}
      >
        <span className="font-interface text-sm text-fg-obsidian">
          {value ?? `${(confidence * 100).toFixed(0)}%`}
        </span>
        {/* Hairline right-side marker per spec */}
        <span
          className="inline-block w-0.5 h-4 self-center rounded-full bg-border-hairline-strong"
          aria-hidden="true"
        />
      </span>
    );
  }

  // Needs review 0.50–0.69
  if (confidence >= 0.5) {
    return (
      <span
        className="inline-flex items-center gap-1.5"
        aria-label={`${value ?? ""}, needs reviewer attention`}
      >
        <span className="font-interface text-sm text-fg-obsidian">
          {value ?? `${(confidence * 100).toFixed(0)}%`}
        </span>
        <span className="inline-flex items-center rounded px-1.5 py-0.5 font-interface text-[10px] font-medium uppercase tracking-wider bg-[rgba(184,145,78,0.12)] text-[#9A7639]">
          Needs review
        </span>
      </span>
    );
  }

  // Low confidence < 0.50
  return (
    <span
      className="inline-flex items-center gap-1.5"
      aria-label={`${value ?? ""}, low confidence, flagged for manual verification`}
    >
      <span className="font-interface text-sm text-fg-obsidian border border-dashed border-[#9A7639] px-1.5 py-0.5 rounded">
        {value ?? `${(confidence * 100).toFixed(0)}%`}
      </span>
      <span className="inline-flex items-center rounded px-1.5 py-0.5 font-interface text-[10px] font-medium uppercase tracking-wider bg-[rgba(184,145,78,0.12)] text-[#9A7639]">
        Low confidence — flag
      </span>
    </span>
  );
}
