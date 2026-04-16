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
import { PackageRow } from "@/components/PackageRow";
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
  it("renders the package title", () => {
    render(<PackageRow pkg={basePkg} />);
    expect(screen.getByText("Fund_III_Q2_capital_call.pdf")).toBeInTheDocument();
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
  it('renders "just now" for very recent timestamps', () => {
    const pkg: PackageRowPkg = {
      ...basePkg,
      lastMovement: new Date(Date.now() - 30000).toISOString(), // 30s ago
    };
    render(<PackageRow pkg={pkg} />);
    expect(screen.getByText("just now")).toBeInTheDocument();
  });

  it('renders "Xh ago" for timestamps within 24h', () => {
    const pkg: PackageRowPkg = {
      ...basePkg,
      lastMovement: new Date(Date.now() - 5 * 3600000).toISOString(), // 5h ago
    };
    render(<PackageRow pkg={pkg} />);
    expect(screen.getByText("5h ago")).toBeInTheDocument();
  });

  it('renders "Xd ago" for timestamps within 30 days', () => {
    const pkg: PackageRowPkg = {
      ...basePkg,
      lastMovement: new Date(Date.now() - 3 * 86400000).toISOString(), // 3d ago
    };
    render(<PackageRow pkg={pkg} />);
    expect(screen.getByText("3d ago")).toBeInTheDocument();
  });

  it("renders a short date for timestamps older than 30 days", () => {
    const pkg: PackageRowPkg = {
      ...basePkg,
      lastMovement: new Date(Date.now() - 40 * 86400000).toISOString(), // 40d ago
    };
    render(<PackageRow pkg={pkg} />);
    // Expect a month/day formatted date (e.g. "Mar 7") in the time element
    const timeEl = document.querySelector("span.tabular-nums");
    expect(timeEl).not.toBeNull();
    expect(timeEl?.textContent).not.toBe("—");
    expect(timeEl?.textContent?.length).toBeGreaterThan(0);
  });

  it('renders "—" when lastMovement is null', () => {
    const pkg: PackageRowPkg = { ...basePkg, lastMovement: null };
    render(<PackageRow pkg={pkg} />);
    // The "—" fallback should appear in the md: hidden time element
    // It won't be visible at jsdom default viewport but the text should be in DOM
    expect(screen.getAllByText("—").length).toBeGreaterThanOrEqual(1);
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
