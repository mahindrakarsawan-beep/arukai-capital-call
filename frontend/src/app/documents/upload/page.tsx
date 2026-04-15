"use client";

/**
 * Upload page — /documents/upload
 * PDF-only file input with 20MB client-side size check.
 * On success: redirects to /documents/[id] to show classification result.
 * Shows loading state while the backend classifies.
 */

import React, { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/Button";
import { StaleBanner } from "@/components/StaleBanner";

const MAX_SIZE_BYTES = 20 * 1024 * 1024; // 20 MB

export default function UploadPage() {
  const router = useRouter();
  const fileRef = useRef<HTMLInputElement>(null);
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
      setFileError("Only PDF files are accepted.");
      setFile(null);
      if (fileRef.current) fileRef.current.value = "";
      return;
    }

    if (selected.size > MAX_SIZE_BYTES) {
      setFileError("File exceeds the 20 MB limit.");
      setFile(null);
      if (fileRef.current) fileRef.current.value = "";
      return;
    }

    setFile(selected);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) {
      setFileError("Please select a PDF file to upload.");
      return;
    }

    setSubmitting(true);
    setServerError(null);

    try {
      // Get token from cookie via fetch to our own API route
      const tokenRes = await fetch("/api/token");
      const { token } = await tokenRes.json();

      if (!token) {
        router.push("/");
        return;
      }

      const form = new FormData();
      // Use filename (without extension) as the package title
      const title = file.name.replace(/\.[^/.]+$/, "") || file.name;
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
        let message = `Upload failed (${res.status})`;
        try {
          const body = await res.json();
          const raw = body?.detail ?? body?.message;
          if (typeof raw === "string") {
            message = raw;
          } else if (Array.isArray(raw) && raw.length > 0) {
            // FastAPI pydantic validation errors: [{loc, msg, type, input}]
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
        err instanceof Error ? err.message : "Upload failed. Please try again."
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
            className="font-display text-lg font-semibold text-fg-obsidian"
          >
            Arukai Capital Call
          </a>
        </div>
      </header>

      <main className="mx-auto w-full max-w-xl flex-1 px-4 py-10">
        <div className="mb-6">
          <h1 className="font-display text-2xl font-light text-fg-obsidian tracking-tight">
            Upload document
          </h1>
          <p className="mt-1 font-interface text-sm text-fg-muted">
            PDF only — max 20 MB. The document will be classified automatically.
          </p>
        </div>

        {serverError && <StaleBanner message={serverError} />}

        <form
          onSubmit={handleSubmit}
          className="rounded-lg border border-border-hairline bg-bg-bone p-6 shadow-sm"
          noValidate
        >
          <div className="flex flex-col gap-1">
            <label
              htmlFor="file"
              className="font-interface text-xs font-medium uppercase tracking-widest text-fg-muted"
            >
              PDF file
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
                to upload
              </p>
            )}
          </div>

          {submitting && (
            <div className="mt-4 rounded-md bg-[rgba(184,145,78,0.08)] px-3 py-2.5">
              <p className="font-interface text-sm text-[#9A7639]">
                Uploading and classifying document — this may take a moment…
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
              Upload and classify
            </Button>
            <a href="/documents">
              <Button type="button" variant="secondary">
                Cancel
              </Button>
            </a>
          </div>
        </form>
      </main>
    </div>
  );
}
