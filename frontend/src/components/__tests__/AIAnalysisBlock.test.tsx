/**
 * AIAnalysisBlock tests — POR-148 / Figma node 61:2
 *
 * Coverage:
 *   - Renders header label "AI ANALYSIS" (case-insensitive)
 *   - Renders classification reasoning paragraph
 *   - Renders fallback reasoning from key_indicators when classification_reasoning absent
 *   - Renders extraction table when extracted_fields present
 *   - Renders ConfidenceBadge per field
 *   - Shows exception callout for fields with confidence < 0.5
 *   - Does NOT show exception callout for fields with confidence >= 0.5
 *   - Renders model attribution footer line
 *   - Shows overall confidence badge when no extracted_fields
 *   - Renders source_text as italicised "found in" line
 */

import React from "react";
import { render, screen, within } from "@testing-library/react";
import "@testing-library/jest-dom";
import { AIAnalysisBlock } from "@/components/AIAnalysisBlock";
import type { Classification } from "@/lib/api";

// ─────────────────────────────────────────────────────────────────────────────
// Fixtures
// ─────────────────────────────────────────────────────────────────────────────

const baseClassification: Classification = {
  doc_type: "capital_call_notice",
  confidence: 0.92,
  key_indicators: [
    "Capital call notice header",
    "Fund III reference",
    "Due date clause",
  ],
  model_version: "claude-haiku-3",
  duration_ms: 1340,
};

const classificationWithFields: Classification = {
  ...baseClassification,
  extracted_fields: {
    call_amount: { value: "$2,500,000", confidence: 0.97, source_text: "Capital call amount: $2,500,000" },
    due_date: { value: "2026-05-15", confidence: 0.91, source_text: "payment due by May 15, 2026" },
    fund_name: { value: "Fund III", confidence: 0.99, source_text: "Blackstone Real Estate Fund III" },
    investor_name: { value: "Arukai LP", confidence: 0.43, source_text: null },
  },
};

const classificationWithReasoning: Classification = {
  ...classificationWithFields,
  classification_reasoning:
    "This document was identified as a Capital Call Notice based on the presence of a formal fund call header, specific dollar amount, and a due date clause in the body.",
};

const ANALYSED_AT = "2026-04-15T10:00:00Z";

// ─────────────────────────────────────────────────────────────────────────────
// Header
// ─────────────────────────────────────────────────────────────────────────────

describe("AIAnalysisBlock — header", () => {
  it("renders the AI ANALYSIS label", () => {
    render(
      <AIAnalysisBlock
        classification={baseClassification}
        analysedAt={ANALYSED_AT}
      />
    );
    expect(screen.getByText(/ai analysis/i)).toBeInTheDocument();
  });

  it("renders the model attribution in the header", () => {
    render(
      <AIAnalysisBlock
        classification={baseClassification}
        analysedAt={ANALYSED_AT}
      />
    );
    expect(screen.getAllByText(/analysis by claude-haiku-3/i).length).toBeGreaterThan(0);
  });

  it("shows duration in seconds when duration_ms >= 1000", () => {
    render(
      <AIAnalysisBlock
        classification={baseClassification}
        analysedAt={ANALYSED_AT}
      />
    );
    // 1340ms → 1.3s
    expect(screen.getAllByText(/1\.3s/i).length).toBeGreaterThan(0);
  });

  it("shows duration in ms when duration_ms < 1000", () => {
    const cls: Classification = { ...baseClassification, duration_ms: 850 };
    render(
      <AIAnalysisBlock classification={cls} analysedAt={ANALYSED_AT} />
    );
    expect(screen.getAllByText(/850ms/i).length).toBeGreaterThan(0);
  });

  it("omits duration when duration_ms is absent", () => {
    const cls: Classification = { ...baseClassification, duration_ms: undefined };
    render(
      <AIAnalysisBlock classification={cls} analysedAt={ANALYSED_AT} />
    );
    // Should not render ms or s measurement as standalone text
    expect(screen.queryByText(/\d+ms/)).not.toBeInTheDocument();
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// Classification reasoning
// ─────────────────────────────────────────────────────────────────────────────

describe("AIAnalysisBlock — classification reasoning", () => {
  it("renders the server-provided classification_reasoning paragraph", () => {
    render(
      <AIAnalysisBlock
        classification={classificationWithReasoning}
        analysedAt={ANALYSED_AT}
      />
    );
    const reasoningEl = screen.getByTestId("classification-reasoning");
    expect(reasoningEl).toHaveTextContent(
      "This document was identified as a Capital Call Notice"
    );
  });

  it("falls back to key_indicators when classification_reasoning is absent", () => {
    render(
      <AIAnalysisBlock
        classification={baseClassification}
        analysedAt={ANALYSED_AT}
      />
    );
    const reasoningEl = screen.getByTestId("classification-reasoning");
    // Should mention "Capital Call Notice" and at least one indicator
    expect(reasoningEl).toHaveTextContent(/Classified as Capital Call Notice/);
    expect(reasoningEl).toHaveTextContent(/Capital call notice header/);
  });

  it("generates fallback with up to 3 key_indicators", () => {
    const cls: Classification = {
      ...baseClassification,
      key_indicators: ["Indicator A", "Indicator B", "Indicator C", "Indicator D"],
    };
    render(<AIAnalysisBlock classification={cls} analysedAt={ANALYSED_AT} />);
    const reasoningEl = screen.getByTestId("classification-reasoning");
    // All 3 (capped) indicators shown
    expect(reasoningEl).toHaveTextContent("Indicator A, Indicator B, Indicator C");
    // 4th indicator not shown
    expect(reasoningEl).not.toHaveTextContent("Indicator D");
  });

  it("produces a minimal fallback when key_indicators is empty", () => {
    const cls: Classification = { ...baseClassification, key_indicators: [] };
    render(<AIAnalysisBlock classification={cls} analysedAt={ANALYSED_AT} />);
    const reasoningEl = screen.getByTestId("classification-reasoning");
    expect(reasoningEl).toHaveTextContent(/Classified as Capital Call Notice/);
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// Extraction table
// ─────────────────────────────────────────────────────────────────────────────

describe("AIAnalysisBlock — extraction table", () => {
  it("renders the extraction table when extracted_fields is present", () => {
    render(
      <AIAnalysisBlock
        classification={classificationWithFields}
        analysedAt={ANALYSED_AT}
      />
    );
    expect(screen.getByTestId("extraction-table")).toBeInTheDocument();
  });

  it("renders a row for each extracted field", () => {
    render(
      <AIAnalysisBlock
        classification={classificationWithFields}
        analysedAt={ANALYSED_AT}
      />
    );
    // 4 fields: call_amount, due_date, fund_name, investor_name
    expect(screen.getByTestId("field-row-call_amount")).toBeInTheDocument();
    expect(screen.getByTestId("field-row-due_date")).toBeInTheDocument();
    expect(screen.getByTestId("field-row-fund_name")).toBeInTheDocument();
    expect(screen.getByTestId("field-row-investor_name")).toBeInTheDocument();
  });

  it("renders the field value in each row", () => {
    render(
      <AIAnalysisBlock
        classification={classificationWithFields}
        analysedAt={ANALYSED_AT}
      />
    );
    expect(screen.getByText("$2,500,000")).toBeInTheDocument();
    expect(screen.getByText("2026-05-15")).toBeInTheDocument();
    expect(screen.getByText("Fund III")).toBeInTheDocument();
    expect(screen.getByText("Arukai LP")).toBeInTheDocument();
  });

  it("renders source_text as 'found in' italicised line", () => {
    render(
      <AIAnalysisBlock
        classification={classificationWithFields}
        analysedAt={ANALYSED_AT}
      />
    );
    // Multiple fields have source_text — at least one "found in" span should appear
    const foundInSpans = screen.getAllByText(/found in/i, { selector: "span" });
    expect(foundInSpans.length).toBeGreaterThan(0);
  });

  it("does not render source_text line when source_text is null", () => {
    render(
      <AIAnalysisBlock
        classification={classificationWithFields}
        analysedAt={ANALYSED_AT}
      />
    );
    // investor_name has source_text: null — its row should have no "found in" span
    const row = screen.getByTestId("field-row-investor_name");
    expect(within(row).queryByText(/found in/i)).not.toBeInTheDocument();
  });

  it("renders ConfidenceBadge for a high-confidence field", () => {
    render(
      <AIAnalysisBlock
        classification={classificationWithFields}
        analysedAt={ANALYSED_AT}
      />
    );
    // fund_name has 99% → rendered as "99%"
    expect(screen.getByText("99%")).toBeInTheDocument();
  });

  it("renders a ConfidenceBadge for a low-confidence field (< 0.5)", () => {
    render(
      <AIAnalysisBlock
        classification={classificationWithFields}
        analysedAt={ANALYSED_AT}
      />
    );
    // investor_name has 0.43 → rendered with ConfidenceBadge showing "43%"
    expect(screen.getByText("43%")).toBeInTheDocument();
  });

  it("does NOT render the extraction table when extracted_fields is absent", () => {
    render(
      <AIAnalysisBlock
        classification={baseClassification}
        analysedAt={ANALYSED_AT}
      />
    );
    expect(screen.queryByTestId("extraction-table")).not.toBeInTheDocument();
  });

  it("renders overall confidence badge when no extracted_fields", () => {
    render(
      <AIAnalysisBlock
        classification={baseClassification}
        analysedAt={ANALYSED_AT}
      />
    );
    // 0.92 → "92%"
    expect(screen.getByText("92%")).toBeInTheDocument();
  });

  it("renders boolean field values as 'Yes' or 'No'", () => {
    const cls: Classification = {
      ...baseClassification,
      extracted_fields: {
        is_signed: { value: true, confidence: 0.88, source_text: null },
        is_amended: { value: false, confidence: 0.75, source_text: null },
      },
    };
    render(<AIAnalysisBlock classification={cls} analysedAt={ANALYSED_AT} />);
    expect(screen.getByText("Yes")).toBeInTheDocument();
    expect(screen.getByText("No")).toBeInTheDocument();
  });

  it("renders null field values as em-dash", () => {
    const cls: Classification = {
      ...baseClassification,
      extracted_fields: {
        unknown_field: { value: null, confidence: 0.60, source_text: null },
      },
    };
    render(<AIAnalysisBlock classification={cls} analysedAt={ANALYSED_AT} />);
    expect(screen.getByText("—")).toBeInTheDocument();
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// Exception callouts
// ─────────────────────────────────────────────────────────────────────────────

describe("AIAnalysisBlock — exception callouts", () => {
  it("shows an exception callout for fields with confidence < 0.5", () => {
    render(
      <AIAnalysisBlock
        classification={classificationWithFields}
        analysedAt={ANALYSED_AT}
      />
    );
    // investor_name has confidence 0.43 — should trigger callout
    const calloutContainer = screen.getByTestId("exception-callouts");
    expect(calloutContainer).toBeInTheDocument();
    const callouts = screen.getAllByTestId("exception-callout");
    expect(callouts.length).toBe(1);
  });

  it("exception callout mentions the field name and percentage", () => {
    render(
      <AIAnalysisBlock
        classification={classificationWithFields}
        analysedAt={ANALYSED_AT}
      />
    );
    const callout = screen.getByTestId("exception-callout");
    expect(callout).toHaveTextContent(/investor name/i);
    expect(callout).toHaveTextContent(/43%/);
    expect(callout).toHaveTextContent(/manual verification recommended/i);
  });

  it("does NOT show exception callouts when all fields are above threshold", () => {
    const cls: Classification = {
      ...baseClassification,
      extracted_fields: {
        call_amount: { value: "$2.5M", confidence: 0.97, source_text: null },
        due_date: { value: "May 15", confidence: 0.91, source_text: null },
      },
    };
    render(<AIAnalysisBlock classification={cls} analysedAt={ANALYSED_AT} />);
    expect(screen.queryByTestId("exception-callouts")).not.toBeInTheDocument();
    expect(screen.queryByTestId("exception-callout")).not.toBeInTheDocument();
  });

  it("shows multiple exception callouts when multiple fields are below threshold", () => {
    const cls: Classification = {
      ...baseClassification,
      extracted_fields: {
        field_a: { value: "X", confidence: 0.30, source_text: null },
        field_b: { value: "Y", confidence: 0.45, source_text: null },
        field_c: { value: "Z", confidence: 0.85, source_text: null },
      },
    };
    render(<AIAnalysisBlock classification={cls} analysedAt={ANALYSED_AT} />);
    const callouts = screen.getAllByTestId("exception-callout");
    expect(callouts.length).toBe(2);
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// Model attribution footer
// ─────────────────────────────────────────────────────────────────────────────

describe("AIAnalysisBlock — model attribution footer", () => {
  it("renders a model attribution element at the bottom", () => {
    render(
      <AIAnalysisBlock
        classification={baseClassification}
        analysedAt={ANALYSED_AT}
      />
    );
    const footer = screen.getByTestId("model-attribution");
    expect(footer).toBeInTheDocument();
  });

  it("footer contains the model name", () => {
    render(
      <AIAnalysisBlock
        classification={baseClassification}
        analysedAt={ANALYSED_AT}
      />
    );
    const footer = screen.getByTestId("model-attribution");
    expect(footer).toHaveTextContent(/claude-haiku-3/i);
  });

  it("footer falls back to 'Claude Haiku' when model_version is absent", () => {
    const cls: Classification = { ...baseClassification, model_version: undefined };
    render(<AIAnalysisBlock classification={cls} analysedAt={ANALYSED_AT} />);
    const footer = screen.getByTestId("model-attribution");
    expect(footer).toHaveTextContent(/claude haiku/i);
  });

  it("footer contains the formatted analysis date", () => {
    render(
      <AIAnalysisBlock
        classification={baseClassification}
        analysedAt={ANALYSED_AT}
      />
    );
    const footer = screen.getByTestId("model-attribution");
    // 2026-04-15 → "April 15, 2026"
    expect(footer).toHaveTextContent(/april 15, 2026/i);
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// Null-safety (crash guard for pre-POR-151 API responses)
// ─────────────────────────────────────────────────────────────────────────────

describe("AIAnalysisBlock — null/undefined defensive rendering", () => {
  it("does not crash when extracted_fields is null (old API response)", () => {
    // Simulate old Haiku pipeline response where extracted_fields is null
    const cls = {
      ...baseClassification,
      extracted_fields: null,
    } as unknown as Classification;
    expect(() =>
      render(<AIAnalysisBlock classification={cls} analysedAt={ANALYSED_AT} />)
    ).not.toThrow();
    expect(screen.getByTestId("ai-analysis-block")).toBeInTheDocument();
  });

  it("does not crash when extracted_fields is undefined", () => {
    const cls: Classification = { ...baseClassification, extracted_fields: undefined };
    expect(() =>
      render(<AIAnalysisBlock classification={cls} analysedAt={ANALYSED_AT} />)
    ).not.toThrow();
    expect(screen.getByTestId("ai-analysis-block")).toBeInTheDocument();
  });

  it("does not crash when key_indicators is null (old API response)", () => {
    const cls = {
      ...baseClassification,
      key_indicators: null,
    } as unknown as Classification;
    expect(() =>
      render(<AIAnalysisBlock classification={cls} analysedAt={ANALYSED_AT} />)
    ).not.toThrow();
    // Should fall back to minimal reasoning
    const reasoningEl = screen.getByTestId("classification-reasoning");
    expect(reasoningEl).toHaveTextContent(/Classified as Capital Call Notice/);
  });

  it("does not crash when classification_reasoning is null", () => {
    const cls: Classification = {
      ...baseClassification,
      classification_reasoning: null,
    };
    expect(() =>
      render(<AIAnalysisBlock classification={cls} analysedAt={ANALYSED_AT} />)
    ).not.toThrow();
    // Should fall back to key_indicators reasoning
    const reasoningEl = screen.getByTestId("classification-reasoning");
    expect(reasoningEl).toHaveTextContent(/Classified as Capital Call Notice/);
  });

  it("renders overall confidence fallback when extracted_fields is null", () => {
    const cls = {
      ...baseClassification,
      extracted_fields: null,
    } as unknown as Classification;
    render(<AIAnalysisBlock classification={cls} analysedAt={ANALYSED_AT} />);
    // 0.92 → "92%"
    expect(screen.getByText("92%")).toBeInTheDocument();
    expect(screen.queryByTestId("extraction-table")).not.toBeInTheDocument();
  });

  it("does not show exception callouts when extracted_fields is null", () => {
    const cls = {
      ...baseClassification,
      extracted_fields: null,
    } as unknown as Classification;
    render(<AIAnalysisBlock classification={cls} analysedAt={ANALYSED_AT} />);
    expect(screen.queryByTestId("exception-callouts")).not.toBeInTheDocument();
  });
});
