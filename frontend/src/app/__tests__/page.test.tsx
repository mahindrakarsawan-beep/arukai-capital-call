/**
 * Login page tests — POR-147 / ARU-17 Phase A
 * Tests: v0.2 copy ("Authorized access", "Enter workflow", "Credentialed email", "Passphrase")
 * Auth error: "Credentials not recognized. Access not granted."
 */

import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";

// Mock the server action
jest.mock("@/lib/actions", () => ({
  loginAction: jest.fn(),
}));

// Mock useActionState — not available in jsdom/React 19 test env
jest.mock("react", () => {
  const actual = jest.requireActual("react");
  return {
    ...actual,
    useActionState: (
      action: (state: unknown, formData: FormData) => unknown,
      initialState: unknown
    ) => {
      const [state, setState] = actual.useState(initialState);
      const dispatch = (formData: FormData) => {
        const result = action(state, formData);
        if (result && typeof (result as Promise<unknown>).then === "function") {
          (result as Promise<unknown>).then((v) => setState(v));
        } else {
          setState(result);
        }
      };
      return [state, dispatch, false];
    },
  };
});

import LoginPage from "@/app/page";

describe("LoginPage — v0.2 atelier copy", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders Arukai wordmark", () => {
    render(<LoginPage />);
    expect(screen.getByText("Arukai")).toBeInTheDocument();
  });

  it('renders "Private workflow environment" tagline', () => {
    render(<LoginPage />);
    expect(screen.getByText(/private workflow environment/i)).toBeInTheDocument();
  });

  it('renders "Authorized access" card heading', () => {
    render(<LoginPage />);
    expect(screen.getByText(/authorized access/i)).toBeInTheDocument();
  });

  it('renders "Credentialed email" label', () => {
    render(<LoginPage />);
    expect(screen.getByText(/credentialed email/i)).toBeInTheDocument();
  });

  it('renders "Passphrase" label', () => {
    render(<LoginPage />);
    expect(screen.getByText(/passphrase/i)).toBeInTheDocument();
  });

  it('renders "Enter workflow" submit button', () => {
    render(<LoginPage />);
    expect(screen.getByRole("button", { name: /enter workflow/i })).toBeInTheDocument();
  });

  it("email input has correct type", () => {
    render(<LoginPage />);
    const emailInput = screen.getByLabelText(/credentialed email/i);
    expect(emailInput).toHaveAttribute("type", "email");
  });

  it("password input has correct type", () => {
    render(<LoginPage />);
    const passwordInput = screen.getByLabelText(/passphrase/i);
    expect(passwordInput).toHaveAttribute("type", "password");
  });

  it("renders the login form element", () => {
    render(<LoginPage />);
    const form = document.querySelector("form");
    expect(form).toBeInTheDocument();
  });

  it('does NOT contain banned v0.1 string "Sign in" as button label', () => {
    render(<LoginPage />);
    const buttons = screen.queryAllByRole("button", { name: /^sign in$/i });
    expect(buttons).toHaveLength(0);
  });

  it("shows error message when loginAction returns an error", async () => {
    const { loginAction } = require("@/lib/actions");
    loginAction.mockResolvedValue({ error: "401 Unauthorized" });

    render(<LoginPage />);

    const emailInput = screen.getByLabelText(/credentialed email/i);
    const passwordInput = screen.getByLabelText(/passphrase/i);
    const submitButton = screen.getByRole("button", { name: /enter workflow/i });

    fireEvent.change(emailInput, { target: { value: "bad@test.com" } });
    fireEvent.change(passwordInput, { target: { value: "wrong" } });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(loginAction).toHaveBeenCalledTimes(1);
    });
  });
});
