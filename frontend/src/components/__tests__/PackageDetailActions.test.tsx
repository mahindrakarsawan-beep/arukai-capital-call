/**
 * PackageDetailActions tests — A2 (POR-147 / ARU-17-A2)
 * Tests: claim/release buttons per role+claim state, route-for-approval per state+role,
 *        attest/reject buttons for approver, API calls via mock fetch.
 */

import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";
import { PackageDetailActions } from "@/app/documents/[id]/PackageDetailActions";

// Mock next/navigation
jest.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: jest.fn(), push: jest.fn() }),
}));

// Mock fetch globally
global.fetch = jest.fn();

const baseProps = {
  documentId: "pkg-001",
  packageTitle: "Fund III — Q2 Capital Call",
};

function mockFetchSuccess() {
  (global.fetch as jest.Mock).mockResolvedValue({
    ok: true,
    json: async () => ({ token: "test-token" }),
  });
}

beforeEach(() => {
  jest.clearAllMocks();
});

describe("PackageDetailActions — approver role, routed_for_approval state", () => {
  it("shows Attest approval and Record rejection buttons", () => {
    render(
      <PackageDetailActions
        {...baseProps}
        userRole="admin"
        packageState="pending_review"
      />
    );
    expect(
      screen.getByRole("button", { name: /attest approval/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /record rejection/i })
    ).toBeInTheDocument();
  });

  it("Attest approval button has brass background", () => {
    render(
      <PackageDetailActions
        {...baseProps}
        userRole="admin"
        packageState="pending_review"
      />
    );
    const btn = screen.getByRole("button", { name: /attest approval/i });
    expect(btn).toHaveStyle({ backgroundColor: "#B8914E" });
  });

  it("Record rejection button does NOT have brass background", () => {
    render(
      <PackageDetailActions
        {...baseProps}
        userRole="admin"
        packageState="pending_review"
      />
    );
    const btn = screen.getByRole("button", { name: /record rejection/i });
    expect(btn).not.toHaveStyle({ backgroundColor: "#B8914E" });
  });
});

describe("PackageDetailActions — reviewer role, claim/release", () => {
  it("shows Claim to review button for unclaimed package (reviewer)", () => {
    render(
      <PackageDetailActions
        {...baseProps}
        userRole="reviewer"
        packageState="pending_review"
        claimState="unclaimed"
      />
    );
    expect(
      screen.getByRole("button", { name: /claim to review/i })
    ).toBeInTheDocument();
  });

  it("shows Release claim button when package claimed by current user", () => {
    render(
      <PackageDetailActions
        {...baseProps}
        userRole="reviewer"
        packageState="pending_review"
        claimState="claimed_by_you"
      />
    );
    expect(
      screen.getByRole("button", { name: /release claim/i })
    ).toBeInTheDocument();
  });

  it("does NOT show claim/release buttons when claimed by other reviewer", () => {
    render(
      <PackageDetailActions
        {...baseProps}
        userRole="reviewer"
        packageState="pending_review"
        claimState="claimed_by_other"
      />
    );
    expect(
      screen.queryByRole("button", { name: /claim to review/i })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /release claim/i })
    ).not.toBeInTheDocument();
  });

  it("shows Route for approval button for reviewer in under_review state", () => {
    render(
      <PackageDetailActions
        {...baseProps}
        userRole="reviewer"
        packageState="pending_review"
        claimState="claimed_by_you"
      />
    );
    expect(
      screen.getByRole("button", { name: /route for approval/i })
    ).toBeInTheDocument();
  });
});

describe("PackageDetailActions — API calls", () => {
  it("calls claim endpoint when Claim to review clicked", async () => {
    // First fetch = token, second = claim API
    (global.fetch as jest.Mock)
      .mockResolvedValueOnce({ ok: true, json: async () => ({ token: "test-token" }) })
      .mockResolvedValueOnce({ ok: true, json: async () => ({}) });

    render(
      <PackageDetailActions
        {...baseProps}
        userRole="reviewer"
        packageState="pending_review"
        claimState="unclaimed"
      />
    );

    fireEvent.click(screen.getByRole("button", { name: /claim to review/i }));

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/packages/pkg-001/claim"),
        expect.objectContaining({ method: "POST" })
      );
    });
  });

  it("calls release endpoint when Release claim clicked", async () => {
    (global.fetch as jest.Mock)
      .mockResolvedValueOnce({ ok: true, json: async () => ({ token: "test-token" }) })
      .mockResolvedValueOnce({ ok: true, json: async () => ({}) });

    render(
      <PackageDetailActions
        {...baseProps}
        userRole="reviewer"
        packageState="pending_review"
        claimState="claimed_by_you"
      />
    );

    fireEvent.click(screen.getByRole("button", { name: /release claim/i }));

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/packages/pkg-001/release"),
        expect.objectContaining({ method: "POST" })
      );
    });
  });

  it("calls transition endpoint when Route for approval clicked", async () => {
    (global.fetch as jest.Mock)
      .mockResolvedValueOnce({ ok: true, json: async () => ({ token: "test-token" }) })
      .mockResolvedValueOnce({ ok: true, json: async () => ({}) });

    render(
      <PackageDetailActions
        {...baseProps}
        userRole="reviewer"
        packageState="pending_review"
        claimState="claimed_by_you"
      />
    );

    fireEvent.click(screen.getByRole("button", { name: /route for approval/i }));

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/packages/pkg-001/transition"),
        expect.objectContaining({ method: "POST" })
      );
    });
  });
});

describe("PackageDetailActions — no actions for terminal state", () => {
  it("shows no action buttons for approved state", () => {
    render(
      <PackageDetailActions
        {...baseProps}
        userRole="admin"
        packageState="approved"
      />
    );
    expect(
      screen.queryByRole("button", { name: /attest/i })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /record rejection/i })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /claim/i })
    ).not.toBeInTheDocument();
  });
});
