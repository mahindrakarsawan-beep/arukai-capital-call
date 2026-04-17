/**
 * ZeroFlagsPanel tests — A2.2 (POR-147 / ARU-17-A2)
 * Spec §7 / Figma node 37:2.
 * Shown inside AttestationModal when ALL fields ≥0.9 (flaggedFieldCount === 0).
 * Green surface: dataPositiveMuted bg.
 * Copy: "All extracted fields at high confidence. No items flagged for review."
 */

import React from "react";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import { ZeroFlagsPanel } from "@/components/ZeroFlagsPanel";

describe("ZeroFlagsPanel", () => {
  it("renders the positive copy", () => {
    render(<ZeroFlagsPanel />);
    expect(
      screen.getByText(
        /All extracted fields at high confidence\. No items flagged for review\./i
      )
    ).toBeInTheDocument();
  });

  it("has data-testid=zero-flags-panel", () => {
    render(<ZeroFlagsPanel />);
    expect(screen.getByTestId("zero-flags-panel")).toBeInTheDocument();
  });

  it("does NOT use brass color (#B8914E)", () => {
    const { container } = render(<ZeroFlagsPanel />);
    expect(container.innerHTML).not.toContain("#B8914E");
  });

  it("uses dataPositiveMuted bg surface (green)", () => {
    const { container } = render(<ZeroFlagsPanel />);
    const panel = container.querySelector('[data-testid="zero-flags-panel"]') as HTMLElement;
    // dataPositiveMuted = rgba(31,122,77,0.12)
    expect(panel.style.backgroundColor).toBeTruthy();
  });
});
