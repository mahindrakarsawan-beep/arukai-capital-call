"use client";

import React from "react";

interface StaleBannerProps {
  message?: string;
}

/**
 * StaleBanner — adapted from Portfolio Analyzer connection issue pattern (P-3.x).
 * Shown when server data cannot be reached or when displaying stale/offline state.
 */
export function StaleBanner({
  message = "Could not connect to the server. Displaying cached data.",
}: StaleBannerProps) {
  return (
    <div
      role="alert"
      className="w-full bg-[rgba(184,145,78,0.12)] border-b border-[rgba(184,145,78,0.20)] px-4 py-2.5"
    >
      <p className="font-interface text-sm text-[#9A7639] text-center">
        {message}
      </p>
    </div>
  );
}
