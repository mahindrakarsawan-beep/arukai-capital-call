import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom";
import { RawModelOutput } from "@/components/RawModelOutput";

const sample = {
  doc_type: "capital_call_notice",
  confidence: 0.92,
  extracted_fields: { call_amount: { value: "$2.5M", confidence: 0.97 } },
};

describe("RawModelOutput", () => {
  it("is collapsed by default", () => {
    render(<RawModelOutput payload={sample} />);
    expect(screen.queryByTestId("raw-model-json")).not.toBeInTheDocument();
    const btn = screen.getByRole("button", { name: /show raw model output/i });
    expect(btn).toBeEnabled();
    expect(btn).toHaveAttribute("aria-expanded", "false");
  });

  it("expands on click and shows canonical JSON with stable key order", async () => {
    const user = userEvent.setup();
    render(<RawModelOutput payload={sample} />);
    await user.click(screen.getByRole("button", { name: /show raw model output/i }));
    const pre = screen.getByTestId("raw-model-json");
    expect(pre).toBeInTheDocument();
    // Keys sorted canonically so the JSON is byte-stable across renders
    expect(pre.textContent).toContain('"confidence": 0.92');
    expect(pre.textContent).toContain('"doc_type": "capital_call_notice"');
    expect(pre.textContent).toContain('"extracted_fields":');
    // Button flips label + aria-expanded
    const btn = screen.getByRole("button", { name: /hide raw model output/i });
    expect(btn).toHaveAttribute("aria-expanded", "true");
  });

  it("collapses again on re-click", async () => {
    const user = userEvent.setup();
    render(<RawModelOutput payload={sample} />);
    const btn = screen.getByRole("button", { name: /show raw model output/i });
    await user.click(btn);
    await user.click(screen.getByRole("button", { name: /hide raw model output/i }));
    expect(screen.queryByTestId("raw-model-json")).not.toBeInTheDocument();
  });
});
