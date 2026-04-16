# Holden — Figma review, Page 3 (7 screens)

**File:** `a6mMsiXmnSdQTQ4qQYS6X2` · Page 3 "Screens @ 1440px" · node `9:3`
**Date:** 2026-04-15
**Reviewer lens:** IA, Arukai brand fit, cohesion, user flow, accessibility, §1–§9 conformance.
**Posture:** self-critical. I drew these. I want them shredded before Bobbie touches a line of JSX.

---

## 0. What I looked at

| # | Node   | Screen                                        | Verdict          |
|---|--------|-----------------------------------------------|------------------|
| 1 | 15:2   | Login                                         | Close. One a11y gap. |
| 2 | 15:21  | Operations console                            | Good bones, two real IA concerns. |
| 3 | 16:2   | Package detail — awaiting reviewer            | Off-spec button. Audit clipping. |
| 4 | 16:139 | Package detail — routed for approval          | Off-spec button. Amber/brass collision risk. |
| 5 | 16:292 | Package detail — decision recorded            | Terminal banner is italic Cormorant — unclear if I meant that. |
| 6 | 17:2   | Attestation modal                             | Ceremonial, but one missing element. |
| 7 | 17:34  | Global audit ledger                           | Reads admin, not first-class. |

---

## 1. Top-line verdict

The atelier posture lands on 5 of 7 screens. The two that slip toward ops-SaaS are the **Operations console** (section 2) — it is a list of lists, not a workflow — and the **Global audit ledger** (section 7) — its emptiness and tabular rigidity read like a reporting admin page. Both are salvageable, but not without opinionated reframes.

**Brass discipline:** violated. I counted 4 brass sites in the design, not 3. See Q1.

**Typography discipline:** intact. Cormorant on displays and attestation italic only, DM Sans on chrome and data, DM Mono on IDs. No Cormorant on buttons or pills — clean.

**Accessibility:** no focus states drawn. No skip link. Credentialed-email field and passphrase field are centered-label — visually pretty, functionally harder to scan vertically. See Q6.

---

## 2. The 9 questions the squad must answer before Bobbie writes a line

### Q1 — The fourth brass site. (Screens 2, 3, 4, 7)

The TopNav carries a **"● 1 PENDING ATTESTATION"** chip on every console/detail/ledger screen. It is painted brass (`brandBrass` surface, brass dot). That is a 4th brass site. Spec §9.3 says exactly three: *Attest approval* button, *routed_for_approval* pill, *Pending approval* section count badge. The global nav chip is not on that list.

**My self-critique:** I added this during the second pass because I wanted approvers to feel a pull toward their queue from any surface. That intent is correct. But I either (a) need to add it to §9.3 as the 4th site and defend why, or (b) re-skin it in slate/fg-obsidian and let the brass pull come only from the console. Right now it is an unsanctioned bleed of brass into chrome, and Miller will reject it as written.

**Proposal:** re-skin the TopNav chip to neutral (fg-obsidian background at 8%, fg-muted text, **no** brass dot). Let it carry shape and count but no color signal. Brass stays holy at the pill, the count, and the button.

### Q2 — "Release claim" button on screen 3. (Screen 3, action bar)

Screen 3 (package detail · awaiting reviewer) shows a **`Release claim`** button next to `Route for approval`. That copy is nowhere in §6.5. Spec §6.5 reviewer row reads: `[Record review note]` + `[Route for approval]`. So either I imported a claim-model (operator claims package → releases back to pool) from a deleted draft, or this is genuinely needed and the spec is incomplete.

**Decision needed:** do we have a claim/assignment model in v0.2? If yes, §2 and §6.5 both need updating and Drummer gets a new ticket. If no, strip the button and the design becomes spec-compliant.

### Q3 — Amber and brass sitting next to each other on the approver action bar. (Screen 4, bottom)

On screen 4, `Record rejection` (dataNegative red) and `Attest approval` (brandBrass) sit 16px apart. That is correct — but a few pixels up, the DUE DATE field carries a `NEEDS REVIEW` amber pill, and SIDE-LETTER REF. carries a `LOW CONFIDENCE — FLAG` amber pill. Amber (`#9A7639`) and brass (`#B8914E`) are 9 hue-degrees apart. On the same viewport, at a glance, they read as the same color family.

**My self-critique:** §9.3 explicitly warns this. I wrote the warning and still put them on the same page together without testing the adjacency. I should have rendered a side-by-side contrast test.

**Proposal:** Miller adds a "brass/amber adjacency" visual diff test to the Playwright E2E. Any page that paints both within 200px of each other fails. Separately: we consider darkening amber's text color from `#8B6B3A` to `#7A5A2E` to push it further from brass.

### Q4 — Audit trail column clipping. (Screens 3, 4, 5)

On every package detail screen, the Audit trail "ACTION" column is clipping text: "lete" instead of "intake complete", "for appro" instead of "routed for approval". This is a layout bug in the Figma, not a spec question — but it signals a deeper design choice.

**Real question:** the 2×2 grid (Source | Extracted facts / Review notes | Audit trail) forces audit into a narrow half-column. At ≥lg, the audit column is ~400px. That is structurally too narrow for `{actor} · {action} · {before → after state}`. Either we widen it (break the 2×2 to a 2×3), we move audit to a full-width bottom strip, or we render a compact event log here and push the full log to the ledger.

**My lean:** full-width audit strip below the 2×2. It emphasizes "first-class" (answering criterion 6). Narrow half-column is the visual root cause of the audit feeling like a hidden admin widget.

### Q5 — Operations console rhythm: 1 row per section. (Screen 2)

The console shows 5 sections each with 1 row, even though the section headers claim counts of 2 / 1 / 4 / 12 / 3. This is a teaser layout; in reality Active packages will render up to 12 rows and the rhythm will change. The design does not show that density.

**Concern:** the user's actual first impression at typical load is five sections, with "Active packages · 12" dominating vertical space and pushing "Recent decisions" below the fold. "Recent decisions" is criterion #6 ("first-class audit ledger") support; if it is always below the fold, it is de-facto hidden.

**Question for the squad:** do we cap Active packages at N rows with an "expand" toggle so Recent decisions stays visible, or do we let the page scroll freely? My answer: cap Active at 5 rows on first paint, with an inline `Show all 12 →` expander. This preserves the full-page rhythm. Bobbie should build this even in Phase A with a hard-coded cap.

### Q6 — Exceptions and Pending approval ordering. (Screen 2)

§5.1 says Exceptions first, Pending approval second. The design obeys this. I am going to defend it in review anyway because I can hear someone saying "approvers come to the console specifically to attest, surface Pending approval first for them."

**My answer:** Pending approval is role-conditional. Approvers see a brass count badge that is visually louder than Exceptions' neutral count. They will already scan there. Exceptions is first because an exception blocks every role — approvers included — and a blocked package cannot be attested. The ordering is correct. But the squad should hear the argument and sign off rather than trusting my fiat. Call this an open question: *do we confirm §5.1's ordering against role-weighted tasks, or should approvers get a re-sorted view where Pending approval floats first?*

### Q7 — Attestation modal is missing the "N fields flagged" count when zero. (Screen 6)

Screen 6 shows the warning strip: "● 1 field was flagged during review. Proceed only if resolved." Good — that is spec §7.1.3. But §7.1.3 also says the strip appears *only when N > 0*. The design does not show the zero-flags variant. I need a second frame in Figma for that case, otherwise Bobbie will guess.

**Also missing from the modal:** the *Classification + intake confidence* line is rendered as body-small and the *amount / due date / fund* line sits below it. In the screenshot the confidence line is partly occluded behind the amount row. Spec §7.1.3 lists them as sibling fields, not stacked subtly. Needs a second look at the modal's summary-panel typography — the Cormorant package title dominates so hard that the supporting data reads as filler. I want to either bump the Cormorant down one step (28pt → 24pt) or promote the amount/due/fund line to a single Cormorant value row.

### Q8 — Audit ledger on screen 7 has 1 row. (Screen 7)

This is the worst screen in the set. As drawn, it is a filter bar over a near-empty table with an Export CSV button. That is the exact ops-SaaS aesthetic I want to avoid. It meets the mechanical spec (filters, rows, export) but fails the "first-class governance artifact" brief entirely.

**Self-critique:** I designed this lazily. A ledger that reads as "governance in the open" should have:

- A hero band (Cormorant) with a sentence: "Every action taken on every package, recorded the moment it happens." Positioned where the page title sits now, but treated as a promise, not a label.
- A **density** cue: at least 15 rows of real data in the mock, so the page reads full. An empty table IS a dashboard; a populated ledger IS governance. I drew the dashboard version.
- A per-package **narrative column** that threads the ledger entry back to the package title in Cormorant, not just the package name in DM Sans. Give the ledger typographic kinship with package detail.
- A quiet badge on each row indicating `system` vs `user` actor, because compliance reviewers will ask.

**Recommendation:** re-draw this screen before build. Ask Bobbie to wait until the redraw lands before she starts. I will own the redraw. This is the one screen I'd defer from Phase A entirely and push to B2 so it has time.

### Q9 — Login accessibility + session-recording disclosure. (Screen 1)

Two a11y problems visible:

1. **Centered field labels.** "CREDENTIALED EMAIL" and "PASSPHRASE" are centered above their inputs. Screen-reader traversal order is fine, but for sighted keyboard users scanning top-to-bottom, centered labels break the left-rag reading column. More importantly, WCAG doesn't mandate left-alignment, but our internal rule (for reviewers with dyslexia on our client list — which we have, and which I chose to ignore when drawing this) is left-aligned form labels.
2. **"Session activity is recorded against your credentialed identity."** This is the only sentence on the entire login page outside the card. It sits at ~14pt DM Sans on bgObsidian in fg-muted (~40% lightness). Measured: contrast ratio is roughly 3.8:1 against obsidian. WCAG AA for small body text is 4.5:1. **This fails.** The line is not decorative — it is a disclosure of session recording, which is a legal/governance statement. It must pass AA.

**Proposal:** bump the recording line to fg-inverse at 70% (not 55%), left-align both field labels, and add a visible focus ring token (2px brass? No — brass discipline. Use fg-obsidian ring at 2px with 4px offset against the card). No focus state is drawn anywhere in the 7 screens; this is my largest single gap across the whole review.

---

## 3. What I'd cut or defer

| Item | Action | Why |
|---|---|---|
| "Release claim" button on screen 3 | **Cut** unless we commit to a claim model | Not in §6.5; if we need it, it's a whole new ticket, not a button |
| "1 PENDING ATTESTATION" brass chip in TopNav | **Re-skin** to neutral | Fourth brass site = §9.3 violation |
| Global audit ledger as drawn | **Defer** to Phase B2 and redraw | Fails criterion 6 on current render |
| Terminal-state italic banner on screen 5 | **Keep but test** | Italic Cormorant on a terminal state reads as ceremonial; could also read as "unfinished." 50/50. |
| Intake screen entirely | **Add** | Page 3 has 7 screens and none is the intake ceremony from §8. Phase C is a lot of the UX weight and we have zero mock for it |
| Exception detail screen | **Add** (at least a stub) | Currently no way to see what an exception looks like when opened |
| Audit trail half-column on detail | **Redraw** as full-width strip | Width is structurally too narrow; root cause of criterion-6 miss on detail pages |
| Console density (1 row per section) | **Redraw** with 3–5 rows per active section | Current mock misrepresents real-load rhythm |

---

## 4. Ownership proposal

Not defaulting to any one dev. Assigning on fit:

| Piece | Owner | Rationale |
|---|---|---|
| **A1 (copy + IA + console)** + the density redraw + capped Active rows | **Bobbie** | Her strength is IA. Console rhythm is IA work. She has built the console once already; she is fastest here. |
| **A2 (attestation modal)** — including zero-flags variant and summary-panel typography fix | **Naomi** | Naomi is quieter on the standup but her modal work on ARU-12 was the cleanest ceremonial-component work we've shipped. Attestation is the moment; give it to someone who will slow down on it. Not Bobbie, who will ship it in 40 minutes because she is fast. Fast is wrong here. |
| **B1 (backend state machine + audit events + review notes)** | **Drummer** | Backend owner, no question. Audit event contract is his. |
| **B2 front-end (per-field confidence + audit ledger redraw)** | **Alex** | Alex is hungry and this screen needs someone who will treat it as a hero surface, not a CRUD page. He also has the most patience for the density-vs-emptiness tradeoff. |
| **C1 (intake ceremony + inline PDF + exception resolution)** | **Bobbie + Drummer** | Already split in §10; no change. |
| **Miller gates for every ticket** | **Miller** | As specced. Additionally: add brass/amber adjacency visual-diff test, add focus-state coverage test, add audit ledger density assertion (at least 10 rows visible at default filter). |
| **Audit-ledger redraw in Figma (before B2 build)** | **Holden** | I drew it lazily; I fix it. Blocks B2 start. I commit to the redraw landing before B1 merges so B2 is not blocked. |
| **Focus-state token + ring spec in design system (Page 2)** | **Bobbie** (with Holden sign-off) | Page 2 today has no focus token. Needs adding as part of A1 scope. |
| **Accessibility contrast audit of login** | **Miller** | Automate it; do not trust my eyeball. |

---

## 5. Criterion-by-criterion scorecard

Criteria from the brief:

1. **Does it feel like a private workflow atelier vs admin dashboard?** — 5/7 yes. Console and ledger slip toward admin. See Q5, Q8.
2. **IA on the console puts exceptions/pending-approval high enough?** — Yes, ordering correct. Density is the risk, not order. See Q5.
3. **Is the attestation modal sufficiently ceremonial?** — Yes, close. Missing zero-flags variant; summary-panel typography needs one tweak. See Q7.
4. **Typography hierarchy and spacing rhythm consistent?** — Yes. Clean. Only exception: the terminal banner on screen 5 (italic Cormorant in a plain border) — needs a squad read.
5. **Brass truly limited to 3 sites?** — **No.** Fourth site in TopNav chip. See Q1.
6. **Audit ledger reads as first-class?** — **No.** See Q4 (narrow column on detail) and Q8 (sparse ledger page).
7. **Any screen that feels more ops-SaaS than family-office?** — Screen 7 (audit ledger) yes, strongly. Screen 2 (console) mildly, fixable with density. Every other screen: no, it holds.
8. **Accessibility gaps?** — **Yes.** No focus states drawn anywhere. Login disclosure line fails AA contrast. Centered form labels. See Q9.

**Net:** 4 pass, 2 partial, 2 fail. Not shippable as-is. Fixable. My estimate: 1 day of redraw on my side, the rest flows into the A1/A2/B2 tickets as already planned with the additions above.

---

## 6. The one thing I will not negotiate

The attestation modal stays ceremonial. If build pressure forces cuts, **do not cut the Cormorant-italic attestation language**, **do not cut the reviewer-notes recap**, **do not default-focus the confirm button**. Everything else can compress. The moment is the product. If Bobbie pushes back on the modal's cost, escalate to me before you compromise.

— Holden
