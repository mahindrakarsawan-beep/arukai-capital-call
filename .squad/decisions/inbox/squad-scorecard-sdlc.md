# Scorecard Integration in SDLC

**Decision:** Bake `scripts/model_scorecard.py` into the squad workflow so model selection is evidence-based, not vibes-based.

**Date:** 2026-04-15
**Author:** Holden (Lead/Architect)

---

## Squad Roundtable

**Holden (Lead/Architect):**
I trigger the scorecard at two points: (1) during blueprint creation for any ticket that adds or changes an AI provider call, and (2) quarterly as a standing re-evaluation. The scorecard output is required evidence in the blueprint before Drummer or Bobbie starts coding. No model choice lands in a PR without a scorecard reference — it gates the blueprint approval, not the PR itself.

**Drummer (Backend):**
Before I write any code that calls an LLM, I check whether a current scorecard run covers my use case category. If not, I run `model_scorecard.py --tier <relevant>` and attach the results to my Linear ticket. The scorecard doesn't block my PR directly — it blocks the blueprint I'm working from. If I want to swap a provider mid-implementation, I re-run the relevant category and update the ticket before opening the PR.

**Bobbie (Frontend):**
The scorecard rarely affects me directly. When Drummer changes a provider and the response schema shifts, he flags it in the ticket and I update any TypeScript types or display logic. I don't run the scorecard myself. My only action item: if the scorecard recommends a faster model and latency drops, I may need to adjust loading state timing or skeleton durations.

**Miller (Test/Reliability):**
I validate that scorecard evidence exists before signing off on any AI-provider ticket. My gate checklist adds one item: "Scorecard reference attached to blueprint or ticket — model choice justified by data." I don't re-run the full scorecard, but I spot-check the chosen model against the relevant category by running that single category if the results are older than 30 days.

**Naomi (Backend Backup):**
The scorecard affects cost projections directly — the `total_cost` column feeds into our burn-rate estimates. When I review migrations or data integrity work, I check whether a model swap changes token volumes or cost structure. I review scorecard results when Drummer flags a provider change, and I update cost projections in the Linear ticket accordingly.

**Alex (Frontend Backup):**
I can use the scorecard's "Code Validation" and "Test Writing" categories to pick the best model for the QA verifier and E2E test generation. When setting up automated verification, I reference the scorecard's cost-efficiency ranking for the `fast` tier — the verifier runs often, so cost matters more than peak quality. I check scorecard results before changing the verifier's model config.

---

## Concrete Proposal

### 1. When the scorecard runs

| Trigger | Scope |
|---------|-------|
| New blueprint that involves an AI provider call | Full run (all tiers) |
| Provider swap mid-sprint | Single category relevant to the change |
| New model release from any provider | Full run, filed as a proactive ticket |
| Quarterly cadence (Jan/Apr/Jul/Oct) | Full run, results compared to previous quarter |

### 2. Who runs it

- **Drummer** runs it for backend AI calls (extraction, logic, code gen).
- **Alex** runs it for QA verifier model selection.
- **Holden** triggers the quarterly cadence and assigns the run.
- Anyone can run it; ownership follows whoever is making the model choice.

### 3. What it gates

- **Blueprint approval** — Holden will not approve a blueprint that selects a model without scorecard evidence for the relevant category.
- **Provider swap PRs** — Miller's gate checklist requires scorecard reference.
- **Cost projection updates** — Naomi won't sign off on cost changes without scorecard data backing the new model's efficiency.

The scorecard does NOT gate every PR. It gates the decision to use a model, which happens at blueprint time.

### 4. Where results live

- **JSON output** committed to `reports/scorecard/YYYY-MM-DD.json` in the repo (machine-readable, diffable).
- **Summary** pasted into the relevant Linear ticket or blueprint document as a comment.
- **Quarterly runs** get their own Linear document titled "Scorecard Q[N] YYYY" in the Arukai project.

### 5. How it updates

- When a new model drops: Holden creates a ticket, assignee runs the scorecard within 5 business days, results posted.
- Quarterly: standing calendar reminder, Holden assigns, full run compared to previous.
- Script maintenance: Drummer owns `model_scorecard.py`. New categories or pricing updates go through normal TDD workflow.

### 6. Integration points

| Point | How |
|-------|-----|
| Blueprint template | Add "Model Scorecard Reference" field — link to JSON or ticket |
| Miller's gate checklist | Add item: "Scorecard evidence present for AI model choices" |
| CI (future) | Optional: run scorecard in CI on changes to `MODELS` dict or provider config, post results as PR comment |
| Intake schema | Add `model_justification` field to any ticket template that touches AI providers |
| `reports/scorecard/` | New directory in repo for committed JSON results |

---

**TL;DR:** The scorecard gates the *decision*, not every commit. Run it when you choose a model, attach evidence to the blueprint, Miller checks it exists, Holden won't approve without it. Quarterly re-runs keep us honest as pricing and quality shift.
