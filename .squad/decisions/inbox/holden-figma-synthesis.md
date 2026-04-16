# Holden — Figma Review Synthesis (POR-147 / ARU-17)

**Date:** 2026-04-15
**Inputs:** 6 independent reviews (holden self, bobbie, alex, drummer, naomi, miller)
**Status:** AWAITING SAWAN APPROVAL — no build begins until Q-block below is answered.

---

## 1. Executive summary

Six reviews, broadly aligned. Phase A build is feasible; Phase B has real structural work (6-state machine, reviewer notes, per-field confidence, global audit ledger); Phase C is where the ceremony lives. The design is **not shippable as drawn** — four blocker fixes land before build: (a) brass discipline violation in TopNav, (b) audit ledger screen is ops-SaaS as-drawn and must be redrawn, (c) "Release claim" button on screen 3 is spec-orphaned, (d) no focus states drawn anywhere. Missing frames: intake ceremony, exception detail, zero-flags attestation variant.

Three highest-risk items across all reviewers:
- **Contract drift (Miller, repeat of POR-146):** 7 new endpoints, no generated types, no contract test extension. Non-negotiable gate.
- **Concurrency race on state transitions (Naomi R2):** two reviewers/approvers clicking simultaneously corrupt the audit trail. Needs optimistic locking (`version` column).
- **PDF iframe auth (Alex A3, Miller Q1):** the current `<iframe src=...>` will silently 401 in staging against token-gated backend. This is shipping broken today.

No Sawan-level blockers that prevent the squad from starting Phase A re-work — but 6 questions below need Sawan's decisions before B1 writes a line of backend.

---

## 2. Figma fixes to land BEFORE any build (owned by Holden)

These are my commits on Page 3, not tickets:

| Fix | Action | Why |
|---|---|---|
| TopNav pending chip | Re-skin neutral (fg-obsidian 8%, fg-muted text, **no brass dot**) | 4th brass site violates §9.3 |
| Audit ledger screen (17:34) | **Full redraw.** Hero band, 15+ rows of real data, `system` vs `user` actor badge, per-row Cormorant narrative | As drawn it is admin-panel aesthetic — fails criterion 6 |
| "Release claim" button | **Remove** from screen 3 until claim-model is decided (Naomi Q1, Drummer Q4) | Not in §6.5; orphan button |
| Focus states | Add 2px fg-obsidian ring with 4px offset to every interactive component on Page 2 | Zero focus states drawn anywhere — a11y miss |
| Intake ceremony frame | **Add** (Phase C surface has no mock) | Phase C has UX weight and zero Figma coverage |
| Exception detail frame | **Add stub** | No way to see what an opened exception looks like |
| Attestation modal — zero-flags variant | **Add** second frame (warning strip absent when N=0) | Bobbie will guess otherwise; Miller Q already flagged |
| Audit trail on detail pages | **Redraw** as full-width bottom strip (not 2×2 half-column) | Column was clipping text; structural root cause of criterion-6 miss |
| Console density (screen 02) | **Redraw** 3–5 rows per active section | Current 1-row-per-section misrepresents real load rhythm |
| Login | Left-align field labels; bump recording disclosure to fg-inverse 70%; add focus ring | AA contrast fail + internal a11y rule |

**ETA on Holden redraws:** 1 day. Commits before B1 branches out. B2 (global audit ledger build) is gated on the audit ledger redraw.

---

## 3. Ownership reconciliation

Reviewed every claim across the 6 reviews. Conflicts resolved below.

### 3.1 Conflicts found and resolved

| Conflict | Resolution |
|---|---|
| **Global audit ledger FE** — Bobbie said "Alex's work"; Alex claimed it explicitly | **Alex owns.** Confirmed. Fresh eyes + no existing code to navigate. |
| **SourceViewer PDF engine** — Bobbie said "shell mine, PDF Alex's"; Alex claimed auth fix | **Split stands.** Bobbie shell, Alex owns auth fix (A3) + pdf.js evaluation. |
| **Operations console sectioning** — both Alex and Bobbie named this | **Bobbie owns.** She has the existing list-page patterns. Alex's version politely deferred. |
| **State machine module** — Drummer proposed as pure module; Naomi proposed to **own** it | **Naomi owns the pure module (`app/state_machine.py`) + optimistic-locking migration. Drummer owns the router-layer endpoints that call it.** Naomi's R2 concurrency catch earns her the transition invariants. |
| **Reviewer notes table + endpoints** — Drummer claimed; Naomi claimed | **Naomi owns.** Her append-only + role-guard design is correct. Drummer consumes via the detail endpoint. |
| **Attestation modal** — Bobbie has it feature-complete; Alex claimed the flagged-field warning panel | **Bobbie keeps modal core; Alex adds the flagged-field warning inset as A4.** Holden reserves final call: Bobbie does not ship the modal in 40 minutes. Ceremonial work gets time. |
| **Classification re-extraction history** (Naomi R7) | **Drummer owns the one-to-many refactor** (remove `unique=True` on `classifications.document_id`, add `is_current` flag). |
| **CSV export** — Drummer deferred to Naomi | **Naomi owns `GET /audit/export` streaming.** Confirmed. |

### 3.2 Gaps (nobody claimed — assigning now)

| Gap | Owner | Rationale |
|---|---|---|
| Audit table append-only DB trigger (Naomi R9) | **Naomi** | Already in her risk register |
| `audit_events.package_id` FK → `RESTRICT` on DELETE (R10) | **Naomi** | Same migration chain |
| Seed user for `approver` role | **Naomi** (per Drummer's scope declaration) | Drummer explicitly declined |
| `package_reference` human-readable id (Naomi Q9) | **Deferred to Phase C.** Use UUID for now. Naomi opens a Phase C ticket. |
| Type generation (`openapi-typescript`) — Miller Q9 | **Miller** | Part of contract test infrastructure |
| Radix Dialog adoption (Miller Q10) | **Bobbie** in A2 | Modal primitive is new; library beats hand-rolled |
| "Return to reviewer" action (Alex Q10) | **Drummer backend + Bobbie frontend** via existing `/transition` endpoint | `routed_for_approval → under_review` is in §2.2 matrix already |
| Login a11y fixes (contrast, label align, focus ring) | **Bobbie (A1)** + **Miller (automated axe-core scan)** | Automate; don't trust eyeball |

### 3.3 Redundancies collapsed

- Drummer and Naomi both wrote migration lists. **Naomi owns the Alembic chain.** Drummer reviews.
- Bobbie and Alex both proposed `TopNav` badge. **Alex owns (A2).** Self-contained, high-visibility.
- Multiple reviewers mentioned `ConfidenceBadge missing band`. **In scope for Phase B (Bobbie, A2 extended).** Not deferred.

---

## 4. Consolidated questions (14 unique, deduplicated)

Grouped by who can answer.

### 4.1 Product decisions for Sawan (6 — block B1 start)

| # | Question | Source |
|---|---|---|
| **S1** | **Claim model:** Does v0.2 have a reviewer claim/release model? If yes, spec §6.5 and §2 need updating and Drummer ships a `claim/release` pair. If no, "Release claim" button is cut from Figma and `under_review → intake_complete` is approver-only (not reviewer self-release). | Holden Q2, Drummer Q4, Naomi Q1 |
| **S2** | **Role naming in DB:** Rename `admin` → `operator` in the user_role enum, or keep `admin` and map at display layer permanently? | Drummer Q1 |
| **S3** | **Per-field extraction scope:** Does the classifier extract fields for all document types, or only `capital_call_notice`? (Cost: ~$0.002/doc extra.) | Drummer Q7 |
| **S4** | **Return-for-revision note:** When approver sends `routed_for_approval → under_review` with a note, is that note a `ReviewNote` (author=approver) or a new type? | Drummer Q5 |
| **S5** | **Audit ledger visibility per role:** Approver + admin only, all roles, or scoped by `uploaded_by`? | Miller Q6, Drummer Q8 |
| **S6** | **Responsive minimum viewport:** Figma is desktop 1440px only. What's the min supported width? (Current `hidden sm:flex` leaves mobile with no nav.) | Alex Q6 |

### 4.2 Backend blockers (4 — Drummer decides, Miller gates)

| # | Question | Decision owner |
|---|---|---|
| **B-Q1** | **Direct rejection from `exception_surfaced`:** `/attest` endpoint accepts `exception_surfaced` as valid from-state? | Drummer (ref §2.2) |
| **B-Q2** | **`AuditEvent.before_state/after_state` canonical schema** for v0.2 state transitions. | Drummer — canonical schema per §4.4 of Drummer review |
| **B-Q3** | **Audit filter query param contract:** `/audit?actor=X&action=Y&start=Z&end=W&page=N&page_size=M`. Inclusive both ends on dates. Cap at 90 days per request. | Drummer + Miller contract test |
| **B-Q4** | **`Approval` uniqueness:** Drop `unique=True` on `package_id` and add `is_final` to support `routed_for_approval → under_review` round-trips without losing history. | Naomi Q2 — decision: one-to-many, drop unique |

### 4.3 Frontend blockers (2 — Holden/squad decides)

| # | Question | Decision |
|---|---|---|
| **F-Q1** | **PDF iframe auth strategy:** blob-URL approach (fetch with Authorization header → `URL.createObjectURL`), server proxy route, or short-lived signed URL? | **Decision: blob-URL in A3 for Phase B.** Short-lived signed URL deferred to Phase C if Safari mobile breaks. Alex implements. |
| **F-Q2** | **Modal primitive:** Radix `Dialog` or hand-rolled? | **Decision: Radix.** Focus trap is too flaky hand-rolled. Bobbie adopts in A2. |

### 4.4 Test / QA setup (2 — Miller owns)

| # | Question | Decision |
|---|---|---|
| **T-Q1** | **Type generation from OpenAPI** via `openapi-typescript`? | **Yes.** In scope for B1 TDD. Miller owns the tooling. |
| **T-Q2** | **Contract test coverage:** does `tests/test_api_contract.py` extend to every new endpoint before B2 merges? | **Non-negotiable yes.** Miller's gate. |

---

## 5. Final build plan

Phases: **A = frontend-only**, **B = backend + frontend integration**, **C = polish/ceremony**, **Z = validation**.

| # | Ticket | Owner | Deps | Est (h) | Acceptance criteria | Phase |
|---|---|---|---|---|---|---|
| **A1** | Copy + IA + console sectioning + density + role visibility + login a11y fixes + focus-state tokens | **Bobbie** | Holden Figma redraws land | 6 | 5-section order matches §5.1, Active cap 5-rows + expand toggle, 3 roles show correct sections, login labels left-aligned + AA contrast passes axe-core, focus ring token added to Page 2 design system | A |
| **A2** | Attestation modal refinement + Radix Dialog adoption + zero-flags variant + summary-panel typography fix + `ConfidenceBadge` missing band + flagged-field warning inset (Alex contributes this sub-task) | **Bobbie** (core) + **Alex** (warning panel sub-A2.1) | A1 copy tokens | 5 | Focus trap via Radix verified, initial focus on cancel, Escape + scrim dismiss do not mutate, zero-flags variant renders strip-absent, all 4 confidence bands + missing band render | A |
| **A3** | SourceViewer auth fix (blob-URL), error fallback states, "source unavailable" strip | **Alex** | (none — A3 is independent) | 3 | iframe PDF loads against token-gated backend in Playwright, 401/404/timeout each render the right fallback, POR-146 regression spec green | A |
| **B1** | Backend state machine (pure module), endpoints (`/transition`, `/attest`, `/review-notes`, `/audit`), migration chain, per-field extraction, role guards, optimistic locking (`version` column), extraction history (one-to-many classifications), append-only audit trigger, seed data | **Drummer** (endpoints + classify) + **Naomi** (state_machine.py + reviewer_notes + migration + audit trigger) | Sawan answers S1–S6; Miller contract test red | 20 | All §2.2 transitions green, all 27 invalid transitions return 409 with spec body, concurrency test (two approvers → one 409), migration test v0.1→v0.2 per §2.3, reviewer_notes append-only (no PATCH/DELETE endpoint), audit_events RESTRICT on delete, contract test passes for every new endpoint | B |
| **B2** | Global audit ledger screen + filter bar (actor/action/date-range) + CSV export hookup + per-field confidence wiring on detail page + review notes write path + `AuditEntry` before/after diff expand | **Alex** (ledger + filter) + **Bobbie** (FieldWithConfidence + review notes form + AuditEntry expand) | B1 merged + **Holden audit ledger redraw committed** | 10 | All 8 filter combinations render correct empty/populated states, CSV export row count matches filtered table, per-field confidence renders all 5 bands, review note POST + optimistic update + empty-state copy exact-matches §1.3, axe-core green | B |
| **B3** | CSV streaming export (`GET /audit/export`) + seed script updates + test fixture refactor for new enum | **Naomi** | B1 schema landed | 4 | Streaming response with `Content-Disposition`, filter params honored, LegacyPackageFactory + updated conftest in place, seeds produce packages in all 6 states + approver user | B |
| **C1** | Intake ceremony screen + inline PDF (pdf.js upgrade) + exception detail view + exception resolution flow + reduced-motion paths + attestation ceremony animation hooks | **Bobbie** (UI) + **Drummer** (exception resolution endpoint wiring) | B2 green, Holden intake + exception Figma frames landed | 8 | Ceremony animations respect `prefers-reduced-motion`, pdf.js replaces iframe behind feature flag, exception panel opens from low-confidence field click, `exception_surfaced → intake_complete` transitions via UI, `data-ceremony-step` attributes emitted for Miller assertion | C |
| **Z1** | Full-flow Playwright (login → intake → review → attest → audit) against staging + POR-146 regression suite (5 specs) + brass-discipline DOM scan + contract test + axe-core CI + visual regression baseline + copy audit script | **Miller** | A1, A2, A3, B1, B2 green | 6 | All 13 Miller deliverables committed + green, full flow runs against staging not just local, brass-discipline scan confirms §9.3 exactly (2 elements), Holden sign-off gate | Z |

**Total: ~62h across 6 agents.** Naomi carries heavier weight than initially assumed — her state-machine + migration ownership is load-bearing.

### 5.1 Risk ownership (Naomi's 14 risks — every one has a home)

| Risk | Sev | Owner | Accepted in ticket |
|---|---|---|---|
| R1 No transition guard | High | Naomi | B1 acceptance: 27 invalid transitions return 409 |
| R2 Concurrency race | Critical | Naomi | B1 acceptance: concurrency test (two approvers → one 409) |
| R3 Operator role confusion | Med | Drummer | S2 answer + role-guard on `/transition` |
| R4 `under_review → intake_complete` note-count guard | Med | Naomi | B1 acceptance: with-notes → 409 `cannot release claim after annotation` |
| R5 Reviewer notes mutability | High | Naomi | B1 acceptance: no PATCH/DELETE; `supersedes_note_id` pattern |
| R6 No role guard on note creation | Med | Naomi | B1 acceptance: `role=reviewer` required on POST |
| R7 Re-classification destroys history | High | Drummer | B1 acceptance: `classifications.is_current` flag; old rows retained |
| R8 Backfill confidence lossy | Med | Drummer | B1 migration uses document-level confidence + `backfilled: true` |
| R9 No append-only on audit | High | Naomi | B1 acceptance: PostgreSQL BEFORE UPDATE OR DELETE trigger; SQLite dev guard |
| R10 SET NULL on audit FK | High | Naomi | B1 migration: `ondelete=RESTRICT`; delete endpoint absent |
| R11 Audit partition plan | Med | Naomi | Documented in B1 migration commit; revisit at 1M rows |
| R12 Migration NULL-confidence silent mis-routing | High | Naomi | B1 migration: NULL → `exception_surfaced` explicit rule |
| R13 Two-column state during migration | Low | Naomi | `legacy_status` read-only generated column |
| R14 Test fixtures incompatible | Low | Naomi | B3 fixture refactor |

### 5.2 Miller deliverables (POR-146 does not repeat)

All 13 committed as failing tests **before** their feature implements. Tracked via Miller's list; Z1 gate validates all green. Specifically load-bearing:

- `backend/tests/test_state_machine.py` (parametrized over §2.2 — 9 positive + 27 negative)
- `backend/tests/test_api_contract.py` (extended for every new endpoint)
- `backend/tests/test_migration.py` (per §2.3)
- `frontend/e2e/regression/por-146.spec.ts` (5 specs, one per Bug 1–5)
- `scripts/audit-copy.sh` (banned string grep)

---

## 6. Sequencing (dependency graph)

```
Holden Figma redraws (1 day, in progress)
    ↓
    ├─→ A1 (Bobbie, 6h) ─┐
    ├─→ A2 (Bobbie + Alex, 5h) ─┤
    └─→ A3 (Alex, 3h) ───┴─→ Sawan answers S1–S6
                              ↓
                              B1 (Drummer + Naomi, 20h) — Miller contract test red first
                              ↓
                              B2 (Alex + Bobbie, 10h) — gated on audit-ledger redraw
                              ↓
                              B3 (Naomi, 4h) — parallel with B2
                              ↓
                              C1 (Bobbie + Drummer, 8h) — gated on intake + exception Figma frames
                              ↓
                              Z1 (Miller, 6h)
                              ↓
                              Holden sign-off → merge → staging → GCP Cloud Run
```

---

## 7. Next action

1. **Holden** begins Figma redraws immediately (TopNav neutral, audit ledger full redraw, intake + exception frames, focus tokens, login a11y fixes). Target: commit by EOD tomorrow.
2. **Sawan** answers S1–S6 (product decisions). Unblocks B1.
3. **Miller** writes the contract test skeleton (red) + adds `openapi-typescript` to B1 scope.
4. **Bobbie, Alex** can start A1/A2/A3 as soon as Holden's A1-relevant redraws (TopNav chip, focus tokens, login) land — they do not need B1 answers.
5. **Naomi, Drummer** wait for Sawan's S1–S6 before B1 branches out.

**No build begins on B1 until S1–S6 are answered.** This is a blocker list, not a nice-to-have.

---

*Filed: Holden · 2026-04-15*
