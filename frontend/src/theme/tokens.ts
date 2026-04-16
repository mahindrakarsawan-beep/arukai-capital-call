/**
 * Arukai Capital Call — web design tokens.
 * Adapted from Portfolio Analyzer mobile tokens (P-3.1 reuse).
 * Palette: Bone/Parchment ↔ Obsidian/Graphite, single brass accent (signal-only).
 * Typography: Cormorant Garamond (display) + DM Sans (interface).
 *
 * BRASS DISCIPLINE (spec §9.3) — brass appears in EXACTLY THREE places:
 *   1. The [Attest approval] button (AttestationModal confirm + PackageDetailActions trigger)
 *   2. The routed_for_approval state pill and its next-owner chip dot
 *   3. The Pending approval section count badge when count > 0
 * Any other use is a spec violation. Amber (#9A7639) is a separate semantic role
 * for exceptions, low-confidence fields, and missing fields — never interchanged with brass.
 */

export const colors = {
  // Light surfaces
  bgBone: "#FAFAF8",
  bgParchment: "#EEE9E0",

  // Dark surfaces
  bgObsidian: "#0D0F12",
  bgGraphite: "#1A1F28",

  // Ink (foreground)
  fgObsidian: "#0D0F12",
  fgSlate: "#5B6472",
  fgMuted: "#8C95A3",

  // Borders
  borderHairline: "rgba(26,31,40,0.10)",
  borderHairlineStrong: "rgba(26,31,40,0.16)",

  // Brand accent — signal-only
  // BRASS SITE 1: AttestationModal confirm ("Attest and record decision") + PackageDetailActions trigger ("Attest approval")
  // BRASS SITE 2: routed_for_approval status pill + its next-owner chip dot
  // BRASS SITE 3: Pending approval section count badge (when count > 0)
  brandBrass: "#B8914E",
  brandBrassPressed: "#9A7639",
  brandBrassMuted: "rgba(184,145,78,0.12)",

  // Semantic data colors
  dataPositive: "#1F7A4D",
  dataPositiveMuted: "rgba(31,122,77,0.12)",
  dataNegative: "#B23A2E",
  dataNegativeMuted: "rgba(178,58,46,0.12)",

  // Warning — amber: exceptions, low-confidence, missing fields (DISTINCT from brass)
  // Amber (#9A7639) ≠ Brass (#B8914E). Close in hue, separate semantic contract.
  warningSurface: "rgba(184,145,78,0.12)",
  warningText: "#9A7639",
  errorSurface: "rgba(178,58,46,0.12)",
  errorText: "#B23A2E",

  // Overlays
  overlayScrim: "rgba(13,15,18,0.55)",
} as const;

export const space = {
  xs: "4px",
  sm: "8px",
  md: "12px",
  lg: "16px",
  xl: "20px",
  xxl: "24px",
  xxxl: "32px",
  hero: "48px",
} as const;

export const radius = {
  sm: "8px",
  md: "12px",
  lg: "16px",
  xl: "20px",
  pill: "9999px",
} as const;

export const motion = {
  fast: "150ms ease-out",
  standard: "240ms ease-out",  // modal fade — withTiming equivalent
  slow: "360ms ease-out",       // hairline draw — Phase C ceremony
} as const;
