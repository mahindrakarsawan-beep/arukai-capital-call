/**
 * IntakeCeremony tests — C1 (POR-147 / ARU-17-C1) + POR-150
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
 *   - POR-150: real AI data in step labels via stepData prop
 */

import React from "react";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import { IntakeCeremony } from "@/components/IntakeCeremony";
import type { IntakeStepData } from "@/components/IntakeCeremony";

const STEP_LABELS_FALLBACK = [
  "Package received",
  "Classifying materials",
  "Extracting key fields",
  "Intake complete",
];

describe("IntakeCeremony — structure (fallback labels, no stepData)", () => {
  it("renders all 4 fallback step labels when visible and stepData is absent", () => {
    render(<IntakeCeremony visible activeStep={1} reducedMotion={false} />);
    STEP_LABELS_FALLBACK.forEach((label) => {
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
    STEP_LABELS_FALLBACK.forEach((label) => {
      expect(screen.getByText(label)).toBeInTheDocument();
    });
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// POR-150: Real AI narration via stepData prop
// ─────────────────────────────────────────────────────────────────────────────

const fullStepData: IntakeStepData = {
  receive: { filesize: "1.40 MB", mimeType: "application/pdf" },
  classify: { docType: "Capital Call Notice", confidence: 0.92, pending: false },
  extract: { totalFields: 8, maxFields: 8, flaggedCount: 1 },
  ready: { nextOwner: "reviewer" },
};

describe("IntakeCeremony — POR-150 real AI narration (stepData)", () => {
  it("step 01 shows filesize and mimeType in the label", () => {
    render(
      <IntakeCeremony
        visible
        activeStep={1}
        reducedMotion={false}
        stepData={fullStepData}
      />
    );
    const label = screen.getByTestId("step-label-1");
    expect(label).toHaveTextContent(/Document received/i);
    expect(label).toHaveTextContent(/1\.40 MB/);
    expect(label).toHaveTextContent(/application\/pdf/);
  });

  it("step 02 shows classified doc type and confidence when classification is ready", () => {
    render(
      <IntakeCeremony
        visible
        activeStep={2}
        reducedMotion={false}
        stepData={fullStepData}
      />
    );
    const label = screen.getByTestId("step-label-2");
    expect(label).toHaveTextContent(/Classified as Capital Call Notice/i);
    expect(label).toHaveTextContent(/confidence 92%/i);
  });

  it("step 02 shows 'Classifying…' when classify.pending is true", () => {
    const pendingData: IntakeStepData = {
      ...fullStepData,
      classify: { pending: true },
    };
    render(
      <IntakeCeremony
        visible
        activeStep={2}
        reducedMotion={false}
        stepData={pendingData}
      />
    );
    const label = screen.getByTestId("step-label-2");
    expect(label).toHaveTextContent(/Classifying…/i);
  });

  it("step 03 shows field count and flagged count", () => {
    render(
      <IntakeCeremony
        visible
        activeStep={3}
        reducedMotion={false}
        stepData={fullStepData}
      />
    );
    const label = screen.getByTestId("step-label-3");
    expect(label).toHaveTextContent(/8 of 8 fields extracted/i);
    expect(label).toHaveTextContent(/1 flagged/i);
  });

  it("step 03 shows '0 flagged' when flaggedCount is 0", () => {
    const noFlagsData: IntakeStepData = {
      ...fullStepData,
      extract: { totalFields: 8, maxFields: 8, flaggedCount: 0 },
    };
    render(
      <IntakeCeremony
        visible
        activeStep={3}
        reducedMotion={false}
        stepData={noFlagsData}
      />
    );
    const label = screen.getByTestId("step-label-3");
    expect(label).toHaveTextContent(/0 flagged/i);
  });

  it("step 04 shows next owner in ready label", () => {
    render(
      <IntakeCeremony
        visible
        activeStep={4}
        reducedMotion={false}
        stepData={fullStepData}
      />
    );
    const label = screen.getByTestId("step-label-4");
    expect(label).toHaveTextContent(/Package ready for review/i);
    expect(label).toHaveTextContent(/awaiting reviewer/i);
  });

  it("step 04 defaults next owner to 'reviewer' when nextOwner is null", () => {
    const noOwnerData: IntakeStepData = {
      ...fullStepData,
      ready: { nextOwner: null },
    };
    render(
      <IntakeCeremony
        visible
        activeStep={4}
        reducedMotion={false}
        stepData={noOwnerData}
      />
    );
    const label = screen.getByTestId("step-label-4");
    expect(label).toHaveTextContent(/awaiting reviewer/i);
  });

  it("renders fallback labels for each step when stepData is partially absent", () => {
    // Only receive data provided — other steps fall back
    const partialData: IntakeStepData = {
      receive: { filesize: "2.10 MB", mimeType: "application/pdf" },
    };
    render(
      <IntakeCeremony
        visible
        activeStep={1}
        reducedMotion={false}
        stepData={partialData}
      />
    );
    // Step 1 should have real data
    expect(screen.getByTestId("step-label-1")).toHaveTextContent(/2\.10 MB/);
    // Step 2 should show fallback "Classifying materials"
    expect(screen.getByTestId("step-label-2")).toHaveTextContent(/Classifying materials/i);
    // Step 3 fallback
    expect(screen.getByTestId("step-label-3")).toHaveTextContent(/Extracting key fields/i);
    // Step 4 fallback
    expect(screen.getByTestId("step-label-4")).toHaveTextContent(/Intake complete/i);
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
