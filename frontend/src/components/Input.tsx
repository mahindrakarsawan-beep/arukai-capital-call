"use client";

import React from "react";

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

/**
 * Form input component with Arukai brand styling.
 */
export function Input({ label, error, id, className = "", ...rest }: InputProps) {
  return (
    <div className="flex flex-col gap-1">
      {label && (
        <label
          htmlFor={id}
          className="font-interface text-xs font-medium tracking-widest uppercase text-fg-muted"
        >
          {label}
        </label>
      )}
      <input
        id={id}
        className={[
          "w-full rounded-md border bg-bg-bone px-3 py-2",
          "font-interface text-sm text-fg-obsidian",
          "placeholder:text-fg-muted",
          "transition-colors duration-fast",
          error
            ? "border-data-negative focus:border-data-negative focus:ring-data-negative"
            : "border-border-hairline focus:border-fg-slate focus:ring-fg-slate",
          "focus:outline-none focus:ring-2 focus:ring-offset-0",
          className,
        ].join(" ")}
        {...rest}
      />
      {error && (
        <p className="font-interface text-xs text-data-negative" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
