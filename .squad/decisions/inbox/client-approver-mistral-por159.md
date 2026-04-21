# Client Approver Review — Mistral Large (Reviewer A) — POR-159 re-review

**Date:** 2026-04-21 (post Sprint 19d merge b2c4ea5)
**Previous review:** client-approver-mistral-por156.md (this morning, NO)

---

NO

**Showstoppers:**
- AI providers still see plaintext without DPAs. The visible-AI work doesn’t change the fact that Mistral/OpenAI ingest unredacted financial documents. This remains a hard blocker.
- Arukai-owned infrastructure. No change; still a single point of failure for data sovereignty.

**Serious concerns (post-Sprint 19d):**
- The visible-AI surfaces are now present, but the **model attribution footer** is too quiet. Family-office reviewers won’t notice it; move it to the top of the "AI Analysis" block.
- **Flagged-field threshold** at 0.80 is better, but the amber callout lacks actionable next steps. Add a one-click "Request human review" button that logs the request in the audit trail.
- **E2E specs** are good hygiene, but they don’t prove the AI reasoning is sound. Add a "Show raw model output" toggle on the detail page so reviewers can inspect the JSON if they doubt the plain-English summary.

**Day-2 trap:**
Upload a capital-call PDF where the due date is written as "15th May 2026" (ordinal) instead of "May 15, 2026". Check if the AI extracts "15th" as "15" or fails to parse it. If the system silently drops the ordinal suffix and logs 99% confidence, I walk. The audit trail must show the exact source text that triggered the extraction.
