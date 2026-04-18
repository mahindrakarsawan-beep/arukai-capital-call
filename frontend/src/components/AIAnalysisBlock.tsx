/**
 * AIAnalysisBlock — POR-148 / Figma node 61:2
 *
 * Visible AI surface for the package detail page (Block 3, between
 * Extracted Facts and Review Notes). Renders the full AI analysis output
 * from the Claude Haiku classification pipeline:
 *
 *   1. Header: "AI ANALYSIS" label + model attribution (right-aligned)
 *   2. Classification reasoning paragraph
 *   3. Field-level extraction table (value, source_text, confidence per field)
 *   4. Exception callout (amber) for any field with confidence < 0.5
 *   5. Model attribution footer line
 *
 * Brass accent border: rgba(184,145,78,0.35) on left edge (spec §9.3 note:
 * this is a brass-tinted surface marker, not a signal — kept at low opacity
 * per Holden design review).
 *
 * Data source: classification.extracted_fields + classification.classification_reasoning
 * from GET /documents/{id}. If the backend hasn't shipped POR-151 yet, falls
 * back to generating reasoning from key_indicators.
 */

import React from "react";
import { ConfidenceBadge } from "@/components/ConfidenceBadge";
import type { Classification } from "@/lib/api";

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

function formatFieldName(key: string): string {
  return key
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString("en-US", {
      year: "numeric",
      month: "long",
      day: "numeric",
    });
  } catch {
    return iso;
  }
}

/**
 * Build a fallback reasoning paragraph from key_indicators when the backend
 * hasn't yet shipped classification_reasoning (POR-151).
 */
function buildFallbackReasoning(
  docType: string,
  keyIndicators: string[]
): string {
  const formatted = docType
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
  if (!keyIndicators.length) {
    return `Classified as ${formatted}.`;
  }
  const list = keyIndicators.slice(0, 3).join(", ");
  return `Classified as ${formatted} based on: ${list}.`;
}

// ─────────────────────────────────────────────────────────────────────────────
// Props
// ─────────────────────────────────────────────────────────────────────────────

export interface AIAnalysisBlockProps {
  classification: Classification;
  /** ISO timestamp of the document upload — used for the date attribution line. */
  analysedAt: string;
  /**
   * Top-level extracted_fields from PackageDetail (POR-151).
   * Takes priority over classification.extracted_fields when present.
   */
  extractedFields?: Record<string, import("@/lib/api").ExtractedField> | null;
  /**
   * Top-level classification_reasoning from PackageDetail.
   * Takes priority over classification.classification_reasoning when present.
   */
  reasoning?: string | null;
  /**
   * Top-level model_used from PackageDetail (e.g. "mistral-small-latest").
   * Falls back to classification.model_version, then "Claude Haiku".
   */
  modelUsed?: string | null;
  /**
   * Top-level classification_duration_ms from PackageDetail.
   * Takes priority over classification.duration_ms when present.
   */
  durationMs?: number | null;
}

// ─────────────────────────────────────────────────────────────────────────────
// Sub-components
// ─────────────────────────────────────────────────────────────────────────────

interface ExceptionCalloutProps {
  fieldName: string;
  confidence: number;
}

function ExceptionCallout({ fieldName, confidence }: ExceptionCalloutProps) {
  const pct = Math.round(confidence * 100);
  return (
    <div
      role="alert"
      data-testid="exception-callout"
      className="flex items-start gap-2 rounded-md px-3 py-2.5"
      style={{ backgroundColor: "rgba(184,145,78,0.10)", border: "1px solid rgba(184,145,78,0.28)" }}
    >
      <span
        className="font-interface text-xs font-semibold flex-shrink-0 mt-0.5"
        style={{ color: "#9A7639" }}
        aria-hidden="true"
      >
        !
      </span>
      <p className="font-interface text-xs" style={{ color: "#9A7639" }}>
        <strong className="font-semibold">{formatFieldName(fieldName)}</strong>{" "}
        has low confidence ({pct}%). Manual verification recommended.
      </p>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main component
// ─────────────────────────────────────────────────────────────────────────────

export function AIAnalysisBlock({
  classification,
  analysedAt,
  extractedFields: topLevelExtractedFields,
  reasoning: topLevelReasoning,
  modelUsed: topLevelModelUsed,
  durationMs: topLevelDurationMs,
}: AIAnalysisBlockProps) {
  // Defensive destructure: API may return null for optional fields on packages
  // classified before POR-151 shipped (old Haiku pipeline). Never crash on null.
  const {
    doc_type,
    confidence,
    extracted_fields: classificationExtractedFields,
    classification_reasoning: classificationReasoning,
    model_version,
    duration_ms,
  } = classification;

  // Top-level PackageDetail AI data takes priority over nested classification fields.
  const extracted_fields = topLevelExtractedFields ?? classificationExtractedFields;
  const classification_reasoning = topLevelReasoning ?? classificationReasoning;
  const model_version_or_used = topLevelModelUsed ?? model_version;
  const effective_duration_ms = topLevelDurationMs ?? duration_ms;

  // key_indicators may be null from old API responses even though the type says string[]
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const key_indicators: string[] = Array.isArray((classification as any).key_indicators)
    ? (classification as any).key_indicators
    : [];

  // Reasoning: prefer server-generated (top-level or nested), fall back to key_indicators synthesis
  const reasoning =
    classification_reasoning ??
    buildFallbackReasoning(doc_type, key_indicators);

  // Model display string
  const modelLabel = model_version_or_used ?? "Claude Haiku";

  // Duration display
  const durationLabel =
    typeof effective_duration_ms === "number"
      ? effective_duration_ms >= 1000
        ? `${(effective_duration_ms / 1000).toFixed(1)}s`
        : `${effective_duration_ms}ms`
      : null;

  const dateLabel = formatDate(analysedAt);

  // Attribution line (shared between header and footer)
  const attributionParts = [
    `Analysis by ${modelLabel}`,
    durationLabel,
    dateLabel,
  ].filter(Boolean);
  const attributionLine = attributionParts.join(" · ");

  // Build field rows — sort for deterministic order
  // Guard: extracted_fields must be a non-null object; individual fields must have numeric confidence
  const fieldEntries = extracted_fields && typeof extracted_fields === "object"
    ? Object.entries(extracted_fields)
        .filter(([, field]) => field != null && typeof field.confidence === "number")
        .sort(([a], [b]) => a.localeCompare(b))
    : [];

  // Exception fields: confidence < 0.5
  const exceptionFields = fieldEntries.filter(
    ([, field]) => typeof field.confidence === "number" && field.confidence < 0.5
  );

  // Fallback overall confidence badge value
  const overallConfidenceLabel = `${Math.round(confidence * 100)}%`;

  return (
    <div
      data-testid="ai-analysis-block"
      className="rounded-lg border border-border-hairline bg-bg-parchment p-5 shadow-sm"
      style={{
        borderLeft: "3px solid rgba(184,145,78,0.35)",
      }}
    >
      {/* ── Header ──────────────────────────────────────────────────── */}
      <div className="mb-4 flex items-center justify-between gap-4 flex-wrap">
        <h2
          className="font-interface text-xs font-medium uppercase tracking-widest"
          style={{ color: "#B8914E" }}
        >
          AI Analysis
        </h2>
        <span className="font-interface text-xs text-fg-muted text-right">
          {attributionLine}
        </span>
      </div>

      {/* ── Classification reasoning ─────────────────────────────────── */}
      <div className="mb-4">
        <p
          data-testid="classification-reasoning"
          className="font-interface text-sm text-fg-slate leading-relaxed"
        >
          {reasoning}
        </p>
      </div>

      {/* ── Field-level extraction table ─────────────────────────────── */}
      {fieldEntries.length > 0 ? (
        <div className="mb-4">
          <p className="mb-2 font-interface text-xs font-medium uppercase tracking-widest text-fg-muted">
            Extracted fields
          </p>
          <div
            className="rounded-md overflow-hidden border border-border-hairline divide-y divide-border-hairline"
            data-testid="extraction-table"
          >
            {fieldEntries.map(([key, field]) => {
              const displayValue =
                field.value === null || field.value === undefined
                  ? "—"
                  : typeof field.value === "boolean"
                  ? field.value
                    ? "Yes"
                    : "No"
                  : String(field.value);

              return (
                <div
                  key={key}
                  data-testid={`field-row-${key}`}
                  className="flex flex-col sm:flex-row sm:items-start gap-1 sm:gap-3 px-3 py-2.5 bg-bg-bone"
                >
                  {/* Field name */}
                  <span className="font-interface text-xs font-medium uppercase tracking-widest text-fg-muted flex-shrink-0 sm:w-36 pt-0.5">
                    {formatFieldName(key)}
                  </span>

                  {/* Value + source + confidence */}
                  <div className="flex-1 flex flex-col gap-0.5 min-w-0">
                    <span className="font-interface text-sm text-fg-obsidian">
                      {displayValue}
                    </span>
                    {field.source_text && (
                      <span
                        className="font-interface text-xs text-fg-muted italic truncate"
                        title={`found in: ${field.source_text}`}
                      >
                        found in &ldquo;{field.source_text}&rdquo;
                      </span>
                    )}
                  </div>

                  {/* Confidence badge */}
                  <div className="flex-shrink-0">
                    <ConfidenceBadge
                      confidence={field.confidence}
                      value={`${Math.round(field.confidence * 100)}%`}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      ) : (
        /* No extracted_fields yet — show overall confidence row */
        <div className="mb-4 flex items-center justify-between border-b border-border-hairline pb-2">
          <span className="font-interface text-xs font-medium uppercase tracking-widest text-fg-muted">
            Overall confidence
          </span>
          <ConfidenceBadge
            confidence={confidence}
            value={overallConfidenceLabel}
          />
        </div>
      )}

      {/* ── Exception callouts ───────────────────────────────────────── */}
      {exceptionFields.length > 0 && (
        <div className="mb-4 flex flex-col gap-2" data-testid="exception-callouts">
          {exceptionFields.map(([key, field]) => (
            <ExceptionCallout
              key={key}
              fieldName={key}
              confidence={field.confidence}
            />
          ))}
        </div>
      )}

      {/* ── Model attribution footer — quiet, not prominent ────────────── */}
      <div className="pt-2 border-t border-border-hairline">
        <p
          data-testid="model-attribution"
          className="font-interface text-[10px] text-fg-muted opacity-70"
        >
          {attributionLine}
        </p>
      </div>
    </div>
  );
}
