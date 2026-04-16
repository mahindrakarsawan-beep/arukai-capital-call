# Alex — Figma Phase B Review
**Date:** 2026-04-15
**Author:** Alex (backup FE)
**Scope:** Page 2 (Components, node 9:2) + Page 3 (Screens, node 9:3) — full walk
**Status:** INBOX — for Holden triage

---

## 1. What I read

I walked all 12 components on Page 2 and all 7 screens on Page 3 in full. I also read the live codebase at `/frontend/src/` — every component file, the detail page, AttestationModal, PackageDetailActions, AuditLogEntry, TopNav, theme tokens, and the v0.2 atelier spec. This review is based on both Figma and live code.

---

## 2. Risk ranking — what's hardest to ship correctly

### HIGH: Screen 07 — Global audit ledger (node 17:34)

This screen does not exist in the codebase. There is no `/audit` route, no `AuditLedger` page, and no API client function for a cross-package audit endpoint. The Figma shows:
- A filter bar with three independent controls: actor (free-text), action (dropdown), and date range ("BETWEEN")
- An Export CSV button
- A flat table of events: TIMESTAMP / ACTOR / PACKAGE / ACTION / BEFORE → AFTER
- A "first-class record of every package event" — meaning this is a global feed, not per-package

The combinatoric risk here is significant: the three filters compose, the date range is a two-part input, and the empty state ("No events match the current filter") must fire on every combination. The Figma only shows the happy path — a fully-populated table with eight rows. There is no skeleton/loading state shown, no pagination shown for >N rows, and no error state for a failed fetch. This is the single highest-risk deliverable in Phase B.

I am volunteering to own this screen end-to-end (see Section 4).

### HIGH: SourceViewer component (node 14:45) — iframe auth gap

The live code at `documents/[id]/page.tsx` embeds an `<iframe src={getDocumentDownloadUrl(doc.id)} />`. `getDocumentDownloadUrl` returns a bare `${API_BASE}/documents/${id}/pdf` URL. The Figma component spec says "Inline PDF preview. Heading, embedded page, sidecar metadata, full-screen link."

The problem: the iframe loads the PDF URL directly in the browser. If the backend `/documents/{id}/pdf` endpoint requires a Bearer token (which it does — it's a protected route), the iframe will silently 401 or show a blank frame. There is no token in the URL, no cookie passthrough for cross-origin requests, and no fallback shown in the Figma. Bobbie has marked this "Phase A acceptable fallback" in a comment, but it will break in staging and is not acceptable for an approver viewing a document they must attest. This is a correctness issue, not a deferred nicety.

### MEDIUM-HIGH: Attestation modal — flagged-field warning (node 17:6)

Screen 06 (the standalone attestation modal screen, node 17:2) shows a warning panel that does not appear in the component library variant: a brass-outlined amber inset reading "1 field was flagged during review. Proceed only if resolved." with a dot indicator. The component library (node 12:117) and the current `AttestationModal.tsx` have no such warning surface. The Figma treats it as part of the modal, but Bobbie has not implemented it. When a package has low-confidence fields (e.g. `NEEDS REVIEW` on due date or `LOW CONFIDENCE — FLAG` on side-letter ref), the approver needs to see this before attesting. The data to power it exists in `classification.key_indicators` and the confidence band logic already in `ConfidenceBadge`. This is a spec gap that will surface in QA.

### MEDIUM: Review notes block — no write path (nodes 16:92–16:98)

All three package detail screens (03, 04, 05) show a Review notes block with a textarea + "Record review note" button. In the live `documents/[id]/page.tsx`, Block 3 is a placeholder with a comment: `{/* Phase B: review notes input will be wired here by Drummer (B1) */}`. The `AuditLogEntry` component exists but there is no API client function for `POST /packages/{id}/review-notes` or equivalent. The Figma shows notes by Lena Voss with timestamps. The component for rendering notes exists implicitly in the modal's `reviewerNotes` prop, but there is no data-fetch path, no optimistic update, and no character limit or validation shown in the Figma. The Figma also does not show what happens when a note is saved mid-typing and the user navigates away.

### MEDIUM: Operations console sectioning — no `/documents` page matches spec (node 15:21)

The live app at `/documents` uses a simple flat list. The Figma shows five distinct sections with section headers and per-section counts: Exceptions (2), Pending approval (1), Needs review (4), Active packages (12), Recent decisions (3). This is a substantial re-architecture of the console layout, not a style change. `resolvePackageState()` exists and maps backend states to UI states, but the list page currently does no client-side bucketing, renders no section headers, shows no counts, and has no "Begin intake" secondary button inside the Active packages section header (as shown in Figma at node 15:147). This is Phase B scope for Bobbie and is high-effort.

### LOW-MEDIUM: TopNav — "Pending attestation" brass badge missing

The TopNav component on screen 02 (node 15:22) shows a brass count chip: "1 PENDING ATTESTATION" with a dot, only when count > 0. The Figma component library (node 14:105) has two variants: `Variant=default` and `Variant=approver-with-brass-pending`. The live `TopNav.tsx` has no badge, no count fetch, and no conditional rendering for approver role. The spec says "Brass pending-attestation badge only when count > 0." This is a clean, scoped piece I can own.

---

## 3. Edge cases the Figma skipped entirely

These are absent from every screen and component in the Figma. They need answers before implementation.

1. **SourceViewer — PDF load failure.** The Figma shows only a rendered PDF. No state for: 401 (auth expired mid-session), 404 (document deleted), network timeout, CORS rejection, or PDF parsing failure in the browser. The iframe will just go blank. We need a fallback UI inside the SourceViewer frame.

2. **SourceViewer — file-too-large for inline render.** The Figma shows a 842 KB PDF. The spec says intake accepts up to 20 MB. A 20 MB PDF in an iframe is a poor experience on a typical laptop. No "preview unavailable — use View source document link" fallback is shown.

3. **AttestationModal — double-submit.** The modal has a loading state (the spinner is implemented in Bobbie's code), but there is no disabled state on the scrim click-to-dismiss during the in-flight POST. A user can spam-click the scrim during submission. This could trigger `onClose` while `loading` is true, abandoning the in-flight request with no user feedback.

4. **AttestationModal — rejection note empty submit.** The Figma labels the field "ATTESTATION NOTE (REQUIRED)" for rejection. Bobbie has implemented the guard (`if (variant === "reject" && !note.trim())`), but the Figma shows no inline validation state — no red border, no helper text. The error goes to the error strip at the top of the modal, which is distant from the field. Mid-typing validation (blur vs. submit) is unspecified.

5. **Audit ledger — date range input.** The filter bar shows "2026-04-10 — 2026-04-17" as a single pre-formatted value in the BETWEEN input. The Figma does not show a date picker, two separate date fields, or the format expected. Is this a freetext ISO range? Two `<input type="date">` fields? A popover calendar? Completely unspecified.

6. **Operations console — zero-state for all sections simultaneously.** The Figma shows `EmptyStateMessage` variants per section, but only one section empty at a time. What does the console look like when the entire queue is empty? Does it show all five section headers with their respective empty states stacked? Does it collapse to a single welcome state?

7. **Responsive/smaller viewports — none shown.** Every Figma screen is 1440px wide. There is no mobile, tablet, or 1280px breakpoint shown. The TopNav's nav items already hide on `sm` in the live code (`hidden sm:flex`), which means "Console" and "Begin intake" links disappear on mobile with no hamburger. The detail page 2-column grid degrades to stacked at `lg` breakpoint, but the action bar buttons are not shown in a stacked layout. No spec guidance exists.

8. **AuditEntry component — "system" actor display.** The Figma shows "system" as an actor name for automated transitions (e.g. intake_complete trigger). The `AuditLogEntry` component renders `event.actor_email ?? "System"` — but the Figma renders "system" in lowercase, matching the raw value. Inconsistent casing — minor but Miller will catch it.

9. **PackageCard — long fund name overflow.** Fund names like "Beaumont European Growth II — Q2 capital call" at 52 chars are shown at full width. The Figma does not show a truncation rule. The live code uses `break-all` on the H1, which will break mid-word on a long fund name. `break-words` + `truncate` with a tooltip is the correct pattern but is not specified.

10. **ConfidenceBadge — "missing" band.** The component library has a `Band=missing` variant (node 14:43) — a 5th band not documented in the four-band spec (§4). It exists in the Figma but is not mentioned in the spec text and is not in the current `ConfidenceBadge` implementation. Is this in scope for Phase B?

---

## 4. Proposed work split

### Alex takes ownership of:

**A1 — Global audit ledger screen (Screen 07)**
Full screen implementation: `/audit` route, filter bar (actor/action/date-range), export CSV, table with all five columns including BEFORE → AFTER state transition rendering, empty state, loading skeleton, error state. This is the most greenfield screen with no existing code to navigate — a good fit for fresh eyes. Drummer needs to confirm the API endpoint shape first.

**A2 — TopNav pending-attestation brass badge**
Conditional brass badge for approver role, count fetched from a `/packages/pending-attestation` or `/documents?status=pending_review` count endpoint. Two-variant TopNav aligned to spec. This is a self-contained, high-visibility piece.

**A3 — SourceViewer auth fix**
Replace the raw iframe with a token-authenticated blob URL approach (fetch PDF with Authorization header → `URL.createObjectURL` → pass to iframe `src`) plus a load-error fallback state. This is a correctness bug, not a Phase B nicety, and should not wait.

**A4 — AttestationModal flagged-field warning panel**
Add the amber warning inset to `AttestationModal` when the package has low-confidence or flagged fields. Wire to the `packageSummary` prop — add `flaggedFieldCount?: number` to the interface. Implement the conditional rendering before the summary block.

### Bobbie should take:

**B1 — Operations console sectioned layout (Screen 02)**
Five-section bucketing, section headers, per-section counts, empty states per section, the "Begin intake" button inside the Active packages header. Bobbie knows the console's data-fetch patterns and the existing list page architecture. This is the largest FE task and Bobbie's core domain.

**B2 — Package detail review notes write path (Screen 03/04)**
The textarea + "Record review note" button, the optimistic note display, and the API call. Bobbie knows the detail page layout and has already scaffolded the placeholder comment.

**B3 — PackageCard / PackageRow long-name overflow rule**
Minor polish but Bobbie is already in that component's file. Fix `break-all` → `break-words` with a max-width and overflow tooltip.

---

## 5. Questions for the squad

**Q1 — For Drummer:** Does `/documents/{id}/pdf` require a Bearer token? If yes, Drummer needs to either (a) add a short-lived signed URL endpoint or (b) confirm we can pass auth via cookie for same-origin requests. Alex needs this answer before building A3.

**Q2 — For Drummer:** What is the API shape for the global audit ledger? Specifically: single endpoint or paginated? Does it support `actor`, `action`, and `date_range` as query params? What are the valid `action` enum values? Is there an export endpoint or do we generate CSV client-side?

**Q3 — For Drummer:** Is there a `/packages/pending-attestation/count` endpoint, or do we derive the count from the document list filtered by status? TopNav badge (A2) depends on this.

**Q4 — For Holden:** Screen 06 shows a standalone attestation modal at 720×900px — larger than the component library variant at 640×720px. The live modal is `max-w-lg` (~512px). Which canvas size is authoritative? The component library variant, or Screen 06?

**Q5 — For Holden:** The `ConfidenceBadge` has a `Band=missing` variant in the Figma (node 14:43) but it is not mentioned in the spec §4. Is this in scope for Phase B or deferred?

**Q6 — For Holden:** Responsive breakpoints — the Figma is desktop-only (1440px). Is there a mobile requirement for v0.2? If not, what is the minimum supported viewport width? The current `hidden sm:flex` on nav items leaves mobile users without navigation.

**Q7 — For Miller:** The `AuditLogEntry` component renders `event.actor_email ?? "System"` with capital S, but the Figma shows "system" in lowercase. Which is canonical? Miller should gate on this in the language audit.

**Q8 — For Bobbie:** The `resolvePackageState()` function maps `pending_review` → `intake_complete` unless confidence < 0.5. But Screen 03 shows a package at `intake_complete` state and Screen 04 shows the same package at `routed_for_approval`. The v0.1 API only has `pending_review` as the reviewable state — there is no native `routed_for_approval` status from the backend. How are you planning to surface the routing step in the console bucketing without a backend state for it? Does Drummer need to add this first?

**Q9 — For all:** The attestation modal's scrim click-to-dismiss fires `onClose` even when `loading === true`. Should we block dismiss during in-flight submission, or show a "Are you sure?" guard? The Figma is silent on this.

**Q10 — For Holden:** The "Return to reviewer" button appears in Screen 04's action bar (node 16:286) for the approver — a Ghost button that presumably un-routes the package back to `under_review`. This workflow action is not in the component library's `AttestationModal` at all, and there is no API call for it in the current codebase. Is this Phase B scope? If yes, it needs a Drummer backend endpoint and Bobbie implementation.

---

## 6. Brand / brass discipline observations

No violations found in Bobbie's current implementation — brass discipline is correctly applied in the three permitted sites only. One soft risk: `PackageDetailActions` wraps the entire action bar in a `border-[rgba(184,145,78,0.30)]` / `bg-[rgba(184,145,78,0.04)]` container. This creates a fourth brass-tinged surface not shown in the Figma and not authorized in spec §9.3. The brass container styling should be replaced with a neutral `border-hairline` / `bg-bone` frame. The brass should live on the button only.

Typography: all components correctly use `font-display` (Cormorant) for headings and `font-interface` (DM Sans) for body/labels. The attestation language blockquote uses `font-display italic` at 18px — spec-correct. No typography violations found.

Amber vs. brass: the token file correctly distinguishes `brandBrass: #B8914E` (signal-only) from `warningText: #9A7639` (amber, exception/confidence). These are 10% lighter vs. darker variants of the same hue and are visually close. Risk: Bobbie using `brandBrassPressed: #9A7639` (the pressed brass state) interchangeably with amber — they are the same hex value. A future hover on a brass button will render identically to an amber warning text. Miller should add a lint rule or comment calling this out explicitly.

---

## 7. Summary

Phase B delivers five new screens/features. The riskiest are the audit ledger (no existing code, complex filtering), the SourceViewer auth gap (silent failure today), and the operations console re-bucketing (largest surface area). I am claiming the audit ledger, TopNav badge, SourceViewer fix, and modal warning panel. Bobbie should keep the console sectioning and review notes write path — that work depends on her knowledge of the existing list/detail patterns.

Three items need Holden decisions before we can start: attestation modal canvas size authority (Q4), ConfidenceBadge missing band scope (Q5), and "Return to reviewer" action scope (Q10). Two items need Drummer confirmation before Alex can start A3 (PDF auth) and A1 (audit API shape).

Recommend Holden triages Q4, Q5, Q10 today so A1/B1 can begin tomorrow.
