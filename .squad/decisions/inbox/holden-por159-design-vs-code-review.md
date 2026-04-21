# Design-vs-code review — D2 Visible AI post-19d merge (Holden, 2026-04-21)

**Subject:** POR-159 (Sprint 19d) shipped code against Figma frames 61:2 / 57:2 / 58:2 on file `a6mMsiXmnSdQTQ4qQYS6X2` (Page 4). This doc is the retroactive visual UAT that should have happened before merge.

**Method:** Pulled the 3 reference frames via Figma MCP. Captured live staging via Playwright at 1440×1024@2x with the same admin login. Compared side-by-side per criterion.

**Disclosure:** Sawan asked why Claude Design wasn't used this sprint. Answer: Claude Design is a human-only web app; I don't have access to it from Claude Code. The rule is now memorialized: before any design-heavy sprint, Holden asks Sawan whether to iterate in Claude Design first, devs wait for an export. See `feedback_claude_design_in_squad.md`. This review is the fallback when the Claude Design step was skipped.

---

## Frame 57:2 — Operations console

### Figma intent
- Display-font fund-name title per row (e.g. *"Meridian Capital Partners III — Q2 capital call"*)
- Below title, quiet grey AI summary line (*"Capital Call · $1.8M due May 20 · Low confidence on due date (62%) — needs operator"*)
- Small "Capital call notice" caption below summary
- State pill on the right in SMALL UPPERCASE
- Classification badge chip NOT shown on the row itself — type is communicated entirely via the AI summary prose
- 5 sections with counts (Exceptions, Pending approval, Needs review, Active packages, Recent decisions · last 30 days)

### Staging actual
- 5 sections ✓
- Each row shows `<DocType text> [<Pill chip>] · <confidence>%` on line 1, then AI summary on line 2, then small doc-type caption
- State pill on the right ✓
- No display-font fund-name title (rows show filename-derived titles like "Capital Call Notice" or "Other" instead of the premium fund-name format)

### Verdict: 57:2 — **PARTIAL**
| Criterion | Figma | Staging | Pass? |
|---|---|---|---|
| 5-section layout with counts | yes | yes | ✓ |
| AI summary line below title (new 19d.1 format) | yes | yes | ✓ |
| Classification chip on row | NO | yes (redundant with prose) | ✗ (minor) |
| Fund-name display title | yes | no (filename-derived) | ✗ (data-dependent — could be a seed issue) |
| State pill right-aligned uppercase | yes | yes | ✓ |
| Brass discipline § 9.3 (≤2 brass accents on page) | yes | yes — TopNav chip + empty-state links only | ✓ |

**Net:** the layout is right. The typographic hierarchy the Figma intended — "large fund name, quiet AI prose below" — is not landing because the data doesn't provide fund names. Staging substitutes the DocType as the title, which is why we see "Capital Call Notice" where Figma has "Meridian Capital Partners III — Q2 capital call". The redundant chip next to the title is a genuine defect.

---

## Frame 61:2 — Package detail with AI Analysis

### Figma intent
- H1: fund name + call ID (e.g. *"Meridian Capital Partners III — Q2 capital call"*)
- Subtitle: `Package submitted 2026-04-15 by Naomi Ito · Classification: Capital Call Notice · 99%`
- State pill `INTAKE COMPLETE · AWAITING REVIEWER` top-right
- 2-column layout: Block 1 Source document | Block 2 Extracted facts
- Block 3 **AI ANALYSIS full-width** with brass `#B8914E` header + quiet footer attribution
  - "CLASSIFICATION REASONING" subhead + paragraph
  - "FIELD-LEVEL EXTRACTION" with rows like `Fund name: Meridian Capital Partners III — found in header, confidence 99%`
  - Amber exception callout `! Side-letter ref SL-MRD-0412 has low confidence (62%). Manual verification recommended.`
- Block 4 Review notes, Block 5 Audit trail
- Bottom: `Release claim` + `Route for approval` actions (state-dependent)

### Staging actual
- H1: no fund name — just breadcrumb `Console /` then the state pill
- Sub: `Package submitted — by 8e1fab63-1846-464a-ba76-f0be77c2b805 · Classification: Unclassified · intake confidence 99%`
  - **Raw UUID instead of user name.**
  - **Missing date** between "submitted" and em-dash.
  - **"Unclassified" doc-type** but 99% intake confidence — contradictory on screen.
- Block 2 "Extracted facts" header: `Extracted by mistral-small-latest on —` — **missing date** (trailing em-dash)
- **Block 3 AI Analysis: RENDERS with brass header** ✓
  - Reasoning present ✓
  - EXTRACTED FIELDS table: 8 rows ✓
  - **Raw values in table:** Amount Due shows `120000000` not `$120M`. 19d.1's `_format_amount` helper was wired into `_build_ai_summary` only, NOT into the Classification schema serialization. The table uses raw extracted values.
  - Amber callout `! Call Number has low confidence (0%). Manual verification recommended.` ✓
- Block 4 Review notes + Block 5 Audit trail + audit-ledger link ✓
- Bottom: `Package closed. Decision recorded — Approved.` (state-dependent, correct for this package's state)

### Verdict: 61:2 — **PARTIAL**
| Criterion | Figma | Staging | Pass? |
|---|---|---|---|
| Fund-name H1 | yes | ✗ missing | ✗ (major) |
| "by <Person Name>" in subtitle | Naomi Ito | UUID | ✗ (major) |
| Submitted date in subtitle | 2026-04-15 | missing | ✗ (minor) |
| Doc-type displayed | Capital Call Notice | Unclassified | data issue |
| State pill top-right | yes | yes | ✓ |
| Block 3 AI Analysis renders | yes | yes | ✓ |
| Brass header color + discipline | yes | yes | ✓ |
| Classification reasoning paragraph | yes | yes (fallback from key_indicators) | ✓ |
| Field-level extraction table | yes | yes | ✓ |
| **Currency formatting in extraction table** | `$2,500,000.00` | `120000000` (raw) | ✗ (major) |
| Amber ExceptionCallout for low-confidence field | yes | yes (Call Number 0%) | ✓ |
| Model attribution | "Claude Haiku · 1.3s · April 15" | "mistral-small-latest · April 21" (missing duration) | ✓ structurally; formatter nit |
| "Extracted by <model> on <date>" | expected date | trailing em-dash, no date | ✗ (minor) |

**Net:** the block structure landed and the brass discipline is right. Two real product defects: (a) user display names not resolved in the detail-page header (UUIDs shown), (b) currency values in the extraction table are raw integers, not formatted — the Sprint 19d `_format_amount` helper only reached `_build_ai_summary` on the list endpoint, not the detail-page serialization.

---

## Frame 58:2 — Intake ceremony

### Figma intent
- Dark obsidian overlay background with "ARUKAI PRIVATE INTAKE" brass eyebrow
- Large display headline: *"Your capital call notice is being received."*
- Sub: *"We will classify it, extract the fields, and return it to you ready for review in under 30 seconds."*
- 4 horizontal step cards (01 Receive, 02 Classify, 03 Extract, 04 Ready)
  - Each card shows: step number (large display), label, 2-line detail text, DONE / WORKING… / PENDING badge
  - Brass accent border on the active step card (03 Extract in the Figma)
- Progress bar below cards
- Brass annotation at bottom (designer's note, not production)

### Staging actual
- **Could not capture.** The Playwright harness fed a minimal valid PDF (1KB) to the intake endpoint, but either the backend PDF validator rejected it or the ceremony dismissed instantly because classification returned synchronously. Captured screenshots are of the resulting detail page, not the ceremony overlay.

### Verdict: 58:2 — **UNVERIFIED**
Needs a real capital-call PDF + a Playwright harness that captures the overlay while it's active (ceremony animates over 1.2s). Existing jest tests in `upload.test.tsx` mock the ceremony; no E2E spec currently exercises the actual overlay.

---

## Brass discipline check (§ 9.3)

Per the squad rule, brass (`#B8914E`) appears on at most 2 elements per visible surface. Scanned all 3 staging shots:

- **Console (57:2):** 0 brass elements visible (TopNav has no pending chip in this view) — ✓
- **Detail (61:2):** 1 brass element — `AI ANALYSIS` block header + left-edge accent — ✓
- **Ceremony (58:2):** unverified but Figma shows 1 brass element (active step accent) — spec-compliant

Passes at page level. The brass-tinted surface markers on the AIAnalysisBlock left edge (35% opacity per spec) are not counted as signals per the spec's own note.

---

## Summary of defects to file

### Major (file as ticket POR-161)
1. **Detail page header shows UUID instead of user name.** Header-level UX regression. Likely cause: `uploaded_by` field on `PackageDetail` is a user ID, and the detail page never resolves it to a name.
2. **Extraction table values not formatted.** `120000000` shown raw instead of `$120,000,000` or `$120M`. 19d.1 formatters live in `_build_ai_summary` only; Classification detail serialization doesn't apply them.

### Minor (same ticket, low priority)
3. "Extracted by <model> on **—**" (trailing em-dash, no date) in the Extracted Facts block
4. Missing submission date in detail-page subtitle
5. Operations console shows a redundant `[Capital Call]` chip next to the title — Figma communicates doc-type via the AI summary prose only
6. Packages display filename-derived titles on staging (no fund-name titles) — probably seed-data, but worth confirming whether the frontend has a `title` → `displayTitle` path that should use fund-name when present

### Unverified (follow-up)
7. Intake ceremony visual parity needs a real capital-call PDF + a Playwright harness that captures the overlay mid-animation

---

## Would Claude Design have caught these?

Probably yes for 3, 4, 5 (pure layout/copy judgments). 1 and 2 are render-time data issues that need to see actual production-shape data to catch — Claude Design reads the codebase but not runtime state, so arguable. 6 is definitely data-layer. 7 is an animation capture problem.

The real preventative: an automated visual-parity CI step (Playwright screenshots + perceptual diff against committed Figma-exported baselines). That's POR-162 territory.

---

*Filed: Holden · 2026-04-21*
