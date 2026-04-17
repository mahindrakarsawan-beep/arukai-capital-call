"use client";

/**
 * ZeroFlagsPanel — A2.2 (POR-147 / ARU-17-A2)
 * Figma node 37:2.
 *
 * Shown inside AttestationModal when ALL extracted fields have confidence ≥0.9
 * (flaggedFieldCount === 0). Replaces FlaggedFieldWarning with a positive,
 * green-surface panel.
 *
 * Green surface: dataPositiveMuted = rgba(31,122,77,0.12)
 * Green text: dataPositive = #1F7A4D
 *
 * Brass MUST NOT appear here — positive/green semantic role only.
 */

import React from "react";

export function ZeroFlagsPanel() {
  return (
    <div
      role="status"
      data-testid="zero-flags-panel"
      className="rounded-md border px-4 py-3 mb-5 flex items-start gap-2"
      style={{
        backgroundColor: "rgba(31,122,77,0.12)", // dataPositiveMuted
        borderColor: "rgba(31,122,77,0.25)",
      }}
    >
      {/* Green dot */}
      <span
        aria-hidden="true"
        className="mt-0.5 flex-shrink-0 h-2 w-2 rounded-full"
        style={{ backgroundColor: "#1F7A4D" }} // dataPositive
      />
      <p
        className="font-interface text-sm font-medium"
        style={{ color: "#1F7A4D" }} // dataPositive
      >
        All extracted fields at high confidence. No items flagged for review.
      </p>
    </div>
  );
}
