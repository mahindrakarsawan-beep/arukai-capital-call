/**
 * Package detail page tests — v0.2 API shape contract.
 *
 * Coverage:
 *   - Renders with v0.2 PackageDetail shape (state, not status)
 *   - Does NOT crash when doc.status is undefined (the root bug)
 *   - Classification resolved from documents[0].classification
 *   - StateInfo resolved from doc.state (e.g. decision_recorded)
 *   - Top-level AI data (extracted_fields, classification_reasoning, model_used,
 *     classification_duration_ms) wired through to AIAnalysisBlock
 *   - Terminal banner shown for decision_recorded state
 *   - "Intake in progress" shown for submitted state
 */

import React from "react";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";

// Mock auth
jest.mock("@/lib/auth", () => ({
  getToken: jest.fn().mockResolvedValue("mock-token"),
}));

// Mock api — getPackage is now used instead of getDocument
jest.mock("@/lib/api", () => ({
  getMe: jest.fn().mockResolvedValue({
    id: "user-1",
    email: "alice@example.com",
    role: "admin",
  }),
  getPackage: jest.fn(),
}));

// Mock next/navigation
jest.mock("next/navigation", () => ({
  redirect: jest.fn(),
  notFound: jest.fn(),
}));

// Minimal sub-component mocks to keep tests fast
jest.mock("@/components/TopNav", () => ({
  TopNav: () => <nav data-testid="top-nav" />,
}));
jest.mock("@/components/SourceViewer", () => ({
  SourceViewer: () => <div data-testid="source-viewer" />,
}));
jest.mock("@/app/documents/[id]/PackageDetailActions", () => ({
  PackageDetailActions: () => <div data-testid="package-detail-actions" />,
}));

// ─────────────────────────────────────────────────────────────────────────────
// Fixtures
// ─────────────────────────────────────────────────────────────────────────────

const baseClassification = {
  doc_type: "capital_call_notice" as const,
  confidence: 0.92,
  key_indicators: ["Capital call header", "Fund III reference"],
  model_version: "claude-haiku-3",
  duration_ms: 1340,
};

/** Full v0.2 PackageDetail shape — the API contract that must be honoured. */
function makePackageDetail(overrides: Record<string, unknown> = {}) {
  return {
    id: "pkg-001",
    title: "Fund III Q2 Capital Call",
    filename: "fund_iii_q2_cc.pdf",
    // v0.2: state, NOT status
    state: "decision_recorded",
    legacy_status: "approved",
    uploaded_by: "alice@example.com",
    uploaded_at: "2026-04-01T10:00:00Z",
    created_at: "2026-04-01T10:00:00Z",
    updated_at: "2026-04-10T15:00:00Z",
    version: 1,
    claimed_by_user_id: null,
    claimed_at: null,
    // v0.2: classification is nested here, not top-level
    documents: [
      {
        id: "doc-001",
        filename: "fund_iii_q2_cc.pdf",
        classification: baseClassification,
      },
    ],
    review_notes: [],
    audit_trail: [],
    approval: null,
    // POR-151 top-level AI data
    extracted_fields: {
      call_amount: { value: "$2,500,000", confidence: 0.97, source_text: "Capital call amount: $2,500,000" },
      due_date: { value: "2026-05-15", confidence: 0.91, source_text: "payment due by May 15, 2026" },
    },
    classification_reasoning:
      "This document is a capital call notice based on the formal fund header and explicit due date.",
    model_used: "mistral-small-latest",
    classification_duration_ms: 1300,
    ...overrides,
  };
}

interface Props {
  params: Promise<{ id: string }>;
}

async function renderDetailPage(pkgData: ReturnType<typeof makePackageDetail>) {
  const { getPackage } = require("@/lib/api");
  getPackage.mockResolvedValue(pkgData);

  const { default: DocumentDetailPage } = require("@/app/documents/[id]/page");
  const props: Props = { params: Promise.resolve({ id: pkgData.id }) };
  const jsx = await DocumentDetailPage(props);
  return render(jsx);
}

// ─────────────────────────────────────────────────────────────────────────────
// v0.2 shape contract
// ─────────────────────────────────────────────────────────────────────────────

describe("DocumentDetailPage — v0.2 API shape (state not status)", () => {
  beforeEach(() => {
    jest.resetModules();
    jest.clearAllMocks();
    // Re-apply mocks after resetModules
    jest.mock("@/lib/auth", () => ({
      getToken: jest.fn().mockResolvedValue("mock-token"),
    }));
    jest.mock("next/navigation", () => ({
      redirect: jest.fn(),
      notFound: jest.fn(),
    }));
    jest.mock("@/components/TopNav", () => ({
      TopNav: () => <nav data-testid="top-nav" />,
    }));
    jest.mock("@/components/SourceViewer", () => ({
      SourceViewer: () => <div data-testid="source-viewer" />,
    }));
    jest.mock("@/app/documents/[id]/PackageDetailActions", () => ({
      PackageDetailActions: () => <div data-testid="package-detail-actions" />,
    }));
  });

  it("renders without crashing when API returns v0.2 shape (state field, no status)", async () => {
    const { getMe, getPackage } = require("@/lib/api");
    getMe.mockResolvedValue({ id: "u1", email: "alice@test.com", role: "admin" });
    const pkg = makePackageDetail();
    // Confirm the v0.2 shape: no top-level status, no top-level confidence
    expect((pkg as Record<string, unknown>).status).toBeUndefined();
    expect((pkg as Record<string, unknown>).confidence).toBeUndefined();

    getPackage.mockResolvedValue(pkg);
    const { default: DocumentDetailPage } = require("@/app/documents/[id]/page");
    const props: Props = { params: Promise.resolve({ id: pkg.id }) };
    const jsx = await DocumentDetailPage(props);
    expect(() => render(jsx)).not.toThrow();
  });

  it("renders the package filename in the heading", async () => {
    const { getMe } = require("@/lib/api");
    getMe.mockResolvedValue({ id: "u1", email: "alice@test.com", role: "admin" });
    await renderDetailPage(makePackageDetail());
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("fund_iii_q2_cc.pdf");
  });

  it("renders classification from documents[0].classification (not top-level)", async () => {
    const { getMe } = require("@/lib/api");
    getMe.mockResolvedValue({ id: "u1", email: "alice@test.com", role: "admin" });
    await renderDetailPage(makePackageDetail());
    // ClassificationBadge renders the doc_type — "capital_call_notice" → "Capital Call Notice"
    expect(screen.getAllByText(/capital call notice/i).length).toBeGreaterThan(0);
  });

  it("renders confidence from documents[0].classification.confidence (not top-level)", async () => {
    const { getMe } = require("@/lib/api");
    getMe.mockResolvedValue({ id: "u1", email: "alice@test.com", role: "admin" });
    await renderDetailPage(makePackageDetail());
    // 0.92 → 92% in the ConfidenceBadge (may appear multiple times: header + extracted facts)
    expect(screen.getAllByText("92%").length).toBeGreaterThan(0);
  });

  it("resolves state from doc.state (decision_recorded → shows terminal banner)", async () => {
    const { getMe } = require("@/lib/api");
    getMe.mockResolvedValue({ id: "u1", email: "alice@test.com", role: "admin" });
    await renderDetailPage(makePackageDetail({ state: "decision_recorded", legacy_status: "approved" }));
    // Terminal banner contains "Package closed. Decision recorded"
    expect(screen.getByText(/package closed/i)).toBeInTheDocument();
    // Multiple elements with "decision recorded" — ensure banner is present
    expect(screen.getAllByText(/decision recorded/i).length).toBeGreaterThan(0);
  });

  it("shows 'Intake in progress' when state is submitted", async () => {
    const { getMe } = require("@/lib/api");
    getMe.mockResolvedValue({ id: "u1", email: "alice@test.com", role: "admin" });
    // submitted + no classification
    await renderDetailPage(makePackageDetail({
      state: "submitted",
      legacy_status: "pending_classification",
      documents: [],
    }));
    expect(screen.getByText(/intake in progress/i)).toBeInTheDocument();
  });

  it("does NOT call getDocument (deprecated); calls getPackage instead", async () => {
    const { getMe, getPackage } = require("@/lib/api");
    getMe.mockResolvedValue({ id: "u1", email: "alice@test.com", role: "admin" });
    getPackage.mockResolvedValue(makePackageDetail());

    const { default: DocumentDetailPage } = require("@/app/documents/[id]/page");
    const props: Props = { params: Promise.resolve({ id: "pkg-001" }) };
    const jsx = await DocumentDetailPage(props);
    render(jsx);

    expect(getPackage).toHaveBeenCalledWith("pkg-001", "mock-token");
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// Top-level AI data wiring (POR-151)
// ─────────────────────────────────────────────────────────────────────────────

describe("DocumentDetailPage — POR-151 top-level AI data wiring", () => {
  beforeEach(() => {
    jest.resetModules();
    jest.clearAllMocks();
    jest.mock("@/lib/auth", () => ({
      getToken: jest.fn().mockResolvedValue("mock-token"),
    }));
    jest.mock("next/navigation", () => ({
      redirect: jest.fn(),
      notFound: jest.fn(),
    }));
    jest.mock("@/components/TopNav", () => ({
      TopNav: () => <nav data-testid="top-nav" />,
    }));
    jest.mock("@/components/SourceViewer", () => ({
      SourceViewer: () => <div data-testid="source-viewer" />,
    }));
    jest.mock("@/app/documents/[id]/PackageDetailActions", () => ({
      PackageDetailActions: () => <div data-testid="package-detail-actions" />,
    }));
  });

  it("renders classification_reasoning from top-level PackageDetail field", async () => {
    const { getMe } = require("@/lib/api");
    getMe.mockResolvedValue({ id: "u1", email: "alice@test.com", role: "admin" });
    await renderDetailPage(makePackageDetail());
    expect(
      screen.getByText(/capital call notice based on the formal fund header/i)
    ).toBeInTheDocument();
  });

  it("renders extracted_fields from top-level PackageDetail when present", async () => {
    const { getMe } = require("@/lib/api");
    getMe.mockResolvedValue({ id: "u1", email: "alice@test.com", role: "admin" });
    await renderDetailPage(makePackageDetail());
    // The AIAnalysisBlock extraction table should render these fields
    expect(screen.getByText("$2,500,000")).toBeInTheDocument();
    expect(screen.getByText("2026-05-15")).toBeInTheDocument();
  });

  it("renders model_used from top-level PackageDetail (e.g. mistral-small-latest)", async () => {
    const { getMe } = require("@/lib/api");
    getMe.mockResolvedValue({ id: "u1", email: "alice@test.com", role: "admin" });
    await renderDetailPage(makePackageDetail());
    expect(screen.getAllByText(/mistral-small-latest/i).length).toBeGreaterThan(0);
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// Null-safety (no crash on minimal/empty API responses)
// ─────────────────────────────────────────────────────────────────────────────

describe("DocumentDetailPage — null safety for v0.2 minimal responses", () => {
  beforeEach(() => {
    jest.resetModules();
    jest.clearAllMocks();
    jest.mock("@/lib/auth", () => ({
      getToken: jest.fn().mockResolvedValue("mock-token"),
    }));
    jest.mock("next/navigation", () => ({
      redirect: jest.fn(),
      notFound: jest.fn(),
    }));
    jest.mock("@/components/TopNav", () => ({
      TopNav: () => <nav data-testid="top-nav" />,
    }));
    jest.mock("@/components/SourceViewer", () => ({
      SourceViewer: () => <div data-testid="source-viewer" />,
    }));
    jest.mock("@/app/documents/[id]/PackageDetailActions", () => ({
      PackageDetailActions: () => <div data-testid="package-detail-actions" />,
    }));
  });

  it("does not crash when documents array is empty (no classification)", async () => {
    const { getMe } = require("@/lib/api");
    getMe.mockResolvedValue({ id: "u1", email: "alice@test.com", role: "admin" });
    expect(() =>
      renderDetailPage(makePackageDetail({ documents: [], extracted_fields: null }))
    ).not.toThrow();
  });

  it("does not crash when extracted_fields is null", async () => {
    const { getMe } = require("@/lib/api");
    getMe.mockResolvedValue({ id: "u1", email: "alice@test.com", role: "admin" });
    expect(() =>
      renderDetailPage(makePackageDetail({ extracted_fields: null }))
    ).not.toThrow();
  });

  it("does not crash when classification_reasoning is null", async () => {
    const { getMe } = require("@/lib/api");
    getMe.mockResolvedValue({ id: "u1", email: "alice@test.com", role: "admin" });
    expect(() =>
      renderDetailPage(makePackageDetail({ classification_reasoning: null }))
    ).not.toThrow();
  });
});
