"use client";

/**
 * SourceViewer — A3 auth fix (POR-147).
 *
 * Fetches the protected PDF via /api/token bridge → Authorization header →
 * blob URL → iframe src. Revokes the blob URL on unmount to prevent leaks.
 *
 * Desktop: inline iframe + "View source document" link + metadata row.
 * Mobile (≤ sm): tap-to-expand accordion — collapsed shows metadata only,
 *   expanded reveals the iframe (per Figma nodes 44:37 / 44:40).
 *
 * Error states:
 *   401 → "Session expired" message with re-auth link
 *   other → StaleBanner with retry button
 */

import React, { useCallback, useEffect, useRef, useState } from "react";
import { StaleBanner } from "@/components/StaleBanner";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface SourceViewerProps {
  documentId: string;
  filename: string;
  sizeBytes: number;
  uploadedAt: string;
}

type LoadState = "loading" | "ready" | "auth_error" | "error";

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch {
    return iso;
  }
}

export function SourceViewer({
  documentId,
  filename,
  sizeBytes,
  uploadedAt,
}: SourceViewerProps) {
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false); // mobile accordion
  const blobUrlRef = useRef<string | null>(null);

  const fetchPdf = useCallback(async () => {
    setLoadState("loading");

    try {
      // Step 1: get JWT from same-origin bridge
      const tokenRes = await fetch("/api/token");
      if (!tokenRes.ok) {
        setLoadState("auth_error");
        return;
      }
      const { token } = await tokenRes.json();
      if (!token) {
        setLoadState("auth_error");
        return;
      }

      // Step 2: fetch protected PDF with Authorization header
      const pdfRes = await fetch(`${API_BASE}/documents/${documentId}/pdf`, {
        headers: { Authorization: `Bearer ${token}` },
      });

      if (pdfRes.status === 401 || pdfRes.status === 403) {
        setLoadState("auth_error");
        return;
      }

      if (!pdfRes.ok) {
        setLoadState("error");
        return;
      }

      // Step 3: create blob URL
      const blob = await pdfRes.blob();
      const url = URL.createObjectURL(blob);

      // Revoke any previous blob URL before storing the new one
      if (blobUrlRef.current) {
        URL.revokeObjectURL(blobUrlRef.current);
      }
      blobUrlRef.current = url;
      setBlobUrl(url);
      setLoadState("ready");
    } catch {
      setLoadState("error");
    }
  }, [documentId]);

  useEffect(() => {
    fetchPdf();

    return () => {
      // Revoke blob URL on unmount to prevent memory leak
      if (blobUrlRef.current) {
        URL.revokeObjectURL(blobUrlRef.current);
        blobUrlRef.current = null;
      }
    };
  }, [fetchPdf]);

  // ─── Metadata row (shared between desktop and mobile) ─────────────────────
  const MetadataRow = (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 font-interface text-xs text-fg-muted">
      <span className="truncate max-w-[200px] text-fg-slate" title={filename}>
        {filename}
      </span>
      <span>{formatFileSize(sizeBytes)}</span>
      <span>Uploaded {formatDate(uploadedAt)}</span>
    </div>
  );

  // ─── Loading skeleton ──────────────────────────────────────────────────────
  if (loadState === "loading") {
    return (
      <div aria-label="Loading source document" data-testid="source-viewer-loading">
        {/* iframe skeleton */}
        <div
          className="w-full rounded border border-border-hairline bg-bg-parchment animate-pulse"
          style={{ height: "600px" }}
          aria-hidden="true"
        />
        {/* metadata skeleton */}
        <div className="mt-3 pt-3 border-t border-border-hairline flex gap-4">
          <div className="h-3 w-32 rounded bg-bg-parchment animate-pulse" />
          <div className="h-3 w-12 rounded bg-bg-parchment animate-pulse" />
          <div className="h-3 w-24 rounded bg-bg-parchment animate-pulse" />
        </div>
      </div>
    );
  }

  // ─── 401 / session expired ─────────────────────────────────────────────────
  if (loadState === "auth_error") {
    return (
      <div
        role="alert"
        data-testid="source-viewer-auth-error"
        className="flex flex-col items-center justify-center gap-3 rounded border border-border-hairline bg-bg-parchment px-6 py-10 text-center"
        style={{ minHeight: "200px" }}
      >
        <p className="font-interface text-sm text-fg-slate">
          Session expired. Please re-authenticate.
        </p>
        <a
          href="/"
          className="font-interface text-sm font-semibold text-fg-obsidian underline underline-offset-2 hover:text-fg-slate transition-colors duration-fast"
        >
          Sign in again
        </a>
      </div>
    );
  }

  // ─── Generic error ─────────────────────────────────────────────────────────
  if (loadState === "error") {
    return (
      <div data-testid="source-viewer-error">
        <StaleBanner message="Source document could not be loaded." />
        <div className="mt-3 flex justify-center">
          <button
            type="button"
            onClick={fetchPdf}
            className="font-interface text-sm font-semibold text-fg-obsidian underline underline-offset-2 hover:text-fg-slate transition-colors duration-fast"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  // ─── Ready — Desktop (inline) + Mobile (accordion) ────────────────────────
  return (
    <div data-testid="source-viewer-ready">
      {/* Desktop: always-visible iframe */}
      <div className="hidden sm:block">
        <iframe
          src={blobUrl!}
          title={`Source PDF: ${filename}`}
          className="w-full rounded border border-border-hairline"
          style={{ height: "600px" }}
          data-testid="source-viewer-iframe"
        />
        <div className="mt-3 pt-3 border-t border-border-hairline flex items-center justify-between flex-wrap gap-2">
          {MetadataRow}
          <a
            href={blobUrl!}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 font-interface text-sm text-fg-slate hover:text-fg-obsidian transition-colors duration-fast"
          >
            <svg
              className="h-4 w-4"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={1.5}
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25"
              />
            </svg>
            View source document
          </a>
        </div>
      </div>

      {/* Mobile (375): tap-to-expand accordion */}
      <div className="sm:hidden">
        {/* Collapsed header — always visible */}
        <button
          type="button"
          aria-expanded={expanded}
          aria-controls="source-viewer-mobile-panel"
          onClick={() => setExpanded((v) => !v)}
          className="flex w-full items-center justify-between rounded border border-border-hairline bg-bg-parchment px-4 py-3 text-left"
          data-testid="source-viewer-mobile-toggle"
        >
          <div className="flex flex-col gap-0.5 min-w-0 mr-3">
            {MetadataRow}
          </div>
          <svg
            className={`h-4 w-4 flex-shrink-0 text-fg-muted transition-transform duration-standard ${
              expanded ? "rotate-180" : ""
            }`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
            aria-hidden="true"
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        </button>

        {/* Expanded panel */}
        {expanded && (
          <div
            id="source-viewer-mobile-panel"
            className="mt-2"
            data-testid="source-viewer-mobile-panel"
          >
            <iframe
              src={blobUrl!}
              title={`Source PDF: ${filename}`}
              className="w-full rounded border border-border-hairline"
              style={{ height: "460px" }}
              data-testid="source-viewer-iframe"
            />
            <div className="mt-2 flex justify-end">
              <a
                href={blobUrl!}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 font-interface text-sm text-fg-slate hover:text-fg-obsidian transition-colors duration-fast"
              >
                <svg
                  className="h-4 w-4"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={1.5}
                  aria-hidden="true"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25"
                  />
                </svg>
                View source document
              </a>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
