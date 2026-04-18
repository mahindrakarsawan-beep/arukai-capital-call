/**
 * Audit ledger page tests — POR-147 / ARU-17-B2
 * TDD: failing tests committed before implementation (Miller gate).
 *
 * Tests:
 *  - Renders "Governed record" heading (Cormorant, §9.1)
 *  - Renders role-gate label "VISIBLE TO ADMINISTRATORS AND APPROVERS"
 *  - Shows role-gate message for reviewer role
 *  - Shows empty state when no events
 *  - Renders audit events table when data present
 *  - Filter bar is rendered
 *  - Export button is rendered
 */

import React from "react";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";

// ── Module mocks ──────────────────────────────────────────────────────────────

jest.mock("next/navigation", () => ({
  redirect: jest.fn(),
  useRouter: jest.fn(() => ({ push: jest.fn() })),
  usePathname: jest.fn(() => "/audit"),
}));

jest.mock("@/lib/auth", () => ({
  getToken: jest.fn().mockResolvedValue("test-token"),
}));

jest.mock("@/lib/api", () => ({
  getMe: jest.fn(),
  listAuditEvents: jest.fn(),
  getAuditExportUrl: jest.fn().mockReturnValue("http://localhost:8000/audit/export.csv"),
}));

jest.mock("@/components/TopNav", () => ({
  TopNav: () => <nav data-testid="top-nav" />,
}));

jest.mock("@/components/AuditFilterBar", () => ({
  AuditFilterBar: () => <div data-testid="audit-filter-bar" />,
}));

jest.mock("@/components/AuditEntryRow", () => ({
  AuditEntryRow: ({ event }: { event: { action: string } }) => (
    <tr data-testid="audit-entry-row">
      <td>{event.action}</td>
    </tr>
  ),
}));

// Mock the client shell so page tests don't require router/navigation setup.
// The client component is unit-tested separately via its own test file.
jest.mock("@/app/audit/AuditLedgerClient", () => ({
  AuditLedgerClient: ({
    initialItems,
    initialFilters,
  }: {
    initialItems: Array<{ action: string }>;
    initialFilters: { action: string };
    initialTotal: number;
    token: string;
    initialNextCursor?: string;
  }) => (
    <div data-testid="audit-ledger-client">
      <div data-testid="audit-filter-bar" />
      {initialItems.length === 0 ? (
        <p>No governed events match your criteria</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Timestamp</th>
              <th>Actor</th>
              <th>Action</th>
              <th>Package</th>
            </tr>
          </thead>
          <tbody>
            {initialItems.map((e: { action: string }, i: number) => (
              <tr key={i} data-testid="audit-entry-row">
                <td>{e.action}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <a href="/audit/export.csv">Export governed record</a>
    </div>
  ),
}));

// ── Helpers ───────────────────────────────────────────────────────────────────

import { getMe, listAuditEvents } from "@/lib/api";

const mockAdmin = { id: "u1", email: "admin@firm.example", role: "admin" as const };
const mockReviewer = { id: "u2", email: "rev@firm.example", role: "reviewer" as const };

const mockEvent = {
  id: "e1",
  action: "package_submitted",
  actor_id: "u1",
  actor_email: "admin@firm.example",
  package_id: "p1",
  package_title: "Fund III — Q2 capital call",
  created_at: "2026-04-10T10:00:00Z",
  before_state: null,
  after_state: { status: "submitted" },
};

// ── Tests ─────────────────────────────────────────────────────────────────────

describe("AuditPage — admin view", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (getMe as jest.Mock).mockResolvedValue(mockAdmin);
    (listAuditEvents as jest.Mock).mockResolvedValue({
      items: [mockEvent],
      next_cursor: undefined,
      total: 1,
    });
  });

  it('renders "Governed record" heading', async () => {
    const AuditPage = (await import("@/app/audit/page")).default;
    const jsx = await AuditPage({ searchParams: Promise.resolve({}) });
    render(jsx as React.ReactElement);
    expect(screen.getByRole("heading", { name: /governed record/i })).toBeInTheDocument();
  });

  it('renders role-gate label "VISIBLE TO ADMINISTRATORS AND APPROVERS"', async () => {
    const AuditPage = (await import("@/app/audit/page")).default;
    const jsx = await AuditPage({ searchParams: Promise.resolve({}) });
    render(jsx as React.ReactElement);
    const matches = screen.getAllByText(/visible to administrators and approvers/i);
    expect(matches.length).toBeGreaterThanOrEqual(1);
  });

  it("renders the filter bar", async () => {
    const AuditPage = (await import("@/app/audit/page")).default;
    const jsx = await AuditPage({ searchParams: Promise.resolve({}) });
    render(jsx as React.ReactElement);
    expect(screen.getByTestId("audit-filter-bar")).toBeInTheDocument();
  });

  it("renders the export button", async () => {
    const AuditPage = (await import("@/app/audit/page")).default;
    const jsx = await AuditPage({ searchParams: Promise.resolve({}) });
    render(jsx as React.ReactElement);
    expect(
      screen.getByRole("link", { name: /export governed record/i })
    ).toBeInTheDocument();
  });

  it("renders audit entry rows when events present", async () => {
    const AuditPage = (await import("@/app/audit/page")).default;
    const jsx = await AuditPage({ searchParams: Promise.resolve({}) });
    render(jsx as React.ReactElement);
    expect(screen.getAllByTestId("audit-entry-row")).toHaveLength(1);
  });

  it("renders table headers: Timestamp, Actor, Action, Package", async () => {
    const AuditPage = (await import("@/app/audit/page")).default;
    const jsx = await AuditPage({ searchParams: Promise.resolve({}) });
    render(jsx as React.ReactElement);
    expect(screen.getByText("Timestamp")).toBeInTheDocument();
    expect(screen.getByText("Actor")).toBeInTheDocument();
    expect(screen.getByText("Action")).toBeInTheDocument();
    expect(screen.getByText("Package")).toBeInTheDocument();
  });
});

describe("AuditPage — empty state", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (getMe as jest.Mock).mockResolvedValue(mockAdmin);
    (listAuditEvents as jest.Mock).mockResolvedValue({
      items: [],
      next_cursor: undefined,
      total: 0,
    });
  });

  it("renders empty state when no events match", async () => {
    const AuditPage = (await import("@/app/audit/page")).default;
    const jsx = await AuditPage({ searchParams: Promise.resolve({}) });
    render(jsx as React.ReactElement);
    expect(screen.getByText(/no governed events match your criteria/i)).toBeInTheDocument();
  });
});

describe("AuditPage — reviewer role gate", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (getMe as jest.Mock).mockResolvedValue(mockReviewer);
    (listAuditEvents as jest.Mock).mockResolvedValue({
      items: [],
      next_cursor: undefined,
      total: 0,
    });
  });

  it("shows access-restricted message for reviewer", async () => {
    const AuditPage = (await import("@/app/audit/page")).default;
    const jsx = await AuditPage({ searchParams: Promise.resolve({}) });
    render(jsx as React.ReactElement);
    expect(screen.getByText(/access restricted/i)).toBeInTheDocument();
    expect(
      screen.getByText(/audit ledger is available to admins and approvers only/i)
    ).toBeInTheDocument();
  });

  it("shows link back to Console for reviewer", async () => {
    const AuditPage = (await import("@/app/audit/page")).default;
    const jsx = await AuditPage({ searchParams: Promise.resolve({}) });
    render(jsx as React.ReactElement);
    expect(screen.getByRole("link", { name: /return to console/i })).toBeInTheDocument();
  });

  it("does NOT render the filter bar for reviewer", async () => {
    const AuditPage = (await import("@/app/audit/page")).default;
    const jsx = await AuditPage({ searchParams: Promise.resolve({}) });
    render(jsx as React.ReactElement);
    expect(screen.queryByTestId("audit-filter-bar")).not.toBeInTheDocument();
  });
});
