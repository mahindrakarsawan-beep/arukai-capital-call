# Phase 2B v0.1 — Capital Call MVP Scope Memo

**Author:** Holden (Squad Lead, Arukai Commissioning Core)
**Date:** 2026-04-12
**Status:** APPROVED FOR EXECUTION
**Repo:** `github.com/mahindrakarsawan-beep/arukai-capital-call` (local: `/home/sawan/arukai-capital-call/`)
**Phase:** 2B — external deployment track, internal operator (no live external operator yet)
**Parent artifacts:** `d2-intake-capital-call.json`, `d2-blueprint-capital-call.md`, `d2-governance-plan.md`, `pattern-extraction.md`

---

## 0. Opus Decision (the one I'm making)

The blueprint describes a 41-hour build with full ingestion pipeline, RBAC hierarchy, exception detection, multi-currency, and Pub/Sub routing. That is the **D2 target state**, not v0.1. For a session-buildable MVP that still proves the commissioning flow end-to-end, I am cutting aggressively:

- **One ingestion channel:** manual upload only. No email, no portal polling.
- **One AI call flow:** document classification. Entity extraction, exception detection, routing engine all deferred.
- **Two roles:** admin, reviewer. No approver/viewer hierarchy.
- **No Pub/Sub.** Synchronous upload → classify → store. Async deferred to v0.2.
- **No Cloud Storage.** PDFs stored as bytea in Postgres for v0.1 (bounded by small test corpus; swap to GCS in v0.2).
- **No OCR.** Text-layer PDFs only; we reject scanned images with a clear error message.
- **No multi-currency.** USD-only formatting.
- **One happy path, end-to-end, tested, deployed.** That is the deliverable.

This preserves the architectural shape (FastAPI + Postgres + Anthropic + Next.js + Cloud Run) so v0.2 adds features without rewrites, while collapsing the buildable surface to something Sonnet can finish in one session.

---

## 1. v0.1 MVP Surface

### 1.1 Backend — FastAPI endpoints (8)

| # | Method | Path | Auth | Purpose |
|---|--------|------|------|---------|
| 1 | POST | `/auth/login` | public | Email + password → JWT (8h) |
| 2 | GET | `/auth/me` | JWT | Return current user {id, email, role} |
| 3 | POST | `/packages` | JWT (reviewer, admin) | Multipart upload PDF → create package row, store bytes, enqueue classify (sync for v0.1) |
| 4 | GET | `/packages` | JWT (any) | List packages (filter: status, own-vs-all by role) |
| 5 | GET | `/packages/{id}` | JWT (any) | Package detail + classification + document metadata |
| 6 | GET | `/packages/{id}/pdf` | JWT (any) | Stream stored PDF bytes |
| 7 | POST | `/packages/{id}/approve` | JWT (admin) | Transition pending_review → approved; write audit event |
| 8 | GET | `/audit/{package_id}` | JWT (any) | Return audit events for package |

Plus `/health` (unauthenticated) for smoke tests. Not counted.

### 1.2 Data models — Postgres schema (6 tables)

| # | Table | Key columns |
|---|-------|-------------|
| 1 | `users` | id (uuid), email (unique), password_hash, role (enum: admin, reviewer), created_at |
| 2 | `packages` | id (uuid), uploaded_by (fk users), status (enum: pending_classification, pending_review, approved, rejected), title, created_at, updated_at |
| 3 | `documents` | id (uuid), package_id (fk), filename, mime_type, size_bytes, content (bytea), created_at |
| 4 | `classifications` | id (uuid), document_id (fk unique), document_type (enum: capital_call_notice, subscription_agreement, side_letter, k1, wire_instructions, other), confidence (numeric), key_indicators (jsonb), model_version, created_at |
| 5 | `audit_events` | id (uuid), package_id (fk), actor_user_id (fk), action (text), before_state (jsonb), after_state (jsonb), created_at (append-only; no update/delete triggers) |
| 6 | `approvals` | id (uuid), package_id (fk unique), decided_by (fk users), decision (enum: approved, rejected), note (text), decided_at |

Alembic migrations. One initial migration creates all six.

### 1.3 AI pipeline — ONE Anthropic call: Document Classification

- **Model:** `claude-haiku-4-20250414` (cost discipline per directive — extraction/classification is Haiku tier).
- **Input:** Extracted text from PDF (via `pypdf`, text layer only; no OCR). First ~6000 chars.
- **System prompt:** cached (prompt caching enabled). Defines six-class taxonomy and asks for JSON.
- **Output schema:** `{"document_type": "...", "confidence": 0.0-1.0, "key_indicators": ["..."]}`.
- **Fallback:** on API error or low confidence (<0.5), filename keyword heuristic → `"other"` with `fallback=true` flag.
- **Token budget:** capped at 4096 output tokens per call. ~20 test packages in session = negligible cost.
- **No entity extraction, no exception detection, no routing** in v0.1.

### 1.4 Frontend — Next.js pages (4)

| # | Route | Purpose |
|---|-------|---------|
| 1 | `/login` | Email + password form → `/auth/login` → store JWT in httpOnly cookie → redirect to `/dashboard` |
| 2 | `/dashboard` | Package list: table (title, uploader, status, classified type, confidence, uploaded_at). Sort by newest. Admin sees all; reviewer sees own uploads + all pending_review. |
| 3 | `/packages/new` | Upload form: title + PDF file. On success redirect to detail page. |
| 4 | `/packages/[id]` | Detail view: title, uploader, classification, confidence, key indicators, embedded PDF viewer (browser native), audit trail table. Admin sees Approve/Reject buttons if status=pending_review. |

Single shared layout with top nav (user email, role badge, logout). Tailwind for styling. Server components for data fetch where JWT allows; client components for forms.

### 1.5 Auth

- JWT HS256, `JWT_SECRET` from env, 8h expiry.
- Two roles: `admin`, `reviewer`.
- Password hashing: bcrypt (passlib).
- Seed script creates 1 admin + 1 reviewer on first migration.
- Middleware: `require_role(roles: list)` dependency on FastAPI routes.

### 1.6 Deployment

- **Cloud Run** (us-east1) — reuse ARU-02 P-5.2 deploy script, swap service name to `arukai-capital-call`.
- **Neon Postgres** — new project or shared; connection pool via SQLAlchemy async.
- **Secrets:** GCP Secret Manager bindings for `ANTHROPIC_API_KEY`, `DATABASE_URL`, `JWT_SECRET`.
- **Frontend:** Cloud Run separate service (Next.js standalone output) OR Vercel — pick Cloud Run to stay inside `arukai-testbed` and match D1 pattern.
- **Single Dockerfile** per service (backend, frontend).
- **GitHub Actions:** on push to main → build both images → deploy staging. Production tag-triggered (not exercised in v0.1).

---

## 2. v0.1 User Story (single happy path)

> Alice (reviewer) logs in at `/login`. She clicks "New Package," titles it "Meridian Fund III — Q2 Capital Call," uploads a PDF. The system stores the file, calls Haiku, which returns `{"document_type": "capital_call_notice", "confidence": 0.94}`. Alice is redirected to `/packages/{id}` and sees the classification. Bob (admin) logs in, sees Alice's package on `/dashboard` in `pending_review` status, opens it, clicks "Approve," adds a one-line note. Package flips to `approved`. An audit event is appended for each action (upload, classified, approved). Both users can view the audit trail. That is the v0.1 demo.

One path. Tested end-to-end. Deployed.

---

## 3. Deferred to v0.2+

| Feature | Reason deferred |
|---------|-----------------|
| Email ingestion (SendGrid/Graph) | Requires external DNS + inbound webhook infra; v0.2 |
| Fund admin portal polling | Requires operator credentials; v0.2+ |
| Multi-role RBAC (approver, viewer) | 2 roles prove the model; full hierarchy v0.2 |
| Exception detection | Requires entity extraction first; v0.2 |
| Entity extraction | Second Anthropic call flow; v0.2 |
| Side letters, sub docs, K-1, wire instructions handling (beyond classification label) | Only capital_call_notice drives the approval flow in v0.1 |
| Advanced approval routing (rules by fund/jurisdiction/amount) | All admins can approve everything in v0.1 |
| Pub/Sub async pipeline | Synchronous is fine at v0.1 volume; async v0.2 |
| GCS document storage | bytea in Postgres works for <100 test docs; migrate v0.2 |
| OCR (Document AI / Textract) | Text-layer PDFs only in v0.1 |
| Multi-currency formatter | USD-only v0.1 |
| Email notifications | No SMTP integration in v0.1 |
| Reporting tab / CSV export | v0.2 |
| Legal hold, retention archival, lifecycle policies | Full retention governance v0.2 |

---

## 4. Squad Plan (model tier per directive)

| Agent | Model | Scope |
|-------|-------|-------|
| **Holden** | Opus | Scope memo (this doc), red-team pass before M4, scorecard synthesis at M6. No implementation. |
| **Drummer** | Sonnet | FastAPI app factory, SQLAlchemy models, Alembic migration, JWT auth, 8 endpoints, Anthropic Haiku client with prompt caching, pytest suite (unit + integration against test Postgres). |
| **Bobbie** | Sonnet | Next.js 14 app-router scaffold, 4 pages, auth cookie flow, Tailwind layout, fetch wrappers, Playwright/jest smoke tests for login → upload → view → approve. |
| **Miller** | Sonnet | Run 14-rule KPI checklist adapted for web (rules 1-3, 6-7, 9-11, 13-14 direct; rules 4, 5 become web a11y variants; rules 8, 12 N/A). Run Miller gate at each PR. Smoke test staging. |
| **Alex** | Haiku | README, `.env.example`, Dockerfiles, docker-compose for local dev, GitHub Actions YAML. |
| **Naomi** | Haiku | Runbook (deploy/rollback/secrets), handoff checklist, D2 v0.1 evidence pack skeleton. |

Cost posture: Opus ≤ 2 turns total (this memo + red-team + scorecard). Everything else Sonnet/Haiku.

---

## 5. Milestones (this session)

| # | Milestone | Owner(s) | Definition of Done |
|---|-----------|----------|--------------------|
| M1 | Repo scaffold committed | Alex + Drummer + Bobbie | `pyproject.toml`, `package.json`, `Dockerfile.backend`, `Dockerfile.frontend`, `.github/workflows/ci.yml`, `docker-compose.yml`, `.env.example`, initial `README.md`. Backend boots with `/health` 200. Frontend boots with root page. CI runs lint + type-check on PR. |
| M2 | Backend v0.1 complete | Drummer | 6 tables migrated, 8 endpoints implemented, JWT auth works, Haiku classification call works against real API, pytest green (>=20 tests, happy path + auth failures + classification fallback). Miller gate cleared. |
| M3 | Frontend v0.1 complete | Bobbie | 4 pages wired, login persists, upload works against backend, dashboard renders, approve flow writes audit event. Playwright smoke test of full happy path green. 14-rule web-adapted attestation posted. Miller gate cleared. |
| M4 | Deployed to Cloud Run staging | Drummer + Alex | `https://arukai-capital-call-<hash>-ue.a.run.app` responds. Frontend service URL responds. Staging smoke test (numbered checklist) PASS. Holden red-team pass: upload real capital-call PDF, classify, approve, audit. No P0. |
| M5 | Governance package | Naomi | Runbook (deploy, rollback, secrets rotate, /health), handoff checklist adapted for v0.1 (no external operator — handoff is partial per directive), D2 evidence pack with Phase 2B v0.1 caveats marked. |
| M6 | Scorecard with actuals | Holden | Actual hours logged per agent, actual Anthropic spend, actual weighted reuse % measured against ARU-08 rubric, Linear tickets closed, delta vs projected-67.7% recorded. |

---

## 6. Reuse Plan (>50% weighted reuse target)

Reusing from ARU-02 / Portfolio Analyzer (NO modification to PA repo):

| Pattern (ARU-02 ID) | Weight | Reuse status in v0.1 | How |
|----|----|----|----|
| P-1.1 Agent Charter | 1.0 | reuse-as-is | Copy `.squad/agents/*/charter.md` schema, swap personas. |
| P-1.2 Decision Inbox Protocol | 1.0 | reuse-as-is | `.squad/decisions/inbox/` directory + naming convention. |
| P-1.3 Linear-First PM Guardrail | 1.0 | reuse-as-is | Same 5-state workflow; team=Portfolio-checker, prefix=POR (reused Linear team). |
| P-1.4 Complexity Defaults | 1.0 | reuse-as-is | Same tier model. |
| P-2.1 N-Rule Copilot Checklist | 2.0 | adapted | Web variants for rules 4, 5 (a11y); rules 8, 12 N/A for web. Document the variant in `.squad/quality/14-rule-web.md`. |
| P-2.2 Handoff Document Pattern | 2.0 | reuse-as-is | Same schema. |
| P-2.3 Smoke Test Pattern | 2.0 | adapted | Numbered check table; new checks: PDF upload, classification call, approve flow, audit append. |
| P-2.4 UAT Report Pattern | 2.0 | deferred-to-v0.2 | Internal rehearsal has no external operator; not run in v0.1. |
| P-4.1 FastAPI App Factory | 3.0 | adapted | `create_base_app()` reused; add JWT middleware, 8 domain routes. No GraphQL in v0.1 (REST only). No scheduler. |
| P-5.1 GCP Infra Provisioning | 3.0 | adapted | Same provision script; add Neon project reference and Secret Manager bindings. Skip Pub/Sub, Cloud Storage, Document AI (deferred). |
| P-5.2 Cloud Run Deploy Script | 3.0 | reuse-as-is | Service name swap only. |
| P-5.3 CI/CD Workflow | 3.0 | adapted | Two-service build (backend + frontend); reuse test stage pattern. |
| P-5.4 Deployment Runbook | 1.0 | adapted | Reuse structure; remove Pub/Sub/GCS sections (not in v0.1). |

**Patterns NOT reused in v0.1 (deferred to v0.2 to maintain scope):**
- P-3.1..P-3.6 frontend tokens/motion (Portfolio Analyzer uses RN; v0.1 frontend is Next.js web — token system applies but motion/gesture patterns do not; adapt-token-only in v0.2).
- P-4.2 GraphQL JSON scalar (REST-only in v0.1).

### Projected v0.1 weighted reuse

- Applicable points: P-1.1 (1.0) + P-1.2 (1.0) + P-1.3 (1.0) + P-1.4 (1.0) + P-2.1 (2.0) + P-2.2 (2.0) + P-2.3 (2.0) + P-4.1 (3.0) + P-5.1 (3.0) + P-5.2 (3.0) + P-5.3 (3.0) + P-5.4 (1.0) = **23.0**
- Earned (reuse-as-is = full weight; adapted = 0.6 × weight per ARU-08): 1.0 + 1.0 + 1.0 + 1.0 + 1.2 + 2.0 + 1.2 + 1.8 + 1.8 + 3.0 + 1.8 + 0.6 = **17.4**
- **Projected weighted reuse for v0.1: 17.4 / 23.0 = 75.6%** — exceeds the >50% target. M6 remeasures with actuals.

---

## 7. Linear Plan — 7 tickets for Phase 2B v0.1

All under project "Arukai Commissioning Core," team Portfolio-checker. Priority High (2) unless noted.

| # | Title | Owner | Priority |
|---|-------|-------|----------|
| T1 | v0.1 M1: Repo scaffold + CI/CD + Dockerfiles | Alex + Drummer + Bobbie | Urgent |
| T2 | v0.1 M2: Backend — FastAPI + Postgres schema + JWT + 8 endpoints + tests | Drummer | Urgent |
| T3 | v0.1 M2b: Backend — Haiku classification pipeline + prompt caching + fallback | Drummer | High |
| T4 | v0.1 M3: Frontend — 4 Next.js pages + auth cookie + Playwright smoke | Bobbie | High |
| T5 | v0.1 M4: Cloud Run staging deploy + smoke test + Holden red-team | Drummer + Holden | High |
| T6 | v0.1 M5: Governance package — runbook + partial handoff evidence | Naomi | Normal |
| T7 | v0.1 M6: Scorecard with actuals + weighted reuse measurement | Holden | Normal |

---

## 8. Hard scope discipline

- **If a feature is not in Section 1, it is not in v0.1.** Exceptions require a new Opus turn.
- **No modification to the Portfolio Analyzer repo** under any circumstances. All reuse is by copy or by reading pattern docs.
- **Cost gate:** if Anthropic spend in the session exceeds $5, stop and report.
- **No operator interaction.** Handoff evidence is labeled partial per the directive.

---

*Memo issued. Execution begins at T1.*
— Holden
