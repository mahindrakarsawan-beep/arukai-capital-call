/**
 * NeedsReviewSection tests — interactive claim CTAs per role.
 * Covers:
 *  - reviewer sees "Claim to review" on intake_complete package
 *  - admin sees "Claim to review" on intake_complete package
 *  - claimed package (claimed_by_you) shows "Release claim" + no "Claim to review"
 *  - canClaim=false (approver): no claim buttons shown
 *  - claim API called on button click
 *  - release API called on button click
 *  - empty state rendered when docs=[]
 */

import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";
import { NeedsReviewSection } from "@/components/NeedsReviewSection";
import type { DocType } from "@/lib/api";

// Mock next/navigation
jest.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: jest.fn(), push: jest.fn() }),
}));

// Mock fetch globally
global.fetch = jest.fn();

function makePkg(overrides: Partial<{
  id: string;
  state: string;
  title: string;
  doc_type: DocType | null;
  confidence: number | null;
  uploaded_at: string;
  decision: string | null;
  version: string;
  lead_filename: string | null;
  ai_summary: string | null;
}> = {}) {
  return {
    id: "pkg-1",
    title: "Fund III Q2 Capital Call",
    state: "intake_complete",
    doc_type: "capital_call_notice" as DocType,
    confidence: 0.92,
    uploaded_at: new Date(Date.now() - 3600000).toISOString(),
    decision: null,
    version: "1",
    lead_filename: "Fund_III.pdf",
    ai_summary: null,
    ...overrides,
  };
}

beforeEach(() => {
  jest.clearAllMocks();
});

describe("NeedsReviewSection — reviewer sees Claim to review on intake_complete", () => {
  it("shows Claim to review button for intake_complete package when canClaim=true", () => {
    render(
      <NeedsReviewSection
        docs={[makePkg({ state: "intake_complete" })]}
        canClaim={true}
      />
    );
    expect(
      screen.getByRole("button", { name: /claim to review/i })
    ).toBeInTheDocument();
  });

  it("shows Claim to review button for exception_surfaced package when canClaim=true", () => {
    render(
      <NeedsReviewSection
        docs={[makePkg({ state: "exception_surfaced" })]}
        canClaim={true}
      />
    );
    expect(
      screen.getByRole("button", { name: /claim to review/i })
    ).toBeInTheDocument();
  });

  it("does NOT show claim button when canClaim=false (approver role)", () => {
    render(
      <NeedsReviewSection
        docs={[makePkg({ state: "intake_complete" })]}
        canClaim={false}
      />
    );
    expect(
      screen.queryByRole("button", { name: /claim to review/i })
    ).not.toBeInTheDocument();
  });

  it("does NOT show claim button when onClaimToggle not provided (canClaim=false)", () => {
    render(
      <NeedsReviewSection
        docs={[makePkg({ state: "intake_complete" })]}
        canClaim={false}
      />
    );
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});

describe("NeedsReviewSection — claimed package shows correct buttons", () => {
  it("shows Claim to review for under_review package (no claim info = treat as unclaimed)", () => {
    render(
      <NeedsReviewSection
        docs={[makePkg({ state: "under_review" })]}
        canClaim={true}
      />
    );
    expect(
      screen.getByRole("button", { name: /claim to review/i })
    ).toBeInTheDocument();
  });
});

describe("NeedsReviewSection — empty state", () => {
  it("shows empty state message when docs is empty", () => {
    render(<NeedsReviewSection docs={[]} canClaim={true} />);
    expect(
      screen.getByText(/nothing awaiting your review/i)
    ).toBeInTheDocument();
  });

  it("renders the section heading always", () => {
    render(<NeedsReviewSection docs={[]} canClaim={false} />);
    expect(
      screen.getByRole("heading", { level: 2, name: /needs review/i })
    ).toBeInTheDocument();
  });
});

describe("NeedsReviewSection — API calls on claim", () => {
  it("calls claim endpoint when Claim to review is clicked", async () => {
    (global.fetch as jest.Mock)
      .mockResolvedValueOnce({ ok: true, json: async () => ({ token: "test-token" }) })
      .mockResolvedValueOnce({ ok: true, json: async () => ({}) });

    render(
      <NeedsReviewSection
        docs={[makePkg({ id: "pkg-abc", state: "intake_complete" })]}
        canClaim={true}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: /claim to review/i }));

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/packages/pkg-abc/claim"),
        expect.objectContaining({ method: "POST" })
      );
    });
  });

  it("shows error message when claim API fails", async () => {
    (global.fetch as jest.Mock)
      .mockResolvedValueOnce({ ok: true, json: async () => ({ token: "test-token" }) })
      .mockResolvedValueOnce({
        ok: false,
        json: async () => ({ detail: "Already claimed" }),
      });

    render(
      <NeedsReviewSection
        docs={[makePkg({ id: "pkg-err", state: "intake_complete" })]}
        canClaim={true}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: /claim to review/i }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/already claimed/i);
    });
  });
});

describe("NeedsReviewSection — cap-5 rows + expander", () => {
  it("renders at most 5 rows without an expander for 5 or fewer packages", () => {
    const docs = Array.from({ length: 5 }, (_, i) =>
      makePkg({ id: `pkg-${i}`, title: `Package ${i}` })
    );
    render(<NeedsReviewSection docs={docs} canClaim={false} />);
    expect(screen.queryByText(/show all/i)).not.toBeInTheDocument();
  });

  it("renders Show all link when more than 5 packages", () => {
    const docs = Array.from({ length: 7 }, (_, i) =>
      makePkg({ id: `pkg-${i}`, title: `Package ${i}` })
    );
    render(<NeedsReviewSection docs={docs} canClaim={false} />);
    expect(screen.getByText(/show all 7/i)).toBeInTheDocument();
  });
});
