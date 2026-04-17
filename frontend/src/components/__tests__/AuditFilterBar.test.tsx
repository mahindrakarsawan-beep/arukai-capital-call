/**
 * AuditFilterBar tests — POR-147 / ARU-17-B2
 * TDD: failing tests committed before implementation (Miller gate).
 *
 * Tests:
 *  - Renders 4 filter inputs (actor, action, date from, date to)
 *  - "Apply filters" button calls onApply with current values
 *  - "Clear" ghost button resets all fields and calls onClear
 *  - Placeholder / label copy matches spec §1.7
 */

import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom";
import { AuditFilterBar } from "@/components/AuditFilterBar";

const noop = jest.fn();

describe("AuditFilterBar — filter inputs present", () => {
  beforeEach(() => jest.clearAllMocks());

  it('renders "Filter by actor" select/input', () => {
    render(<AuditFilterBar onApply={noop} onClear={noop} />);
    expect(screen.getByLabelText(/filter by actor/i)).toBeInTheDocument();
  });

  it('renders "Filter by action" select/input', () => {
    render(<AuditFilterBar onApply={noop} onClear={noop} />);
    expect(screen.getByLabelText(/filter by action/i)).toBeInTheDocument();
  });

  it('renders "From" date input', () => {
    render(<AuditFilterBar onApply={noop} onClear={noop} />);
    expect(screen.getByLabelText(/from/i)).toBeInTheDocument();
  });

  it('renders "To" date input', () => {
    render(<AuditFilterBar onApply={noop} onClear={noop} />);
    // Use the exact label text to avoid ambiguity with "From"
    expect(screen.getByLabelText("To")).toBeInTheDocument();
  });

  it('renders "Apply filters" button', () => {
    render(<AuditFilterBar onApply={noop} onClear={noop} />);
    expect(screen.getByRole("button", { name: /apply filters/i })).toBeInTheDocument();
  });

  it('renders "Clear" button', () => {
    render(<AuditFilterBar onApply={noop} onClear={noop} />);
    expect(screen.getByRole("button", { name: /^clear$/i })).toBeInTheDocument();
  });
});

describe("AuditFilterBar — apply callback", () => {
  it("calls onApply with current filter values on Apply click", async () => {
    const onApply = jest.fn();
    render(<AuditFilterBar onApply={onApply} onClear={noop} />);

    const actionInput = screen.getByLabelText(/filter by action/i);
    await userEvent.type(actionInput, "package_submitted");

    fireEvent.click(screen.getByRole("button", { name: /apply filters/i }));

    expect(onApply).toHaveBeenCalledTimes(1);
    expect(onApply).toHaveBeenCalledWith(
      expect.objectContaining({ action: "package_submitted" })
    );
  });

  it("calls onApply with empty object when no filters set", () => {
    const onApply = jest.fn();
    render(<AuditFilterBar onApply={onApply} onClear={noop} />);
    fireEvent.click(screen.getByRole("button", { name: /apply filters/i }));
    expect(onApply).toHaveBeenCalledWith(
      expect.objectContaining({ action: "" })
    );
  });
});

describe("AuditFilterBar — clear callback", () => {
  it("calls onClear when Clear button clicked", () => {
    const onClear = jest.fn();
    render(<AuditFilterBar onApply={noop} onClear={onClear} />);
    fireEvent.click(screen.getByRole("button", { name: /^clear$/i }));
    expect(onClear).toHaveBeenCalledTimes(1);
  });

  it("resets all inputs after Clear click", async () => {
    const onClear = jest.fn();
    render(<AuditFilterBar onApply={noop} onClear={onClear} />);

    const actionInput = screen.getByLabelText(/filter by action/i) as HTMLInputElement;
    await userEvent.type(actionInput, "some_action");
    expect(actionInput.value).toBe("some_action");

    fireEvent.click(screen.getByRole("button", { name: /^clear$/i }));
    expect(actionInput.value).toBe("");
  });
});

describe("AuditFilterBar — initial values", () => {
  it("accepts and displays initial filter values", () => {
    render(
      <AuditFilterBar
        onApply={noop}
        onClear={noop}
        initialValues={{ action: "package_submitted", actor_id: "", from_date: "", to_date: "" }}
      />
    );
    const actionInput = screen.getByLabelText(/filter by action/i) as HTMLInputElement;
    expect(actionInput.value).toBe("package_submitted");
  });
});
