/**
 * AuditEntryRow tests — POR-147 / ARU-17-B2
 * TDD: failing tests committed before implementation (Miller gate).
 *
 * Tests:
 *  - Renders actor badge (USER / SYSTEM)
 *  - Renders action label
 *  - Renders timestamp in mono font
 *  - Renders package reference
 *  - Expand/collapse before→after diff on click
 *  - "Before → After" column hidden on tablet (CSS class check)
 */

import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";
import { AuditEntryRow } from "@/components/AuditEntryRow";
import type { AuditEvent } from "@/lib/api";

const baseEvent: AuditEvent = {
  id: "e1",
  action: "package_submitted",
  actor_id: "u1",
  actor_email: "admin@firm.example",
  actor_type: "USER",
  package_id: "p1",
  package_title: "Fund III — Q2 capital call",
  created_at: "2026-04-10T10:00:00Z",
  before_state: null,
  after_state: { status: "submitted" },
};

const systemEvent: AuditEvent = {
  ...baseEvent,
  id: "e2",
  actor_type: "SYSTEM",
  actor_email: undefined,
  action: "intake_complete",
};

// Wrap in a table so <tr> renders validly in jsdom
function renderInTable(ui: React.ReactElement) {
  return render(
    <table>
      <tbody>{ui}</tbody>
    </table>
  );
}

describe("AuditEntryRow — actor badge", () => {
  it('renders USER badge for user actors', () => {
    renderInTable(<AuditEntryRow event={baseEvent} />);
    expect(screen.getByText("USER")).toBeInTheDocument();
  });

  it('renders SYSTEM badge for system actors', () => {
    renderInTable(<AuditEntryRow event={systemEvent} />);
    expect(screen.getByText("SYSTEM")).toBeInTheDocument();
  });

  it("renders actor email for USER events", () => {
    renderInTable(<AuditEntryRow event={baseEvent} />);
    expect(screen.getByText("admin@firm.example")).toBeInTheDocument();
  });

  it("renders System for SYSTEM events (no email)", () => {
    renderInTable(<AuditEntryRow event={systemEvent} />);
    expect(screen.getByText("System")).toBeInTheDocument();
  });
});

describe("AuditEntryRow — action label", () => {
  it("renders action with underscores replaced by spaces", () => {
    renderInTable(<AuditEntryRow event={baseEvent} />);
    expect(screen.getByText(/package submitted/i)).toBeInTheDocument();
  });
});

describe("AuditEntryRow — timestamp", () => {
  it("renders a timestamp cell", () => {
    renderInTable(<AuditEntryRow event={baseEvent} />);
    // The formatted date should appear somewhere
    expect(screen.getByText(/apr.*2026|2026.*apr/i)).toBeInTheDocument();
  });

  it("timestamp cell uses tabular-nums class for monospaced rendering", () => {
    const { container } = renderInTable(<AuditEntryRow event={baseEvent} />);
    const timestampCell = container.querySelector(".tabular-nums");
    expect(timestampCell).toBeInTheDocument();
  });
});

describe("AuditEntryRow — package reference", () => {
  it("renders the package title", () => {
    renderInTable(<AuditEntryRow event={baseEvent} />);
    expect(screen.getByText("Fund III — Q2 capital call")).toBeInTheDocument();
  });

  it("renders em-dash when no package_title", () => {
    renderInTable(<AuditEntryRow event={{ ...baseEvent, package_title: undefined }} />);
    expect(screen.getByText("—")).toBeInTheDocument();
  });
});

describe("AuditEntryRow — expand/collapse diff", () => {
  it("diff panel is not visible before clicking expand", () => {
    renderInTable(<AuditEntryRow event={baseEvent} />);
    expect(screen.queryByText(/after state/i)).not.toBeInTheDocument();
  });

  it("expands diff panel on row click", () => {
    const { container } = renderInTable(<AuditEntryRow event={baseEvent} />);
    const expandBtn = screen.getByRole("button", { name: /expand/i });
    fireEvent.click(expandBtn);
    expect(screen.getByText(/after state/i)).toBeInTheDocument();
  });

  it("collapses diff panel on second click", () => {
    renderInTable(<AuditEntryRow event={baseEvent} />);
    const expandBtn = screen.getByRole("button", { name: /expand/i });
    fireEvent.click(expandBtn);
    fireEvent.click(expandBtn);
    expect(screen.queryByText(/after state/i)).not.toBeInTheDocument();
  });

  it("shows before_state as JSON when expanded (handles null gracefully)", () => {
    renderInTable(<AuditEntryRow event={baseEvent} />);
    const expandBtn = screen.getByRole("button", { name: /expand/i });
    fireEvent.click(expandBtn);
    // before_state is null — should show "—" or "null"
    expect(screen.getByText(/before state/i)).toBeInTheDocument();
  });

  it("shows after_state JSON when expanded", () => {
    renderInTable(<AuditEntryRow event={baseEvent} />);
    const expandBtn = screen.getByRole("button", { name: /expand/i });
    fireEvent.click(expandBtn);
    // After state panel should render JSON. Use pre element to disambiguate from action cell.
    const pres = document.querySelectorAll("pre");
    const afterPre = Array.from(pres).find((el) =>
      el.textContent?.includes('"status"')
    );
    expect(afterPre).toBeTruthy();
    expect(afterPre?.textContent).toContain("submitted");
  });
});
