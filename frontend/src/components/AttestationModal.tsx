"use client";

/**
 * AttestationModal — spec §7.
 * Approve variant: brass confirm, Cormorant italic attestation language.
 * Reject variant: neutral dark confirm, attestation note required.
 *
 * Brass is ONLY used on the Attest approval confirm button — spec §9.3.
 */

import React, { useEffect, useRef, useState } from "react";
import { FlaggedFieldWarning } from "@/components/FlaggedFieldWarning";
import { ZeroFlagsPanel } from "@/components/ZeroFlagsPanel";
import { attestPackage } from "@/lib/api";

interface PackageSummary {
  title: string;
  classification?: string;
  confidence?: number | null;
  amount?: string | null;
  dueDate?: string | null;
  fundName?: string | null;
  reviewerNotes?: Array<{ author: string; timestamp: string; body: string }>;
  /** Number of fields flagged during extraction review (A2.1). Defaults to 0. */
  flaggedFieldCount?: number;
  /** Names of the flagged fields (A2.1). */
  flaggedFields?: string[];
}

interface AttestationModalProps {
  variant: "approve" | "reject";
  packageSummary: PackageSummary;
  documentId: string;
  onClose: () => void;
  onSuccess: () => void;
}

export function AttestationModal({
  variant,
  packageSummary,
  documentId,
  onClose,
  onSuccess,
}: AttestationModalProps) {
  const [note, setNote] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Focus trap: initial focus on cancel/return button per spec §7.3
  const cancelRef = useRef<HTMLButtonElement>(null);
  const modalRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    cancelRef.current?.focus();
  }, []);

  // Escape to close
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  // Focus trap within modal
  useEffect(() => {
    const modal = modalRef.current;
    if (!modal) return;

    const focusable = modal.querySelectorAll<HTMLElement>(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    );
    const first = focusable[0];
    const last = focusable[focusable.length - 1];

    function handleTab(e: KeyboardEvent) {
      if (e.key !== "Tab") return;
      if (e.shiftKey) {
        if (document.activeElement === first) {
          e.preventDefault();
          last?.focus();
        }
      } else {
        if (document.activeElement === last) {
          e.preventDefault();
          first?.focus();
        }
      }
    }

    document.addEventListener("keydown", handleTab);
    return () => document.removeEventListener("keydown", handleTab);
  }, []);

  async function handleConfirm() {
    if (variant === "reject" && !note.trim()) {
      setError("Attestation note is required for rejection.");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const tokenRes = await fetch("/api/token");
      const { token } = await tokenRes.json();

      if (!token) {
        onClose();
        return;
      }

      await attestPackage(
        documentId,
        variant === "approve" ? "approved" : "rejected",
        note.trim(),
        token
      );

      onSuccess();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  const isApprove = variant === "approve";

  const attestationText = isApprove
    ? "I attest that I have reviewed this capital-call package, considered the reviewer notes above, and approve it for operator execution. This decision is recorded against my name and the current timestamp."
    : "I have reviewed this package and am recording a rejection. The package will be returned for revision with the following reason.";

  return (
    /* Scrim / backdrop — desktop: centered overlay, mobile: fullscreen sheet (§6/S6) */
    <div
      className="fixed inset-0 z-50 flex items-end sm:items-center justify-center sm:p-4"
      style={{ backgroundColor: "rgba(13,15,18,0.55)" }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      aria-modal="true"
      role="dialog"
      aria-labelledby="attestation-modal-heading"
    >
      <div
        ref={modalRef}
        className="w-full sm:max-w-lg rounded-t-[16px] sm:rounded-[16px] border border-border-hairline bg-bg-bone p-6 sm:p-8 shadow-xl"
        style={{ maxHeight: "95dvh", overflowY: "auto" }}
      >
        {/* Error strip */}
        {error && (
          <div
            role="alert"
            className="mb-4 rounded-md bg-[rgba(178,58,46,0.08)] px-3 py-2 font-interface text-sm text-data-negative"
          >
            {error}
          </div>
        )}

        {/* Heading */}
        <h1
          id="attestation-modal-heading"
          className="font-display text-[28px] font-light text-fg-obsidian tracking-tight mb-2"
        >
          {isApprove ? "Attestation" : "Record rejection"}
        </h1>

        {/* Subheading */}
        <p className="font-interface text-sm text-fg-slate mb-6">
          You are about to record a binding decision on this package.
        </p>

        {/* Package summary panel */}
        <div className="rounded-lg bg-bg-parchment p-4 mb-5">
          <p className="font-display text-base font-light text-fg-obsidian mb-1">
            {packageSummary.title}
          </p>
          {packageSummary.classification && (
            <p className="font-interface text-xs text-fg-slate mb-1">
              {packageSummary.classification}
              {typeof packageSummary.confidence === "number" &&
                ` · ${(packageSummary.confidence * 100).toFixed(0)}% intake confidence`}
            </p>
          )}
          {(packageSummary.amount || packageSummary.dueDate || packageSummary.fundName) && (
            <div className="mt-2 flex flex-wrap gap-3">
              {packageSummary.fundName && (
                <span className="font-interface text-xs text-fg-muted">
                  Fund: <span className="text-fg-obsidian">{packageSummary.fundName}</span>
                </span>
              )}
              {packageSummary.amount && (
                <span className="font-interface text-xs text-fg-muted">
                  Amount: <span className="text-fg-obsidian">{packageSummary.amount}</span>
                </span>
              )}
              {packageSummary.dueDate && (
                <span className="font-interface text-xs text-fg-muted">
                  Due: <span className="text-fg-obsidian">{packageSummary.dueDate}</span>
                </span>
              )}
            </div>
          )}
        </div>

        {/* Confidence panel (A2.1 + A2.2):
            - flaggedFieldCount === 0 and explicitly provided → ZeroFlagsPanel (green)
            - flaggedFieldCount > 0 → FlaggedFieldWarning (amber)
            - flaggedFieldCount not provided → nothing rendered */}
        {packageSummary.flaggedFields !== undefined ? (
          packageSummary.flaggedFieldCount === 0 ? (
            <ZeroFlagsPanel />
          ) : (
            <FlaggedFieldWarning
              flaggedCount={packageSummary.flaggedFieldCount ?? 0}
              flaggedFields={packageSummary.flaggedFields}
            />
          )
        ) : null}

        {/* Reviewer notes recap */}
        <div className="mb-5">
          <p className="font-interface text-xs font-medium uppercase tracking-widest text-fg-muted mb-2">
            Reviewer notes on record
          </p>
          {packageSummary.reviewerNotes && packageSummary.reviewerNotes.length > 0 ? (
            <div className="flex flex-col gap-2">
              {packageSummary.reviewerNotes.map((note, i) => (
                <div
                  key={i}
                  className="rounded-md border border-border-hairline bg-bg-parchment px-3 py-2"
                >
                  <div className="flex gap-2 font-interface text-xs text-fg-muted mb-0.5">
                    <span>{note.author}</span>
                    <span>·</span>
                    <span>{note.timestamp}</span>
                  </div>
                  <p className="font-interface text-sm text-fg-obsidian">{note.body}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="font-interface text-sm text-fg-muted italic">
              No review notes were recorded before this attestation.
            </p>
          )}
        </div>

        {/* Attestation language — Cormorant italic 18pt */}
        <blockquote className="mb-5 border-l-2 border-border-hairline pl-4">
          <p className="font-display text-[18px] italic font-light text-fg-obsidian leading-relaxed">
            &#8220;{attestationText}&#8221;
          </p>
        </blockquote>

        {/* Attestation note */}
        <div className="mb-6 flex flex-col gap-1">
          <label
            htmlFor="attestation-note"
            className="font-interface text-xs font-medium uppercase tracking-widest text-fg-muted"
          >
            Attestation note{isApprove ? " (optional)" : " (required)"}
          </label>
          <textarea
            id="attestation-note"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            rows={3}
            placeholder={
              isApprove
                ? "Optional context for this decision"
                : "Reasons for rejection — required"
            }
            className="w-full rounded-md border border-border-hairline bg-bg-bone px-3 py-2 font-interface text-sm text-fg-obsidian placeholder:text-fg-muted focus:outline-none focus:ring-2 focus:ring-fg-slate focus:ring-offset-0 resize-none"
            required={!isApprove}
          />
        </div>

        {/* Action row */}
        <div className="flex items-center justify-between gap-3">
          {/* Left: cancel/return — initial focus per spec */}
          <button
            ref={cancelRef}
            type="button"
            onClick={onClose}
            disabled={loading}
            className="font-interface text-sm font-semibold text-fg-muted hover:text-fg-obsidian transition-colors duration-fast disabled:opacity-50"
          >
            Return to package
          </button>

          {/* Right: confirm */}
          {isApprove ? (
            /* Brass — only the Attest approval confirm button (spec §9.3) */
            <button
              type="button"
              onClick={handleConfirm}
              disabled={loading}
              className="inline-flex items-center gap-2 rounded-md px-4 py-2 font-interface text-sm font-semibold text-white transition-colors duration-fast focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-[#B8914E] disabled:opacity-50 disabled:cursor-not-allowed"
              style={{ backgroundColor: "#B8914E" }}
            >
              {loading ? (
                <>
                  <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" aria-hidden="true" />
                  <span>Recording…</span>
                </>
              ) : (
                "Attest and record decision"
              )}
            </button>
          ) : (
            /* Rejection — neutral dark (spec §7.2: not brass) */
            <button
              type="button"
              onClick={handleConfirm}
              disabled={loading}
              className="inline-flex items-center gap-2 rounded-md px-4 py-2 font-interface text-sm font-semibold transition-colors duration-fast focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-fg-obsidian disabled:opacity-50 disabled:cursor-not-allowed"
              style={{ backgroundColor: "#0D0F12", color: "#FAFAF8" }}
            >
              {loading ? (
                <>
                  <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" aria-hidden="true" />
                  <span>Recording…</span>
                </>
              ) : (
                "Record rejection"
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
