import React from "react";
import Link from "next/link";
import { logoutAction } from "@/lib/actions";
import { displayRole, canViewAuditLedger } from "@/lib/state";
import type { User } from "@/lib/api";

interface TopNavProps {
  user?: User | null;
  /**
   * Count of packages pending attestation.
   * When provided, renders a neutral status chip in the nav (no brass — per Holden's fix,
   * the TopNav chip was the 4th brass site, violating §9.3. Chip is now neutral-muted.)
   */
  pendingAttestationCount?: number;
}

/**
 * TopNav — v0.2 atelier navigation per spec §1.6.
 * Labels: Console · Begin intake · Audit ledger (approver/admin only) · {name} · {role} · Leave workflow
 *
 * Pending attestation chip: dataSlateMuted bg + dataSlate fg, no brass dot (Holden fix).
 * Responsive: nav links hidden on mobile (sm: breakpoint), full bar on md+.
 */
export function TopNav({ user, pendingAttestationCount }: TopNavProps) {
  const showAuditLedger = canViewAuditLedger(user?.role ?? null);
  // "Begin intake" / upload is available to admin and operator only.
  // Reviewer and approver roles do not upload packages.
  const role = user?.role ?? null;
  const showBeginIntake = role === null || role === "admin" || role === "operator";

  return (
    <header className="border-b border-border-hairline bg-bg-bone sticky top-0 z-10">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
        {/* Wordmark */}
        <Link
          href="/documents"
          className="font-display text-lg font-light text-fg-obsidian tracking-tight"
        >
          Arukai
        </Link>

        {/* Nav items — visible from md up */}
        <nav className="hidden md:flex items-center gap-6">
          <Link
            href="/documents"
            className="font-interface text-sm text-fg-slate hover:text-fg-obsidian transition-colors duration-fast"
          >
            Console
          </Link>
          {showBeginIntake && (
            <Link
              href="/documents/upload"
              className="font-interface text-sm text-fg-slate hover:text-fg-obsidian transition-colors duration-fast"
            >
              Begin intake
            </Link>
          )}
          {/* Audit ledger: admin + approver only (S5) */}
          {showAuditLedger && (
            <Link
              href="/audit"
              className="font-interface text-sm text-fg-slate hover:text-fg-obsidian transition-colors duration-fast"
            >
              Audit ledger
            </Link>
          )}
        </nav>

        <div className="flex items-center gap-3 md:gap-4">
          {/* Pending attestation chip — neutral skin per Holden review (§9.3 fix).
              No brass dot. Background: fg-obsidian 8% opacity; text: fg-slate.
              This was the 4th brass site — now neutralized. */}
          {!!pendingAttestationCount && (
            <span
              className="hidden sm:inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 font-interface text-xs font-medium tracking-wide bg-[rgba(13,15,18,0.08)] text-fg-slate border border-[rgba(13,15,18,0.10)]"
              aria-label={`${pendingAttestationCount} pending attestation${pendingAttestationCount !== 1 ? "s" : ""}`}
            >
              {pendingAttestationCount} PENDING ATTESTATION
            </span>
          )}

          {user && (
            <>
              <span className="hidden sm:inline font-interface text-sm text-fg-slate">
                {user.email} · {displayRole(user.role)}
              </span>
              <form action={logoutAction}>
                <button
                  type="submit"
                  className="font-interface text-sm text-fg-muted hover:text-fg-obsidian transition-colors duration-fast"
                >
                  Leave workflow
                </button>
              </form>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
