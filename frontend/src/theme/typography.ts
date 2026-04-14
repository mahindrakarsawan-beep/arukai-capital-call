/**
 * Arukai Capital Call — web typography scale.
 * Display: Cormorant Garamond (serif, hero headings only)
 * Interface: DM Sans (everything else — forms, tables, nav)
 *
 * Fonts loaded via Google Fonts link in layout.tsx.
 */

export const fontFamily = {
  display: "'Cormorant Garamond', Georgia, serif",
  interface: "'DM Sans', system-ui, sans-serif",
} as const;

export const typeScale = {
  hero: {
    fontFamily: fontFamily.display,
    fontSize: "2.75rem",
    lineHeight: "1.05",
    letterSpacing: "-0.03em",
    fontWeight: "300",
  },
  h1: {
    fontFamily: fontFamily.display,
    fontSize: "1.75rem",
    lineHeight: "1.15",
    letterSpacing: "-0.02em",
    fontWeight: "400",
  },
  h2: {
    fontFamily: fontFamily.interface,
    fontSize: "1.25rem",
    lineHeight: "1.3",
    fontWeight: "600",
  },
  body: {
    fontFamily: fontFamily.interface,
    fontSize: "0.875rem",
    lineHeight: "1.571",
    fontWeight: "400",
  },
  caption: {
    fontFamily: fontFamily.interface,
    fontSize: "0.75rem",
    lineHeight: "1.333",
    fontWeight: "400",
  },
  label: {
    fontFamily: fontFamily.interface,
    fontSize: "0.6875rem",
    lineHeight: "1.27",
    fontWeight: "500",
    letterSpacing: "0.04em",
    textTransform: "uppercase" as const,
  },
  button: {
    fontFamily: fontFamily.interface,
    fontSize: "0.875rem",
    lineHeight: "1.25",
    fontWeight: "600",
    letterSpacing: "0.01em",
  },
} as const;
