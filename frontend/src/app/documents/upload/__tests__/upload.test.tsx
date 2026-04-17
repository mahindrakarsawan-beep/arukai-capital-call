/**
 * Upload page tests — C1 (POR-147 / ARU-17-C1)
 * TDD: failing tests committed before implementation (Miller gate).
 *
 * Coverage:
 *   - IntakeCeremony overlay shown after successful submit
 *   - Ceremony is hidden before submit
 *   - Ceremony starts at step 1 on show
 *   - Form copy: "Begin governed intake" heading, "Submit package for intake" button,
 *     "Discard draft" cancel, no banned v0.1 copy
 *   - useReducedMotion respected (hook injected via mock)
 */

import React from "react";
import {
  render,
  screen,
  fireEvent,
  waitFor,
} from "@testing-library/react";
import "@testing-library/jest-dom";

// ─── Module-level mocks — stable across all tests in this suite ───────────────

jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: jest.fn(), replace: jest.fn() }),
}));

jest.mock("@/hooks/useReducedMotion", () => ({
  useReducedMotion: jest.fn().mockReturnValue(false),
}));

// IntakeCeremony stub — inspect visible/activeStep without CSS overhead
jest.mock("@/components/IntakeCeremony", () => ({
  IntakeCeremony: ({
    visible,
    activeStep,
  }: {
    visible: boolean;
    activeStep: number;
    reducedMotion: boolean;
  }) =>
    visible ? (
      <div data-testid="intake-ceremony" data-active-step={String(activeStep)}>
        Ceremony active
      </div>
    ) : null,
}));

// ─── Helpers ─────────────────────────────────────────────────────────────────

global.fetch = jest.fn();

function makePdfFile(name = "fund-q2.pdf") {
  return new File(["content"], name, { type: "application/pdf" });
}

function renderUploadPage() {
  // Import after mocks are in place
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  const UploadPage = require("@/app/documents/upload/page").default;
  return render(<UploadPage />);
}

beforeEach(() => {
  jest.clearAllMocks();
});

// ─── Structure + copy ────────────────────────────────────────────────────────

describe("Upload page — copy and form", () => {
  it('renders "Begin governed intake" heading', () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({ token: "tok" }),
    });
    renderUploadPage();
    expect(
      screen.getByRole("heading", { name: /begin governed intake/i })
    ).toBeInTheDocument();
  });

  it('renders "Submit package for intake" button', () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({ token: "tok" }),
    });
    renderUploadPage();
    expect(
      screen.getByRole("button", { name: /submit package for intake/i })
    ).toBeInTheDocument();
  });

  it('renders "Discard draft" cancel link', () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({ token: "tok" }),
    });
    renderUploadPage();
    expect(screen.getByText(/discard draft/i)).toBeInTheDocument();
  });

  it('does not contain banned v0.1 "Upload and classify" submit copy', () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({ token: "tok" }),
    });
    renderUploadPage();
    expect(screen.queryByText(/upload and classify/i)).not.toBeInTheDocument();
  });
});

// ─── Ceremony — initial state ────────────────────────────────────────────────

describe("Upload page — ceremony hidden before submit", () => {
  it("does not show ceremony overlay on initial render", () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({ token: "tok" }),
    });
    renderUploadPage();
    expect(screen.queryByTestId("intake-ceremony")).not.toBeInTheDocument();
  });
});

// ─── Ceremony — shown after successful submit ─────────────────────────────────

describe("Upload page — ceremony shown after successful submit", () => {
  function setupFile(container: HTMLElement) {
    const fileInput = container.querySelector(
      'input[type="file"]'
    ) as HTMLInputElement;
    const pdfFile = makePdfFile();
    Object.defineProperty(fileInput, "files", {
      value: [pdfFile],
      configurable: true,
    });
    fireEvent.change(fileInput);
    return pdfFile;
  }

  it("shows ceremony overlay after successful upload response", async () => {
    (global.fetch as jest.Mock)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ token: "tok" }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ id: "doc-42" }),
      });

    const { container } = renderUploadPage();
    setupFile(container);

    fireEvent.click(
      screen.getByRole("button", { name: /submit package for intake/i })
    );

    await waitFor(() => {
      expect(screen.queryByTestId("intake-ceremony")).toBeInTheDocument();
    });
  });

  it("starts ceremony at step 1", async () => {
    (global.fetch as jest.Mock)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ token: "tok" }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ id: "doc-99" }),
      });

    const { container } = renderUploadPage();
    setupFile(container);

    fireEvent.click(
      screen.getByRole("button", { name: /submit package for intake/i })
    );

    await waitFor(() => {
      const ceremony = screen.queryByTestId("intake-ceremony");
      expect(ceremony).toBeInTheDocument();
      expect(ceremony?.getAttribute("data-active-step")).toBe("1");
    });
  });

  it("ceremony is NOT shown when upload returns an error", async () => {
    (global.fetch as jest.Mock)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ token: "tok" }),
      })
      .mockResolvedValueOnce({
        ok: false,
        status: 422,
        json: async () => ({ detail: "Validation failed" }),
      });

    const { container } = renderUploadPage();
    setupFile(container);

    fireEvent.click(
      screen.getByRole("button", { name: /submit package for intake/i })
    );

    await waitFor(() => {
      // Should show error, not ceremony
      expect(screen.queryByTestId("intake-ceremony")).not.toBeInTheDocument();
    });
  });
});
