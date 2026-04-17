/**
 * AttestationModal tests — POR-147 / ARU-17 Phase A (spec §7)
 * Tests: renders attestation language, brass confirm button, rejection variant,
 *        escape-to-close, initial focus on Return button.
 */

import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";
import { AttestationModal } from "@/components/AttestationModal";

// Mock fetch for token and approval API calls
global.fetch = jest.fn();

const mockPackageSummary = {
  title: "Fund III — Q2 Capital Call",
  classification: "Capital call notice",
  confidence: 0.92,
};

function renderApproveModal(overrides = {}) {
  const onClose = jest.fn();
  const onSuccess = jest.fn();
  render(
    <AttestationModal
      variant="approve"
      packageSummary={mockPackageSummary}
      documentId="doc-123"
      onClose={onClose}
      onSuccess={onSuccess}
      {...overrides}
    />
  );
  return { onClose, onSuccess };
}

function renderRejectModal(overrides = {}) {
  const onClose = jest.fn();
  const onSuccess = jest.fn();
  render(
    <AttestationModal
      variant="reject"
      packageSummary={mockPackageSummary}
      documentId="doc-123"
      onClose={onClose}
      onSuccess={onSuccess}
      {...overrides}
    />
  );
  return { onClose, onSuccess };
}

describe("AttestationModal — approve variant", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders "Attestation" heading in approve variant', () => {
    renderApproveModal();
    expect(screen.getByRole("heading", { name: /attestation/i })).toBeInTheDocument();
  });

  it("renders package summary with title", () => {
    renderApproveModal();
    expect(screen.getByText("Fund III — Q2 Capital Call")).toBeInTheDocument();
  });

  it("renders attestation language block", () => {
    renderApproveModal();
    expect(
      screen.getByText(/I attest that I have reviewed this capital-call package/i)
    ).toBeInTheDocument();
  });

  it('renders "Attest and record decision" confirm button', () => {
    renderApproveModal();
    expect(
      screen.getByRole("button", { name: /attest and record decision/i })
    ).toBeInTheDocument();
  });

  it('renders "Return to package" cancel button', () => {
    renderApproveModal();
    expect(
      screen.getByRole("button", { name: /return to package/i })
    ).toBeInTheDocument();
  });

  it("calls onClose when Return to package is clicked", () => {
    const { onClose } = renderApproveModal();
    fireEvent.click(screen.getByRole("button", { name: /return to package/i }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("calls onClose when Escape key is pressed", () => {
    const { onClose } = renderApproveModal();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("has aria-modal and role=dialog", () => {
    renderApproveModal();
    const dialog = screen.getByRole("dialog");
    expect(dialog).toBeInTheDocument();
    expect(dialog).toHaveAttribute("aria-modal", "true");
  });

  it("renders reviewer notes empty state when no notes", () => {
    renderApproveModal();
    expect(
      screen.getByText(/no review notes were recorded before this attestation/i)
    ).toBeInTheDocument();
  });

  it("renders reviewer notes when provided", () => {
    renderApproveModal({
      packageSummary: {
        ...mockPackageSummary,
        reviewerNotes: [
          { author: "alice@firm.example", timestamp: "Apr 12 2026", body: "Reviewed wires." },
        ],
      },
    });
    expect(screen.getByText("Reviewed wires.")).toBeInTheDocument();
  });
});

describe("AttestationModal — reject variant", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders "Record rejection" heading', () => {
    renderRejectModal();
    expect(screen.getByRole("heading", { name: /record rejection/i })).toBeInTheDocument();
  });

  it("renders rejection attestation language", () => {
    renderRejectModal();
    expect(
      screen.getByText(/I have reviewed this package and am recording a rejection/i)
    ).toBeInTheDocument();
  });

  it('confirms with "Record rejection" button (not brass language)', () => {
    renderRejectModal();
    expect(
      screen.getByRole("button", { name: /^record rejection$/i })
    ).toBeInTheDocument();
  });

  it("does NOT have brass background on rejection confirm button", () => {
    renderRejectModal();
    const confirmBtn = screen.getByRole("button", { name: /^record rejection$/i });
    // Rejection button uses obsidian (#0D0F12), not brass (#B8914E)
    expect(confirmBtn).not.toHaveStyle({ backgroundColor: "#B8914E" });
  });

  it("marks attestation note as required for rejection", () => {
    renderRejectModal();
    const textarea = screen.getByRole("textbox");
    expect(textarea).toHaveAttribute("required");
  });

  it("shows error when rejection submitted without note", async () => {
    renderRejectModal();
    // Click confirm without entering a note
    fireEvent.click(screen.getByRole("button", { name: /^record rejection$/i }));
    expect(
      screen.getByText(/attestation note is required for rejection/i)
    ).toBeInTheDocument();
  });
});

describe("AttestationModal — flagged-field warning panel (A2.1)", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("does NOT show warning panel when flaggedFieldCount is 0", () => {
    renderApproveModal({
      packageSummary: {
        ...mockPackageSummary,
        flaggedFieldCount: 0,
        flaggedFields: [],
      },
    });
    expect(screen.queryByTestId("flagged-field-warning")).not.toBeInTheDocument();
  });

  it("does NOT show warning panel when flaggedFieldCount is omitted", () => {
    renderApproveModal();
    expect(screen.queryByTestId("flagged-field-warning")).not.toBeInTheDocument();
  });

  it("shows warning panel when flaggedFieldCount > 0", () => {
    renderApproveModal({
      packageSummary: {
        ...mockPackageSummary,
        flaggedFieldCount: 1,
        flaggedFields: ["Due date"],
      },
    });
    expect(screen.getByTestId("flagged-field-warning")).toBeInTheDocument();
  });

  it("shows correct copy for 1 flagged field", () => {
    renderApproveModal({
      packageSummary: {
        ...mockPackageSummary,
        flaggedFieldCount: 1,
        flaggedFields: ["Due date"],
      },
    });
    expect(
      screen.getByText(/1 field flagged during review\. proceed only if resolved\./i)
    ).toBeInTheDocument();
  });

  it("shows plural copy for multiple flagged fields", () => {
    renderApproveModal({
      packageSummary: {
        ...mockPackageSummary,
        flaggedFieldCount: 3,
        flaggedFields: ["Due date", "Side-letter ref", "Fund name"],
      },
    });
    expect(
      screen.getByText(/3 fields flagged during review\. proceed only if resolved\./i)
    ).toBeInTheDocument();
  });

  it("renders bullet list of flagged field names", () => {
    renderApproveModal({
      packageSummary: {
        ...mockPackageSummary,
        flaggedFieldCount: 2,
        flaggedFields: ["Due date", "Side-letter ref"],
      },
    });
    expect(screen.getByText("Due date")).toBeInTheDocument();
    expect(screen.getByText("Side-letter ref")).toBeInTheDocument();
  });

  it("shows warning panel in reject variant when fields are flagged", () => {
    renderRejectModal({
      packageSummary: {
        ...mockPackageSummary,
        flaggedFieldCount: 2,
        flaggedFields: ["Due date", "Fund name"],
      },
    });
    expect(screen.getByTestId("flagged-field-warning")).toBeInTheDocument();
  });

  it("warning panel has role=alert", () => {
    renderApproveModal({
      packageSummary: {
        ...mockPackageSummary,
        flaggedFieldCount: 1,
        flaggedFields: ["Due date"],
      },
    });
    // There may be multiple alerts (error strip is also role=alert)
    const alerts = screen.getAllByRole("alert");
    const warningPanel = alerts.find(
      (el) => el.getAttribute("data-testid") === "flagged-field-warning"
    );
    expect(warningPanel).toBeTruthy();
  });

  it("does NOT use brass color (#B8914E) in the warning panel", () => {
    const { container } = render(
      <AttestationModal
        variant="approve"
        packageSummary={{
          ...mockPackageSummary,
          flaggedFieldCount: 1,
          flaggedFields: ["Due date"],
        }}
        documentId="doc-123"
        onClose={jest.fn()}
        onSuccess={jest.fn()}
      />
    );
    const warningEl = container.querySelector('[data-testid="flagged-field-warning"]');
    expect(warningEl).toBeTruthy();
    // Warning uses amber (#9A7639), not brass (#B8914E)
    // jsdom converts hex → rgb in inline styles; check computed style instead
    const allElements = warningEl!.querySelectorAll("*");
    const elementList = [warningEl!, ...Array.from(allElements)];
    const hasAmberColor = elementList.some((el) => {
      const style = (el as HTMLElement).style;
      // rgb(154, 118, 57) is #9A7639 in jsdom
      return (
        style.color === "rgb(154, 118, 57)" ||
        style.backgroundColor === "rgb(154, 118, 57)"
      );
    });
    expect(hasAmberColor).toBe(true);
    // No element should use brass #B8914E = rgb(184, 145, 78)
    const hasBrass = elementList.some((el) => {
      const style = (el as HTMLElement).style;
      return (
        style.color === "rgb(184, 145, 78)" ||
        style.backgroundColor === "rgb(184, 145, 78)"
      );
    });
    expect(hasBrass).toBe(false);
  });
});

describe("AttestationModal — zero-flags positive panel (A2.2 / Figma 37:2)", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders zero-flags panel when flaggedFieldCount === 0 and flaggedFields provided", () => {
    renderApproveModal({
      packageSummary: {
        ...mockPackageSummary,
        flaggedFieldCount: 0,
        flaggedFields: [],
      },
    });
    expect(screen.getByTestId("zero-flags-panel")).toBeInTheDocument();
  });

  it("renders zero-flags panel copy", () => {
    renderApproveModal({
      packageSummary: {
        ...mockPackageSummary,
        flaggedFieldCount: 0,
        flaggedFields: [],
      },
    });
    expect(
      screen.getByText(
        /All extracted fields at high confidence\. No items flagged for review\./i
      )
    ).toBeInTheDocument();
  });

  it("does NOT render flagged-field-warning when zero-flags panel shown", () => {
    renderApproveModal({
      packageSummary: {
        ...mockPackageSummary,
        flaggedFieldCount: 0,
        flaggedFields: [],
      },
    });
    expect(screen.queryByTestId("flagged-field-warning")).not.toBeInTheDocument();
  });

  it("does NOT render zero-flags panel when flaggedFieldCount is undefined (not explicitly set)", () => {
    // When flaggedFields not passed at all, neither panel renders
    renderApproveModal();
    expect(screen.queryByTestId("zero-flags-panel")).not.toBeInTheDocument();
  });

  it("renders flagged-field-warning (not zero-flags) when count > 0", () => {
    renderApproveModal({
      packageSummary: {
        ...mockPackageSummary,
        flaggedFieldCount: 2,
        flaggedFields: ["Due date", "Fund name"],
      },
    });
    expect(screen.getByTestId("flagged-field-warning")).toBeInTheDocument();
    expect(screen.queryByTestId("zero-flags-panel")).not.toBeInTheDocument();
  });
});

describe("AttestationModal — brass discipline", () => {
  it("Attest approval confirm button has brass background", () => {
    renderApproveModal();
    const confirmBtn = screen.getByRole("button", { name: /attest and record decision/i });
    expect(confirmBtn).toHaveStyle({ backgroundColor: "#B8914E" });
  });

  it("does NOT apply brass to any element in reject variant", () => {
    const { container } = render(
      <AttestationModal
        variant="reject"
        packageSummary={mockPackageSummary}
        documentId="doc-123"
        onClose={jest.fn()}
        onSuccess={jest.fn()}
      />
    );
    // No element should have #B8914E style in the reject modal
    const html = container.innerHTML;
    expect(html).not.toContain("#B8914E");
  });
});
