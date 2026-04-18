# Holden Decision: Visible AI Redesign for D2

**Date:** 2026-04-15
**Author:** Holden (requirements + architecture)
**Status:** APPROVED — ready for squad execution
**Linear parent:** POR-147
**Figma file:** a6mMsiXmnSdQTQ4qQYS6X2 (Page 4 — Visible AI Redesign)

---

## Problem Statement

Two critical deficiencies identified by client + independent QA (Mistral + OpenAI):

### Problem 1: UI doesn't match Figma
- Console rows lack classification data visually despite it being in the API
- Package detail is missing 3 of 4 blocks (only Source Document block renders meaningfully)
- Existing Figma designs (Page 3, nodes 15:21 through 37:25) specify a 4-block detail layout, 5-section console, attestation modal — the live app renders a skeleton of this

### Problem 2: No visible AI in the flow
- Classification happens silently in the background via Claude Haiku pipeline
- The backend already extracts 8 per-field values with source_text, confidence, and model attribution
- NONE of this data is surfaced to the user
- The system feels like a form processor, not an AI-assisted workflow
- Client quote: "I am not seeing any LLM or AI usage in the flow which is one of the core promises of Arukai"

## Root Cause Analysis

The backend (classify.py) does rich work:
- `classify_document_text()` calls Claude Haiku with tool_use
- Returns: document_type, confidence, key_indicators[], extracted_fields{} (8 fields with value/confidence/source_text), model_version, duration_ms
- All stored in Classification model with extracted_fields JSONB column

The frontend ignores most of it:
- `Classification` type in api.ts has key_indicators and model_version but NOT extracted_fields
- PackageRow shows doc_type badge + confidence number but no AI summary
- IntakeCeremony shows cosmetic step labels ("Package received") not real AI output
- No AI reasoning or explanation surface exists anywhere in the UI

**The data is there. The surface is not.**

## Figma Updates Created

Three new screens on Page 4 — "Visible AI Redesign (D2)":

### Screen 1: Package Detail with AI Analysis block (node 61:2)
- New Block 3 "AI ANALYSIS" between Extracted Facts and Review/Audit
- Classification reasoning paragraph composed from key_indicators
- Field-level extraction table: field name, value, source_text, confidence%
- Exception callout (amber) for fields with confidence < 0.80
- Model attribution: "Analysis by Claude Haiku · 1.3s · April 15, 2026"
- Brass accent border (#B8914E at 35% opacity)

### Screen 2: Operations Console with AI summaries (node 57:2)
- Each row shows 1-line AI summary below the title
- Format: "Capital Call · $2.5M due May 15 · 8 fields extracted · 99% confidence · 0 flags"
- Replaces bare "Intake complete · awaiting reviewer" status text

### Screen 3: Intake Ceremony with AI narration (node 58:2)
- Horizontal 4-card layout (was vertical step list)
- Each card shows real AI output data from the classification pipeline
- 01 Receive: file metadata (size, type, timestamp)
- 02 Classify: classification result + confidence
- 03 Extract: field count + flag count + specific flag details
- 04 Ready: handoff status

## QA Review (Holden self-review of Figma screens)

### Detail page (61:2) — PASS
- AI Analysis block clearly visible with brass accent
- Classification reasoning is natural language, not raw JSON
- Per-field extraction shows source_text provenance
- Exception callout highlights low-confidence fields specifically
- Model attribution provides transparency

### Console (57:2) — PASS
- AI summary line transforms each row from "status display" to "intelligence display"
- User can see doc type, amount, due date, confidence at a glance without clicking in
- Exception row clearly communicates WHY it's an exception (not just "exception surfaced")

### Intake ceremony (58:2) — PASS
- Step cards narrate what the AI actually does, not cosmetic labels
- User watches real classification happen, sees confidence emerge, sees field counts populate
- This is the "AI is working for you" moment the client expects

## Squad Task Distribution

### POR-151 — Drummer (Backend): Expose extracted_fields + ai_summary [5h] — URGENT, START FIRST
- Serialize extracted_fields in GET /documents/{id} response
- Add duration_ms to classification object
- Compute ai_summary string on GET /packages list endpoint
- New GET /packages/{id}/intake-status for ceremony data
- **Blocks:** POR-148, POR-149, POR-150

### POR-152 — Miller (Testing): E2E tests for AI surfaces [4h] — START PARALLEL WITH DRUMMER
- Write failing tests for AI Analysis block, console summary, ceremony data
- Tests committed BEFORE implementation (TDD gate)
- Screenshot capture for QA comparison

### POR-148 — Bobbie (Frontend): AI Analysis block [6h] — AFTER POR-151
- New component: AIAnalysisBlock.tsx
- Renders classification reasoning, field extraction table, exception callouts
- Brass accent border, model attribution
- Integrate into /documents/[id]/page.tsx as Block 3

### POR-149 — Bobbie (Frontend): Console AI summary [4h] — AFTER POR-151
- Extend PackageRowPkg type with aiSummary field
- Add second line to PackageRow component
- Wire to all 5 console sections

### POR-150 — Bobbie (Frontend): Intake ceremony redesign [8h] — AFTER POR-151
- Horizontal 4-card layout replacing vertical step list
- Poll/stream intake progress from backend
- Populate cards with real AI output as steps complete

## Execution Order

```
Phase 1 (parallel):
  Drummer: POR-151 (backend API) ─────────┐
  Miller:  POR-152 (failing tests) ───────┤
                                           │
Phase 2 (sequential, after Phase 1):       │
  Bobbie:  POR-148 (AI Analysis block) ◄───┘
  Bobbie:  POR-149 (Console AI summary) ◄──┘
  Bobbie:  POR-150 (Intake ceremony) ◄────┘

Phase 3:
  Miller:  Run all tests, capture screenshots
  Holden:  QA review of screenshots vs Figma
```

## Total Estimated Effort

| Ticket | Owner | Hours |
|--------|-------|-------|
| POR-151 | Drummer | 5 |
| POR-152 | Miller | 4 |
| POR-148 | Bobbie | 6 |
| POR-149 | Bobbie | 4 |
| POR-150 | Bobbie | 8 |
| **Total** | | **27 hours** |

## Key Technical Notes

1. **No new AI calls needed.** The classification pipeline already produces all the data. This is a surface-only fix with one API serialization change.

2. **Frontend Classification type must be extended.** Add to api.ts:
   ```typescript
   export interface Classification {
     doc_type: DocType;
     confidence: number;
     key_indicators: string[];
     extracted_fields?: Record<string, {
       value: string | boolean | null;
       confidence: number;
       source_text: string | null;
     }>;
     model_version?: string;
     duration_ms?: number;
     classification_error?: string | null;
   }
   ```

3. **PackageListOut must add ai_summary.** Add to api.ts:
   ```typescript
   export interface PackageListOut {
     // ... existing fields ...
     ai_summary: string | null;
   }
   ```

4. **IntakeCeremony steps must be data-driven.** Replace the hardcoded STEPS array with props that accept real classification pipeline output.

## Decision

This is the make-or-break moment for D2. The system works technically — classify.py produces rich, auditable AI output with per-field confidence and source text provenance. But the user sees none of it. The fix is to surface what already exists, not to build new AI features.

**Approved for immediate execution. Drummer starts POR-151 now. Miller writes failing tests in parallel. Bobbie builds surfaces once the API is ready.**
