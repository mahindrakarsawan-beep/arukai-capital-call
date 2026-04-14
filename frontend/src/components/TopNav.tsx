import React from "react";
import Link from "next/link";
import { logoutAction } from "@/lib/actions";
import type { User } from "@/lib/api";

interface TopNavProps {
  user?: User | null;
}

export function TopNav({ user }: TopNavProps) {
  return (
    <header className="border-b border-border-hairline bg-bg-bone sticky top-0 z-10">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
        <Link
          href="/documents"
          className="font-display text-lg font-semibold text-fg-obsidian tracking-tight"
        >
          Arukai Capital Call
        </Link>

        {user && (
          <div className="flex items-center gap-4">
            <span className="font-interface text-sm text-fg-slate">
              {user.email}
            </span>
            <span
              className={[
                "inline-flex items-center rounded-full px-2 py-0.5",
                "font-interface text-xs font-medium",
                user.role === "admin"
                  ? "bg-[rgba(184,145,78,0.12)] text-[#9A7639]"
                  : "bg-[rgba(60,72,88,0.10)] text-fg-slate",
              ].join(" ")}
            >
              {user.role}
            </span>
            <form action={logoutAction}>
              <button
                type="submit"
                className="font-interface text-sm text-fg-muted hover:text-fg-obsidian transition-colors duration-fast"
              >
                Sign out
              </button>
            </form>
          </div>
        )}
      </div>
    </header>
  );
}
