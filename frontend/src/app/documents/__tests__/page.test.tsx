/**
 * Operations console page tests — POR-147 / ARU-17 Phase A (A1 refinement)
 * Tests:
 *   - v0.2 copy ("Operations console", five sections, "Begin intake" CTA, empty states)
 *   - 5-section order (Exceptions → Pending approval → Needs review → Active packages → Recent decisions)
 *   - Empty states per section with Arukai-language copy
 *   - Cap-5 rows + "Show all N" expander when > 5 items
 *   - PackageRow component used instead of inline ConsoleRow
 *   - Viewport collapse: tablet (md) + mobile (sm) layout cues present in DOM
 */

import React from "react";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";

// Mock auth and API
jest.mock("@/lib/auth", () => ({
  getToken: jest.fn().mockResolvedValue("mock-token"),
}));

jest.mock("@/lib/api", () => ({
  getMe: jest.fn().mockResolvedValue({
    id: "user-1",
    email: "alice@example.com",
    role: "admin",
  }),
  listDocuments: jest.fn().mockResolvedValue([]),
}));

// Mock next/navigation redirect
jest.mock("next/navigation", () => ({
  redirect: jest.fn(),
  notFound: jest.fn(),
}));

// ─── Helpers ─────────────────────────────────────────────────────────────────

function makeDoc(overrides: Partial<{
  id: string;
  filename: string;
  doc_type: string;
  uploaded_at: string;
  status: string;
  confidence: number | null;
}> = {}) {
  return {
    id: "doc-1",
    filename: "Fund_III_Q2_capital_call.pdf",
    doc_type: "capital_call_notice",
    uploaded_at: new Date(Date.now() - 2 * 3600000).toISOString(),
    status: "pending_review",
    confidence: 0.94,
    ...overrides,
  };
}

async function renderPage() {
  const { default: DocumentsPage } = require("@/app/documents/page");
  const jsx = await DocumentsPage({});
  return render(jsx);
}

// ─── Core structure ───────────────────────────────────────────────────────────

describe("DocumentsPage — v0.2 operations console (A1)", () => {
  beforeEach(() => {
    jest.resetModules();
    jest.clearAllMocks();
  });

  it('renders "Operations console" H1', async () => {
    const { getMe, listDocuments } = require("@/lib/api");
    getMe.mockResolvedValue({ id: "u1", email: "alice@test.com", role: "admin" });
    listDocuments.mockResolvedValue([]);
    await renderPage();
    expect(screen.getByRole("heading", { level: 1, name: /operations console/i })).toBeInTheDocument();
  });

  it("renders all five section headers", async () => {
    const { getMe, listDocuments } = require("@/lib/api");
    getMe.mockResolvedValue({ id: "u1", email: "alice@test.com", role: "admin" });
    listDocuments.mockResolvedValue([]);
    await renderPage();

    const h2s = screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent?.trim());
    expect(h2s).toContain("Exceptions");
    expect(h2s).toContain("Pending approval");
    expect(h2s).toContain("Needs review");
    expect(h2s).toContain("Active packages");
    expect(h2s).toContain("Recent decisions");
  });

  it("renders sections in the correct order", async () => {
    const { getMe, listDocuments } = require("@/lib/api");
    getMe.mockResolvedValue({ id: "u1", email: "alice@test.com", role: "admin" });
    listDocuments.mockResolvedValue([]);
    const { container } = await renderPage();

    const h2Texts = Array.from(container.querySelectorAll("h2")).map((h) => h.textContent?.trim());
    const expected = ["Exceptions", "Pending approval", "Needs review", "Active packages", "Recent decisions"];
    const positions = expected.map((name) => h2Texts.indexOf(name));
    // Each section should appear in strictly ascending index order
    for (let i = 0; i < positions.length - 1; i++) {
      expect(positions[i]).toBeLessThan(positions[i + 1]);
    }
  });

  it('renders "Begin intake" CTA in Active packages section header', async () => {
    const { getMe, listDocuments } = require("@/lib/api");
    getMe.mockResolvedValue({ id: "u1", email: "alice@test.com", role: "admin" });
    listDocuments.mockResolvedValue([]);
    await renderPage();
    // At least one "Begin intake" appears (section CTA + mobile sticky CTA)
    expect(screen.getAllByText("Begin intake").length).toBeGreaterThanOrEqual(1);
  });

  it('does NOT contain banned "Upload new" string', async () => {
    const { getMe, listDocuments } = require("@/lib/api");
    getMe.mockResolvedValue({ id: "u1", email: "alice@test.com", role: "admin" });
    listDocuments.mockResolvedValue([]);
    await renderPage();
    expect(screen.queryByText("Upload new")).not.toBeInTheDocument();
  });
});

// ─── Empty states ─────────────────────────────────────────────────────────────

describe("DocumentsPage — empty states per section", () => {
  beforeEach(() => {
    jest.resetModules();
    jest.clearAllMocks();
  });

  it("shows Exceptions empty state: no exceptions surfaced", async () => {
    const { getMe, listDocuments } = require("@/lib/api");
    getMe.mockResolvedValue({ id: "u1", email: "alice@test.com", role: "admin" });
    listDocuments.mockResolvedValue([]);
    await renderPage();
    expect(screen.getByText(/no exceptions surfaced/i)).toBeInTheDocument();
  });

  it("shows Pending approval empty state", async () => {
    const { getMe, listDocuments } = require("@/lib/api");
    getMe.mockResolvedValue({ id: "u1", email: "alice@test.com", role: "admin" });
    listDocuments.mockResolvedValue([]);
    await renderPage();
    expect(screen.getByText(/no packages routed for attestation/i)).toBeInTheDocument();
  });

  it("shows Needs review empty state", async () => {
    const { getMe, listDocuments } = require("@/lib/api");
    getMe.mockResolvedValue({ id: "u1", email: "alice@test.com", role: "admin" });
    listDocuments.mockResolvedValue([]);
    await renderPage();
    expect(screen.getByText(/nothing awaiting your review/i)).toBeInTheDocument();
  });

  it("shows Active packages empty state", async () => {
    const { getMe, listDocuments } = require("@/lib/api");
    getMe.mockResolvedValue({ id: "u1", email: "alice@test.com", role: "admin" });
    listDocuments.mockResolvedValue([]);
    await renderPage();
    // Both page subtitle and Active empty state use this copy — at least one present
    expect(screen.getAllByText(/no packages in flight/i).length).toBeGreaterThanOrEqual(1);
  });

  it("shows Recent decisions empty state", async () => {
    const { getMe, listDocuments } = require("@/lib/api");
    getMe.mockResolvedValue({ id: "u1", email: "alice@test.com", role: "admin" });
    listDocuments.mockResolvedValue([]);
    await renderPage();
    expect(screen.getByText(/no decisions recorded in the last 30 days/i)).toBeInTheDocument();
  });
});

// ─── Section routing ──────────────────────────────────────────────────────────

describe("DocumentsPage — section routing", () => {
  beforeEach(() => {
    jest.resetModules();
    jest.clearAllMocks();
  });

  it("routes exception_surfaced docs to Exceptions section (hides empty state)", async () => {
    const { getMe, listDocuments } = require("@/lib/api");
    getMe.mockResolvedValue({ id: "u1", email: "alice@test.com", role: "admin" });
    listDocuments.mockResolvedValue([makeDoc({ id: "d-low", confidence: 0.3 })]);
    await renderPage();
    expect(screen.queryByText(/no exceptions surfaced/i)).not.toBeInTheDocument();
  });

  it("routes normal pending_review docs to Needs review section", async () => {
    const { getMe, listDocuments } = require("@/lib/api");
    getMe.mockResolvedValue({ id: "u1", email: "alice@test.com", role: "admin" });
    listDocuments.mockResolvedValue([makeDoc({ confidence: 0.94 })]);
    await renderPage();
    expect(screen.queryByText(/nothing awaiting your review/i)).not.toBeInTheDocument();
  });

  it("routes approved docs to Recent decisions", async () => {
    const { getMe, listDocuments } = require("@/lib/api");
    getMe.mockResolvedValue({ id: "u1", email: "alice@test.com", role: "admin" });
    listDocuments.mockResolvedValue([makeDoc({ status: "approved", confidence: null })]);
    await renderPage();
    expect(screen.queryByText(/no decisions recorded/i)).not.toBeInTheDocument();
  });

  it("routes rejected docs to Recent decisions (S4 — rejection as distinct type)", async () => {
    const { getMe, listDocuments } = require("@/lib/api");
    getMe.mockResolvedValue({ id: "u1", email: "alice@test.com", role: "admin" });
    listDocuments.mockResolvedValue([makeDoc({ status: "rejected", confidence: null })]);
    await renderPage();
    expect(screen.queryByText(/no decisions recorded/i)).not.toBeInTheDocument();
  });
});

// ─── Cap-5 rows + expander ────────────────────────────────────────────────────

describe("DocumentsPage — cap-5 rows + Show all expander", () => {
  beforeEach(() => {
    jest.resetModules();
    jest.clearAllMocks();
  });

  it("shows at most 5 rows per section without an expander", async () => {
    const { getMe, listDocuments } = require("@/lib/api");
    getMe.mockResolvedValue({ id: "u1", email: "alice@test.com", role: "admin" });
    const docs = Array.from({ length: 4 }, (_, i) =>
      makeDoc({ id: `d-${i}`, filename: `file-${i}.pdf`, confidence: 0.94 })
    );
    listDocuments.mockResolvedValue(docs);
    await renderPage();
    expect(screen.queryByText(/show all/i)).not.toBeInTheDocument();
  });

  it('shows "Show all N" expander when section has more than 5 rows', async () => {
    const { getMe, listDocuments } = require("@/lib/api");
    getMe.mockResolvedValue({ id: "u1", email: "alice@test.com", role: "admin" });
    // 6 items in Needs review / Active
    const docs = Array.from({ length: 6 }, (_, i) =>
      makeDoc({ id: `d-${i}`, filename: `file-${i}.pdf`, confidence: 0.94 })
    );
    listDocuments.mockResolvedValue(docs);
    await renderPage();
    expect(screen.getAllByText(/show all 6/i).length).toBeGreaterThanOrEqual(1);
  });

  it("renders exactly 5 links per overflowing section (not all 6)", async () => {
    const { getMe, listDocuments } = require("@/lib/api");
    getMe.mockResolvedValue({ id: "u1", email: "alice@test.com", role: "admin" });
    const docs = Array.from({ length: 6 }, (_, i) =>
      makeDoc({ id: `d-${i}`, filename: `unique-${i}.pdf`, confidence: 0.94 })
    );
    listDocuments.mockResolvedValue(docs);
    await renderPage();
    // file-5 (the 6th item) should not appear in the first 5 shown
    expect(screen.queryByText("unique-5.pdf")).not.toBeInTheDocument();
  });
});

// ─── Pending attestation chip ─────────────────────────────────────────────────

describe("DocumentsPage — pending attestation count", () => {
  beforeEach(() => {
    jest.resetModules();
    jest.clearAllMocks();
  });

  it("does not render attestation chip when no pending approval docs", async () => {
    const { getMe, listDocuments } = require("@/lib/api");
    getMe.mockResolvedValue({ id: "u1", email: "alice@test.com", role: "admin" });
    listDocuments.mockResolvedValue([]);
    await renderPage();
    expect(screen.queryByText(/pending attestation/i)).not.toBeInTheDocument();
  });
});

// ─── Error state ──────────────────────────────────────────────────────────────

describe("DocumentsPage — error handling", () => {
  beforeEach(() => {
    jest.resetModules();
    jest.clearAllMocks();
  });

  it("shows stale banner on fetch error with workflow language", async () => {
    const { getMe, listDocuments } = require("@/lib/api");
    getMe.mockResolvedValue({ id: "u1", email: "alice@test.com", role: "admin" });
    listDocuments.mockRejectedValue(new Error("Network error"));
    await renderPage();
    expect(screen.getByText(/workflow state could not be refreshed/i)).toBeInTheDocument();
  });

  it("shows subtitle with active count when packages exist", async () => {
    const { getMe, listDocuments } = require("@/lib/api");
    getMe.mockResolvedValue({ id: "u1", email: "alice@test.com", role: "admin" });
    listDocuments.mockResolvedValue([makeDoc({ confidence: 0.94 })]);
    await renderPage();
    expect(screen.getByText(/active package.*across your desk/i)).toBeInTheDocument();
  });
});

// ─── Viewport layout cues ─────────────────────────────────────────────────────

describe("DocumentsPage — responsive layout DOM cues", () => {
  beforeEach(() => {
    jest.resetModules();
    jest.clearAllMocks();
  });

  it("renders mobile sticky bottom CTA with md:hidden class", async () => {
    const { getMe, listDocuments } = require("@/lib/api");
    getMe.mockResolvedValue({ id: "u1", email: "alice@test.com", role: "admin" });
    listDocuments.mockResolvedValue([]);
    const { container } = await renderPage();
    // The mobile sticky CTA div should be in the DOM
    const stickyDiv = container.querySelector(".md\\:hidden.fixed.bottom-0");
    expect(stickyDiv).toBeInTheDocument();
  });

  it("renders PackageRow rows with responsive flex classes on tablet/mobile", async () => {
    const { getMe, listDocuments } = require("@/lib/api");
    getMe.mockResolvedValue({ id: "u1", email: "alice@test.com", role: "admin" });
    listDocuments.mockResolvedValue([makeDoc({ confidence: 0.94 })]);
    const { container } = await renderPage();
    // PackageRow link uses flex-col sm:flex-row for mobile card → row collapse
    const rowLinks = container.querySelectorAll("a.flex-col");
    expect(rowLinks.length).toBeGreaterThanOrEqual(1);
  });
});
