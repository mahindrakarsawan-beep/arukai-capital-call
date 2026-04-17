/**
 * IntakeCeremony tests — C1 (POR-147 / ARU-17-C1)
 * TDD: failing tests committed before implementation (Miller gate per TDD workflow).
 *
 * Coverage:
 *   - Renders all 4 steps
 *   - Active step has brass text (data-active + style)
 *   - Completed steps (index < activeStep) show checkmark
 *   - Inactive future steps show muted text
 *   - Arukai wordmark rendered at bottom
 *   - overlay visible when visible=true, hidden (null) when false
 *   - reducedMotion prop does not break rendering
 */

import React from "react";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import { IntakeCeremony } from "@/components/IntakeCeremony";

const STEP_LABELS = [
  "Package received",
  "Classifying materials",
  "Extracting key fields",
  "Intake complete",
];

describe("IntakeCeremony — structure", () => {
  it("renders all 4 step labels when visible", () => {
    render(<IntakeCeremony visible activeStep={1} reducedMotion={false} />);
    STEP_LABELS.forEach((label) => {
      expect(screen.getByText(label)).toBeInTheDocument();
    });
  });

  it("renders the Arukai wordmark at the bottom", () => {
    render(<IntakeCeremony visible activeStep={1} reducedMotion={false} />);
    // Wordmark may appear as text node
    expect(screen.getByText(/arukai/i)).toBeInTheDocument();
  });

  it("renders step numbers 01–04", () => {
    render(<IntakeCeremony visible activeStep={2} reducedMotion={false} />);
    ["01", "02", "03", "04"].forEach((n) => {
      expect(screen.getByText(n)).toBeInTheDocument();
    });
  });

  it("returns null when visible=false", () => {
    const { container } = render(
      <IntakeCeremony visible={false} activeStep={1} reducedMotion={false} />
    );
    expect(container.firstChild).toBeNull();
  });
});

describe("IntakeCeremony — active step brass", () => {
  it("marks the active step row with data-active=true", () => {
    render(<IntakeCeremony visible activeStep={2} reducedMotion={false} />);
    const activeRow = document.querySelector('[data-active="true"]');
    expect(activeRow).toBeInTheDocument();
  });

  it("active step row text includes brandBrass color via inline style", () => {
    render(<IntakeCeremony visible activeStep={1} reducedMotion={false} />);
    // The step row for index 1 should carry inline brass color
    const activeRow = document.querySelector('[data-active="true"]');
    expect(activeRow).toBeTruthy();
    // The number span inside should have brass color
    const numberSpan = activeRow?.querySelector("[data-step-number]");
    expect(numberSpan).toBeInTheDocument();
    expect(numberSpan).toHaveStyle({ color: "#B8914E" });
  });

  it("inactive future steps do NOT have brass color", () => {
    render(<IntakeCeremony visible activeStep={1} reducedMotion={false} />);
    // Step 3 is in the future — its row should not be active
    const rows = document.querySelectorAll("[data-step-row]");
    // row index 2 (step 3) should not be active
    const step3Row = rows[2];
    expect(step3Row).not.toHaveAttribute("data-active", "true");
  });
});

describe("IntakeCeremony — completed steps checkmark", () => {
  it("shows checkmark icon for completed steps (index < activeStep)", () => {
    render(<IntakeCeremony visible activeStep={3} reducedMotion={false} />);
    // Steps 1 and 2 are completed; expect checkmark icons
    const checkmarks = document.querySelectorAll("[data-checkmark]");
    expect(checkmarks.length).toBe(2);
  });

  it("does not show checkmark for active step", () => {
    render(<IntakeCeremony visible activeStep={2} reducedMotion={false} />);
    const activeRow = document.querySelector('[data-active="true"]');
    const checkmark = activeRow?.querySelector("[data-checkmark]");
    expect(checkmark).not.toBeInTheDocument();
  });

  it("does not show checkmarks when on first step", () => {
    render(<IntakeCeremony visible activeStep={1} reducedMotion={false} />);
    const checkmarks = document.querySelectorAll("[data-checkmark]");
    expect(checkmarks.length).toBe(0);
  });
});

describe("IntakeCeremony — reduced motion", () => {
  it("renders correctly with reducedMotion=true without throwing", () => {
    expect(() => {
      render(<IntakeCeremony visible activeStep={2} reducedMotion />);
    }).not.toThrow();
  });

  it("with reducedMotion, still renders all 4 steps", () => {
    render(<IntakeCeremony visible activeStep={2} reducedMotion />);
    STEP_LABELS.forEach((label) => {
      expect(screen.getByText(label)).toBeInTheDocument();
    });
  });
});

describe("IntakeCeremony — activeStep guard", () => {
  it("handles out-of-range activeStep (5) without crashing", () => {
    expect(() => {
      render(<IntakeCeremony visible activeStep={5} reducedMotion={false} />);
    }).not.toThrow();
  });

  it("handles activeStep=0 without crashing", () => {
    expect(() => {
      render(<IntakeCeremony visible activeStep={0} reducedMotion={false} />);
    }).not.toThrow();
  });
});
