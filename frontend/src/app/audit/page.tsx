/**
 * Audit ledger — /audit (spec §B2, Figma node 17:34 Page 3)
 *
 * Server component: fetches /audit using JWT from cookie.
 * Role gate (S5): admin + approver only. Reviewer → access-restricted message.
 *
 * Layout (per Figma / spec §B2):
 *  - Hero: "Audit ledger" Cormorant 32pt + "VISIBLE TO ADMINS AND APPROVERS ONLY" warningText label
 *  - Filter bar (client): actor · action · date from · date to + Apply + Clear
 *  - Results table: Timestamp | Actor | Action | Package | Before → After
 *  - Each row expandable (full before/after JSON diff)
 *  - Pagination: "Load more" cursor-based
 *  - Export: "Export ledger (CSV)" → /audit/export.csv
 *  - Empty state: "No audit events match your filters"
 *
 * Responsive:
 *  - Desktop 1280+: full table with all columns incl. Before → After
 *  - Tablet 768-1279: table without Before/After column; shown on expand
 *  - Mobile 375-767: card layout (AuditLedgerClient renders mobile cards)
 *
 * Typography: Cormorant for H1 only; DM Sans everywhere else (§9.1 / §9.2).
 */

import React from "react";
import Link from "next/link";
import { redirect } from "next/navigation";
import { getToken } from "@/lib/auth";
import { getMe, listAuditEvents } from "@/lib/api";
import { canViewAuditLedger } from "@/lib/state";
import { TopNav } from "@/components/TopNav";
import { StaleBanner } from "@/components/StaleBanner";
import { AuditLedgerClient } from "./AuditLedgerClient";
import type { User } from "@/lib/api";
import type { AuditFilterValues } from "@/components/AuditFilterBar";

const PAGE_LIMIT = 50;

interface AuditPageProps {
  searchParams: Promise<{
    actor_id?: string;
    action?: string;
    from_date?: string;
    to_date?: string;
    package_id?: string;
    cursor?: string;
  }>;
}

export default async function AuditPage({ searchParams }: AuditPageProps) {
  const token = await getToken();

  if (!token) {
    redirect("/");
  }

  const params = await searchParams;

  let user: User | null = null;
  let fetchError: string | null = null;

  try {
    user = await getMe(token);
  } catch (err) {
    fetchError = err instanceof Error ? err.message : "Failed to load user.";
  }

  // ── Role gate ───────────────────────────────────────────────────────────────
  // S5: admin + approver only. Reviewer sees access-restricted message.
  const canView = canViewAuditLedger(user?.role ?? null);

  if (!canView) {
    return (
      <div className="flex min-h-screen flex-col bg-bg-bone">
        <TopNav user={user} />
        <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 md:py-12 flex flex-col items-center justify-center text-center">
          {/* Hero with restricted heading */}
          <h1 className="font-display text-2xl md:text-4xl font-light text-fg-obsidian tracking-tight mb-3">
            Audit ledger
          </h1>
          <div className="mt-4 rounded-lg border border-[rgba(154,118,57,0.30)] bg-[rgba(154,118,57,0.06)] px-6 py-8 max-w-md">
            <p className="font-interface text-base font-semibold text-fg-obsidian mb-2">
              Access restricted.
            </p>
            <p className="font-interface text-sm text-fg-slate">
              The audit ledger is available to admins and approvers only.
            </p>
            <Link
              href="/documents"
              className="mt-6 inline-block font-interface text-sm font-semibold text-fg-obsidian underline underline-offset-2 hover:opacity-70 transition-opacity duration-fast focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-fg-slate rounded"
            >
              Return to Console
            </Link>
          </div>
        </main>
      </div>
    );
  }

  // ── Fetch audit events ──────────────────────────────────────────────────────
  const activeFilters: AuditFilterValues = {
    actor_id: params.actor_id ?? "",
    action: params.action ?? "",
    from_date: params.from_date ?? "",
    to_date: params.to_date ?? "",
  };

  let items: import("@/lib/api").AuditEvent[] = [];
  let nextCursor: string | undefined;
  let total = 0;

  if (!fetchError) {
    try {
      const result = await listAuditEvents(token, {
        actor_id: params.actor_id || undefined,
        action: params.action || undefined,
        from_date: params.from_date || undefined,
        to_date: params.to_date || undefined,
        package_id: params.package_id || undefined,
        limit: PAGE_LIMIT,
        cursor: params.cursor || undefined,
      });
      items = result.items;
      nextCursor = result.next_cursor;
      total = result.total;
    } catch (err) {
      fetchError = err instanceof Error ? err.message : "Failed to load audit events.";
    }
  }

  return (
    <div className="flex min-h-screen flex-col bg-bg-bone">
      <TopNav user={user} />

      {fetchError && (
        <StaleBanner message="Workflow state could not be refreshed. The information shown may be stale." />
      )}

      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 md:py-8">
        {/* ── Hero ────────────────────────────────────────────────────────── */}
        <div className="mb-6 md:mb-8">
          <h1 className="font-display text-2xl md:text-[32px] font-light text-fg-obsidian tracking-tight leading-tight">
            Audit ledger
          </h1>
          {/* Role-gate label — warningText tone per spec */}
          <p className="mt-1 font-interface text-xs font-medium uppercase tracking-wider text-[#9A7639]">
            Visible to admins and approvers only
          </p>
        </div>

        {/* ── Client shell: filters + table + pagination + export ─────────── */}
        <AuditLedgerClient
          initialItems={items}
          initialNextCursor={nextCursor}
          initialTotal={total}
          token={token}
          initialFilters={activeFilters}
        />
      </main>
    </div>
  );
}
