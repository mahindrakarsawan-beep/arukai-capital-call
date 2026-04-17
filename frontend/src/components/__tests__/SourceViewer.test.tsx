/**
 * SourceViewer tests — A3 (POR-147).
 *
 * Covers:
 *  1. Renders loading state initially
 *  2. Success path: fetches blob, creates object URL, iframe renders
 *  3. 401 path: shows "Session expired" message
 *  4. 500 path: shows StaleBanner with retry
 *  5. Unmount revokes object URL (memory leak prevention)
 *  6. Mobile variant: tap-to-expand accordion
 */

import React from "react";
import { render, screen, act, waitFor, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";
import { SourceViewer } from "@/components/SourceViewer";

// ─── Mocks ────────────────────────────────────────────────────────────────────

const MOCK_BLOB_URL = "blob:http://localhost/mock-pdf-123";

// Mock URL.createObjectURL / revokeObjectURL — must be set before any import
// that uses them, so we use jest.spyOn after the initial assignment.
const createObjectURLMock = jest.fn().mockReturnValue(MOCK_BLOB_URL);
const revokeObjectURLMock = jest.fn();
global.URL.createObjectURL = createObjectURLMock;
global.URL.revokeObjectURL = revokeObjectURLMock;

// Default props
const defaultProps = {
  documentId: "doc-abc",
  filename: "fund-iii-q2-capital-call.pdf",
  sizeBytes: 862_208, // ~842 KB
  uploadedAt: "2026-04-10T09:30:00Z",
};

// Typed mock fetch
let fetchMock: jest.Mock;

// Mock response builders — all return plain objects matching the fetch Response
// interface shape that SourceViewer actually reads (.ok, .status, .json, .blob).
function makeTokenOkResponse() {
  return {
    ok: true,
    status: 200,
    json: () => Promise.resolve({ token: "jwt-test-token" }),
    blob: () => Promise.reject(new Error("not a blob")),
  };
}

function makePdfOkResponse() {
  const blob = new Blob(["PDF content"], { type: "application/pdf" });
  return {
    ok: true,
    status: 200,
    json: () => Promise.reject(new Error("not json")),
    blob: () => Promise.resolve(blob),
  };
}

function makePdf401Response() {
  return { ok: false, status: 401, json: () => Promise.resolve({}), blob: () => Promise.resolve(new Blob()) };
}

function makePdf500Response() {
  return { ok: false, status: 500, json: () => Promise.resolve({}), blob: () => Promise.resolve(new Blob()) };
}

function makeTokenNullResponse() {
  return {
    ok: true,
    status: 200,
    json: () => Promise.resolve({ token: null }),
    blob: () => Promise.reject(new Error("not a blob")),
  };
}

/**
 * Set up fetch mock to return the given response objects in sequence.
 * Each element is a plain object (not a factory function).
 */
function setupFetchMock(responses: object[]) {
  let callIndex = 0;
  fetchMock.mockImplementation(() => {
    const resp = responses[callIndex] ?? responses[responses.length - 1];
    callIndex++;
    return Promise.resolve(resp);
  });
}

// ─── Setup / teardown ────────────────────────────────────────────────────────

beforeEach(() => {
  fetchMock = jest.fn();
  global.fetch = fetchMock;
  createObjectURLMock.mockClear().mockReturnValue(MOCK_BLOB_URL);
  revokeObjectURLMock.mockClear();
});

// ─── Tests ───────────────────────────────────────────────────────────────────

describe("SourceViewer — loading state", () => {
  it("renders loading skeleton before fetch completes", () => {
    // Never resolves — stays loading
    fetchMock.mockReturnValue(new Promise(() => {}));

    render(<SourceViewer {...defaultProps} />);

    expect(screen.getByLabelText("Loading source document")).toBeInTheDocument();
    expect(screen.getByTestId("source-viewer-loading")).toBeInTheDocument();
  });
});

describe("SourceViewer — success path", () => {
  it("fetches blob, creates object URL, and renders iframe", async () => {
    setupFetchMock([makeTokenOkResponse(), makePdfOkResponse()]);

    render(<SourceViewer {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByTestId("source-viewer-ready")).toBeInTheDocument();
    });

    // Iframe rendered with blob URL
    const iframes = screen.getAllByTestId("source-viewer-iframe");
    expect(iframes.length).toBeGreaterThan(0);
    expect(iframes[0]).toHaveAttribute("src", MOCK_BLOB_URL);

    // URL.createObjectURL called once with a blob
    expect(createObjectURLMock).toHaveBeenCalledTimes(1);
    expect(createObjectURLMock.mock.calls[0][0]).toBeInstanceOf(Blob);
  });

  it("fetches token first, then PDF with Authorization header", async () => {
    setupFetchMock([makeTokenOkResponse(), makePdfOkResponse()]);

    render(<SourceViewer {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByTestId("source-viewer-ready")).toBeInTheDocument();
    });

    const calls = fetchMock.mock.calls;
    // First call: /api/token (no auth header needed)
    expect(calls[0][0]).toBe("/api/token");
    // Second call: PDF URL with Authorization
    expect(calls[1][0]).toContain("/documents/doc-abc/pdf");
    expect(calls[1][1]?.headers?.Authorization).toBe("Bearer jwt-test-token");
  });

  it("shows filename and formatted file size in metadata", async () => {
    setupFetchMock([makeTokenOkResponse(), makePdfOkResponse()]);

    render(<SourceViewer {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByTestId("source-viewer-ready")).toBeInTheDocument();
    });

    expect(screen.getAllByTitle("fund-iii-q2-capital-call.pdf").length).toBeGreaterThan(0);
    // 862_208 bytes → ~842 KB
    expect(screen.getAllByText(/842 KB/i).length).toBeGreaterThan(0);
  });
});

describe("SourceViewer — 401 path", () => {
  it("shows 'Session expired' message on 401", async () => {
    setupFetchMock([makeTokenOkResponse(), makePdf401Response()]);

    render(<SourceViewer {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByTestId("source-viewer-auth-error")).toBeInTheDocument();
    });

    expect(
      screen.getByText(/session expired\. please re-authenticate/i)
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /re-enter workflow/i })).toBeInTheDocument();
  });

  it("shows 'Session expired' when token bridge returns null", async () => {
    setupFetchMock([makeTokenNullResponse()]);

    render(<SourceViewer {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByTestId("source-viewer-auth-error")).toBeInTheDocument();
    });

    expect(
      screen.getByText(/session expired\. please re-authenticate/i)
    ).toBeInTheDocument();
  });
});

describe("SourceViewer — error path", () => {
  it("shows StaleBanner with retry button on 500", async () => {
    setupFetchMock([makeTokenOkResponse(), makePdf500Response()]);

    render(<SourceViewer {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByTestId("source-viewer-error")).toBeInTheDocument();
    });

    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("retry button re-fetches on click", async () => {
    // First render: 500; retry: success
    setupFetchMock([
      makeTokenOkResponse(),
      makePdf500Response(),
      makeTokenOkResponse(),
      makePdfOkResponse(),
    ]);

    render(<SourceViewer {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByTestId("source-viewer-error")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /retry/i }));

    await waitFor(() => {
      expect(screen.getByTestId("source-viewer-ready")).toBeInTheDocument();
    });
  });

  it("shows StaleBanner on network error (fetch throws)", async () => {
    fetchMock
      .mockResolvedValueOnce(makeTokenOkResponse())
      .mockRejectedValueOnce(new Error("Network error"));

    render(<SourceViewer {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByTestId("source-viewer-error")).toBeInTheDocument();
    });
  });
});

describe("SourceViewer — memory leak: unmount revokes blob URL", () => {
  it("calls URL.revokeObjectURL on unmount", async () => {
    setupFetchMock([makeTokenOkResponse(), makePdfOkResponse()]);

    const { unmount } = render(<SourceViewer {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByTestId("source-viewer-ready")).toBeInTheDocument();
    });

    expect(createObjectURLMock).toHaveBeenCalledTimes(1);
    expect(revokeObjectURLMock).not.toHaveBeenCalled();

    act(() => {
      unmount();
    });

    expect(revokeObjectURLMock).toHaveBeenCalledTimes(1);
    expect(revokeObjectURLMock).toHaveBeenCalledWith(MOCK_BLOB_URL);
  });
});

describe("SourceViewer — mobile accordion", () => {
  it("renders mobile toggle button", async () => {
    setupFetchMock([makeTokenOkResponse(), makePdfOkResponse()]);

    render(<SourceViewer {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByTestId("source-viewer-ready")).toBeInTheDocument();
    });

    const toggle = screen.getByTestId("source-viewer-mobile-toggle");
    expect(toggle).toBeInTheDocument();
    expect(toggle).toHaveAttribute("aria-expanded", "false");
  });

  it("expands accordion on tap to show mobile iframe", async () => {
    setupFetchMock([makeTokenOkResponse(), makePdfOkResponse()]);

    render(<SourceViewer {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByTestId("source-viewer-ready")).toBeInTheDocument();
    });

    const toggle = screen.getByTestId("source-viewer-mobile-toggle");
    expect(screen.queryByTestId("source-viewer-mobile-panel")).not.toBeInTheDocument();

    fireEvent.click(toggle);

    expect(screen.getByTestId("source-viewer-mobile-panel")).toBeInTheDocument();
    expect(toggle).toHaveAttribute("aria-expanded", "true");
  });

  it("collapses accordion on second tap", async () => {
    setupFetchMock([makeTokenOkResponse(), makePdfOkResponse()]);

    render(<SourceViewer {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByTestId("source-viewer-ready")).toBeInTheDocument();
    });

    const toggle = screen.getByTestId("source-viewer-mobile-toggle");
    fireEvent.click(toggle); // expand
    expect(screen.getByTestId("source-viewer-mobile-panel")).toBeInTheDocument();

    fireEvent.click(toggle); // collapse
    expect(screen.queryByTestId("source-viewer-mobile-panel")).not.toBeInTheDocument();
    expect(toggle).toHaveAttribute("aria-expanded", "false");
  });
});
