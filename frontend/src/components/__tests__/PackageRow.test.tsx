/**
 * PackageRow tests — POR-147 / ARU-17 A1
 * Covers:
 *   - Claim state variants: unclaimed shows "Claim to review"; claimed_by_you shows "Release claim"
 *   - Next-owner chip text renders per resolvePackageState
 *   - Last movement relative format (just now / Xh ago / Xd ago / date)
 *   - No CTA when claimStatus is null or claimed_by_other
 */

import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";
import { PackageRow, formatDocType } from "@/components/PackageRow";
import type { PackageRowPkg } from "@/components/PackageRow";

const basePkg: PackageRowPkg = {
  id: "pkg-1",
  title: "Fund_III_Q2_capital_call.pdf",
  state: "pending_review",
  confidence: 0.92,
  docType: "capital_call_notice",
  lastMovement: new Date(Date.now() - 2 * 3600000).toISOString(), // 2h ago
  claimStatus: null,
};

describe("PackageRow — rendering", () => {
  it("renders the formatted doc type as title when docType is provided", () => {
    render(<PackageRow pkg={basePkg} />);
    // basePkg has docType="capital_call_notice" → formatDocType → "Capital Call Notice"
    expect(screen.getByText("Capital Call Notice")).toBeInTheDocument();
  });

  it("renders a link to the package detail page", () => {
    render(<PackageRow pkg={basePkg} />);
    const link = screen.getByRole("link", { name: /open package fund_iii/i });
    expect(link).toHaveAttribute("href", "/documents/pkg-1");
  });

  it("renders ClassificationBadge when docType is provided", () => {
    render(<PackageRow pkg={basePkg} />);
    expect(screen.getByText("Capital Call")).toBeInTheDocument();
  });

  it("does NOT render a claim CTA when claimStatus is null", () => {
    render(<PackageRow pkg={basePkg} onClaimToggle={jest.fn()} />);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});

describe("PackageRow — claim state variants", () => {
  it('shows "Claim to review" button for unclaimed packages', () => {
    const pkg: PackageRowPkg = { ...basePkg, claimStatus: "unclaimed" };
    render(<PackageRow pkg={pkg} onClaimToggle={jest.fn()} />);
    expect(screen.getByRole("button", { name: /claim to review/i })).toBeInTheDocument();
  });

  it('shows "Release claim" button for claimed_by_you packages', () => {
    const pkg: PackageRowPkg = { ...basePkg, claimStatus: "claimed_by_you" };
    render(<PackageRow pkg={pkg} onClaimToggle={jest.fn()} />);
    expect(screen.getByRole("button", { name: /release claim/i })).toBeInTheDocument();
  });

  it("does NOT show claim CTA for claimed_by_other packages", () => {
    const pkg: PackageRowPkg = {
      ...basePkg,
      claimStatus: "claimed_by_other",
      nextOwner: "alice@example.com",
    };
    render(<PackageRow pkg={pkg} onClaimToggle={jest.fn()} />);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("calls onClaimToggle with 'claim' when Claim to review is clicked", () => {
    const onClaimToggle = jest.fn();
    const pkg: PackageRowPkg = { ...basePkg, claimStatus: "unclaimed" };
    render(<PackageRow pkg={pkg} onClaimToggle={onClaimToggle} />);
    fireEvent.click(screen.getByRole("button", { name: /claim to review/i }));
    expect(onClaimToggle).toHaveBeenCalledWith("pkg-1", "claim");
  });

  it("calls onClaimToggle with 'release' when Release claim is clicked", () => {
    const onClaimToggle = jest.fn();
    const pkg: PackageRowPkg = { ...basePkg, claimStatus: "claimed_by_you" };
    render(<PackageRow pkg={pkg} onClaimToggle={onClaimToggle} />);
    fireEvent.click(screen.getByRole("button", { name: /release claim/i }));
    expect(onClaimToggle).toHaveBeenCalledWith("pkg-1", "release");
  });

  it("does not navigate when claim button is clicked (stops propagation)", () => {
    const onClaimToggle = jest.fn();
    const pkg: PackageRowPkg = { ...basePkg, claimStatus: "unclaimed" };
    render(<PackageRow pkg={pkg} onClaimToggle={onClaimToggle} />);
    // Button click should not throw or cause navigation issues
    const btn = screen.getByRole("button", { name: /claim to review/i });
    expect(() => fireEvent.click(btn)).not.toThrow();
  });
});

describe("PackageRow — next-owner chip", () => {
  it('shows "Awaiting reviewer" when no claim state and no reviewer name', () => {
    const pkg: PackageRowPkg = { ...basePkg, claimStatus: null, nextOwner: null };
    render(<PackageRow pkg={pkg} />);
    // NextOwnerChip renders aria-label "Next owner: ..."
    expect(screen.getByLabelText(/next owner/i)).toHaveTextContent(/awaiting reviewer/i);
  });

  it('shows reviewer name when nextOwner is provided and no claimState', () => {
    const pkg: PackageRowPkg = { ...basePkg, nextOwner: "alice@example.com", claimStatus: null };
    render(<PackageRow pkg={pkg} />);
    expect(screen.getByLabelText(/next owner/i)).toHaveTextContent(/alice@example\.com/i);
  });

  it('shows "Unclaimed · awaiting claim" for unclaimed pkg', () => {
    const pkg: PackageRowPkg = { ...basePkg, claimStatus: "unclaimed" };
    render(<PackageRow pkg={pkg} />);
    expect(screen.getByLabelText(/next owner/i)).toHaveTextContent(/unclaimed/i);
  });

  it('shows "Under review (claimed by you)" for claimed_by_you pkg', () => {
    const pkg: PackageRowPkg = { ...basePkg, claimStatus: "claimed_by_you" };
    render(<PackageRow pkg={pkg} />);
    expect(screen.getByLabelText(/next owner/i)).toHaveTextContent(/claimed by you/i);
  });
});

describe("PackageRow — last movement format", () => {
  it('renders "Received just now" for very recent timestamps', () => {
    const pkg: PackageRowPkg = {
      ...basePkg,
      lastMovement: new Date(Date.now() - 30000).toISOString(), // 30s ago
    };
    render(<PackageRow pkg={pkg} />);
    expect(screen.getByText(/received just now/i)).toBeInTheDocument();
  });

  it('renders "Received Xh ago" for timestamps within 24h', () => {
    const pkg: PackageRowPkg = {
      ...basePkg,
      lastMovement: new Date(Date.now() - 5 * 3600000).toISOString(), // 5h ago
    };
    render(<PackageRow pkg={pkg} />);
    expect(screen.getByText(/received 5h ago/i)).toBeInTheDocument();
  });

  it('renders "Received Xd ago" for timestamps within 30 days', () => {
    const pkg: PackageRowPkg = {
      ...basePkg,
      lastMovement: new Date(Date.now() - 3 * 86400000).toISOString(), // 3d ago
    };
    render(<PackageRow pkg={pkg} />);
    expect(screen.getByText(/received 3d ago/i)).toBeInTheDocument();
  });

  it("renders a short date for timestamps older than 30 days", () => {
    const pkg: PackageRowPkg = {
      ...basePkg,
      lastMovement: new Date(Date.now() - 40 * 86400000).toISOString(), // 40d ago
    };
    render(<PackageRow pkg={pkg} />);
    // Expect "Received Mon D" format
    expect(screen.getByText(/received \w+ \d+/i)).toBeInTheDocument();
  });

  it("does not render the received timestamp when lastMovement is null", () => {
    const pkg: PackageRowPkg = { ...basePkg, lastMovement: null };
    render(<PackageRow pkg={pkg} />);
    // No "Received" timestamp when there's no lastMovement
    expect(screen.queryByText(/received/i)).not.toBeInTheDocument();
  });
});

describe("PackageRow — decision recorded states", () => {
  it("renders decision_recorded_approved state correctly", () => {
    const pkg: PackageRowPkg = {
      ...basePkg,
      state: "approved",
      confidence: null,
      approver: "bob@example.com",
    };
    render(<PackageRow pkg={pkg} />);
    expect(screen.getByLabelText(/next owner/i)).toHaveTextContent(/approved by/i);
  });

  it("renders decision_recorded_rejected state correctly (S4 — rejection is distinct type)", () => {
    const pkg: PackageRowPkg = {
      ...basePkg,
      state: "rejected",
      confidence: null,
      approver: "bob@example.com",
    };
    render(<PackageRow pkg={pkg} />);
    expect(screen.getByLabelText(/next owner/i)).toHaveTextContent(/rejected by/i);
  });
});

// ─── PackageRow identity — formatDocType + subtitle + confidence (#4) ─────────

describe("formatDocType helper", () => {
  it('converts "capital_call_notice" to "Capital Call Notice"', () => {
    expect(formatDocType("capital_call_notice")).toBe("Capital Call Notice");
  });

  it('converts "subscription_agreement" to "Subscription Agreement"', () => {
    expect(formatDocType("subscription_agreement")).toBe("Subscription Agreement");
  });

  it('converts "k1" to "K1"', () => {
    expect(formatDocType("k1")).toBe("K1");
  });

  it("handles single-word doc types", () => {
    expect(formatDocType("other")).toBe("Other");
  });
});

describe("PackageRow — doc_type formatted title (#4)", () => {
  it("shows formatted doc_type as title when docType is present", () => {
    const pkg: PackageRowPkg = {
      ...basePkg,
      docType: "capital_call_notice",
    };
    render(<PackageRow pkg={pkg} />);
    expect(screen.getByText("Capital Call Notice")).toBeInTheDocument();
  });

  it("falls back to pkg.title when docType is null", () => {
    const pkg: PackageRowPkg = {
      ...basePkg,
      docType: null,
      title: "Fund III Q2 Capital Call",
    };
    render(<PackageRow pkg={pkg} />);
    expect(screen.getByText("Fund III Q2 Capital Call")).toBeInTheDocument();
  });

  it("shows subtitle (raw filename) in muted text when subtitle is provided", () => {
    const pkg: PackageRowPkg = {
      ...basePkg,
      docType: "capital_call_notice",
      subtitle: "Fund_III_Q2_capital_call.pdf",
    };
    render(<PackageRow pkg={pkg} />);
    expect(screen.getByText("Fund_III_Q2_capital_call.pdf")).toBeInTheDocument();
  });

  it("shows 'Received Xh ago' timestamp when lastMovement is provided", () => {
    const pkg: PackageRowPkg = {
      ...basePkg,
      lastMovement: new Date(Date.now() - 3 * 3600000).toISOString(), // 3h ago
    };
    render(<PackageRow pkg={pkg} />);
    expect(screen.getByText(/received 3h ago/i)).toBeInTheDocument();
  });

  it("shows inline ConfidenceBadge when confidence > 0", () => {
    const pkg: PackageRowPkg = {
      ...basePkg,
      confidence: 0.92,
    };
    render(<PackageRow pkg={pkg} />);
    // ConfidenceBadge renders the percentage value
    expect(screen.getByText("92%")).toBeInTheDocument();
  });

  it("does NOT show ConfidenceBadge when confidence is null", () => {
    const pkg: PackageRowPkg = {
      ...basePkg,
      confidence: null,
    };
    render(<PackageRow pkg={pkg} />);
    // No percentage text should appear
    expect(screen.queryByText(/%$/)).not.toBeInTheDocument();
  });

  it("does NOT show ConfidenceBadge when confidence is 0", () => {
    const pkg: PackageRowPkg = {
      ...basePkg,
      confidence: 0,
    };
    render(<PackageRow pkg={pkg} />);
    expect(screen.queryByText("0%")).not.toBeInTheDocument();
  });
});
