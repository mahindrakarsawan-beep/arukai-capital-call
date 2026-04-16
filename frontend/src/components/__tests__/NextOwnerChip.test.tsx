/**
 * NextOwnerChip tests — POR-147 / ARU-17 Phase A (spec §3)
 * Tests: next owner text per state, dot color per tone, brass only on routed_for_approval
 */

import React from "react";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import { NextOwnerChip } from "@/components/NextOwnerChip";
import type { PackageStateInfo } from "@/lib/state";

function makeStateInfo(
  uiState: PackageStateInfo["uiState"],
  nextOwnerText: string,
  nextOwnerDot: PackageStateInfo["nextOwnerDot"],
  pillTone: PackageStateInfo["pillTone"] = "neutral"
): PackageStateInfo {
  return {
    uiState,
    pillLabel: "",
    pillTone,
    nextOwnerText,
    nextOwnerDot,
  };
}

describe("NextOwnerChip — next owner text rendering", () => {
  it('renders "Awaiting system intake" for submitted state', () => {
    render(
      <NextOwnerChip
        stateInfo={makeStateInfo("submitted", "Awaiting system intake", "neutral")}
      />
    );
    expect(screen.getByText("Awaiting system intake")).toBeInTheDocument();
  });

  it('renders "Awaiting reviewer" for intake_complete', () => {
    render(
      <NextOwnerChip
        stateInfo={makeStateInfo("intake_complete", "Awaiting reviewer", "neutral")}
      />
    );
    expect(screen.getByText("Awaiting reviewer")).toBeInTheDocument();
  });

  it('renders "Awaiting approver attestation" for routed_for_approval with brass dot', () => {
    render(
      <NextOwnerChip
        stateInfo={makeStateInfo(
          "routed_for_approval",
          "Awaiting approver attestation",
          "brass",
          "brass"
        )}
      />
    );
    expect(screen.getByText("Awaiting approver attestation")).toBeInTheDocument();
  });

  it("renders decision recorded text for approved state", () => {
    render(
      <NextOwnerChip
        stateInfo={makeStateInfo(
          "decision_recorded_approved",
          "Decision recorded — approver attested on Apr 12 2026",
          "neutral"
        )}
      />
    );
    expect(
      screen.getByText(/decision recorded — approver attested on Apr 12 2026/i)
    ).toBeInTheDocument();
  });

  it("renders exception text with amber dot for exception_surfaced", () => {
    const { container } = render(
      <NextOwnerChip
        stateInfo={makeStateInfo(
          "exception_surfaced",
          "Awaiting operator — low confidence",
          "amber"
        )}
      />
    );
    expect(screen.getByText("Awaiting operator — low confidence")).toBeInTheDocument();
    // Dot should use amber color
    const dot = container.querySelector('[aria-hidden="true"]');
    expect(dot?.className).toContain("bg-[#9A7639]");
  });

  it("uses brass dot color for routed_for_approval", () => {
    const { container } = render(
      <NextOwnerChip
        stateInfo={makeStateInfo(
          "routed_for_approval",
          "Awaiting approver attestation",
          "brass"
        )}
      />
    );
    const dot = container.querySelector('[aria-hidden="true"]');
    expect(dot?.className).toContain("bg-[#B8914E]");
  });

  it("uses muted dot color for neutral states", () => {
    const { container } = render(
      <NextOwnerChip
        stateInfo={makeStateInfo("submitted", "Awaiting system intake", "neutral")}
      />
    );
    const dot = container.querySelector('[aria-hidden="true"]');
    expect(dot?.className).toContain("bg-fg-muted");
  });
});
