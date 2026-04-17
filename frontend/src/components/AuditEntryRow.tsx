"use client";

/**
 * AuditEntryRow — expandable audit event row.
 * Spec §B2:
 *  - Columns: Timestamp | Actor | Action | Package | Before → After
 *  - Actor badge: USER (user-initiated) or SYSTEM (automated)
 *  - Timestamp: tabular-nums mono style, full datetime
 *  - Expand on click: full before/after JSON diff
 *  - Tablet (768-1279): Before/After column hidden; shown on expand only
 *  - Mobile: card layout handled by parent page; row itself stays table-native
 *    so parent can switch between table and card view at the page level.
 *
 * Typography: DM Sans throughout (never Cormorant in table rows — §9.1).
 */

import React, { useState } from "react";
import type { AuditEvent } from "@/lib/api";

interface AuditEntryRowProps {
  event: AuditEvent;
}

function formatDateTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    });
  } catch {
    return iso;
  }
}

function formatAction(action: string): string {
  return action.replace(/_/g, " ");
}

function JsonBlock({
  label,
  value,
}: {
  label: string;
  value: Record<string, unknown> | null | undefined;
}) {
  return (
    <div>
      <p className="font-interface text-xs font-medium uppercase tracking-wider text-fg-muted mb-1">
        {label}
      </p>
      {value == null ? (
        <p className="font-interface text-xs text-fg-muted italic">—</p>
      ) : (
        <pre className="font-mono text-xs text-fg-slate bg-bg-parchment border border-border-hairline rounded p-2 overflow-x-auto whitespace-pre-wrap break-words">
          {JSON.stringify(value, null, 2)}
        </pre>
      )}
    </div>
  );
}

export function AuditEntryRow({ event }: AuditEntryRowProps) {
  const [expanded, setExpanded] = useState(false);

  const actorType: "USER" | "SYSTEM" =
    event.actor_type ?? (event.actor_email ? "USER" : "SYSTEM");
  const actorLabel = event.actor_email ?? "System";
  const timestamp = event.created_at ? formatDateTime(event.created_at) : "—";
  const actionLabel = formatAction(event.action ?? "unknown");
  const packageTitle = event.package_title ?? "—";

  const actorBadgeClass =
    actorType === "SYSTEM"
      ? "bg-[rgba(140,149,163,0.18)] text-fg-muted"
      : "bg-[rgba(60,72,88,0.10)] text-fg-slate";

  return (
    <>
      <tr
        className="border-b border-border-hairline last:border-0 hover:bg-[rgba(13,15,18,0.02)] transition-colors duration-fast"
        aria-expanded={expanded}
      >
        {/* Timestamp */}
        <td className="px-4 py-3 font-interface text-xs tabular-nums text-fg-muted whitespace-nowrap">
          {timestamp}
        </td>

        {/* Actor */}
        <td className="px-4 py-3">
          <div className="flex flex-col gap-0.5">
            <span
              className={`inline-flex w-fit items-center rounded-full px-1.5 py-0.5 font-interface text-[10px] font-medium uppercase tracking-wider ${actorBadgeClass}`}
            >
              {actorType}
            </span>
            <span className="font-interface text-xs text-fg-slate truncate max-w-[12rem]">
              {actorLabel}
            </span>
          </div>
        </td>

        {/* Action */}
        <td className="px-4 py-3 font-interface text-sm text-fg-obsidian capitalize">
          {actionLabel}
        </td>

        {/* Package */}
        <td className="px-4 py-3 font-interface text-xs text-fg-slate max-w-[14rem]">
          <span className="truncate block" title={packageTitle}>
            {packageTitle}
          </span>
        </td>

        {/* Before → After summary (desktop 1280+; hidden on tablet) */}
        <td className="hidden xl:table-cell px-4 py-3 font-interface text-xs text-fg-muted max-w-[18rem]">
          {event.before_state || event.after_state ? (
            <span className="text-fg-muted italic">
              {event.before_state
                ? Object.keys(event.before_state).join(", ")
                : "—"}{" "}
              →{" "}
              {event.after_state
                ? Object.keys(event.after_state).join(", ")
                : "—"}
            </span>
          ) : (
            <span className="text-fg-muted">—</span>
          )}
        </td>

        {/* Expand toggle */}
        <td className="px-3 py-3 text-right w-10">
          <button
            type="button"
            aria-label={expanded ? "Collapse audit detail" : "Expand audit detail"}
            onClick={() => setExpanded((v) => !v)}
            className="inline-flex h-6 w-6 items-center justify-center rounded text-fg-muted hover:text-fg-obsidian hover:bg-[rgba(13,15,18,0.06)] transition-colors duration-fast focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-fg-slate"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 16 16"
              fill="currentColor"
              className={`h-3.5 w-3.5 transition-transform duration-fast ${expanded ? "rotate-180" : ""}`}
              aria-hidden="true"
            >
              <path
                fillRule="evenodd"
                d="M4.22 6.22a.75.75 0 0 1 1.06 0L8 8.94l2.72-2.72a.75.75 0 1 1 1.06 1.06l-3.25 3.25a.75.75 0 0 1-1.06 0L4.22 7.28a.75.75 0 0 1 0-1.06Z"
                clipRule="evenodd"
              />
            </svg>
          </button>
        </td>
      </tr>

      {/* Expanded diff panel */}
      {expanded && (
        <tr className="bg-bg-parchment border-b border-border-hairline">
          <td colSpan={6} className="px-6 py-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <JsonBlock label="Before state" value={event.before_state} />
              <JsonBlock label="After state" value={event.after_state} />
            </div>
          </td>
        </tr>
      )}
    </>
  );
}
