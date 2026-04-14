/**
 * DocumentCard component tests — POR-142 M3
 * Tests: renders props correctly, links to detail page
 */

import React from "react";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import { DocumentCard } from "@/components/DocumentCard";
import type { DocumentSummary } from "@/lib/api";

const baseDocument: DocumentSummary = {
  id: "doc-abc123",
  filename: "meridian_capital_call_q2.pdf",
  doc_type: "capital_call_notice",
  uploaded_at: "2026-04-12T10:00:00Z",
  status: "pending_review",
  confidence: 0.94,
};

function renderRow(doc: DocumentSummary) {
  return render(
    <table>
      <tbody>
        <DocumentCard document={doc} />
      </tbody>
    </table>
  );
}

describe("DocumentCard", () => {
  it("renders the filename", () => {
    renderRow(baseDocument);
    expect(screen.getByText("meridian_capital_call_q2.pdf")).toBeInTheDocument();
  });

  it("renders a link to the document detail page", () => {
    renderRow(baseDocument);
    const link = screen.getByRole("link", { name: "meridian_capital_call_q2.pdf" });
    expect(link).toHaveAttribute("href", "/documents/doc-abc123");
  });

  it("renders the View link", () => {
    renderRow(baseDocument);
    expect(screen.getByText("View →")).toBeInTheDocument();
  });

  it("renders the status pill", () => {
    renderRow(baseDocument);
    expect(screen.getByText("Pending Review")).toBeInTheDocument();
  });

  it("renders the classification badge", () => {
    renderRow(baseDocument);
    expect(screen.getByText("Capital Call")).toBeInTheDocument();
  });

  it("renders a formatted upload date", () => {
    renderRow(baseDocument);
    // The date is formatted — check it contains 'Apr' and '2026'
    const dateText = screen.getByText(/apr.*2026/i);
    expect(dateText).toBeInTheDocument();
  });

  it("handles missing doc_type gracefully", () => {
    const doc = { ...baseDocument, doc_type: null as never };
    renderRow(doc);
    expect(screen.getByText("Unclassified")).toBeInTheDocument();
  });

  it("handles missing status gracefully", () => {
    const doc = { ...baseDocument, status: null as never };
    renderRow(doc);
    expect(screen.getByText("Unknown")).toBeInTheDocument();
  });

  it("renders approved status correctly", () => {
    const doc = { ...baseDocument, status: "approved" as const };
    renderRow(doc);
    expect(screen.getByText("Approved")).toBeInTheDocument();
  });

  it("renders rejected status correctly", () => {
    const doc = { ...baseDocument, status: "rejected" as const };
    renderRow(doc);
    expect(screen.getByText("Rejected")).toBeInTheDocument();
  });
});
