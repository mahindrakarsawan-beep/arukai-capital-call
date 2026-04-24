"use client";
/**
 * AIAnalysisBlock — POR-148 / Figma node 61:2
 *
 * Visible AI surface for the package detail page (Block 3, between
 * Extracted Facts and Review Notes). Renders the full AI analysis output
 * from the Claude Haiku classification pipeline:
 *
 *   1. Header: "AI ANALYSIS" label + model attribution (right-aligned)
 *      POR-160 Change 1: attribution lifted from text-xs/muted to
 *      text-sm/medium obsidian so the model+duration ceremony is readable
 *      without leaning in. Client-persona review flagged the previous
 *      styling as "quiet to the point of absent".
 *   2. Classification reasoning paragraph
 *   3. Field-level extraction table (value, source_text, confidence per field)
 *   4. Exception callout (amber) for any field with confidence < 0.80 —
 *      POR-160 Change 2 adds an inline "Request human review" button
 *      that POSTs /packages/{id}/flag-field and writes an audit event.
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

import React, { useState } from "react";
import { ConfidenceBadge } from "@/components/ConfidenceBadge";
import { flagFieldForReview } from "@/lib/api";
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
 * POR-161 #2: format an extracted-field value for display in the extraction
 * table. Picks a formatter based on field key: currency keys get $12,500,000
 * with thousands separators; date keys get "May 15, 2026". Unknown keys pass
 * through as string. Preserves raw value in the API response for downstream
 * consumers — this is a presentation-layer concern.
 */
const CURRENCY_FIELD_KEYS = new Set([
  "amount_due",
  "call_amount",
  "commitment",
  "total_commitment",
  "remaining_commitment",
]);

const DATE_FIELD_KEYS = new Set([
  "due_date",
  "notice_date",
  "effective_date",
  "as_of_date",
]);

function formatFieldValue(key: string, raw: string | number | boolean | null | undefined): string {
  if (raw === null || raw === undefined) return "—";
  if (typeof raw === "boolean") return raw ? "Yes" : "No";

  if (CURRENCY_FIELD_KEYS.has(key)) {
    // Accept either numeric or numeric-looking string inputs; strip symbols/commas
    const str = String(raw).replace(/[$,€£\s]/g, "").trim();
    const n = Number(str);
    if (Number.isFinite(n)) {
      return new Intl.NumberFormat("en-US", {
        style: "currency",
        currency: "USD",
        maximumFractionDigits: 0,
      }).format(n);
    }
    return String(raw);
  }

  if (DATE_FIELD_KEYS.has(key)) {
    const d = new Date(String(raw));
    if (!Number.isNaN(d.getTime())) {
      return d.toLocaleDateString("en-US", {
        year: "numeric",
        month: "long",
        day: "numeric",
      });
    }
    return String(raw);
  }

  return String(raw);
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
  /**
   * POR-160: package id + auth token threaded through for the
   * "Request human review" action on ExceptionCallout. If either is
   * missing (e.g. preview / storybook mode), the button is hidden.
   */
  packageId?: string | null;
  token?: string | null;
}

// ─────────────────────────────────────────────────────────────────────────────
// Sub-components
// ─────────────────────────────────────────────────────────────────────────────

interface ExceptionCalloutProps {
  fieldName: string;
  confidence: number;
  /** POR-160: when both packageId + token are present, the "Request human
   *  review" button is rendered and calls POST /packages/{id}/flag-field. */
  packageId?: string | null;
  token?: string | null;
}

type RequestState = "idle" | "pending" | "requested" | "error";

function ExceptionCallout({
  fieldName,
  confidence,
  packageId,
  token,
}: ExceptionCalloutProps) {
  const pct = Math.round(confidence * 100);
  const canRequest = Boolean(packageId && token);
  const [status, setStatus] = useState<RequestState>("idle");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleRequest = async () => {
    if (!packageId || !token) return;
    // Allow firing from idle or error (retry); block while pending or already requested.
    if (status !== "idle" && status !== "error") return;
    setStatus("pending");
    setErrorMsg(null);
    try {
      await flagFieldForReview(packageId, fieldName, token, {
        fieldConfidence: confidence,
      });
      setStatus("requested");
    } catch (err) {
      setStatus("error");
      setErrorMsg(
        err instanceof Error ? err.message : "Failed to request review"
      );
    }
  };

  let buttonLabel = "Request human review";
  if (status === "pending") buttonLabel = "Requesting…";
  else if (status === "requested") buttonLabel = "Review requested";
  else if (status === "error") buttonLabel = "Retry request";

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
      <div className="flex flex-1 flex-col gap-1.5">
        <p className="font-interface text-xs" style={{ color: "#9A7639" }}>
          <strong className="font-semibold">{formatFieldName(fieldName)}</strong>{" "}
          has low confidence ({pct}%). Manual verification recommended.
        </p>
        {canRequest && (
          <div className="flex items-center gap-2">
            <button
              type="button"
              data-testid={`flag-field-button-${fieldName}`}
              onClick={handleRequest}
              disabled={status !== "idle" && status !== "error"}
              aria-label={`Request human review for ${formatFieldName(fieldName)}`}
              aria-pressed={status === "requested"}
              className="font-interface text-xs font-medium underline-offset-2 transition-colors disabled:cursor-not-allowed disabled:opacity-70"
              style={{
                color: status === "requested" ? "#6B5530" : "#9A7639",
                textDecoration: status === "idle" || status === "error" ? "underline" : "none",
              }}
            >
              {buttonLabel}
            </button>
            {status === "error" && errorMsg && (
              <span
                data-testid={`flag-field-error-${fieldName}`}
                className="font-interface text-[10px]"
                style={{ color: "#9A7639" }}
              >
                {errorMsg}
              </span>
            )}
          </div>
        )}
      </div>
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
  packageId,
  token,
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

  // Model display string. Default reflects current production primary (Sprint 3 swap:
  // Mistral Small replaced Claude Haiku). "Claude Haiku" fallback would mislead clients
  // about data residency when model_version is null.
  const modelLabel = model_version_or_used ?? "Mistral Small";

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

  // Exception fields: confidence < 0.80 (POR-159 19d.3, matches backend _build_ai_summary threshold)
  const exceptionFields = fieldEntries.filter(
    ([, field]) => typeof field.confidence === "number" && field.confidence < 0.80
  );

  // Fallback overall confidence badge value
  const overallConfidenceLabel = `${Math.round(confidence * 100)}%`;

  return (
    <div
      data-testid="ai-analysis-block"
      className="rounded-lg border border-border-hairline bg-bg-parchment p-6 lg:p-8 shadow-sm"
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
        <span
          data-testid="model-attribution-header"
          className="font-interface text-sm font-medium text-fg-obsidian text-right"
        >
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
              // POR-161 #2: currency + date formatters based on field key.
              // Raw API value preserved server-side; presentation applied here.
              const displayValue = formatFieldValue(key, field.value);

              return (
                <div
                  key={key}
                  data-testid={`field-row-${key}`}
                  className="flex flex-col sm:flex-row sm:items-start gap-1 sm:gap-3 px-4 py-3 bg-bg-bone"
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
              packageId={packageId}
              token={token}
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
