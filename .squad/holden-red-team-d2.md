# Holden Red-Team Review — D2 Phase 2B

**Author:** Holden (Opus, squad lead)
**Date:** 2026-04-15
**Scope:** Pressure-test D2 v0.1 actuals before they leave the squad as evidence.
**Posture:** Adversarial. Assume an investor diligence reader who is sympathetic but skeptical.

---

## 1. Is the hours reduction (72 -> 14) legitimate or misleading?

**Verdict: Misleading if presented headline-only. Legitimate as a directional signal when paired with the scope disclosure.**

The 14 hours is real session-effort across six agents, all session-based estimates (no per-task instrumentation). The 72 hours for D1 is also estimate-based but covered a full mobile fintech app with 20+ screens, async pipelines, and 281 tests. D2 v0.1 covered 1 happy path, 2 roles, sync pipeline, 8 endpoints, 4 pages, 64 tests.

What the 14-hour number actually means:
- It is **not** evidence that the same scope can be delivered ~5x faster than D1.
- It **is** evidence that an aggressively scoped vertical slice on a reused stack lands in a session.
- The honest like-for-like extrapolation (Section 5 of the evidence pack) is ~25-30 hours for full D2 scope. That is the number an investor should anchor on, not 14.

The scorecard discloses this in Section 4.3 and Section 7.2. The evidence pack discloses it in Section 4. The risk is that the 14 number gets repeated without the disclosure travelling with it. **Recommendation: never quote 14 hours without the v0.1-scope qualifier in the same sentence.**

---

## 2. Is 54.8% reuse meaningful? Is excluding 4 patterns gaming the metric?

**Verdict: 54.8% is defensible but soft. The exclusion is structurally honest, but two of the four exclusions deserve harder scrutiny.**

The four "not applied" patterns:

| Pattern | Reason | Honest? |
|---------|--------|---------|
| P08 UAT report | No external operator existed in v0.1 | Yes — structurally inapplicable |
| P09 Figma audit | No Figma file produced for D2 | Borderline — we *chose* not to make one |
| P17 Private Intake ceremony | Out of v0.1 scope | Yes — explicit deferral |
| P18 Atelier Threshold | Out of v0.1 scope | Yes — explicit deferral |

P09 is the weakest exclusion. Producing a Figma file was a choice the squad made not to do, not a structural impossibility. Calling it "not applicable" rather than "skipped" is a small but real bias toward the metric.

**Stress-test calculation if all four are scored 0.0 / "failed to reuse" instead of excluded:** No change. The model already treats "Not Applied" as 0.0 earned points against the full 31.0 denominator. The 54.8% already reflects the unfavorable accounting. This is good — it means the headline reuse number is not gamed at the denominator.

What is soft: the model treats "adapted" as 0.5 weight. Several "adapted" patterns (P12 Cloud Run, P13 FastAPI scaffold) involved meaningful net-new work (JWT auth middleware, 8 new REST endpoints). An auditor could reasonably argue some "adapted" should be "net-new with scaffold reuse" scored lower. If half the adapted patterns dropped a tier, reuse would land closer to 45%.

**Recommendation: publish the 54.8% as the headline, but include a sensitivity table showing reuse under stricter adaptation accounting (~45%) and looser (~63% if Figma+UAT were attempted). Show the range, not just the point.**

---

## 3. What did Phase 2B prove that Phase 2A did not?

Phase 2A produced: a feasibility score (69.0 Amber), a reuse projection (66.1%), a blueprint, a margin model, and an instrumentation plan. All paper.

Phase 2B added five concrete things that did not exist before:

1. **A running deployment.** Two Cloud Run services responding to HTTPS, JWT auth working for both roles, /health returning 200. Before this, the D2 commissioning pipeline had never produced a live system.
2. **Measured reuse vs projected reuse.** 54.8% measured against 66.1% projected. The reuse model now has a calibration data point, not just a forecast. The 11.3pp gap is decomposed and explained.
3. **A real velocity datum.** ~14 hours actual against 41 projected. Independent of scope concerns, this gives the velocity model something to fit against on the next deployment.
4. **5 new patterns added to the library.** JWT RBAC middleware, approval state machine, immutable audit trail, Haiku classification pipeline, Next.js 4-page scaffold. These are codified, not theoretical.
5. **Demonstration that the squad model works in a new domain.** Same six-agent squad, different domain (PE vs consumer fintech), same delivery shape. Phase 2A could not show this.

What Phase 2B did **not** newly prove (but was sometimes implied):
- That the commissioning model produces *commercially viable* deployments — no revenue, no external operator.
- That the reuse projection model is accurate at full scope — only the v0.1 subset was tested.
- That handoff actually works — handoff was 6/15 delivered, and there is no operator to receive it.

---

## 4. Top 3 investor-diligence risks in this evidence pack

**Risk 1 — Scope-cut compression masquerading as efficiency.**
The headline numbers (14 hrs, $2,100, <1 day) are dramatic. A diligence reader who skims will read this as a 5x productivity claim. The disclosures are present but secondary. If a competing narrative emerges that says "Arukai claims session-speed delivery," it will be hard to walk back even though the squad's own documents are honest. **Mitigation: lead every external version with the scope disclosure, not bury it in section 4.**

**Risk 2 — Zero external validation.**
Every evidence artifact in this pack was produced by Arukai, for Arukai, in a single day. There is no external operator, no signed contract, no third-party UAT, no CI run on a remote, no merged PR. A sophisticated diligence reader will ask "what is the smallest piece of this that someone outside your team has touched?" The current answer is "nothing." This is the single biggest gap and it is commercial, not technical.

**Risk 3 — Estimate-based hour and cost inputs.**
All hours are session-estimates. There is no per-task time log. Cost is hours x $150 blended rate. If an investor asks "how do you know it was 14 hours and not 22?", the honest answer is "we don't, with precision." This compounds with Risk 1 — the soft input feeds the dramatic headline. **Mitigation: instrument time tracking on D3 (even simple stop/start logs per agent per milestone) so the next data point is auditable, not attested.**

Honorable mentions:
- KI-005 (no 7-year retention enforcement) is a P1 compliance gap that will not survive a real PE client's IT review.
- KI-003 (possibly shared Neon DB) is a real isolation question for a regulated workload.
- 0 merged PRs / 0 CI runs means the formal quality gate that the rest of the methodology relies on has not actually fired.

---

## 5. Scorecard integrity check

Reviewed `.squad/scorecard-deployment-2.md` line by line. Findings:

**No outright overclaims.** The scorecard is unusually self-aware — Section 4.3 explicitly disclaims that the deltas mix reuse and scope effects, Section 7.2 calls the cost reduction "scope-driven, not efficiency-driven," and Section 10.2 enumerates what is not proven.

**Caveats present and adequate:**
- All hours labeled `[ESTIMATE]`.
- "Not investor-grade proof" repeated in three places.
- "Estimated YES" used for Copilot KPI (no PR data).

**Minor inconsistencies / things to tighten:**

1. Section 6.1 says "earned reuse points 17.0" and Section 6.4 says the gap is "-3.0 pts. Accounts for the full 3.5 pt difference (rounding from projection methodology)." That's not rounding — it's a 0.5 pt unaccounted residual. Either name the source (P16 over-performance noted in evidence pack §3.2 = +0.5) or call it methodology drift explicitly. Right now it reads like hand-waving.

2. Section 5.5 (Copilot KPI): "Estimated compliant per agent attestations" should probably be "Not measured — 0 PRs to score against" with a flag rather than an "Estimated YES." This is the one place where the scorecard hedges toward the favorable read.

3. Section 7.1 lists Anthropic Haiku tokens at "~$0.50" but the scorecard does not include the Sonnet/Opus inference cost for the squad agents themselves. If the meta-claim is that AI-assisted squads have a cost story, the model inference cost should be in the table even if it's de minimis. Right now it's invisible.

4. Section 10.4 says "weighted reuse is above threshold and below projection — the gap is structurally justified by v0.1 scope, not by pattern failure." The word "structurally" is doing heavy lifting (see §2 above on P09 Figma being a *choice*). Consider softening to "explained by v0.1 scope decisions."

5. The `[ESTIMATE]` discipline is good but inconsistent — "5 commits" is treated as exact but is also session-derived. Either tag everything attested or instrument it.

**Consistency with margin model (ARU-10):** Holds. The "no commercial margin" call is correct under the model — there is no revenue denominator.

**Consistency with reuse model (ARU-08):** Holds. The 3:2:1 weights and 1.0/0.5/0.0 statuses are applied correctly. The denominator is the right 31.0 for the original 19 patterns.

**Net:** The scorecard is the strongest document in the pack. The risks above are about emphasis and one residual-points reconciliation, not factual error.

---

## 6. Bottom line for the squad

D2 v0.1 is an honest, narrow proof. It moves the project from "paper" to "running." It does not move the project from "running" to "investor-grade." That second move requires an external operator and 90 days, neither of which Opus or Sonnet can fabricate.

The biggest thing this squad can do to protect its own credibility is to **stop quoting the 14-hour number without the scope qualifier** and to **instrument hour tracking on D3** so the next data point can survive a Big-4 audit-style read.

— Holden
