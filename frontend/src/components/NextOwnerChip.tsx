import React from "react";
import type { PackageStateInfo } from "@/lib/state";

interface NextOwnerChipProps {
  stateInfo: PackageStateInfo;
}

/**
 * NextOwnerChip — borderless text chip showing next owner per spec §3.
 * Two-chip pattern: paired with StatePill on every row.
 * Dot color: neutral (muted) | brass (routed_for_approval) | amber (exception)
 */
export function NextOwnerChip({ stateInfo }: NextOwnerChipProps) {
  const dotClass =
    stateInfo.nextOwnerDot === "brass"
      ? "bg-[#B8914E]"
      : stateInfo.nextOwnerDot === "amber"
        ? "bg-[#9A7639]"
        : "bg-fg-muted";

  return (
    <span
      className="inline-flex items-center gap-1.5 font-interface text-xs text-fg-slate"
      aria-label={`Next owner: ${stateInfo.nextOwnerText}`}
    >
      <span
        className={`inline-block h-1.5 w-1.5 flex-shrink-0 rounded-full ${dotClass}`}
        aria-hidden="true"
      />
      {stateInfo.nextOwnerText}
    </span>
  );
}
