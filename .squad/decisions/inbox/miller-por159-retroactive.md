# Miller — POR-159 retroactive gate audit

**Date:** 2026-04-22
**Scope:** Retroactive verdict on commit `b2c4ea5` (Sprint 19d / POR-159) which merged to `main` via PR #3 without an on-record Miller green sign-off.
**Requested by:** Holden.

---

## Verdict

**CLEARED-WITH-DEBT.**

The third bounce-fix commit folded into the squash addressed the true root cause of my second bounce (a missing frontend mapper, not the seed-data mismatch I originally cited) and hardened both Spec A and Spec B per my recommendations. The specs on `main` today should pass. However, the green-phase run was never executed against my gate and no evidence pack is on record — the merge shipped on a commit-message claim of "198 passed" that only covers backend pytest. The E2E green-phase re-run is a structural gap.

## Summary (3 lines)

1. My final bounce on 2026-04-20 GATE-FAILed `08e0b4f` with Specs A and B red; I attributed Spec B to a staging seed-data defect.
2. A third fix-up ("wire aiSummary in docs/page.tsx toRowPkg + harden specs A/B") landed in the same squash as `b2c4ea5` and fixed the actual FE defect (a missing `aiSummary: pkg.ai_summary` line in `toRowPkg`) plus implemented both my recommended spec hardenings — but was never re-gated by me before PR #3 opened.
3. Current `main` has the fix and the hardened specs, but no recorded green-phase Playwright run exists on file, so I cannot prove the shipped state passed — only that it *should*.

## Timeline

| Date | SHA | Event |
|------|-----|-------|
| 2026-04-20 | `08e0b4f` | Second bounce re-gate. Specs A (row-selection) + B (format regex) RED. I recommended (i) hard-seed staging with ≥1 `N flagged` row, (ii) harden Spec A to prefer a flagged row, (iii) consider Spec B relaxation only as fallback. |
| (same day) | (unpushed) | Third fix-up authored by Holden per PR-3 message: added `aiSummary: pkg.ai_summary` to `frontend/src/app/documents/page.tsx` `toRowPkg`, added `openPackageDetailPreferFlagged` helper in `frontend/e2e/visible-ai.spec.ts`, relaxed Spec B to accept minimal-shape trailing regex. **This fix was never presented to me for re-gate.** |
| 2026-04-21 12:06 | `b2c4ea5` | Squash merge of PR #3 to `main` carrying all three fix-ups. Commit message cites `pytest tests/ -q → 198 passed` but no E2E results. |
| 2026-04-21 13:58 | `a279fdf` | POR-161 Sprint 19e ships (Figma polish). Does NOT touch `visible-ai.spec.ts`. Touches `backend/app/routers/packages.py` only for the `uploaded_by_email` join — unrelated to `_build_ai_summary`. |
| 2026-04-22 | HEAD | No seed-data migration, no fixture change, no further touch to `visible-ai.spec.ts` since `b2c4ea5`. |

## Evidence

- **Third fix-up is in the merge**, verified on `main`:
  - `frontend/src/app/documents/page.tsx` L45 on `b2c4ea5`: `aiSummary: pkg.ai_summary,` — the missing mapper line.
  - `frontend/e2e/visible-ai.spec.ts` L55–72 on `b2c4ea5`: `openPackageDetailPreferFlagged` helper with flagged-row filter `[1-9]\d* flagged`, falls back to first row.
  - `frontend/e2e/visible-ai.spec.ts` L198 on `b2c4ea5`: `minimalFormat = /·\s+\d+%\s+confidence\s+·\s+(?:\d+\s+flagged|0\s+flags)$/` — Spec B relaxed per graceful-degradation contract.
- **My original bounce was partially wrong.** Spec B's staging failures were caused by `PackageRow.tsx:140` falling back to `buildClientSummary(pkg)` because `aiSummary` was undefined — not by three degraded Capital Call rows in staging. Fixing the mapper caused all staging rows to render the backend-formatted `ai_summary` directly, so the relaxed Spec B matches real staging output.
- **No green-phase evidence on record.** `.squad/decisions/inbox/` contains `miller-por159-final.md` (RED-phase + two bounces) but no `miller-por159-green.md`. `git log b2c4ea5..HEAD` confirms nothing since merge touched the spec or the mapper.
- **Stash `stash@{0}`** ("miller-por159-final edit") is my 106-line second-bounce text, unchanged and still unpushed.

## Why this is debt and not "cleared"

1. No Playwright run was witnessed on the squad gate before merge. The structural trigger for this retroactive audit is that a failing-tests-on-record state transitioned to merged-to-main without the gate being re-hit.
2. The staging data assumption in Spec A (`prefer a flagged row`) relies on at least one `N flagged` package existing on staging. There is no seed-data enforcement guaranteeing this — if the flagged package is ever deleted or replaced, Spec A silently falls back to `openFirstPackageDetail` and the ExceptionCallout assertion at A.6 becomes non-deterministic. This is the same class of fragility I cited in my second bounce; the fix mitigated it for current data but didn't eliminate the seed-data coupling.

## Recommended actions

**New Linear tickets (recommend Holden file):**

1. **POR-163 (Drummer):** Seed/fixture guarantee for visible-AI E2E. Add a staging seed migration (or Alembic data migration) that ensures at least one Capital Call package exists with (a) a full extracted-fields set and (b) exactly one field at confidence in `[0.5, 0.80)`. Gate E2E preconditions on this invariant. Addresses Spec A fallback fragility.
2. **POR-164 (Miller):** File a retroactive green-phase evidence pack for POR-159 — run the full visible-ai.spec.ts suite against current staging, record output under `.squad/decisions/inbox/miller-por159-green.md`, and close the gate gap on the record.

**Standing-gate additions:**

3. Miller gate §7 addition: **No squash-merge may include a fix-up that post-dates the most recent recorded Miller verdict.** If a new commit lands after a bounce, the re-gate is mandatory before PR opens. Holden's PR #3 squashed three fixes (one of which I never saw) into a single merge — this should not have been possible without a fresh gate.
4. Miller gate §3 reinforcement: E2E green-phase evidence (Playwright output paste or test-results archive reference) is required in the PR body, not merely a pytest citation. "198 passed" in a commit message is backend-only and does not discharge the E2E obligation.

## Signed

Miller — standing gate auditor, 2026-04-22
