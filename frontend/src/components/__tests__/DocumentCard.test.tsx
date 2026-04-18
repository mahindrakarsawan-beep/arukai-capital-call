/**
 * DocumentCard component tests — POR-147 / ARU-17 Phase A
 * Tests: renders props correctly, links to detail page.
 * Note: StatusPill now shows v0.2 labels via state façade.
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

  it("renders a status pill for pending_review (v0.2 label: 'Intake complete')", () => {
    renderRow(baseDocument);
    // pending_review + confidence 0.94 → intake_complete
    expect(
      screen.getByText(/intake complete — ready for review/i)
    ).toBeInTheDocument();
  });

  it("renders the classification badge", () => {
    renderRow(baseDocument);
    expect(screen.getByText("Capital Call")).toBeInTheDocument();
  });

  it("renders a formatted upload date", () => {
    renderRow(baseDocument);
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

  it("renders approved status with v0.2 decision label", () => {
    const doc = { ...baseDocument, status: "approved" as const };
    renderRow(doc);
    expect(screen.getByText(/approved · approver/i)).toBeInTheDocument();
  });

  it("renders rejected status with v0.2 decision label", () => {
    const doc = { ...baseDocument, status: "rejected" as const };
    renderRow(doc);
    expect(screen.getByText(/rejected · approver/i)).toBeInTheDocument();
  });

  it("renders exception_surfaced for pending_review with low confidence", () => {
    const doc = { ...baseDocument, status: "pending_review" as const, confidence: 0.3 };
    renderRow(doc);
    expect(screen.getByText(/exception surfaced/i)).toBeInTheDocument();
  });
});
