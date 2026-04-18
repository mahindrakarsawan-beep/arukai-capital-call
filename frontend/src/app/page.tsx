"use client";

/**
 * Login page — / (spec §8)
 * Obsidian background, bone card, Cormorant wordmark, DM Sans interface.
 * Submit button: neutral dark (never brass on login — spec §8.2).
 * Copy: "Authorized access", "Enter workflow", "Credentialed email", "Passphrase".
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
    <main
      className="flex min-h-screen flex-col items-center justify-center px-4 py-24"
      style={{ backgroundColor: "#0D0F12" }}
    >
      {/* Wordmark — top third */}
      <div className="mb-10 text-center">
        <h1 className="font-display text-[40px] font-light tracking-tight" style={{ color: "#FAFAF8" }}>
          Arukai
        </h1>
        <p className="mt-2 font-interface text-sm" style={{ color: "rgba(250,250,248,0.55)" }}>
          Private workflow environment
        </p>
      </div>

      {/* Auth card — bgBone surface per spec §8.2 */}
      <div
        className="w-full rounded-[24px] border p-8 md:p-10"
        style={{
          maxWidth: "448px",
          backgroundColor: "#FAFAF8",
          borderColor: "rgba(26,31,40,0.10)",
          boxShadow: "0 4px 24px 0 rgba(0,0,0,0.18), 0 1px 4px 0 rgba(0,0,0,0.10)",
        }}
      >
        <h2 className="mb-1 font-display text-2xl font-light text-fg-obsidian tracking-tight">
          Authorized access
        </h2>
        <p className="mb-6 font-interface text-sm text-fg-muted">
          Governed capital-call review. Credentialed access only.
        </p>

        <form action={formAction} className="flex flex-col gap-4" noValidate>
          <Input
            id="email"
            name="email"
            type="email"
            label="Credentialed email"
            placeholder="name@firm.example"
            autoComplete="email"
            required
          />
          <Input
            id="password"
            name="password"
            type="password"
            label="Passphrase"
            placeholder="••••••••"
            autoComplete="current-password"
            required
          />

          {state?.error && (
            <p
              className="rounded-md bg-[rgba(178,58,46,0.08)] px-3 py-2 font-interface text-sm text-data-negative"
              role="alert"
            >
              Credentials not recognized. Access not granted.
            </p>
          )}

          {/* Submit: neutral dark — never brass on login (spec §8.2) */}
          <Button type="submit" variant="primary" loading={isPending}>
            Enter workflow
          </Button>
        </form>
      </div>
    </main>
  );
}
