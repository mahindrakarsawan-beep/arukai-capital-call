# D2 v0.2 — Atelier Spec (POR-147 / ARU-17)

**Author:** Holden (UX + squad lead)
**Date:** 2026-04-15
**Model tier:** Opus decision turn — single-pass. Bobbie and Drummer execute on Sonnet from this spec without further interpretation.
**Binding authority:** POR-147 client directive, `feedback_arukai_product_language.md`, ARU-13 IP separation (Arukai layer tokens P-3.1).

Premise: v0.1 shipped as a generic admin dashboard. v0.2 must read as a **private workflow atelier for governed capital-call intake**. Every decision below is concrete enough to build from. No interpretive slack.

---

## 1. Product language table (final)

Authoritative copy. Every v0.1 string replaced. Miller audits against this table; zero tolerance for drift.

### 1.1 Buttons

| Where | v0.1 string | v0.2 string |
|---|---|---|
| Login submit | Sign in | Enter workflow |
| Login card heading | Sign in | Authorized access |
| Top nav primary CTA | Upload new | Begin intake |
| Dashboard empty CTA | Upload your first document | Begin the first intake |
| Upload submit | Upload and classify | Submit package for intake |
| Upload cancel | Cancel | Discard draft |
| Package detail — admin approve | Approve | Attest approval |
| Package detail — admin reject | Reject | Record rejection |
| Approval modal confirm | Approve | Attest and record decision |
| Approval modal cancel | Cancel | Return to package |
| Review notes save | Save | Record review note |
| Exception resolve | Resolve | Mark exception resolved |
| PDF download link | Download PDF | View source document |
| Logout | Sign out | Leave workflow |

### 1.2 Headings

| Where | v0.1 heading | v0.2 heading |
|---|---|---|
| Login H1 | Arukai | Arukai |
| Login H2 | Sign in / Capital Call Management | Private workflow environment |
| Login subtext | (none) | Governed capital-call review. Authorized access only. |
| Dashboard H1 | Documents | Operations console |
| Dashboard subtext | N documents | N active packages across your desk |
| Upload H1 | Upload document | Begin governed intake |
| Upload subtext | PDF only — max 20 MB. The document will be classified automatically. | Submit a capital-call package. Intake is governed: classification, review, and attestation steps are recorded. PDF, up to 20 MB. |
| Detail H1 | {filename} | {package title} |
| Detail subtext | Uploaded {date} by {actor} | Package submitted {date} by {actor} |
| Detail block 1 | (none) | Source document |
| Detail block 2 | Classification | Extracted facts |
| Detail block 3 | (none) | Review notes |
| Detail block 4 | (none) | Audit trail |
| Approval modal H1 | (none) | Attestation |
| Global audit H1 | (none) | Audit ledger |

### 1.3 Empty states

| Surface | v0.2 copy |
|---|---|
| Dashboard — Active packages | No packages in flight. Begin an intake to open the first record. |
| Dashboard — Needs review | Nothing awaiting your review. Reviewer queue is clear. |
| Dashboard — Pending approval | No packages routed for attestation. |
| Dashboard — Recent decisions | No decisions recorded in the last 30 days. |
| Dashboard — Exceptions | No exceptions surfaced. All packages within confidence thresholds. |
| Package detail — Review notes (none yet) | No review notes recorded. Reviewers will annotate here before routing for approval. |
| Package detail — Audit trail (should never be empty; placeholder) | Package has no recorded events yet. Submission event will appear on intake. |
| Global audit ledger | No events match the current filter. |

### 1.4 Status pills (package state → pill copy)

| State | Pill label | Tone |
|---|---|---|
| `submitted` | Submitted · awaiting intake | neutral slate |
| `intake_complete` | Intake complete · awaiting reviewer | neutral slate |
| `under_review` | Under review · {reviewer name} | neutral slate |
| `routed_for_approval` | Routed for approval · awaiting approver | **brass** (signal) |
| `decision_recorded` (approved) | Approved · {approver} · {date} | positive |
| `decision_recorded` (rejected) | Rejected · {approver} · {date} | negative |
| `exception_surfaced` | Exception surfaced · needs operator | amber warning |

### 1.5 Alerts / toasts / banners

| Trigger | v0.2 copy |
|---|---|
| Submit success | Package submitted. Intake in progress. |
| Intake complete (async) | Intake complete. Package routed to reviewer queue. |
| Review note saved | Review note recorded. |
| Approval recorded | Decision recorded. Package closed. |
| Rejection recorded | Rejection recorded. Package closed. |
| Session expired | Workflow session has ended. Re-authenticate to continue. |
| Fetch failure (StaleBanner) | Workflow state could not be refreshed. The information shown may be stale. |
| File too large | File exceeds the 20 MB intake limit. |
| File wrong type | Only PDF packages are accepted for intake. |
| Low confidence on submit | Intake complete with exceptions. Low-confidence fields need reviewer attention. |
| Permission denied | This action is outside your workflow role. |

### 1.6 Navigation items (top nav)

| Item | Label |
|---|---|
| Home / dashboard | Console |
| Begin intake | Begin intake |
| Global audit | Audit ledger |
| User menu — identity | {name} · {role} |
| User menu — leave | Leave workflow |

Role strings: `Operator`, `Reviewer`, `Approver`. (Drop `admin`/`reviewer` DB values at the display layer; they remain as enum codes.)

### 1.7 Form field labels

| Form | Field | v0.2 label | Placeholder |
|---|---|---|---|
| Login | email | Credentialed email | name@firm.example |
| Login | password | Passphrase | — (dots) |
| Intake | title | Package reference | e.g. Fund III — Q2 capital call |
| Intake | file | Source PDF | Select package PDF |
| Review note | body | Reviewer annotation | What requires operator attention before attestation? |
| Attestation | note | Attestation note (optional) | Optional context for this decision |
| Audit filter | actor | Filter by actor | — |
| Audit filter | action | Filter by action | — |
| Audit filter | date range | Between | — |

---

## 2. State model (backend)

Replace the `package_status` enum. Add new enum `package_state` with six values. Keep a compatibility mapping for v0.1 data (one-time migration).

### 2.1 States

| State | Definition | Owner of next action | UI signal |
|---|---|---|---|
| `submitted` | Operator has submitted package; classification not yet run | System (auto) | Neutral pill, indeterminate intake spinner on detail |
| `intake_complete` | Classification + extraction complete, all confidence within thresholds, no exceptions | Reviewer | Neutral pill, row appears in "Needs review" block |
| `under_review` | A reviewer has opened the package and recorded at least one review note, or explicitly claimed it | Reviewer | Neutral pill carrying reviewer identity |
| `routed_for_approval` | Reviewer has completed their pass and routed for attestation | Approver | **Brass** pill — the only brass on the screen |
| `decision_recorded` | Approver has attested (approved) or rejected; terminal | None (closed) | Positive or negative pill with approver + date |
| `exception_surfaced` | Intake produced a low-confidence field (<0.5) OR extraction failed OR a required field is missing | Operator | Amber pill, row appears in "Exceptions" block |

### 2.2 Transitions (valid only)

```
submitted
  ├─> intake_complete         (system: classification success, all fields ≥0.5)
  └─> exception_surfaced      (system: classification failure OR any field <0.5 OR required field missing)

intake_complete
  ├─> under_review             (reviewer: claim OR record first review note)
  └─> exception_surfaced      (reviewer: flag as exception)

under_review
  ├─> routed_for_approval     (reviewer: route)
  ├─> intake_complete         (reviewer: release claim, no notes recorded — allowed only if no notes)
  └─> exception_surfaced      (reviewer: escalate)

routed_for_approval
  ├─> decision_recorded       (approver: attest approval OR record rejection)
  └─> under_review            (approver: return to reviewer with note — "return for revision")

exception_surfaced
  ├─> intake_complete         (operator: resolve exception — fields corrected)
  └─> decision_recorded       (approver: reject directly from exception)

decision_recorded
  └─> (terminal, no transitions)
```

Drummer: all transitions must write an `AuditEvent` with `before_state`, `after_state`, `actor_user_id`. Invalid transitions return 409 with body `{"detail":"Transition {from}→{to} not permitted"}`.

### 2.3 v0.1 → v0.2 migration

| v0.1 status | v0.2 state |
|---|---|
| `pending_classification` | `submitted` |
| `pending_review` (confidence ≥ 0.5) | `intake_complete` |
| `pending_review` (confidence < 0.5) | `exception_surfaced` |
| `approved` | `decision_recorded` (with `decision='approved'` on Approval) |
| `rejected` | `decision_recorded` (with `decision='rejected'`) |

One-shot alembic migration. Keep old column temporarily as `legacy_status` for one sprint, then drop.

---

## 3. Next-owner chip copy

Every status row on every surface carries a next-owner chip beside the state pill. Two-chip pattern: `[state pill]  [next-owner chip]`.

| State | Next-owner chip |
|---|---|
| `submitted` | Awaiting system intake |
| `intake_complete` | Awaiting reviewer |
| `under_review` (claimed by named reviewer) | With {reviewer} |
| `under_review` (unclaimed) | Awaiting reviewer |
| `routed_for_approval` | Awaiting approver attestation |
| `decision_recorded` (approved) | Decision recorded — {approver} attested on {date} |
| `decision_recorded` (rejected) | Decision recorded — {approver} rejected on {date} |
| `exception_surfaced` | Awaiting operator — {reason: low confidence \| missing field \| extraction failure} |

Visual: next-owner chip is a borderless text chip, `font-interface text-xs`, `text-fg-slate`, with a 6px leading dot (`bg-fg-muted` for neutral, `bg-brandBrass` for `routed_for_approval`, `bg-warningText` for exceptions). Never filled. The chip is prose, not a badge.

---

## 4. Confidence display rules

Per-field confidence is required for every AI-extracted value. v0.1 only showed document-level classification confidence; v0.2 surfaces per-field.

### 4.1 Thresholds

| Band | Range | Visual treatment | Screen-reader text |
|---|---|---|---|
| High | ≥ 0.90 | Value only. No pill, no marker. `text-fg-obsidian`. No suffix. | "{field}: {value}" |
| Confident | 0.70–0.89 | Value + hairline right-side marker (2px column, `bg-borderHairlineStrong`). Hover/long-press reveals: "Extracted with high confidence ({pct}%)". | "{field}: {value}, extracted with high confidence" |
| Needs review | 0.50–0.69 | Value + small amber pill to the right: `Needs review`. Pill uses `bg-warningSurface`, `text-warningText`, `font-interface text-[10px] uppercase tracking-wider`. | "{field}: {value}, needs reviewer attention" |
| Low confidence | < 0.50 | Value wrapped in a 1px dashed `border-warningText` box; pill to the right: `Low confidence — flag`. Clicking/tapping opens the exception panel. Package itself becomes `exception_surfaced` on intake. | "{field}: {value}, low confidence, flagged for manual verification" |

### 4.2 Rendering rules

- Confidence band is computed at render time from numeric `confidence` (0–1 float per field, returned by backend).
- Never show the raw percentage as the primary marker. Percentages only appear on hover/tooltip ("Extracted with {pct}% confidence").
- Confidence markers never use `brandBrass`. Brass is reserved for the `routed_for_approval` state and the attestation confirm button — nothing else.
- Missing field (extraction returned null) renders as: `—` with amber pill `Missing`. Treat same as <0.5 for exception routing.

---

## 5. Dashboard — operations console layout

Not a table of documents. A stacked operations console with five named sections in this exact order. Each section has: header row (title + count + optional action), rows, explicit empty state.

```
┌──────────────────────────────────────────────────────────────────┐
│ [TopNav: Arukai · Console · Begin intake · Audit ledger · user] │
├──────────────────────────────────────────────────────────────────┤
│  Operations console                                              │
│  12 active packages across your desk                             │
│                                                                  │
│  ─ Exceptions ─────────────────────────── 2 ─────────────────    │
│  [rows — see below]                                              │
│                                                                  │
│  ─ Pending approval ─────────────────── 1 ───── (brass count) ─  │
│  [rows]                                                          │
│                                                                  │
│  ─ Needs review ────────────────────── 4 ─────────────────────   │
│  [rows]                                                          │
│                                                                  │
│  ─ Active packages ─────────────────── 12 ─────── [Begin intake]│
│  [rows — everything still in flight]                             │
│                                                                  │
│  ─ Recent decisions ────────────────── last 30 days ──────────   │
│  [rows — terminal, closed packages]                              │
└──────────────────────────────────────────────────────────────────┘
```

### 5.1 Section order and rationale

1. **Exceptions** — surface first because they block flow. If zero, render empty state but keep the section visible.
2. **Pending approval** — second because approvers visit the console to attest. Only section whose count can render in brass (when > 0).
3. **Needs review** — reviewer queue.
4. **Active packages** — the full in-flight set (everything except `decision_recorded`). This is the "where is my work" view.
5. **Recent decisions** — closed record. Read-only proof of governance.

### 5.2 Section header pattern

`{title} · {count}  ───────────────────────────────  [optional action]`

- Title: `font-display text-xl font-light text-fg-obsidian tracking-tight`
- Count: `font-interface text-sm text-fg-muted tabular-nums`
- Hairline separator (`border-border-hairline`)
- Optional action button (only on "Active packages": `Begin intake`)

### 5.3 Row shape

Every row across every section has the same columns (consistent rhythm):

| Column | Content | Weight |
|---|---|---|
| Package reference | `{title}` (Cormorant regular, 16pt) | primary |
| Classification | Small DM Sans label: "Capital call notice" etc. | secondary |
| State pill | Per §1.4 | — |
| Next-owner chip | Per §3 | — |
| Last movement | Relative timestamp ("3h ago") + absolute on hover | tertiary |

Click target: entire row → `/packages/{id}`. Keyboard-focusable, enter to open.

### 5.4 Empty state per section

Per §1.3. Empty state replaces the rows, not the section header.

### 5.5 Role-based visibility

- Operators: see Exceptions (own), Active (own), Recent (own). Do not see Needs review, Pending approval.
- Reviewers: see all sections, but Pending approval is read-only.
- Approvers: see all sections, Pending approval actionable.

(v0.1 does not yet distinguish reviewer/approver in the enum — Drummer: add `approver` role in Phase B or treat `admin` as approver for v0.2 Phase A.)

---

## 6. Package detail layout

Four blocks, stacked in this order on narrow viewports, 2×2 grid ≥lg. Headings exactly as given.

```
┌───────────────────────── Header ──────────────────────────┐
│  {Package title}                  [state pill][next owner]│
│  Package submitted {date} by {actor}                       │
│  Classification: {Capital call notice} · intake confidence│
├───────────────┬───────────────────────────────────────────┤
│  Source       │  Extracted facts                          │
│  document     │  (per-field confidence per §4)            │
│               │                                           │
├───────────────┼───────────────────────────────────────────┤
│  Review notes │  Audit trail                              │
│               │                                           │
└───────────────┴───────────────────────────────────────────┘
                          [Route for approval] (reviewer)
                          [Attest approval] [Record rejection] (approver, brass)
```

### 6.1 Source document

Heading: **Source document**

- Inline PDF preview via `<object>` / `pdf.js` embed. Default open.
- "View source document" link opens full-screen viewer in new tab (replaces v0.1 download link copy).
- Sidecar metadata: filename, size, MIME, uploaded-at, SHA-256 checksum (Phase C — for Phase A, omit checksum).
- Phase A acceptable fallback: embedded `<iframe src={pdfUrl}>` at 600px height; full viewer opens on click.

### 6.2 Extracted facts

Heading: **Extracted facts**

- Two-column key/value list. Key: DM Sans label (uppercase tracked). Value: Cormorant regular for numerics and names; DM Sans for prose fields.
- Every field renders with confidence treatment per §4.
- Header line beneath the block title: "Extracted by {model_version} on {date}". Links to audit event.
- Fields for capital call notice (initial set): Fund name, Call number, Call amount, Due date, Wire instructions reference, Investor of record, Side-letter reference (if any).
- If `fallback: true` on the classification, render a banner inside the block: "Extracted via fallback parser. Reviewer attention recommended on all fields."

### 6.3 Review notes

Heading: **Review notes**

- List of reviewer annotations, newest first. Each entry: author, timestamp, body, linked-field (optional).
- Input at bottom (reviewer role only): textarea + "Record review note" button.
- Notes are **separate** from approval notes. Approval notes live on the attestation record, not here. This is the single most important backend separation in Phase B.
- Empty state per §1.3.

### 6.4 Audit trail

Heading: **Audit trail**

- First-class, not hidden. Visible on every package detail page.
- Chronological list (oldest first, collapsible to newest-first).
- Each entry: `{actor} · {action} · {timestamp}` with expandable before/after JSON diff.
- Link at the bottom: "Open in audit ledger →" filters the global ledger by this package.

### 6.5 Bottom action bar

- Reviewer (state = `under_review` or `intake_complete`): [Record review note] (if typed), [Route for approval] (secondary → secondary-strong once at least one note recorded).
- Approver (state = `routed_for_approval`): [Attest approval] (**brass primary** — the only brass button in the app), [Record rejection] (secondary), [Return to reviewer] (ghost).
- Operator (state = `exception_surfaced`): [Mark exception resolved] (secondary).
- Terminal (`decision_recorded`): no actions. Banner: "Package closed. Decision recorded by {approver} on {date}."

---

## 7. Approval attestation dialog

Modal, not inline. Triggered from `[Attest approval]` on package detail. Blocks background; scrim `overlayScrim`. Framed as a moment, not a click.

### 7.1 Structure (top to bottom inside the modal)

1. **Modal heading:** *Attestation* (Cormorant, 28pt, light)
2. **Subheading:** *You are about to record a binding decision on this package.* (DM Sans, 14pt, slate)
3. **Package summary panel** (read-only, `bg-parchment`, inset):
   - Package title (Cormorant)
   - Classification + intake confidence
   - Amount / due date / fund (if extracted)
   - Any field still in "Needs review" band — surfaced as a warning strip above the summary: *N fields were flagged during review. Proceed only if resolved.*
4. **Reviewer notes recap** (embedded, not a link):
   - Panel heading: *Reviewer notes on record*
   - Each note: author · timestamp · body
   - Empty state: *No review notes were recorded before this attestation.* (italic warning if empty — attestation still permitted but visibly unusual.)
5. **Attestation language** (bold block, Cormorant italic 18pt):
   > "I attest that I have reviewed this capital-call package, considered the reviewer notes above, and approve it for operator execution. This decision is recorded against my name and the current timestamp."
6. **Optional attestation note** (textarea): *Attestation note (optional) — context for the record.*
7. **Action row:**
   - Left: **[Return to package]** (ghost, neutral)
   - Right: **[Attest and record decision]** (brass primary, requires a single click — no double-confirm; the modal itself is the confirmation)

### 7.2 Rejection variant

Triggered from `[Record rejection]`. Same structure but:
- Heading: *Record rejection*
- Attestation language:
  > "I reject this capital-call package. The reasons noted below are recorded against my name and the current timestamp. The package will be closed as rejected."
- Attestation note is **required** on rejection.
- Confirm button: **[Record rejection]** (neutral dark — `fg-obsidian` background, `bg-bone` text). Brass is not used on rejection.

### 7.3 Behavior

- On confirm: POST to backend → server creates Approval row + AuditEvent + flips state to `decision_recorded` atomically.
- On success: modal closes with a 240ms fade, toast `Decision recorded. Package closed.`, package detail re-renders in closed state.
- On failure: modal stays open with inline error strip at top; buttons re-enabled.
- Escape key / backdrop click: close modal (safe — no state mutation).
- Focus: trapped inside modal; initial focus on `[Return to package]` (do not default focus the destructive/binding action).

---

## 8. Login screen — copy and visual

### 8.1 Copy

| Element | Copy |
|---|---|
| Wordmark | `Arukai` (Cormorant, light, 40pt) |
| Tagline under wordmark | `Private workflow environment` |
| Card heading | `Authorized access` |
| Card subtext | `Governed capital-call review. Credentialed access only.` |
| Email label | `Credentialed email` |
| Password label | `Passphrase` |
| Submit button | `Enter workflow` |
| Auth error alert | `Credentials not recognized. Access not granted.` |
| Session-expired re-entry banner | `Your workflow session has ended. Re-authenticate to continue.` |

### 8.2 Visual

- **Background:** Obsidian (`bgObsidian` `#0D0F12`). Full viewport.
- **Wordmark and tagline:** `text-bg-bone` on obsidian, centered, top third of viewport.
- **Auth card:** `bgBone` surface, `radius.lg` (16px), 1px `borderHairline`, 32px internal padding, 400px max width, centered.
- **Submit button:** neutral dark (`bg-fgObsidian`, `text-bgBone`). **Never brass on the login.** Brass on the login would trivialize the only-brass-for-attestation rule.
- **Ceremony (Phase C):** on successful credential submit, card fades to 0 over 240ms (`withTiming`, per animation memory note — no springs), a single hairline draws across the viewport at 1/3 height over 360ms (`withTiming`), then route transitions to `/console`. Reduced-motion: skip drawing hairline, just fade.
- **No gradients. No glow. No illustration.** Obsidian void + bone card + Cormorant wordmark.

---

## 9. Typography and color use

### 9.1 Cormorant Garamond (display)

Use for:
- Arukai wordmark (login, top nav)
- All page-level H1s (`Operations console`, `Audit ledger`, package title on detail)
- Extracted fact values that are numeric or proper-noun (amounts, fund names, call numbers, investor names)
- Attestation language block (italic 18pt) in the approval modal
- Modal H1 (`Attestation`)

Never use Cormorant for:
- Button labels
- Status pills, next-owner chips, confidence pills
- Table headers, form labels
- Body paragraphs
- Timestamps, IDs, metadata

### 9.2 DM Sans (interface)

Default for everything else: body, labels, buttons, pills, table rows, form fields, timestamps, navigation, toasts, tooltips.

Weights:
- Regular — body, values
- Medium — labels (uppercase tracked), table column headers
- SemiBold — buttons, card titles, nav-active

### 9.3 Brass (`#B8914E`) — signal-only use

Brass appears in exactly these places, nowhere else:

1. The **Attest approval** button (approval modal confirm + the action bar button that opens the modal).
2. The **`routed_for_approval`** state pill and its leading dot on the next-owner chip.
3. The dashboard count badge next to the **Pending approval** section header *when the count is greater than zero*.

That is the complete list. Any other brass use is a violation; Miller rejects it.

Amber (`warningSurface` / `warningText` `#9A7639`) is a distinct colour role — it marks exceptions, low-confidence fields, and missing fields. Brass (`#B8914E`) is never amber; amber is never brass. The two are close in hue but carry separate semantic contracts. Do not use one for the other.

### 9.4 Surface rhythm

- `bgBone` — default canvas for cards and modals
- `bgParchment` — insets (read-only summary panels, source document sidecar, empty states)
- `bgObsidian` — login background only in v0.2; reserved for ceremony surfaces in future
- `borderHairline` everywhere a divider is needed; never a thicker border except for the low-confidence dashed box (§4.1)

---

## 10. Squad dispatch plan

Four tickets. Sonnet-tier for all build agents. Opus only for the final decision validation.

### Phase A — Frontend reframe (no backend changes)

**Ticket A1 — ARU-17-A1: Copy and IA reframe + console layout**
- Agent: **Bobbie** (Sonnet)
- Miller gate: **Miller** (Sonnet) — Playwright E2E copy audit + principle conformance
- Holden writes failing tests first (Miller can assist): login copy, console section order, next-owner chips render, brass appears only on routed-for-approval pill.
- Scope: §1 (all copy), §5 (console sections — map v0.1 statuses to v0.2 states at render time via a façade; no backend changes), §6.1–6.4 excluding per-field confidence (§6.2 renders whatever backend exposes today with document-level confidence), §8 (login reframe, no ceremony), §9 typography + brass discipline.
- Non-goals: per-field confidence (needs Drummer), attestation modal (needs A2), reviewer notes separation (needs Drummer).
- Estimated: 1 day with TDD. Holden approves copy diff; Miller validates.

**Ticket A2 — ARU-17-A2: Attestation modal + role-routed action bar**
- Agent: **Bobbie** (Sonnet)
- Miller gate: **Miller**
- Scope: §7 attestation modal (approve + reject variants), §6.5 action bar role routing. Uses existing `approved`/`rejected` backend endpoints renamed at the API-client layer to `attestApproval` / `recordRejection`. No new backend.
- Animation: modal fade 240ms `withTiming`; no spring. Adheres to animation memory note.
- Estimated: 0.5 day.

### Phase B — Backend state expansion + per-field confidence

**Ticket B1 — ARU-17-B1: State machine + reviewer notes model + per-field confidence**
- Agent: **Drummer** (Sonnet)
- Miller gate: **Miller**
- Failing tests: state transitions (§2.2 transition matrix), reviewer notes table isolation from approval notes, per-field confidence round-trip through API.
- Scope:
  - Alembic migration: new `package_state` enum (§2.1), migrate v0.1 data per §2.3, add `legacy_status` column.
  - New `ReviewNote` table: `id`, `package_id`, `author_id`, `body`, `linked_field` (nullable), `created_at`.
  - Classification schema extension: `extracted_fields` JSON column with shape `{field_name: {value, confidence}}`. Backfill existing rows with document-level confidence applied uniformly (with `backfilled: true` flag).
  - New endpoints: `POST /packages/{id}/review-notes`, `GET /packages/{id}/review-notes`, `POST /packages/{id}/transition` (validates against §2.2), `GET /audit` (global ledger with actor/action/date filters).
  - Existing approve/reject endpoints: keep functional behaviour, but now drive `decision_recorded` state transition and write audit events per contract.
- Estimated: 1.5 days.

**Ticket B2 — ARU-17-B2: Frontend wires up per-field confidence, review notes, global audit ledger**
- Agent: **Bobbie** (Sonnet)
- Miller gate: **Miller**
- Scope: §4 confidence rendering (all 4 bands), §6.2 extracted-facts per-field visuals, §6.3 reviewer notes panel + input, new `/audit` page (audit ledger with filters per §1.7), next-owner chip copy pulled from real backend state (§3).
- Depends on: B1 merged.
- Estimated: 1 day.

### Phase C — Polish

**Ticket C1 — ARU-17-C1: Intake ceremony + inline PDF viewer + exception resolution**
- Agent: **Bobbie + Drummer** (Sonnet, split by surface)
- Miller gate: **Miller**
- Scope:
  - Inline PDF viewer per §6.1 (replace `<iframe>` fallback with pdf.js).
  - Intake ceremony animation on submit (Phase A used a toast; Phase C draws the hairline, adapts ARU-02-P17). 240/360ms `withTiming` only, reduced-motion fallback.
  - Login ceremony per §8.2.
  - Exception detail view + "Mark exception resolved" flow.
- Estimated: 1 day.

### Final validation (Opus)

**Ticket Z1 — ARU-17-Z: Decision validation**
- Agent: **Holden** (Opus — single turn)
- Scope: walk the full flow (login → intake → review → attestation → audit) on the running app. Compare every surface to this spec. Sign off or reject. If reject, one concrete delta ticket, not a re-brief.

### Dispatch sequencing

```
A1 ──┐
     ├── merge → A2 ──┐
                      ├── merge → B1 → B2 ──┐
                                            ├── merge → C1 ──┐
                                                             └── Z1 (Holden Opus)
```

A1 and B1 cannot run in parallel meaningfully because A1's tests reference the copy/state mapping layer; B1 changes the state model. A1 ships first with a translation façade, B1 rips the façade out.

### Dispatch boilerplate (each ticket)

Every Bobbie/Drummer dispatch prompt must include:
- The 14 Copilot KPI rules (per memory note `feedback_dispatch_must_include_rules.md`).
- `isolation:worktree` (parallel agent safety, per `feedback_squad_subagent_dispatch.md`).
- TDD requirement: failing tests committed before implementation; Miller validates the gate (per `feedback_tdd_and_miller_gate.md`).
- Local-first: develop and test locally before staging (per `feedback_local_first_dev.md`).
- Animation: `withTiming` only. Springs reserved for refresh/sheet — neither applies in v0.2 scope (per `feedback_animation_quality.md`).

---

## Appendix A — What Miller audits

1. **Copy drift:** grep for banned v0.1 strings (`Upload`, `Sign in`, `Approve` as button label, `Success`, `Processing complete`). Zero matches allowed.
2. **Brass discipline:** scan DOM for any element with `brandBrass` color. Must match exactly the three cases in §9.3.
3. **Cormorant discipline:** any button or pill using `font-display` is a violation.
4. **State transitions:** every state change writes an `AuditEvent`. No orphan transitions.
5. **Confidence coverage:** every extracted field renders a confidence band. No bare AI value without a band.
6. **Next-owner chip coverage:** every state pill on every surface is paired with a next-owner chip.
7. **Attestation moment:** `[Attest approval]` never fires without the modal rendered.
8. **Playwright E2E:** login → begin intake → intake complete → review note → route for approval → attest → decision recorded → verify audit ledger shows the full trail.

---

*End of spec. Bobbie and Drummer execute. No further interpretive turns until Z1.*
