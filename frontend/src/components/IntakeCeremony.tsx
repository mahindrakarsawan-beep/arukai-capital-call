"use client";

/**
 * IntakeCeremony — 4-step private intake overlay (C1, POR-147 / ARU-17-C1)
 * Updated POR-150: real AI narration data replaces cosmetic labels.
 *
 * Steps now display real output from the classification pipeline:
 *   01 Receive:  "Document received · [filesize] · [mime_type]"
 *   02 Classify: "Classified as [doc_type] · confidence [X]%"
 *              → "Classifying..." until classification arrives
 *   03 Extract:  "[N] of [M] fields extracted · [flagged] flagged"
 *   04 Ready:    "Package ready for review · awaiting [next_owner]"
 *
 * When stepData is not provided, falls back to the original cosmetic labels
 * so existing callers without classification data still work correctly.
 *
 * Animation rules (per animation memory):
 *   - withTiming only — CSS transition: opacity 200ms ease-out
 *   - No springs in intake context
 *   - Reduced-motion: prefers-reduced-motion media query collapses to instant
 *
 * Brass discipline (spec §9.3): brass appears ONLY on the active step here.
 */

import React from "react";

// ─────────────────────────────────────────────────────────────────────────────
// Step data shape — real AI output per step (POR-150)
// ─────────────────────────────────────────────────────────────────────────────

export interface IntakeStepData {
  /** Step 1: file receive metadata */
  receive?: {
    /** Human-readable file size, e.g. "1.4 MB" */
    filesize?: string | null;
    /** MIME type, e.g. "application/pdf" */
    mimeType?: string | null;
  } | null;
  /** Step 2: classification result */
  classify?: {
    /** Formatted doc type, e.g. "Capital Call Notice" */
    docType?: string | null;
    /** Confidence 0–1 */
    confidence?: number | null;
    /** True while classification is still in progress (async) */
    pending?: boolean;
  } | null;
  /** Step 3: extraction result */
  extract?: {
    /** Total number of extracted fields */
    totalFields?: number | null;
    /** Number of fields attempted (denominator for "N of M") */
    maxFields?: number | null;
    /** Number of low-confidence / flagged fields */
    flaggedCount?: number | null;
  } | null;
  /** Step 4: ready handoff */
  ready?: {
    /** Next owner e.g. "reviewer" or a specific email */
    nextOwner?: string | null;
  } | null;
}

// ─────────────────────────────────────────────────────────────────────────────
// Helpers — build label strings from step data
// ─────────────────────────────────────────────────────────────────────────────

function buildReceiveLabel(data?: IntakeStepData["receive"]): string {
  if (!data) return "Package received";
  const parts: string[] = ["Document received"];
  if (data.filesize) parts.push(data.filesize);
  if (data.mimeType) parts.push(data.mimeType);
  return parts.join(" · ");
}

function buildClassifyLabel(data?: IntakeStepData["classify"]): string {
  if (!data) return "Classifying materials";
  if (data.pending) return "Classifying…";
  const parts: string[] = [];
  if (data.docType) parts.push(`Classified as ${data.docType}`);
  if (typeof data.confidence === "number" && data.confidence > 0) {
    parts.push(`confidence ${Math.round(data.confidence * 100)}%`);
  }
  return parts.length > 0 ? parts.join(" · ") : "Classifying materials";
}

function buildExtractLabel(data?: IntakeStepData["extract"]): string {
  if (!data) return "Extracting key fields";
  const total = data.totalFields ?? 0;
  const max = data.maxFields ?? total;
  const flagged = data.flaggedCount ?? 0;
  const extractedPart = max > 0 ? `${total} of ${max} fields extracted` : `${total} fields extracted`;
  const flaggedPart = flagged > 0 ? `${flagged} flagged` : "0 flagged";
  return `${extractedPart} · ${flaggedPart}`;
}

function buildReadyLabel(data?: IntakeStepData["ready"]): string {
  if (!data) return "Intake complete";
  const owner = data.nextOwner ?? "reviewer";
  return `Package ready for review · awaiting ${owner}`;
}

// ─────────────────────────────────────────────────────────────────────────────
// Internal step shape
// ─────────────────────────────────────────────────────────────────────────────

interface Step {
  index: number;
  number: string;
  label: string;
}

const TOTAL_STEPS = 4;

function safeActiveStep(v: unknown): number {
  if (typeof v !== "number" || !Number.isFinite(v)) return 1;
  if (v < 1 || v > TOTAL_STEPS) return 1;
  return Math.round(v);
}

// ─────────────────────────────────────────────────────────────────────────────
// Props
// ─────────────────────────────────────────────────────────────────────────────

export interface IntakeCeremonyProps {
  /** When false, overlay is unmounted entirely. */
  visible: boolean;
  /** 1-based index of the currently illuminated step (1–4). */
  activeStep: number;
  /** From useReducedMotion() — collapses all CSS transitions to instant. */
  reducedMotion: boolean;
  /**
   * Real AI output data for each step label (POR-150).
   * When omitted, falls back to original cosmetic labels for backward compat.
   */
  stepData?: IntakeStepData;
}

// ─────────────────────────────────────────────────────────────────────────────
// StepRow inner component
// ─────────────────────────────────────────────────────────────────────────────

interface StepRowProps extends Step {
  isActive: boolean;
  isCompleted: boolean;
  reducedMotion: boolean;
}

function StepRow({
  index,
  number,
  label,
  isActive,
  isCompleted,
  reducedMotion,
}: StepRowProps) {
  const opacity = isActive || isCompleted ? 1 : 0.28;
  const transitionStyle = reducedMotion
    ? {}
    : { transition: "opacity 200ms ease-out" };

  return (
    <div
      data-step-row
      data-active={isActive ? "true" : "false"}
      aria-current={isActive ? "step" : undefined}
      style={{
        display: "flex",
        alignItems: "baseline",
        gap: "8px",
        opacity,
        ...transitionStyle,
      }}
    >
      {/* Number: brass when active, muted otherwise */}
      <span
        data-step-number
        style={{
          fontFamily: "'DM Sans', system-ui, sans-serif",
          fontSize: "11px",
          fontWeight: 500,
          lineHeight: "14px",
          letterSpacing: "0.44px",
          textTransform: "uppercase",
          color: isActive ? "#B8914E" : "#8C95A3",
        }}
      >
        {number}
      </span>

      {/* Label: Cormorant 20pt, brass when active, muted when future */}
      <span
        data-testid={`step-label-${index}`}
        style={{
          fontFamily: "'Cormorant Garamond', Georgia, serif",
          fontSize: "20px",
          fontWeight: isActive ? 400 : 300,
          lineHeight: "26px",
          color: isActive ? "#B8914E" : "#8C95A3",
        }}
      >
        {label}
      </span>

      {/* Checkmark for completed steps */}
      {isCompleted && (
        <span
          data-checkmark
          aria-label="complete"
          style={{
            color: "#8C95A3",
            fontSize: "12px",
            marginLeft: "4px",
          }}
        >
          ✓
        </span>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main component
// ─────────────────────────────────────────────────────────────────────────────

export function IntakeCeremony({
  visible,
  activeStep,
  reducedMotion,
  stepData,
}: IntakeCeremonyProps) {
  const safeStep = safeActiveStep(activeStep);

  if (!visible) return null;

  // Build the 4 step objects with real AI narration labels (POR-150)
  const STEPS: readonly Step[] = [
    {
      index: 1,
      number: "01",
      label: buildReceiveLabel(stepData?.receive),
    },
    {
      index: 2,
      number: "02",
      label: buildClassifyLabel(stepData?.classify),
    },
    {
      index: 3,
      number: "03",
      label: buildExtractLabel(stepData?.extract),
    },
    {
      index: 4,
      number: "04",
      label: buildReadyLabel(stepData?.ready),
    },
  ];

  return (
    <div
      data-testid="private-intake-ceremony"
      role="progressbar"
      aria-label={`Intake: step ${safeStep} of ${TOTAL_STEPS}`}
      aria-valuenow={safeStep}
      aria-valuemin={1}
      aria-valuemax={TOTAL_STEPS}
      style={{
        position: "fixed",
        inset: 0,
        backgroundColor: "rgba(13,15,18,0.95)",
        zIndex: 50,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: "24px",
        ...(reducedMotion ? {} : { animation: "ceremonyFadeIn 200ms ease-out both" }),
      }}
    >
      {/* Steps card */}
      <div
        style={{
          backgroundColor: "#FAFAF8",
          borderRadius: "16px",
          border: "1px solid rgba(26,31,40,0.10)",
          padding: "32px 40px",
          minWidth: "280px",
          maxWidth: "520px",
          width: "100%",
          boxShadow: "0 2px 8px rgba(13,15,18,0.12)",
          display: "flex",
          flexDirection: "column",
          gap: "24px",
        }}
      >
        {/* Eyebrow */}
        <span
          style={{
            fontFamily: "'DM Sans', system-ui, sans-serif",
            fontSize: "11px",
            fontWeight: 500,
            letterSpacing: "0.44px",
            textTransform: "uppercase",
            color: "#8C95A3",
            textAlign: "center",
          }}
        >
          Private intake
        </span>

        {/* Step list */}
        <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
          {STEPS.map((step) => (
            <StepRow
              key={step.index}
              {...step}
              isActive={step.index === safeStep}
              isCompleted={step.index < safeStep}
              reducedMotion={reducedMotion}
            />
          ))}
        </div>
      </div>

      {/* Arukai wordmark at bottom */}
      <div
        style={{
          marginTop: "32px",
          fontFamily: "'Cormorant Garamond', Georgia, serif",
          fontSize: "18px",
          fontWeight: 300,
          color: "rgba(250,250,248,0.45)",
          letterSpacing: "0.02em",
          textAlign: "center",
        }}
      >
        Arukai
      </div>

      {/* Keyframe for overlay fade-in — scoped to this element via style tag */}
      {!reducedMotion && (
        <style>{`
          @keyframes ceremonyFadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
          }
          @media (prefers-reduced-motion: reduce) {
            [role="progressbar"] {
              animation: none !important;
              transition: none !important;
            }
          }
        `}</style>
      )}
    </div>
  );
}
