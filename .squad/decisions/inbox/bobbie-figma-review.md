# Bobbie — Figma Implementation Feasibility Review
**Date:** 2026-04-15
**Figma file:** a6mMsiXmnSdQTQ4qQYS6X2 (v0.2 Phase B design)
**Reviewer lens:** Next.js 15 + Tailwind, component API, state management, performance, data coupling
**Scope read:** Page 2 (Components, node 9:2) + Page 3 (Screens, node 9:3) metadata; full codebase `/frontend/src/`

> Note: `mcp__figma__get_design_context` was not available in this session (permission denied). This review is based on the full Figma structural metadata (all node IDs, frame trees, variant names, layer names) combined with full codebase reading. Design context calls would add pixel-perfect CSS but would not change the feasibility conclusions below.

---

## 1. Component inventory — what exists vs. what Figma adds

### Already built and matching Figma intent

| Figma component (Page 2) | Phase A file | Match quality |
|---|---|---|
| `Button` (5 variants) | `Button.tsx` — Primary, Secondary, Brass, Danger, Ghost | Near-exact. Missing `Ghost` variant. |
| `StatusPill` (7 states) | `StatusPill.tsx` | Correct. State façade in `state.ts` covers all 7. |
| `NextOwnerChip` (5 variants) | `NextOwnerChip.tsx` | Near-exact. |
| `ConfidenceBadge` (4 bands) | `ConfidenceBadge.tsx` | Solid, all 4 bands implemented. |
| `AttestationModal` (approve + reject) | `AttestationModal.tsx` | Fully built, both variants, correct focus trap, correct brass discipline. |
| `TopNav` (default + brass-pending badge) | `TopNav.tsx` | Missing the brass pending-attestation count badge (variant 2). |
| `AuditEntry` (5 row variants) | `AuditLogEntry.tsx` | Built as a table row. Figma adds before→after state display per row. Gap: no expandable diff. |

### New components required for Phase B

| Figma component | Node | Complexity | Owner |
|---|---|---|---|
| `PackageRow` | 12:2 | Medium | Bobbie |
| `PackageCard` (detail header block) | 12:73 | Easy | Bobbie |
| `FieldWithConfidence` | 14:2 | Medium | Bobbie |
| `SourceViewer` | 14:45 | Hard | Bobbie (shell) + Alex (PDF mechanics) |
| `EmptyStateMessage` (7 variants) | 14:79 | Easy | Bobbie |
| `Button` Ghost variant | 11:25 | Trivial | Bobbie |

---

## 2. Screen-by-screen feasibility analysis

### Screen 01 — Login (node 15:2)
**Status: 90% done in Phase A**

The spec §8 login screen — obsidian background, centered bone card, wordmark + tagline — is specified. What Phase A built: the login page at `app/page.tsx` likely has most copy. What Figma adds is visual mostly (obsidian background). No new data coupling.

- The current codebase's login page was not read in full but the spec is honored.
- One gap: the ceremony hairline draw (Phase C, `withTiming`, 360ms) is deferred. Fine.
- **Effort to close: 1–2h.** Bobbie.

---

### Screen 02 — Operations Console (node 15:21)
**Status: Layout built, two missing details**

Phase A console (`app/documents/page.tsx`) has the five-section structure, correct ordering, correct empty states, correct brass count on Pending approval. The ConsoleRow component uses a flex layout matching the Figma PackageRow columns.

**Gaps:**
1. `PackageRow` in Figma uses a more structured identity column: leading avatar/thumbnail area (206px left offset before the title text), plus a classification label under the title. Phase A's `ConsoleRow` has these but uses `flex-1 min-w-0` text truncation, not a fixed-column grid. The Figma design uses consistent column widths (identity ~719px, status ~480px, timestamp ~49px on a 1344px row). That's a fixed layout at 1440px viewport.
   - **Risk:** The fixed-column approach in Figma does not flex well below 1024px. Needs a decision — do we keep the responsive flex layout from Phase A, or force min-width column offsets?

2. TopNav variant 2 (`Variant=approver-with-brass-pending`) shows a brass dot + "1 PENDING ATTESTATION" counter in the top right. Phase A `TopNav.tsx` does not have this. Requires the TopNav to receive a `pendingAttestationCount` prop and conditionally render the chip. This is a straightforward prop addition but requires the count to come from somewhere — currently the console page doesn't pass it to TopNav.

3. Role-based section visibility (§5.5) is not implemented. Phase A shows all sections to all roles. Operators should not see Needs Review or Pending Approval. Requires the console server component to check `user.role` and conditionally render sections.

**Effort: 3–4h.** Bobbie.

---

### Screen 03 — Package Detail (node not in truncated metadata, but spec §6 is clear)
**Status: 70% done, two hard gaps**

Phase A detail page (`app/documents/[id]/page.tsx`) has:
- Correct 2×2 grid layout
- Source document as iframe (Phase A acceptable fallback)
- Extracted facts block (document-level confidence only via ConfidenceBadge)
- Review notes and audit trail as stubs with placeholder text
- Correct attestation action bar via `PackageDetailActions`

**Gaps:**
1. **Extracted facts — per-field confidence**: The current extracted facts block only shows doc_type and classification.confidence. Figma's `FieldWithConfidence` is a two-column key/value row where each field value carries its own confidence band. This requires the backend to return per-field extraction data with individual confidence scores. The current `Classification` type in `api.ts` only has `doc_type`, `confidence`, `key_indicators`, `model_version`. No per-field data. This is a backend dependency on Drummer (Phase B).
   - Until Drummer ships the per-field API, I can build `FieldWithConfidence` as a component and render it with document-level confidence across all fields as a placeholder. The component API should be `{ label: string, value: string, confidence: number | null }`.

2. **Review notes block**: Figma shows a live list of reviewer annotations + an input at bottom (reviewer role only). Phase A has a stub placeholder. Needs the reviewer notes endpoint from Drummer, and a client-side form for submitting. This is the most important backend separation in the spec (§6.3). I cannot build the notes input without Drummer's endpoint.

3. **Audit trail block**: Figma's `AuditEntry` rows show actor + action + before→after state with expandable JSON diff. Phase A's `AuditLogEntry.tsx` is a table row with actor/action/time but no before/after. The audit trail is a stub on the detail page — it needs `GET /documents/{id}/audit` from Drummer.

4. **Action bar role routing**: Phase A only checks `user.role === "admin"` for the attestation bar. Figma shows three role variants: reviewer gets "Route for approval" button, approver gets brass "Attest approval", operator gets "Mark exception resolved". Need to extend `PackageDetailActions` to handle all three. Reviewer and Operator variants need Drummer's new state transitions.

**Effort: 5–6h for Bobbie-owned parts.** Data dependencies on Drummer noted below.

---

### Screen 04 — Global Audit Ledger (implied by TopNav "Audit ledger" link and spec)
**Status: NOT BUILT AT ALL**

There is no `app/audit/` or `app/audit-ledger/` page in the codebase. The TopNav links to "Audit ledger" but the route does not exist. Figma shows this as a dedicated screen with:
- Chronological ledger of all AuditEvents across all packages
- Filter bar: actor, action type, date range
- Uses the `AuditEntry` component
- Empty state "No events match the current filter."

This is a whole new page. It also needs a new API endpoint — currently `api.ts` has no audit listing function.

**This is Alex's work, not mine.** Rationale: it's a new server route, a new API client function, and a filter bar that involves query-string state management. Alex handles Copilot review fixes and backend-coupled new routes. I should not grab this.

**Effort estimate if I were to own it: 4–6h.** Recommend Alex.

---

## 3. Component build analysis

### `PackageRow` (node 12:2) — medium
Figma shows 5 state variants (routed_for_approval, exception_surfaced, under_review, intake_complete, decision_recorded-approved). This is essentially what `ConsoleRow` in `documents/page.tsx` does inline — it's not extracted as a component. Phase B should extract it into `components/PackageRow.tsx`.

The identity column in Figma has a leading area (~200px wide) before the title. Looking at the node positions: title starts at x=206 within the 1344px row. That leading space likely holds a fund-logo thumbnail or placeholder rectangle — but no image nodes appear in the metadata. Probably just padding. Safe to implement as `gap-4` flex without fixed positions.

**Risk:** The Figma identity column also shows the classification label *under* the title (two-line stacking). Phase A puts classification in a separate column. This is a layout change that affects visual density.

**Effort: 2h.** Bobbie owns.

---

### `PackageCard` (node 12:73) — easy
Detail page header block: title, state pill, next-owner chip, metadata line. Phase A already renders this inline on the detail page header. Extract to `PackageCard.tsx`. Three state variants in Figma (under_review, routed_for_approval, decision_recorded). The component just takes `stateInfo` from the existing façade.

**Effort: 1–1.5h.** Bobbie owns.

---

### `FieldWithConfidence` (node 14:2) — medium
5 band variants: high, confident, needs_review, low, missing. The existing `ConfidenceBadge.tsx` handles confidence rendering for a single value. `FieldWithConfidence` is the full row: label + value + confidence treatment. This is new.

API design question: should the `confidence` prop be at the row level or should the value carry it? I'd go with `{ label: string; value: string | null; confidence: number | null }` — keep it flat.

The existing `ConfidenceBadge` can be used internally. The Band=low variant adds a dashed box wrapper. Band=missing renders `—` with amber pill.

**Effort: 1.5–2h.** Bobbie owns.

---

### `SourceViewer` (node 14:45) — hard
Figma: "Inline PDF preview. Heading, embedded page, sidecar metadata, full-screen link."

The node is a `Variant=default` symbol at 600×760px. Sidecar metadata in the spec means filename, size, MIME, uploaded-at. Phase A uses `<iframe src={pdfUrl}>` at 600px height as an acceptable fallback.

**The hard part is not the shell — it's the PDF.** `<iframe>` works in Chrome/Firefox/Edge but is unreliable in Safari mobile. A proper `SourceViewer` would use `react-pdf` (pdf.js wrapper) for reliable cross-browser rendering, page navigation, and zoom. That's a dependency add, bundle size impact, and dynamic import work.

**My call:** I own the shell component (container, heading, sidecar metadata, full-screen link button). Alex should evaluate whether to add `react-pdf` or keep the iframe. If we keep iframe, the component is trivial. If we add `react-pdf`, budget 4–5h just for the PDF mechanics.

**Effort (shell only): 1.5h.** Bobbie owns shell. Alex decides on PDF engine.

---

### `EmptyStateMessage` (node 14:79) — easy
7 variants by surface name. Figma: "Parchment inset, italic editorial voice." This is just a styled `<p>` in a `bg-bg-parchment` inset with italic DM Sans text. Phase A already renders inline empty states in every section. Extract to a reusable `EmptyStateMessage` component that takes a `variant` prop and renders the correct copy from §1.3.

**Effort: 1h.** Bobbie owns.

---

### `AuditEntry` expansion — medium
Phase A `AuditLogEntry.tsx` is a `<tr>` with action/actor/timestamp. Figma `AuditEntry` has 5 row variants with before→after state columns. The expandable JSON diff is not in the Figma metadata but is in the spec (§6.4). Need to add `before_state`/`after_state` columns to the row (already on the `AuditEvent` interface) and a toggle for the diff panel.

The existing `AuditEvent` interface already has `before_state: Record<string, unknown> | null` and `after_state: Record<string, unknown> | null`. So the data contract is ready — it's a display question. The diff can be rendered as a simple JSON `<pre>` block behind a toggle rather than a full diff library.

**Effort: 1.5–2h.** Bobbie owns the component update. Data comes from Drummer's `GET /documents/{id}/audit`.

---

### `TopNav` brass pending badge — easy
Add `pendingAttestationCount?: number` prop. When `> 0`, render the brass dot + "N PENDING ATTESTATION" text (uppercase, DM Sans medium, brass color). Console page needs to derive this count from the `pendingApproval` array before passing to `TopNav`. Server component — no client state needed.

**Effort: 0.5h.** Bobbie owns.

---

### `Button` Ghost variant — trivial
Add `ghost` to the variant union in `Button.tsx`. Figma: 173px wide, ghost styling (borderless, text-fg-slate, hover text-fg-obsidian). Already handled for the "Return to package" button in `AttestationModal.tsx` via inline classes. Just needs to be promoted to the shared `Button` component.

**Effort: 0.5h.** Bobbie owns.

---

## 4. Data coupling analysis

### What Bobbie can build without Drummer

- All pure component builds (PackageRow, PackageCard, FieldWithConfidence shell, EmptyStateMessage, SourceViewer shell, Button ghost, TopNav badge)
- Console layout improvements (column structure, role visibility, TopNav brass badge count)
- FieldWithConfidence rendering document-level confidence as placeholder across all fields
- AttestationModal: already feature-complete against the Figma spec
- AuditEntry component update (display only; no new data needed beyond existing interface)

### What requires Drummer before I can complete

| Feature | Drummer endpoint needed | Bobbie can ship stub? |
|---|---|---|
| Per-field confidence on Extracted Facts block | `GET /documents/{id}` — add `extracted_fields: Array<{key, value, confidence}>` | Yes, placeholder with doc-level confidence |
| Review notes list + input | `GET /documents/{id}/notes`, `POST /documents/{id}/notes` | Yes, empty state shown |
| Audit trail on detail page | `GET /documents/{id}/audit` | Yes, AuditLogEntry rows with mock/empty |
| Audit Ledger page (Alex) | `GET /audit` with filter params | Alex's problem |
| Reviewer action bar ("Route for approval") | `POST /documents/{id}/route` + `under_review` state | Can show button but disabled |
| Operator action bar ("Mark exception resolved") | `POST /documents/{id}/resolve` | Can show button but disabled |
| v0.2 state enum from backend | State migration (Drummer) | Façade in `state.ts` covers Phase A |
| `routed_for_approval` as a real backend state | Phase B state migration | Façade works for now |

---

## 5. Work split — Bobbie vs. Alex

### Bobbie owns

| Piece | Hours |
|---|---|
| `PackageRow` component extract + 5 state variants | 2h |
| `PackageCard` component extract | 1.5h |
| `FieldWithConfidence` component | 2h |
| `SourceViewer` shell (no PDF engine decision) | 1.5h |
| `EmptyStateMessage` component (7 variants) | 1h |
| `AuditEntry` expand to include before/after columns + toggle | 2h |
| `Button` Ghost variant | 0.5h |
| `TopNav` brass pending badge prop | 0.5h |
| Console: column layout decision + role-based section visibility | 3h |
| Detail page: role-routed action bar (reviewer + operator stubs + approver complete) | 2h |
| Detail page: FieldWithConfidence wired with doc-level confidence as placeholder | 1h |
| Login: confirm copy matches spec §8 | 0.5h |
| **Total Bobbie** | **~17.5h** |

### Alex owns

| Piece | Hours |
|---|---|
| Global Audit Ledger page (`/audit-ledger`) — new route + API client function | 5h |
| Audit filter bar (actor/action/date range, query string state) | 3h |
| `SourceViewer` PDF engine decision + implementation if `react-pdf` added | 4h |
| Review notes form (once Drummer ships endpoint) — client form component, optimistic update | 3h |
| **Total Alex** | **~15h** |

---

## 6. Layouts the current React setup can handle vs. cannot

### Handles fine
- Five-section stacked console: flex-col sections, each a rounded card — already in place.
- 2×2 grid on detail page: `grid gap-4 lg:grid-cols-2` — already in place.
- Modal with scrim: `fixed inset-0 z-50` pattern — already in place and correct.
- Sticky TopNav: `sticky top-0 z-10` — already in place.

### Potential issues

1. **Fixed-column PackageRow at 1440px**: Figma designs the row at exactly 1440px with fixed x-positions (identity at x=24, status at x=767, timestamp at x=1271). At 1440px this works. Below 1024px the status chip and timestamp need to collapse or wrap. Phase A's flex layout handles this gracefully. If we adopt fixed widths to match Figma precisely, we'll break the responsive layout. **Recommendation: keep flex layout, use min-width hints, not fixed px columns.** This is worth a quick word with Holden.

2. **SourceViewer at 600×760px**: The Figma component is fixed 600px wide. On a 4xl max-w (896px), this fits in one column of the 2-col grid at 1024px. Below 768px it'll overflow. Need `w-full` override rather than the Figma fixed width.

3. **AttestationModal content width 640px**: The Figma modal is `max-w-[640px]`. Phase A uses `max-w-lg` (512px). The Figma has more content per the reviewer notes recap section — 640px is the right call for Phase B. Easy to update.

4. **Reviewer notes within the modal**: The Figma `note` frame inside AttestationModal has `x=-66, width=692` — meaning it bleeds outside the 640px modal by 66px on the left. This is almost certainly a Figma layout artifact (absolute position without proper constraints). Do not reproduce this in code. Contain the note to the modal padding bounds.

---

## 7. Accessibility notes

- AttestationModal: correctly implemented (focus trap, ESC, role="dialog", aria-labelledby, initial focus on cancel). No changes needed.
- FieldWithConfidence: the existing ConfidenceBadge has correct aria-labels. Extend the same pattern to FieldWithConfidence — the label should be on the row container, not split across two elements.
- PackageRow: entire row as a link (`<Link>`) is correct. Screen reader will read the full label including the aria-label on `ConsoleRow`. The new PackageRow extract needs the same aria-label pattern: `aria-label=\`Open package ${title}\``.
- AuditEntry expandable diff: toggle button needs `aria-expanded` and `aria-controls`.
- TopNav brass badge: decorative dot should be `aria-hidden`. Count text should be readable as "1 pending attestation" — avoid uppercase-only text without an `aria-label` (the existing StaleBanner pattern of showing text inline is fine here).

---

## 8. Implementation questions for the squad

1. **PackageRow column layout vs. responsiveness**: Figma uses fixed column positions at 1440px. Phase A uses responsive flex. Do we adopt a `grid-cols-[auto_120px_320px_60px]` pattern with `overflow-hidden` on narrow, or keep flex with `flex-shrink-0` hints? Need Holden's call — this is a visual fidelity vs. responsive-quality tradeoff.

2. **SourceViewer — react-pdf or iframe?**: Adding `react-pdf` means ~400KB extra bundle (even with dynamic import), PDF.js worker complexity, and test overhead. The iframe is already working. If the client hasn't asked for a page-navigation control or zoom within the viewer, the iframe is fine for Phase B. **Do we add the dependency?** Alex to advise; Holden to decide.

3. **Per-field extraction API shape**: Drummer needs to confirm the field schema before I can finalise `FieldWithConfidence` props. My proposed type is `{ key: string; displayLabel: string; value: string | null; confidence: number | null; fallback?: boolean }`. Does Drummer's extraction model produce this, or does it return a flat dict with separate confidence dict? I need the shape before writing the component.

4. **Review notes endpoint auth**: Can reviewers and operators both write notes, or only reviewers? Figma and spec §6.3 say reviewer role only for input. But operators might need to annotate exceptions. Holden to confirm scope.

5. **AttestationModal max-width**: Phase A uses `max-w-lg` (512px). Figma is 640px. The reviewer notes recap section needs the extra width. Shall I update to `max-w-2xl` (672px) or `max-w-[640px]` (pixel-exact)? I'll go `max-w-2xl` unless there's an objection.

6. **Global Audit Ledger route**: Is it `/audit`, `/audit-ledger`, or `/console/audit`? TopNav labels it "Audit ledger" but the route hasn't been decided. Affects the `<Link href>` in TopNav and the filter link at the bottom of each package's audit trail block.

7. **Reviewer name in `under_review` chip**: The next-owner chip for `under_review` should show "With {reviewer name}". The current API types for `DocumentSummary` have no `reviewer` field — only the document-level `uploaded_by`. Does Drummer add `current_reviewer_email` or `reviewer_name` to the summary endpoint, or do we derive it from audit events?

8. **Role-based console section visibility (§5.5)**: Operators should not see Needs Review or Pending Approval sections. Phase A shows all sections to all roles. The `user.role` is available server-side. Should I gate sections behind role checks now, or wait for Drummer to ship the v0.2 role enum (`operator`, `reviewer`, `approver`) before doing this? If I gate on `admin`/`reviewer` now I'll need to update again after migration.

9. **`routed_for_approval` as a real backend state**: The state façade in `state.ts` correctly handles Phase A mapping but `pendingApproval` section will always be empty because no v0.1 document has `routed_for_approval` as a backend status. Should I wire a demo/seed row so the brass count badge and Pending Approval section are visually testable before Drummer ships the state migration?

10. **AuditEntry before/after diff display**: The spec says "expandable before/after JSON diff" (§6.4). The Figma shows 5 entry variants by content but no expand toggle in the metadata I have. Do we want a `<details>/<summary>` native expand or a React `useState` toggle? And do we render raw JSON or a formatted diff (e.g. highlight changed keys)? A raw `<pre>` is faster to build and reviewable; a visual diff is nicer but takes 1–2 extra hours. Holden to decide scope.

---

## 9. Summary risk assessment

| Item | Risk | Mitigation |
|---|---|---|
| Per-field confidence depends on Drummer API | High — blocks FieldWithConfidence real data | Build component now with doc-level placeholder; Drummer ships field shape |
| Review notes form — no endpoint | High — blocks reviewer workflow | Build UI stub; enable on Drummer Phase B |
| Audit trail on detail page — no endpoint | Medium — audit trail is stubbed in Phase A already | Acceptable stub; unblock in B1 |
| Audit Ledger page (Alex) — no route, no API | Medium — TopNav link goes nowhere | Alex builds in B1; interim: link is rendered but 404s |
| SourceViewer PDF engine | Low/Medium — iframe works, react-pdf is optional | Defer decision to Alex + Holden |
| Fixed-column row layout vs. responsive | Low — responsive flex is already working | Keep flex; raise with Holden before switching |
| `routed_for_approval` brass badge invisible in staging | Low — Phase A staging has no such docs | Seed data or wait for Drummer migration |

Phase B frontend work is well-structured. The biggest risk is not UI complexity — it's backend data availability for the FieldWithConfidence and review notes features. Everything in my column is buildable now except those two. I'll stub both and unblock on Drummer.

---
*Filed: Bobbie (Sonnet 4.6) · 2026-04-15*
