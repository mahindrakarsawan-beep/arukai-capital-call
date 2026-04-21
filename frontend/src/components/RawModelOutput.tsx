"use client";

/**
 * RawModelOutput — POR-158 A2 (Mistral client-persona follow-up).
 *
 * Collapsible "Show raw model output" panel. Renders the raw classifier
 * payload as canonicalized JSON (sorted keys, 2-space indent) so a skeptical
 * reviewer can verify the plain-English analysis against the model's actual
 * output without digging into the network tab.
 *
 * Intentionally tiny + dependency-free. Styled quietly; the button sits
 * adjacent to the prose analysis and the expanded <pre> is readable mono.
 */
import React, { useState } from "react";

interface RawModelOutputProps {
  payload: unknown;
}

function canonicalJson(value: unknown): string {
  // Recursively sort object keys for a byte-stable render. Non-objects pass
  // through. Arrays preserve order (meaningful); only plain objects are
  // key-sorted. We don't try to handle Map/Set/Date — classifier payloads
  // are pure JSON.
  const sortKeys = (v: unknown): unknown => {
    if (Array.isArray(v)) return v.map(sortKeys);
    if (v !== null && typeof v === "object") {
      return Object.keys(v as Record<string, unknown>)
        .sort()
        .reduce<Record<string, unknown>>((acc, k) => {
          acc[k] = sortKeys((v as Record<string, unknown>)[k]);
          return acc;
        }, {});
    }
    return v;
  };
  return JSON.stringify(sortKeys(value), null, 2);
}

export function RawModelOutput({ payload }: RawModelOutputProps) {
  const [open, setOpen] = useState(false);
  const label = open ? "Hide raw model output" : "Show raw model output";

  return (
    <div className="mt-3">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="font-interface text-xs font-medium underline underline-offset-2 text-fg-muted hover:text-fg-obsidian"
      >
        {label}
      </button>
      {open && (
        <pre
          data-testid="raw-model-json"
          className="mt-2 overflow-x-auto rounded-md bg-bg-bone p-3 font-mono text-[11px] leading-snug text-fg-slate"
        >
          {canonicalJson(payload)}
        </pre>
      )}
    </div>
  );
}
