/**
 * Documents list page tests — POR-142 M3
 * Tests: renders list, shows empty state
 *
 * Note: DocumentsPage is a server component (async). We test it by
 * mocking its data dependencies and rendering it in a wrapper.
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
    role: "reviewer",
  }),
  listDocuments: jest.fn().mockResolvedValue([]),
}));

// Mock next/navigation redirect
jest.mock("next/navigation", () => ({
  redirect: jest.fn(),
  notFound: jest.fn(),
}));

// eslint-disable-next-line @typescript-eslint/no-unused-vars
async function renderAsync(_component: React.ReactNode) {
  const { default: DocumentsPage } = await import("@/app/documents/page");
  // Resolve the async component (no props for this server component)
  const resolved = await (DocumentsPage as () => Promise<React.ReactElement>)();
  return render(resolved);
}

describe("DocumentsPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("shows empty state when there are no documents", async () => {
    const { getMe, listDocuments } = require("@/lib/api");
    getMe.mockResolvedValue({ id: "u1", email: "alice@test.com", role: "reviewer" });
    listDocuments.mockResolvedValue([]);

    const { default: DocumentsPage } = require("@/app/documents/page");
    const jsx = await DocumentsPage({});
    render(jsx);

    expect(
      screen.getByText(/no documents have been uploaded yet/i)
    ).toBeInTheDocument();
  });

  it("renders Upload new button", async () => {
    const { getMe, listDocuments } = require("@/lib/api");
    getMe.mockResolvedValue({ id: "u1", email: "alice@test.com", role: "reviewer" });
    listDocuments.mockResolvedValue([]);

    const { default: DocumentsPage } = require("@/app/documents/page");
    const jsx = await DocumentsPage({});
    render(jsx);

    expect(screen.getByText("Upload new")).toBeInTheDocument();
  });

  it("renders table when documents exist", async () => {
    const { getMe, listDocuments } = require("@/lib/api");
    getMe.mockResolvedValue({ id: "u1", email: "alice@test.com", role: "reviewer" });
    listDocuments.mockResolvedValue([
      {
        id: "doc-1",
        filename: "capital_call_q2.pdf",
        doc_type: "capital_call_notice",
        uploaded_at: "2026-04-12T10:00:00Z",
        status: "pending_review",
        confidence: 0.94,
      },
      {
        id: "doc-2",
        filename: "subscription_form.pdf",
        doc_type: "subscription_agreement",
        uploaded_at: "2026-04-11T09:30:00Z",
        status: "approved",
        confidence: 0.88,
      },
    ]);

    const { default: DocumentsPage } = require("@/app/documents/page");
    const jsx = await DocumentsPage({});
    render(jsx);

    expect(screen.getByText("capital_call_q2.pdf")).toBeInTheDocument();
    expect(screen.getByText("subscription_form.pdf")).toBeInTheDocument();
  });

  it("shows document count in subtitle", async () => {
    const { getMe, listDocuments } = require("@/lib/api");
    getMe.mockResolvedValue({ id: "u1", email: "alice@test.com", role: "reviewer" });
    listDocuments.mockResolvedValue([
      {
        id: "doc-1",
        filename: "test.pdf",
        doc_type: "other",
        uploaded_at: "2026-04-12T10:00:00Z",
        status: "approved",
        confidence: 0.7,
      },
    ]);

    const { default: DocumentsPage } = require("@/app/documents/page");
    const jsx = await DocumentsPage({});
    render(jsx);

    expect(screen.getByText(/1 document/i)).toBeInTheDocument();
  });

  it("shows stale banner on fetch error", async () => {
    const { getMe, listDocuments } = require("@/lib/api");
    getMe.mockResolvedValue({ id: "u1", email: "alice@test.com", role: "reviewer" });
    listDocuments.mockRejectedValue(new Error("Network error"));

    const { default: DocumentsPage } = require("@/app/documents/page");
    const jsx = await DocumentsPage({});
    render(jsx);

    expect(screen.getByText(/network error/i)).toBeInTheDocument();
  });
});
