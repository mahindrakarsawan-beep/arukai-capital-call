"use client";

/**
 * PackageDetailActions — bottom action bar for package detail (spec §6.5).
 * Approver role (mapped from 'admin'): shows [Attest approval] (brass) and [Record rejection].
 * Both trigger the AttestationModal — no inline approve/reject.
 */

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { AttestationModal } from "@/components/AttestationModal";

interface PackageDetailActionsProps {
  documentId: string;
  packageTitle: string;
  classification?: string;
  confidence?: number | null;
}

export function PackageDetailActions({
  documentId,
  packageTitle,
  classification,
  confidence,
}: PackageDetailActionsProps) {
  const router = useRouter();
  const [modal, setModal] = useState<"approve" | "reject" | null>(null);

  function handleSuccess() {
    setModal(null);
    // Short delay for modal fade (240ms per spec §7.3)
    setTimeout(() => {
      router.refresh();
    }, 240);
  }

  const packageSummary = {
    title: packageTitle,
    classification,
    confidence,
  };

  return (
    <>
      <div className="rounded-lg border border-[rgba(184,145,78,0.30)] bg-[rgba(184,145,78,0.04)] p-5">
        <p className="mb-4 font-interface text-sm text-fg-slate">
          This package is awaiting attestation. Review the extracted facts and reviewer notes before proceeding.
        </p>
        <div className="flex gap-3">
          {/* Brass — Attest approval: the only brass button in the app (spec §9.3) */}
          <button
            type="button"
            onClick={() => setModal("approve")}
            className="inline-flex items-center gap-2 rounded-md px-4 py-2 font-interface text-sm font-semibold text-white transition-colors duration-fast focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-[#B8914E]"
            style={{ backgroundColor: "#B8914E" }}
          >
            Attest approval
          </button>

          {/* Record rejection — secondary, not brass */}
          <button
            type="button"
            onClick={() => setModal("reject")}
            className="inline-flex items-center gap-2 rounded-md px-4 py-2 font-interface text-sm font-semibold text-fg-obsidian border border-border-hairline bg-bg-parchment hover:bg-bg-bone transition-colors duration-fast focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-fg-slate"
          >
            Record rejection
          </button>
        </div>
      </div>

      {modal && (
        <AttestationModal
          variant={modal}
          packageSummary={packageSummary}
          documentId={documentId}
          onClose={() => setModal(null)}
          onSuccess={handleSuccess}
        />
      )}
    </>
  );
}
