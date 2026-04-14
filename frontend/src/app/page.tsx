"use client";

/**
 * Login page — /
 * Email + password form, POST /auth/login via server action,
 * stores JWT in httpOnly cookie, redirects to /documents on success.
 */

import React, { useActionState } from "react";
import { loginAction } from "@/lib/actions";
import { Button } from "@/components/Button";
import { Input } from "@/components/Input";

const initialState = { error: null as string | null };

export default function LoginPage() {
  const [state, formAction, isPending] = useActionState(
    loginAction,
    initialState
  );

  return (
    <main className="flex min-h-screen items-center justify-center bg-bg-parchment px-4">
      <div className="w-full max-w-sm">
        {/* Wordmark */}
        <div className="mb-8 text-center">
          <h1 className="font-display text-3xl font-light text-fg-obsidian tracking-tight">
            Arukai
          </h1>
          <p className="mt-1 font-interface text-sm text-fg-muted">
            Capital Call Management
          </p>
        </div>

        {/* Card */}
        <div className="rounded-lg border border-border-hairline bg-bg-bone p-6 shadow-sm">
          <h2 className="mb-6 font-interface text-base font-semibold text-fg-obsidian">
            Sign in
          </h2>

          <form action={formAction} className="flex flex-col gap-4" noValidate>
            <Input
              id="email"
              name="email"
              type="email"
              label="Email"
              placeholder="you@example.com"
              autoComplete="email"
              required
            />
            <Input
              id="password"
              name="password"
              type="password"
              label="Password"
              placeholder="••••••••"
              autoComplete="current-password"
              required
            />

            {state?.error && (
              <p
                className="rounded-md bg-[rgba(178,58,46,0.08)] px-3 py-2 font-interface text-sm text-data-negative"
                role="alert"
              >
                {state.error}
              </p>
            )}

            <Button type="submit" variant="primary" loading={isPending}>
              Sign in
            </Button>
          </form>
        </div>
      </div>
    </main>
  );
}
