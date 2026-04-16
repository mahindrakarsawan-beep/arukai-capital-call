/**
 * Shared formatting utilities — date, time, number.
 * Keep pure (no React, no DOM).
 */

/**
 * Format an ISO timestamp as a human-relative string.
 *   < 1h  → "just now"
 *   < 24h → "Xh ago"
 *   < 30d → "Xd ago"
 *   ≥ 30d → "Mon D" (e.g. "Apr 12")
 */
export function formatRelative(iso: string): string {
  try {
    const diff = Date.now() - new Date(iso).getTime();
    const h = Math.floor(diff / 3600000);
    if (h < 1) return "just now";
    if (h < 24) return `${h}h ago`;
    const d = Math.floor(h / 24);
    if (d < 30) return `${d}d ago`;
    return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric" });
  } catch {
    return iso;
  }
}

/**
 * Format an ISO timestamp as an absolute short date: "Apr 12, 2026".
 */
export function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch {
    return iso;
  }
}
