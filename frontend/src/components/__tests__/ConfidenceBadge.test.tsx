/**
 * ConfidenceBadge tests — POR-147 / ARU-17 Phase A (spec §4)
 * Four bands: ≥0.9 high, 0.7-0.89 confident, 0.5-0.69 needs review, <0.5 low confidence
 * Also: null → "Missing"
 */

import React from "react";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import { ConfidenceBadge } from "@/components/ConfidenceBadge";

describe("ConfidenceBadge — confidence bands", () => {
  describe("High band (≥ 0.90)", () => {
    it("renders value only with no pill for confidence 0.95", () => {
      render(<ConfidenceBadge confidence={0.95} value="$1,000,000" />);
      expect(screen.getByText("$1,000,000")).toBeInTheDocument();
      expect(screen.queryByText(/needs review/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/low confidence/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/missing/i)).not.toBeInTheDocument();
    });

    it("renders value only at exactly 0.90", () => {
      render(<ConfidenceBadge confidence={0.9} value="Fund III" />);
      expect(screen.getByText("Fund III")).toBeInTheDocument();
      expect(screen.queryByText(/needs review/i)).not.toBeInTheDocument();
    });
  });

  describe("Confident band (0.70–0.89)", () => {
    it("renders value with hairline marker at 0.80", () => {
      const { container } = render(
        <ConfidenceBadge confidence={0.8} value="Capital call notice" />
      );
      expect(screen.getByText("Capital call notice")).toBeInTheDocument();
      // Hairline marker: a span with bg-border-hairline-strong
      const marker = container.querySelector(
        '[class*="bg-border-hairline-strong"]'
      );
      expect(marker).toBeInTheDocument();
    });

    it("has title tooltip with percentage at 0.75", () => {
      const { container } = render(
        <ConfidenceBadge confidence={0.75} value="Q2 2026" />
      );
      const wrapper = container.firstChild as HTMLElement;
      expect(wrapper).toHaveAttribute("title", expect.stringContaining("75%"));
    });

    it("renders at exactly 0.70 as confident band", () => {
      render(<ConfidenceBadge confidence={0.7} value="test" />);
      expect(screen.getByText("test")).toBeInTheDocument();
      expect(screen.queryByText(/needs review/i)).not.toBeInTheDocument();
    });
  });

  describe("Needs review band (0.50–0.69)", () => {
    it("renders 'Needs review' pill at 0.60", () => {
      render(<ConfidenceBadge confidence={0.6} value="Wire instructions" />);
      expect(screen.getByText("Wire instructions")).toBeInTheDocument();
      expect(screen.getByText(/needs review/i)).toBeInTheDocument();
    });

    it("renders at exactly 0.50 as needs-review band", () => {
      render(<ConfidenceBadge confidence={0.5} value="value" />);
      expect(screen.getByText(/needs review/i)).toBeInTheDocument();
    });

    it("does NOT show 'Low confidence' pill at 0.65", () => {
      render(<ConfidenceBadge confidence={0.65} value="v" />);
      expect(screen.queryByText(/low confidence/i)).not.toBeInTheDocument();
    });
  });

  describe("Low confidence band (< 0.50)", () => {
    it("renders 'Low confidence — flag' pill at 0.3", () => {
      render(<ConfidenceBadge confidence={0.3} value="Unverified fund" />);
      expect(screen.getByText("Unverified fund")).toBeInTheDocument();
      expect(screen.getByText(/low confidence — flag/i)).toBeInTheDocument();
    });

    it("renders dashed border on value at 0.2", () => {
      const { container } = render(
        <ConfidenceBadge confidence={0.2} value="suspicious" />
      );
      const valueSpan = screen.getByText("suspicious");
      expect(valueSpan.className).toContain("border-dashed");
    });

    it("renders at confidence 0.0", () => {
      render(<ConfidenceBadge confidence={0} value="zero" />);
      expect(screen.getByText(/low confidence — flag/i)).toBeInTheDocument();
    });

    it("renders at confidence 0.49 as low-confidence (not needs-review)", () => {
      render(<ConfidenceBadge confidence={0.49} value="borderline" />);
      expect(screen.getByText(/low confidence — flag/i)).toBeInTheDocument();
      expect(screen.queryByText(/needs review/i)).not.toBeInTheDocument();
    });
  });

  describe("Missing field (null/undefined)", () => {
    it("renders '—' with 'Missing' pill when confidence is null", () => {
      render(<ConfidenceBadge confidence={null} />);
      expect(screen.getByText("—")).toBeInTheDocument();
      expect(screen.getByText(/missing/i)).toBeInTheDocument();
    });

    it("renders Missing pill when confidence is undefined", () => {
      render(<ConfidenceBadge confidence={undefined} />);
      expect(screen.getByText(/missing/i)).toBeInTheDocument();
    });
  });

  describe("Brass discipline", () => {
    it("never uses brandBrass color on any confidence band", () => {
      const cases = [0.95, 0.8, 0.6, 0.3, null];
      cases.forEach((conf) => {
        const { container } = render(
          <ConfidenceBadge confidence={conf} value="test" />
        );
        // Check no element uses #B8914E (brass) inline style or class
        const html = container.innerHTML;
        expect(html).not.toContain("#B8914E");
        expect(html).not.toContain("brand-brass");
        expect(html).not.toContain("brandBrass");
      });
    });
  });
});
