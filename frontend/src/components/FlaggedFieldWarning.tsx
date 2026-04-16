"use client";

/**
 * FlaggedFieldWarning — A2.1 (POR-147, bundled with A3).
 *
 * Amber warning panel shown inside AttestationModal when flaggedFieldCount > 0.
 * Uses warningSurface bg + warningText fg per spec tokens (§4, tokens.ts).
 * Figma ref: node 17:6 (Screen 06 attestation modal).
 *
 * Props:
 *   flaggedCount  — number of flagged fields (must be > 0 to render)
 *   flaggedFields — array of field name strings to render as bullet list
 *
 * When flaggedCount === 0 → caller renders the positive confidence panel instead
 * (per Figma screen 37:2 zero-flags variant). This component does NOT render
 * the zero-flags case — the conditional lives in AttestationModal.
 */

import React from "react";

export interface FlaggedFieldWarningProps {
  flaggedCount: number;
  flaggedFields: string[];
}

export function FlaggedFieldWarning({
  flaggedCount,
  flaggedFields,
}: FlaggedFieldWarningProps) {
  if (flaggedCount === 0) return null;

  return (
    <div
      role="alert"
      data-testid="flagged-field-warning"
      className="rounded-md border px-4 py-3 mb-5"
      style={{
        backgroundColor: "rgba(184,145,78,0.12)", // warningSurface
        borderColor: "rgba(184,145,78,0.30)",
      }}
    >
      {/* Header row: amber dot + copy */}
      <div className="flex items-start gap-2">
        {/* Amber dot icon */}
        <span
          aria-hidden="true"
          className="mt-0.5 flex-shrink-0 h-2 w-2 rounded-full"
          style={{ backgroundColor: "#9A7639" }} // warningText
        />
        <p
          className="font-interface text-sm font-medium"
          style={{ color: "#9A7639" }} // warningText
        >
          {flaggedCount} field{flaggedCount !== 1 ? "s" : ""} flagged during review.
          Proceed only if resolved.
        </p>
      </div>

      {/* Bullet list of flagged field names */}
      {flaggedFields.length > 0 && (
        <ul
          className="mt-2 ml-4 flex flex-col gap-0.5"
          data-testid="flagged-field-list"
        >
          {flaggedFields.map((field, i) => (
            <li
              key={i}
              className="flex items-start gap-2 font-interface text-xs"
              style={{ color: "#9A7639" }} // warningText
            >
              <span
                aria-hidden="true"
                className="mt-1 flex-shrink-0 h-1 w-1 rounded-full"
                style={{ backgroundColor: "#9A7639" }}
              />
              {field}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
