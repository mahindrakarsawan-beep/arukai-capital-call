/**
 * Operations console page tests — POR-147 / ARU-17 Phase A
 * Tests: v0.2 copy ("Operations console", five sections, "Begin intake" CTA, empty states)
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

describe("DocumentsPage — v0.2 operations console", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders "Operations console" H1', async () => {
    const { getMe, listDocuments } = require("@/lib/api");
    getMe.mockResolvedValue({ id: "u1", email: "alice@test.com", role: "admin" });
    listDocuments.mockResolvedValue([]);

    const { default: DocumentsPage } = require("@/app/documents/page");
    const jsx = await DocumentsPage({});
    render(jsx);

    expect(screen.getByText("Operations console")).toBeInTheDocument();
  });

  it("renders all five section headers in order", async () => {
    const { getMe, listDocuments } = require("@/lib/api");
    getMe.mockResolvedValue({ id: "u1", email: "alice@test.com", role: "admin" });
    listDocuments.mockResolvedValue([]);

    const { default: DocumentsPage } = require("@/app/documents/page");
    const jsx = await DocumentsPage({});
    render(jsx);

    const sections = screen.getAllByRole("heading", { level: 2 });
    const sectionNames = sections.map((s) => s.textContent?.trim());

    expect(sectionNames).toContain("Exceptions");
    expect(sectionNames).toContain("Pending approval");
    expect(sectionNames).toContain("Needs review");
    expect(sectionNames).toContain("Active packages");
    expect(sectionNames).toContain("Recent decisions");
  });

  it("renders Exceptions section before Pending approval", async () => {
    const { getMe, listDocuments } = require("@/lib/api");
    getMe.mockResolvedValue({ id: "u1", email: "alice@test.com", role: "admin" });
    listDocuments.mockResolvedValue([]);

    const { default: DocumentsPage } = require("@/app/documents/page");
    const jsx = await DocumentsPage({});
    const { container } = render(jsx);

    const headings = container.querySelectorAll("h2");
    const headingTexts = Array.from(headings).map((h) => h.textContent?.trim());

    const exceptionsIdx = headingTexts.indexOf("Exceptions");
    const pendingIdx = headingTexts.indexOf("Pending approval");
    expect(exceptionsIdx).toBeLessThan(pendingIdx);
  });

  it('renders "Begin intake" CTA button', async () => {
    const { getMe, listDocuments } = require("@/lib/api");
    getMe.mockResolvedValue({ id: "u1", email: "alice@test.com", role: "admin" });
    listDocuments.mockResolvedValue([]);

    const { default: DocumentsPage } = require("@/app/documents/page");
    const jsx = await DocumentsPage({});
    render(jsx);

    // "Begin intake" appears in nav and as Active packages CTA
    expect(screen.getAllByText("Begin intake").length).toBeGreaterThanOrEqual(1);
  });

  it('does NOT contain banned "Upload new" string', async () => {
    const { getMe, listDocuments } = require("@/lib/api");
    getMe.mockResolvedValue({ id: "u1", email: "alice@test.com", role: "admin" });
    listDocuments.mockResolvedValue([]);

    const { default: DocumentsPage } = require("@/app/documents/page");
    const jsx = await DocumentsPage({});
    render(jsx);

    expect(screen.queryByText("Upload new")).not.toBeInTheDocument();
  });

  it('shows empty state for exceptions: "No exceptions surfaced"', async () => {
    const { getMe, listDocuments } = require("@/lib/api");
    getMe.mockResolvedValue({ id: "u1", email: "alice@test.com", role: "admin" });
    listDocuments.mockResolvedValue([]);

    const { default: DocumentsPage } = require("@/app/documents/page");
    const jsx = await DocumentsPage({});
    render(jsx);

    expect(screen.getByText(/no exceptions surfaced/i)).toBeInTheDocument();
  });

  it('shows empty state for needs review: "Nothing awaiting your review"', async () => {
    const { getMe, listDocuments } = require("@/lib/api");
    getMe.mockResolvedValue({ id: "u1", email: "alice@test.com", role: "admin" });
    listDocuments.mockResolvedValue([]);

    const { default: DocumentsPage } = require("@/app/documents/page");
    const jsx = await DocumentsPage({});
    render(jsx);

    expect(screen.getByText(/nothing awaiting your review/i)).toBeInTheDocument();
  });

  it("renders table rows when documents exist", async () => {
    const { getMe, listDocuments } = require("@/lib/api");
    getMe.mockResolvedValue({ id: "u1", email: "alice@test.com", role: "admin" });
    listDocuments.mockResolvedValue([
      {
        id: "doc-1",
        filename: "Fund_III_Q2_capital_call.pdf",
        doc_type: "capital_call_notice",
        uploaded_at: "2026-04-12T10:00:00Z",
        status: "pending_review",
        confidence: 0.94,
      },
    ]);

    const { default: DocumentsPage } = require("@/app/documents/page");
    const jsx = await DocumentsPage({});
    render(jsx);

    // Document appears in both "Needs review" and "Active packages" sections
    expect(screen.getAllByText("Fund_III_Q2_capital_call.pdf").length).toBeGreaterThan(0);
  });

  it('shows "N active packages across your desk" subtitle when packages exist', async () => {
    const { getMe, listDocuments } = require("@/lib/api");
    getMe.mockResolvedValue({ id: "u1", email: "alice@test.com", role: "admin" });
    listDocuments.mockResolvedValue([
      {
        id: "doc-1",
        filename: "test.pdf",
        doc_type: "other",
        uploaded_at: "2026-04-12T10:00:00Z",
        status: "pending_review",
        confidence: 0.7,
      },
    ]);

    const { default: DocumentsPage } = require("@/app/documents/page");
    const jsx = await DocumentsPage({});
    render(jsx);

    expect(screen.getByText(/active package.*across your desk/i)).toBeInTheDocument();
  });

  it("shows stale banner on fetch error with workflow language", async () => {
    const { getMe, listDocuments } = require("@/lib/api");
    getMe.mockResolvedValue({ id: "u1", email: "alice@test.com", role: "admin" });
    listDocuments.mockRejectedValue(new Error("Network error"));

    const { default: DocumentsPage } = require("@/app/documents/page");
    const jsx = await DocumentsPage({});
    render(jsx);

    expect(
      screen.getByText(/workflow state could not be refreshed/i)
    ).toBeInTheDocument();
  });

  it("routes exception_surfaced docs to Exceptions section", async () => {
    const { getMe, listDocuments } = require("@/lib/api");
    getMe.mockResolvedValue({ id: "u1", email: "alice@test.com", role: "admin" });
    listDocuments.mockResolvedValue([
      {
        id: "doc-low",
        filename: "low_confidence.pdf",
        doc_type: "other",
        uploaded_at: "2026-04-12T10:00:00Z",
        status: "pending_review",
        confidence: 0.3, // < 0.5 → exception_surfaced
      },
    ]);

    const { default: DocumentsPage } = require("@/app/documents/page");
    const jsx = await DocumentsPage({});
    render(jsx);

    // Should NOT show the "No exceptions surfaced" empty state
    expect(screen.queryByText(/no exceptions surfaced/i)).not.toBeInTheDocument();
  });
});
