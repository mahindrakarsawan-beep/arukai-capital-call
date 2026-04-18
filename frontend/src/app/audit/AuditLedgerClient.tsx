"use client";

/**
 * AuditLedgerClient — client shell for the audit ledger.
 * Handles:
 *  - Filter bar state → re-fetch on Apply (router.push with new searchParams)
 *  - "Load more" cursor-based pagination
 *  - Responsive layout: table (lg+), card stacks (mobile)
 *
 * Server component (page.tsx) passes initial data; this component owns
 * subsequent fetches so the page doesn't need full server round-trips for
 * "Load more" or filter changes.
 *
 * Animation: none (static table). No springs, no withTiming — not a
 * sheet or refresh context. Per animation memory note.
 */

import React, { useState, useTransition } from "react";
import { useRouter, usePathname } from "next/navigation";
import { AuditFilterBar, type AuditFilterValues } from "@/components/AuditFilterBar";
import { AuditEntryRow } from "@/components/AuditEntryRow";
import { listAuditEvents, getAuditExportUrl } from "@/lib/api";
import type { AuditEvent } from "@/lib/api";

interface AuditLedgerClientProps {
  /** Initial batch of events fetched on the server. */
  initialItems: AuditEvent[];
  initialNextCursor?: string;
  initialTotal: number;
  /** JWT token forwarded from the server for client-side "Load more" fetches. */
  token: string;
  /** Active filter values pre-populated from URL searchParams. */
  initialFilters: AuditFilterValues;
}

const PAGE_LIMIT = 50;

export function AuditLedgerClient({
  initialItems,
  initialNextCursor,
  initialTotal,
  token,
  initialFilters,
}: AuditLedgerClientProps) {
  const router = useRouter();
  const pathname = usePathname();
  const [isPending, startTransition] = useTransition();

  const [items, setItems] = useState<AuditEvent[]>(initialItems);
  const [nextCursor, setNextCursor] = useState<string | undefined>(initialNextCursor);
  const [total] = useState(initialTotal);
  const [loadingMore, setLoadingMore] = useState(false);

  // Active filters are driven by URL (server-side filtering via searchParams).
  // When user applies filters, we push a new URL → server re-renders with fresh data.
  function handleApply(filters: AuditFilterValues) {
    const params = new URLSearchParams();
    if (filters.actor_id) params.set("actor_id", filters.actor_id);
    if (filters.action) params.set("action", filters.action);
    if (filters.from_date) params.set("from_date", filters.from_date);
    if (filters.to_date) params.set("to_date", filters.to_date);
    startTransition(() => {
      router.push(`${pathname}?${params.toString()}`);
    });
  }

  function handleClear() {
    startTransition(() => {
      router.push(pathname);
    });
  }

  // "Load more" — client-side cursor fetch; appends to current list.
  async function handleLoadMore() {
    if (!nextCursor || loadingMore) return;
    setLoadingMore(true);
    try {
      const result = await listAuditEvents(token, {
        actor_id: initialFilters.actor_id || undefined,
        action: initialFilters.action || undefined,
        from_date: initialFilters.from_date || undefined,
        to_date: initialFilters.to_date || undefined,
        limit: PAGE_LIMIT,
        cursor: nextCursor,
      });
      setItems((prev) => [...prev, ...result.items]);
      setNextCursor(result.next_cursor);
    } catch {
      // Silent fail — user can retry; stale data still shown.
    } finally {
      setLoadingMore(false);
    }
  }

  const exportUrl = getAuditExportUrl({
    actor_id: initialFilters.actor_id || undefined,
    action: initialFilters.action || undefined,
    from_date: initialFilters.from_date || undefined,
    to_date: initialFilters.to_date || undefined,
  });

  return (
    <>
      {/* Filter bar */}
      <div
        className={`mb-10 transition-opacity duration-fast ${isPending ? "opacity-50 pointer-events-none" : ""}`}
      >
        <AuditFilterBar
          onApply={handleApply}
          onClear={handleClear}
          initialValues={initialFilters}
        />
      </div>

      {/* Top toolbar: total count + export */}
      <div className="mb-4 flex items-center justify-between">
        <p className="font-interface text-sm text-fg-muted tabular-nums">
          {total > 0
            ? `${total} event${total !== 1 ? "s" : ""}`
            : ""}
        </p>
        <a
          href={exportUrl}
          download
          className="inline-flex items-center gap-2 font-interface text-xs font-medium text-fg-muted border border-border-hairline rounded-full px-3 py-1.5 bg-transparent hover:text-fg-obsidian hover:border-fg-obsidian transition-colors duration-fast focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-fg-slate"
          aria-label="Export governed record as CSV"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 16 16"
            fill="currentColor"
            className="h-3 w-3"
            aria-hidden="true"
          >
            <path d="M8.75 2.75a.75.75 0 0 0-1.5 0v5.69L5.03 6.22a.75.75 0 0 0-1.06 1.06l3.5 3.5a.75.75 0 0 0 1.06 0l3.5-3.5a.75.75 0 0 0-1.06-1.06L8.75 8.44V2.75Z" />
            <path d="M3.5 9.75a.75.75 0 0 0-1.5 0v1.5A2.75 2.75 0 0 0 4.75 14h6.5A2.75 2.75 0 0 0 14 11.25v-1.5a.75.75 0 0 0-1.5 0v1.5c0 .69-.56 1.25-1.25 1.25h-6.5c-.69 0-1.25-.56-1.25-1.25v-1.5Z" />
          </svg>
          Export governed record
        </a>
      </div>

      {/* ── Desktop / Tablet table ── */}
      {items.length === 0 ? (
        <div className="rounded-lg border border-border-hairline bg-bg-parchment px-6 py-10 text-center">
          <p className="font-interface text-sm text-fg-muted italic">
            No audit events match your filters
          </p>
        </div>
      ) : (
        <>
          {/* Table — hidden on mobile (xs), card view shown instead */}
          <div className="hidden sm:block rounded-lg border border-border-hairline bg-bg-bone overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead>
                  <tr className="border-b border-border-hairline bg-bg-parchment">
                    <th className="px-4 py-3 font-display text-sm font-light tracking-wide text-fg-slate">
                      Timestamp
                    </th>
                    <th className="px-4 py-3 font-display text-sm font-light tracking-wide text-fg-slate">
                      Actor
                    </th>
                    <th className="px-4 py-3 font-display text-sm font-light tracking-wide text-fg-slate">
                      Action
                    </th>
                    <th className="px-4 py-3 font-display text-sm font-light tracking-wide text-fg-slate">
                      Package
                    </th>
                    {/* Before → After: desktop only (xl+) — hidden on tablet */}
                    <th className="hidden xl:table-cell px-4 py-3 font-display text-sm font-light tracking-wide text-fg-slate">
                      Before → After
                    </th>
                    {/* Expand toggle column */}
                    <th className="w-10" aria-label="Expand" />
                  </tr>
                </thead>
                <tbody>
                  {items.map((event) => (
                    <AuditEntryRow key={event.id} event={event} />
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Mobile card stack — visible only on xs */}
          <div className="sm:hidden flex flex-col gap-3">
            {items.map((event) => (
              <AuditMobileCard key={event.id} event={event} />
            ))}
          </div>
        </>
      )}

      {/* Load more */}
      {nextCursor && (
        <div className="mt-6 text-center">
          <button
            type="button"
            onClick={handleLoadMore}
            disabled={loadingMore}
            className="font-interface text-sm text-fg-slate border border-border-hairline rounded px-4 py-2 hover:text-fg-obsidian hover:border-fg-obsidian transition-colors duration-fast focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-fg-slate disabled:opacity-50"
          >
            {loadingMore ? "Loading…" : "Load more"}
          </button>
        </div>
      )}
    </>
  );
}

// ── Mobile card ───────────────────────────────────────────────────────────────

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

function AuditMobileCard({ event }: { event: AuditEvent }) {
  const [expanded, setExpanded] = useState(false);

  const actorType = event.actor_type ?? (event.actor_email ? "USER" : "SYSTEM");
  const actorLabel = event.actor_email ?? "System";
  const timestamp = event.created_at ? formatDateTime(event.created_at) : "—";
  const actionLabel = (event.action ?? "").replace(/_/g, " ");
  const packageTitle = event.package_title ?? "—";

  return (
    <div className="rounded-lg border border-border-hairline bg-bg-bone overflow-hidden">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="w-full text-left px-4 py-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-fg-slate"
        aria-expanded={expanded}
      >
        <div className="flex items-start justify-between gap-2">
          <div className="flex-1 min-w-0">
            <p className="font-interface text-sm text-fg-obsidian capitalize truncate">
              {actionLabel}
            </p>
            <p className="font-interface text-xs text-fg-muted tabular-nums mt-0.5">
              {timestamp}
            </p>
          </div>
          <span
            className={`inline-flex items-center rounded-full px-1.5 py-0.5 font-interface text-[10px] font-medium uppercase tracking-wider flex-shrink-0 ${
              actorType === "SYSTEM"
                ? "bg-[rgba(140,149,163,0.18)] text-fg-muted"
                : "bg-[rgba(60,72,88,0.10)] text-fg-slate"
            }`}
          >
            {actorType}
          </span>
        </div>
        <p className="font-interface text-xs text-fg-slate mt-1 truncate">
          {actorLabel}
        </p>
        {packageTitle !== "—" && (
          <p className="font-interface text-xs text-fg-muted mt-0.5 truncate">
            {packageTitle}
          </p>
        )}
      </button>

      {expanded && (
        <div className="border-t border-border-hairline bg-bg-parchment px-4 py-3">
          <div className="grid grid-cols-1 gap-3">
            <div>
              <p className="font-interface text-[10px] font-medium uppercase tracking-wider text-fg-muted mb-1">
                Before state
              </p>
              {event.before_state ? (
                <pre className="font-mono text-xs text-fg-slate overflow-x-auto whitespace-pre-wrap break-words">
                  {JSON.stringify(event.before_state, null, 2)}
                </pre>
              ) : (
                <p className="font-interface text-xs text-fg-muted italic">—</p>
              )}
            </div>
            <div>
              <p className="font-interface text-[10px] font-medium uppercase tracking-wider text-fg-muted mb-1">
                After state
              </p>
              {event.after_state ? (
                <pre className="font-mono text-xs text-fg-slate overflow-x-auto whitespace-pre-wrap break-words">
                  {JSON.stringify(event.after_state, null, 2)}
                </pre>
              ) : (
                <p className="font-interface text-xs text-fg-muted italic">—</p>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
