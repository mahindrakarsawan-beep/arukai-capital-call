"use client";

/**
 * Intake page — /documents/upload (spec §1.2, §1.7)
 * H1: "Begin governed intake"
 * Subtext: per spec §1.2 upload subtext.
 * Submit: "Submit package for intake"
 * Cancel: "Discard draft"
 * File label: "Source PDF"
 */

import React, { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/Button";
import { StaleBanner } from "@/components/StaleBanner";

const MAX_SIZE_BYTES = 20 * 1024 * 1024; // 20 MB

export default function UploadPage() {
  const router = useRouter();
  const fileRef = useRef<HTMLInputElement>(null);
  const titleRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const selected = e.target.files?.[0] ?? null;
    setFileError(null);
    setServerError(null);

    if (!selected) {
      setFile(null);
      return;
    }

    if (selected.type !== "application/pdf") {
      setFileError("Only PDF packages are accepted for intake.");
      setFile(null);
      if (fileRef.current) fileRef.current.value = "";
      return;
    }

    if (selected.size > MAX_SIZE_BYTES) {
      setFileError("File exceeds the 20 MB intake limit.");
      setFile(null);
      if (fileRef.current) fileRef.current.value = "";
      return;
    }

    setFile(selected);
    // Auto-fill package reference from filename if blank
    if (titleRef.current && !titleRef.current.value) {
      titleRef.current.value = selected.name.replace(/\.[^/.]+$/, "") || selected.name;
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) {
      setFileError("Select a PDF package to begin intake.");
      return;
    }

    setSubmitting(true);
    setServerError(null);

    try {
      const tokenRes = await fetch("/api/token");
      const { token } = await tokenRes.json();

      if (!token) {
        router.push("/");
        return;
      }

      const form = new FormData();
      const title =
        (titleRef.current?.value?.trim()) ||
        file.name.replace(/\.[^/.]+$/, "") ||
        file.name;
      form.append("title", title);
      form.append("file", file);

      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/documents/upload`,
        {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
          body: form,
        }
      );

      if (!res.ok) {
        let message = `Intake failed (${res.status})`;
        try {
          const body = await res.json();
          const raw = body?.detail ?? body?.message;
          if (typeof raw === "string") {
            message = raw;
          } else if (Array.isArray(raw) && raw.length > 0) {
            message = raw.map((e: { msg?: string }) => e?.msg ?? JSON.stringify(e)).join("; ");
          } else if (raw != null) {
            message = JSON.stringify(raw);
          }
        } catch {
          // ignore
        }
        setServerError(message);
        return;
      }

      const doc = await res.json();
      router.push(`/documents/${doc.id}`);
    } catch (err) {
      setServerError(
        err instanceof Error ? err.message : "Package submitted. Intake in progress."
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen flex-col">
      {/* Minimal nav */}
      <header className="border-b border-border-hairline bg-bg-bone sticky top-0">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
          <a
            href="/documents"
            className="font-display text-lg font-light text-fg-obsidian tracking-tight"
          >
            Arukai
          </a>
          <a
            href="/documents"
            className="font-interface text-sm text-fg-muted hover:text-fg-obsidian transition-colors duration-fast"
          >
            Console
          </a>
        </div>
      </header>

      <main className="mx-auto w-full max-w-xl flex-1 px-4 py-10">
        <div className="mb-6">
          <h1 className="font-display text-2xl font-light text-fg-obsidian tracking-tight">
            Begin governed intake
          </h1>
          <p className="mt-1 font-interface text-sm text-fg-muted">
            Submit a capital-call package. Intake is governed: classification, review, and
            attestation steps are recorded. PDF, up to 20 MB.
          </p>
        </div>

        {serverError && <StaleBanner message={serverError} />}

        <form
          onSubmit={handleSubmit}
          className="rounded-lg border border-border-hairline bg-bg-bone p-6 shadow-sm"
          noValidate
        >
          {/* Package reference */}
          <div className="mb-4 flex flex-col gap-1">
            <label
              htmlFor="title"
              className="font-interface text-xs font-medium uppercase tracking-widest text-fg-muted"
            >
              Package reference
            </label>
            <input
              ref={titleRef}
              id="title"
              name="title"
              type="text"
              placeholder="e.g. Fund III — Q2 capital call"
              className="w-full rounded-md border border-border-hairline bg-bg-parchment px-3 py-2 font-interface text-sm text-fg-obsidian placeholder:text-fg-muted focus:outline-none focus:ring-2 focus:ring-fg-slate focus:ring-offset-0"
            />
          </div>

          {/* Source PDF */}
          <div className="flex flex-col gap-1">
            <label
              htmlFor="file"
              className="font-interface text-xs font-medium uppercase tracking-widest text-fg-muted"
            >
              Source PDF
            </label>
            <input
              ref={fileRef}
              id="file"
              name="file"
              type="file"
              accept="application/pdf"
              onChange={handleFileChange}
              className="block w-full rounded-md border border-border-hairline bg-bg-parchment px-3 py-2 font-interface text-sm text-fg-obsidian file:mr-3 file:rounded file:border-0 file:bg-fg-obsidian file:px-3 file:py-1 file:font-interface file:text-xs file:text-bg-bone file:font-medium cursor-pointer"
            />
            {/* Placeholder text for file input */}
            <span className="sr-only">Select package PDF</span>
            {fileError && (
              <p
                className="font-interface text-xs text-data-negative"
                role="alert"
              >
                {fileError}
              </p>
            )}
            {file && !fileError && (
              <p className="font-interface text-xs text-data-positive">
                {file.name} ({(file.size / 1024 / 1024).toFixed(2)} MB) — ready
              </p>
            )}
          </div>

          {submitting && (
            <div className="mt-4 rounded-md bg-[rgba(60,72,88,0.06)] px-3 py-2.5">
              <p className="font-interface text-sm text-fg-slate">
                Package submitted. Intake in progress…
              </p>
            </div>
          )}

          <div className="mt-6 flex gap-3">
            <Button
              type="submit"
              variant="primary"
              loading={submitting}
              disabled={!file || submitting}
            >
              Submit package for intake
            </Button>
            <a href="/documents">
              <Button type="button" variant="secondary">
                Discard draft
              </Button>
            </a>
          </div>
        </form>
      </main>
    </div>
  );
}
