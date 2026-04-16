# Sawan's Answers — Figma Squad Questions (POR-147)

**Date:** 2026-04-16

## S1 — Claim model

**Answer:** Keep the "Release claim" button. Claim model stays.

**Implication:** Reviewer claims a package before editing. Prevents double-edit race (addresses Naomi R2). Requires:
- `claimed_by_user_id` + `claimed_at` on Package
- `POST /packages/{id}/claim` and `/release`
- UI: reviewers see "Claim to review" CTA on unclaimed packages; "Release claim" on claimed ones they own

## S2 — DB role naming

**Answer:** Squad decides.

**Decision locked:** Add dedicated `approver` role (third enum value: `admin`, `reviewer`, `approver`). Clean separation — admin operates platform, approver attests decisions, reviewer annotates. Deprecate the current `admin can approve` path via migration.

## S3 — Per-field extraction scope

**Answer:** Depends on the document type.

**Implication:** Tool_use schema is per-doc-type, not generic. For v0.2 we only need **capital_call_notice** fields (well-defined). Deferred doc types (subscription, side_letter) get their own schemas when we tackle them in v0.3.

**v0.2 capital_call_notice fields:** `fund_name`, `call_number`, `amount_due`, `currency`, `due_date`, `recipient_entity`, `wire_instructions_present` (bool), `notice_date`. Each with confidence and source_text.

## S4 — Return-for-revision / rejection

**Answer:** Rejection is a new type.

**Implication:**
- `ApprovalDecision` table: `action` enum = `approved` | `rejected`, with `reason` field
- Separate from `ReviewerNote` (reviewer commentary) and `AttestationNote` (approver attestation text)
- Three distinct note types, never conflated

## S5 — Audit ledger role visibility

**Answer:** Admin + approvers only.

**Implication:**
- Reviewers CANNOT see the global audit ledger at `/audit`
- Per-package audit trail remains visible on the Package Detail page for reviewers (they see their own actions in context)
- Role gate on `GET /audit` endpoint + FE route

## S6 — Minimum viewport

**Answer:** Desktop, tablet, AND mobile.

**Implication — THIS IS A SCOPE EXPANSION:**
- All 7 screens + 2 modals now need responsive layouts at 3 breakpoints
- Mobile (375px): stacked single column, sticky nav, drawer patterns for audit trail
- Tablet (768-1023px): 2-column where possible, slightly collapsed side rails
- Desktop (1280px+): the current Figma designs

**Ownership impact:**
- Bobbie + Alex both need to build mobile variants — ~12 extra hours total
- Holden needs to redraw 7 screens × 2 more breakpoints = 14 additional frames in Figma before build

## Decisions made without blocking Sawan

- **PDF auth:** blob-URL with token (Bobbie/Alex A3)
- **Modal library:** Radix UI Dialog (addresses Miller's focus-trap concern)
- **openapi-typescript codegen:** adopted (Miller's contract test prevention)
