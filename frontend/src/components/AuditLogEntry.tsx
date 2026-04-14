import React from "react";

export interface AuditEvent {
  id: string;
  action: string;
  actor_email?: string;
  created_at: string;
  before_state?: Record<string, unknown> | null;
  after_state?: Record<string, unknown> | null;
}

interface AuditLogEntryProps {
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
    });
  } catch {
    return iso;
  }
}

/**
 * Reusable audit log row for the document detail page and future use.
 */
export function AuditLogEntry({ event }: AuditLogEntryProps) {
  // Defensive normalizer
  const action = event?.action ?? "unknown";
  const actor = event?.actor_email ?? "System";
  const time = event?.created_at ? formatDateTime(event.created_at) : "—";

  return (
    <tr className="border-b border-border-hairline last:border-0">
      <td className="px-4 py-2.5 font-interface text-sm text-fg-obsidian capitalize">
        {action.replace(/_/g, " ")}
      </td>
      <td className="px-4 py-2.5 font-interface text-sm text-fg-slate">
        {actor}
      </td>
      <td className="px-4 py-2.5 font-interface text-sm text-fg-muted tabular-nums">
        {time}
      </td>
    </tr>
  );
}
