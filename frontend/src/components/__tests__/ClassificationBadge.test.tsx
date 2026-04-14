/**
 * ClassificationBadge component tests — POR-142 M3
 * Tests: different doc_types render different styles and labels
 */

import React from "react";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import { ClassificationBadge } from "@/components/ClassificationBadge";
import type { DocType } from "@/lib/api";

describe("ClassificationBadge", () => {
  it("renders 'Capital Call' for capital_call_notice", () => {
    render(<ClassificationBadge docType="capital_call_notice" />);
    expect(screen.getByText("Capital Call")).toBeInTheDocument();
  });

  it("renders 'Subscription Agmt' for subscription_agreement", () => {
    render(<ClassificationBadge docType="subscription_agreement" />);
    expect(screen.getByText("Subscription Agmt")).toBeInTheDocument();
  });

  it("renders 'Side Letter' for side_letter", () => {
    render(<ClassificationBadge docType="side_letter" />);
    expect(screen.getByText("Side Letter")).toBeInTheDocument();
  });

  it("renders 'K-1' for k1", () => {
    render(<ClassificationBadge docType="k1" />);
    expect(screen.getByText("K-1")).toBeInTheDocument();
  });

  it("renders 'Wire Instructions' for wire_instructions", () => {
    render(<ClassificationBadge docType="wire_instructions" />);
    expect(screen.getByText("Wire Instructions")).toBeInTheDocument();
  });

  it("renders 'Other' for other", () => {
    render(<ClassificationBadge docType="other" />);
    expect(screen.getByText("Other")).toBeInTheDocument();
  });

  it("renders 'Unclassified' when docType is null", () => {
    render(<ClassificationBadge docType={null} />);
    expect(screen.getByText("Unclassified")).toBeInTheDocument();
  });

  it("capital_call_notice has green styling", () => {
    render(<ClassificationBadge docType="capital_call_notice" />);
    const badge = screen.getByText("Capital Call");
    // Should have data-positive (green) text class
    expect(badge).toHaveClass("text-data-positive");
  });

  it("wire_instructions has red styling (high-risk signal)", () => {
    render(<ClassificationBadge docType="wire_instructions" />);
    const badge = screen.getByText("Wire Instructions");
    expect(badge).toHaveClass("text-data-negative");
  });

  it("other has muted styling", () => {
    render(<ClassificationBadge docType="other" />);
    const badge = screen.getByText("Other");
    expect(badge).toHaveClass("text-fg-muted");
  });

  it("subscription_agreement has slate styling", () => {
    render(<ClassificationBadge docType="subscription_agreement" />);
    const badge = screen.getByText("Subscription Agmt");
    expect(badge).toHaveClass("text-fg-slate");
  });

  it("renders as a span element", () => {
    render(<ClassificationBadge docType="capital_call_notice" />);
    const badge = screen.getByText("Capital Call");
    expect(badge.tagName.toLowerCase()).toBe("span");
  });
});
