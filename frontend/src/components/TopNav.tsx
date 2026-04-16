import React from "react";
import Link from "next/link";
import { logoutAction } from "@/lib/actions";
import { displayRole } from "@/lib/state";
import type { User } from "@/lib/api";

interface TopNavProps {
  user?: User | null;
}

/**
 * TopNav — v0.2 atelier navigation per spec §1.6.
 * Labels: Console · Begin intake · Audit ledger · {name} · {role} · Leave workflow
 */
export function TopNav({ user }: TopNavProps) {
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

        {/* Nav items */}
        <nav className="hidden sm:flex items-center gap-6">
          <Link
            href="/documents"
            className="font-interface text-sm text-fg-slate hover:text-fg-obsidian transition-colors duration-fast"
          >
            Console
          </Link>
          <Link
            href="/documents/upload"
            className="font-interface text-sm text-fg-slate hover:text-fg-obsidian transition-colors duration-fast"
          >
            Begin intake
          </Link>
        </nav>

        {user && (
          <div className="flex items-center gap-4">
            <span className="font-interface text-sm text-fg-slate">
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
          </div>
        )}
      </div>
    </header>
  );
}
