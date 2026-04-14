"use client";

import React from "react";

type Variant = "primary" | "secondary" | "danger" | "brass";

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  loading?: boolean;
  children: React.ReactNode;
}

const variantClasses: Record<Variant, string> = {
  primary:
    "bg-fg-obsidian text-bg-bone hover:bg-bg-graphite focus-visible:ring-fg-obsidian",
  secondary:
    "bg-bg-parchment text-fg-obsidian border border-border-hairline hover:bg-bg-bone focus-visible:ring-fg-slate",
  danger:
    "bg-data-negative text-white hover:opacity-90 focus-visible:ring-data-negative",
  // brass — signal-only: admin-approval CTAs only (per brand rules)
  brass:
    "bg-brand-brass text-white hover:bg-brand-brass-pressed focus-visible:ring-brand-brass",
};

/**
 * PrimaryButton equivalent for Arukai Capital Call web.
 * variant="brass" is reserved for admin-approval CTAs only.
 */
export function Button({
  variant = "primary",
  loading = false,
  disabled,
  children,
  className = "",
  ...rest
}: ButtonProps) {
  return (
    <button
      disabled={disabled || loading}
      className={[
        "inline-flex items-center justify-center gap-2 rounded-md px-4 py-2",
        "font-interface text-sm font-semibold tracking-wide",
        "transition-colors duration-fast",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2",
        "disabled:opacity-50 disabled:cursor-not-allowed",
        variantClasses[variant],
        className,
      ].join(" ")}
      {...rest}
    >
      {loading ? (
        <>
          <span
            className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent"
            aria-hidden="true"
          />
          <span>Loading…</span>
        </>
      ) : (
        children
      )}
    </button>
  );
}
