# Client Validation Report — Capital Call v0.1

**For:** Workflow owner (family-office operator)
**From:** Arukai Squad
**Date:** 2026-04-14
**Status:** Ready for your validation

---

## What You Asked For

A governed private system that ingests capital call / subscription package materials, classifies them, routes review, tracks approvals, surfaces exceptions, and maintains an audit trail.

## What We Built (v0.1)

A working staging deployment of the core workflow. One happy path end-to-end, so you can validate the commissioning approach before we expand scope.

### Live URLs

- **Web app:** https://arukai-capital-call-frontend-staging-1035777337524.europe-west4.run.app
- **Backend API:** https://arukai-capital-call-backend-staging-1035777337524.europe-west4.run.app
- **Health check:** `/health` on backend

### Test Credentials (v0.1 — rotate before production)

| Role | Email | Password |
|------|-------|----------|
| Admin | admin@arukai.example | admin123 |
| Reviewer | reviewer@arukai.example | reviewer123 |

---

## 15-Minute Validation Walkthrough

**Step 1 — Log in as Reviewer (2 min)**
Sign in as `reviewer@arukai.example`. You should see an empty Documents dashboard.

**Step 2 — Upload a capital call document (5 min)**
Click "Upload new" → select a PDF → submit. System classifies via Claude Haiku. You're redirected to the detail page showing doc_type, confidence, and extracted fields (fund name, amount, due date, recipient).

**Step 3 — Review on dashboard (3 min)**
Document appears with "pending" status and classification badge. Download the original PDF to verify.

**Step 4 — Log in as Admin and approve (3 min)**
Log out, sign in as admin. On the document detail page, click Approve or Reject with a reason.

**Step 5 — Check audit trail (2 min)**
As admin, call `GET /audit` on the backend. Every action from steps 1-4 should be logged with actor, action, resource, timestamp.

---

## What Works

Login (JWT + bcrypt), PDF upload (max 20MB), AI classification (Haiku, ~2-5s, fallback on error), field extraction, document listing, download, admin approve/reject, full audit trail, role-based access.

## What's Deferred to v0.2+

Email ingestion, portal integrations, side letter / subscription doc types validated against real data, exception detection, reclassification override, approver + viewer roles, multi-currency, notifications, search, mobile UI.

## Known Gaps (Honest)

- No GCP Cloud Monitoring dashboard or alert policies
- Dev credentials must be rotated before production
- 7-year retention policy documented but not automated
- No external UAT yet (this walkthrough produces one)
- Only capital call type validated; others accepted but not tuned

Full list: `docs/KNOWN_ISSUES.md`

---

## Validation Feedback Requested

Please confirm after your walkthrough:

- [ ] Login works for both roles
- [ ] PDF upload + classification succeeds
- [ ] Classification is directionally correct (doc_type + 2/4 fields)
- [ ] Approve/reject flow works for admin
- [ ] Audit trail captures every action

Please answer:

1. Which classification fields matter most?
2. What document types beyond capital call notices?
3. Who in your organization operates this?
4. Email ingestion source (Gmail/Outlook/other)?
5. Must-have integrations?
6. Does 7-year retention cover your regulatory needs?

---

## Build Summary

| Metric | Value |
|--------|-------|
| Tests | 64 (31 backend + 33 frontend) |
| Hours | ~14 |
| Commits | 5 |
| Services | 2 |
| Uptime | 100% since deploy |
| P0/P1 incidents | 0 |
| Pattern reuse | 54.8% (17.0 / 31.0 weighted points) |

Built using Arukai's Commissioning Core v1 — same approach as Portfolio Analyzer (Deployment 1). 45.2% was capital-call-specific domain work.

---

## Next Steps

1. You validate → walkthrough + feedback
2. We fix any classification issues
3. v0.2 scope: email ingestion, additional doc types, expanded RBAC
4. Monitoring + alerts before any production use
5. Formal UAT with you as operator
6. Production deploy, handoff package, credential rotation

Repository: https://github.com/mahindrakarsawan-beep/arukai-capital-call

No code changes until you've validated v0.1.
