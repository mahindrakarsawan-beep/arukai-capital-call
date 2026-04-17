"use client";

/**
 * IntakeCeremony — 4-step private intake overlay (C1, POR-147 / ARU-17-C1)
 *
 * Adapted from Portfolio Analyzer PrivateIntakeCeremony (ARU-02-P17) for Next.js:
 * - CSS transitions instead of Reanimated (withTiming → transition: opacity 200ms ease-out)
 * - prefers-reduced-motion: collapses to instant transitions
 * - Obsidian overlay at 95% opacity
 * - Cormorant 20pt step labels
 * - Active step: brandBrass (#B8914E) text + number
 * - Completed steps: checkmark + fgMuted
 * - "Arukai" wordmark at bottom
 *
 * Animation rules (per animation memory):
 *   - withTiming only — CSS transition: opacity 200ms ease-out
 *   - No springs in intake context
 *   - Reduced-motion: prefers-reduced-motion media query collapses to instant
 *
 * Props:
 *   visible       — when false, component returns null (unmounted)
 *   activeStep    — 1-based index of the illuminated step (1–4)
 *   reducedMotion — from useReducedMotion(); collapses transitions to instant
 *
 * Brass discipline (spec §9.3): brass appears ONLY on the active step here.
 * This overlay is a system ceremony surface — not a navigation or approval context.
 */

import React from "react";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

interface Step {
  index: number;
  number: string;
  label: string;
}

const STEPS: readonly Step[] = [
  { index: 1, number: "01", label: "Package received" },
  { index: 2, number: "02", label: "Classifying materials" },
  { index: 3, number: "03", label: "Extracting key fields" },
  { index: 4, number: "04", label: "Intake complete" },
] as const;

const TOTAL_STEPS = STEPS.length;

/**
 * Clamp activeStep to [1, TOTAL_STEPS].
 * Defensive guard: non-integer or out-of-range defaults to 1.
 */
function safeActiveStep(v: unknown): number {
  if (typeof v !== "number" || !Number.isFinite(v)) return 1;
  if (v < 1 || v > TOTAL_STEPS) return 1;
  return Math.round(v);
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface IntakeCeremonyProps {
  /** When false, overlay is unmounted entirely. */
  visible: boolean;
  /** 1-based index of the currently illuminated step (1–4). */
  activeStep: number;
  /** From useReducedMotion() — collapses all CSS transitions to instant. */
  reducedMotion: boolean;
}

// ---------------------------------------------------------------------------
// StepRow inner component
// ---------------------------------------------------------------------------

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
  // Opacity: active/completed → 1, future → 0.28
  const opacity = isActive || isCompleted ? 1 : 0.28;

  // withTiming equivalent: CSS transition on opacity
  // Reduced motion: duration 0ms (instant); full motion: 200ms ease-out
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
        style={{
          fontFamily: "'Cormorant Garamond', Georgia, serif",
          fontSize: "20px",
          fontWeight: isActive ? 400 : 300,
          lineHeight: "26px",
          color: isActive ? "#B8914E" : isCompleted ? "#8C95A3" : "#8C95A3",
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

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function IntakeCeremony({
  visible,
  activeStep,
  reducedMotion,
}: IntakeCeremonyProps) {
  const safeStep = safeActiveStep(activeStep);

  if (!visible) return null;

  return (
    <div
      data-testid="private-intake-ceremony"
      role="progressbar"
      aria-label={`Intake: step ${safeStep} of ${TOTAL_STEPS}`}
      aria-valuenow={safeStep}
      aria-valuemin={1}
      aria-valuemax={TOTAL_STEPS}
      style={{
        // Obsidian overlay at 95% opacity
        position: "fixed",
        inset: 0,
        backgroundColor: "rgba(13,15,18,0.95)",
        zIndex: 50,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: "24px",
        // Overlay entry: fade in
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
          maxWidth: "420px",
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
