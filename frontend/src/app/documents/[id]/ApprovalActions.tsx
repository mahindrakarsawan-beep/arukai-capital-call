"use client";

/**
 * ApprovalActions — client component for admin approve/reject.
 * Uses brass variant for Approve CTA (signal-only, admin-approval only — brand rule).
 * Uses danger variant for Reject.
 * On success: redirects to /documents.
 */

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/Button";

interface ApprovalActionsProps {
  documentId: string;
}

export function ApprovalActions({ documentId }: ApprovalActionsProps) {
  const router = useRouter();
  const [reason, setReason] = useState("");
  const [loading, setLoading] = useState<"approve" | "reject" | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function getToken(): Promise<string | null> {
    const res = await fetch("/api/token");
    const data = await res.json();
    return data.token ?? null;
  }

  async function handleDecision(decision: "approve" | "reject") {
    setLoading(decision);
    setError(null);

    try {
      const token = await getToken();
      if (!token) {
        router.push("/");
        return;
      }

      const apiBase =
        process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

      const res = await fetch(`${apiBase}/approvals/${documentId}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          decision: decision === "approve" ? "approved" : "rejected",
          note: reason.trim() || undefined,
        }),
      });

      if (!res.ok) {
        let message = `Failed (${res.status})`;
        try {
          const body = await res.json();
          message = body?.detail ?? body?.message ?? message;
        } catch {
          // ignore
        }
        setError(message);
        return;
      }

      router.push("/documents");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setLoading(null);
    }
  }

  return (
    <div className="rounded-lg border border-[rgba(184,145,78,0.30)] bg-[rgba(184,145,78,0.06)] p-5">
      <h2 className="mb-1 font-interface text-sm font-semibold text-fg-obsidian">
        Admin action required
      </h2>
      <p className="mb-4 font-interface text-sm text-fg-slate">
        Review the classification and approve or reject this document.
      </p>

      <div className="mb-4">
        <label
          htmlFor="reason"
          className="mb-1 block font-interface text-xs font-medium uppercase tracking-widest text-fg-muted"
        >
          Note (optional)
        </label>
        <textarea
          id="reason"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          rows={2}
          placeholder="Add a note…"
          className="w-full rounded-md border border-border-hairline bg-bg-bone px-3 py-2 font-interface text-sm text-fg-obsidian placeholder:text-fg-muted focus:outline-none focus:ring-2 focus:ring-brand-brass focus:ring-offset-0 resize-none"
        />
      </div>

      {error && (
        <p
          className="mb-3 rounded-md bg-[rgba(178,58,46,0.08)] px-3 py-2 font-interface text-sm text-data-negative"
          role="alert"
        >
          {error}
        </p>
      )}

      <div className="flex gap-3">
        {/* brass — admin-approval CTA only (brand rule) */}
        <Button
          variant="brass"
          loading={loading === "approve"}
          disabled={loading !== null}
          onClick={() => handleDecision("approve")}
        >
          Approve
        </Button>
        <Button
          variant="danger"
          loading={loading === "reject"}
          disabled={loading !== null}
          onClick={() => handleDecision("reject")}
        >
          Reject
        </Button>
      </div>
    </div>
  );
}
