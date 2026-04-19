# Capital Call v0.2.1 — Handoff Package

## Assets to transfer

### Infrastructure (GCP project: arukai-testbed)

| Asset | Service | Transfer action |
|-------|---------|----------------|
| Backend | Cloud Run `arukai-capital-call-backend-staging` | Transfer GCP project ownership |
| Frontend | Cloud Run `arukai-capital-call-frontend-staging` | Same project |
| Database | Neon Postgres `eu-central-1` | Transfer Neon account or export |
| Secrets | GCP Secret Manager (CC_*, MISTRAL_*, etc.) | Client rotates all keys |
| Container images | Artifact Registry `europe-west4` | Same project |
| GPU (future) | GCP L4 VM for self-hosted AI | Client provisions |

### Source code

| Repo | URL | Transfer |
|------|-----|----------|
| Capital Call | github.com/mahindrakarsawan-beep/arukai-capital-call | Transfer or fork |
| WhatsApp Bridge | ~/arukai-whatsapp (local) | Deliver as archive |

### Documentation delivered

| # | Document | Status |
|---|----------|--------|
| H1 | OPERATIONAL_RUNBOOK.md | Delivered |
| H2 | Monitoring (GCP Cloud Monitoring) | Setup guide delivered, dashboard not provisioned |
| H3 | Alert policies | Setup guide delivered |
| H4 | CLIENT_TRAINING.md | Delivered |
| H5 | SUPPORT_TIERS.md | Delivered |
| H6 | ACCESS_CREDENTIALS.md | Delivered (dev creds, prod rotation required) |
| H7 | Deployment scorecard | Delivered |
| H8 | UAT report | Partial (AI approver reviews, no external operator) |
| H9 | Production smoke | Delivered (QA verifier) |
| H10 | KNOWN_ISSUES.md | Delivered |
| H11 | Architecture decisions | Delivered (squad decision inbox) |
| H12 | Source code | Delivered (GitHub) |
| H13 | RBAC_ADMIN.md | Delivered (Authentik replaces custom) |
| H14 | RETENTION_POLICY.md | Delivered |
| H15 | AUDIT_TRAIL_GUIDE.md | Delivered |
| H16 | NDA_ASSET_TRANSFER_TEMPLATE.md | Delivered |
| H17 | WAF_SETUP.md | Delivered |
| H18 | SELF_HOSTED_AI_SETUP.md | Delivered |

### Credential rotation checklist

Before production handoff:
- [ ] Rotate all seed passwords (admin123 etc. are dev-only)
- [ ] Generate production JWT_SECRET
- [ ] Generate production FIELD_ENCRYPTION_KEY
- [ ] Set up Authentik with real user accounts
- [ ] Rotate Mistral API key (or remove — self-hosted replaces it)
- [ ] Set APP_ENV=production on Cloud Run
- [ ] Enable Cloudflare WAF
- [ ] Provision GCP Cloud Monitoring dashboard
- [ ] Set up alert policies (P0: health fail, P1: latency >3s)

## System summary

| Component | Technology | Tests |
|-----------|-----------|-------|
| Backend | FastAPI + SQLAlchemy + Neon Postgres | 198 |
| Frontend | Next.js 15 + Tailwind + Arukai tokens | 321 |
| AI classification | Mistral Small → self-hosted Qwen 2.5 7B | Benchmarked |
| Identity + MFA | Authentik (TOTP, WebAuthn, OIDC) | Integrated |
| Workflow | Windmill (visual approval flows) | Client configured |
| Encryption | AES-256-GCM + GCP KMS | 12 tests |
| Auth | JWT (15-min access + 7-day refresh + revoke-all) | 9 tests |
| Rate limiting | slowapi (10/min login, 100/min auth'd) | Configured |
| PDF validation | Magic bytes + size + JS detection | Configured |
| Monitoring | /metrics (Prometheus) + /health/detailed | Configured |
| Backup | scripts/backup.py (dump → encrypt → GCS) | Script ready |
| QA | qa_verifier.py + qa_e2e_verifier.py + model_scorecard.py | 3 tools |

## What's proven vs not

| Claim | Status |
|-------|--------|
| End-to-end workflow (upload → classify → review → approve) | Proven (live) |
| AI classification with visible reasoning | Proven (live) |
| Role-based access (admin/reviewer/approver) | Proven (live) |
| Field-level encryption | Proven (tests) |
| Self-hosted AI path | Ready (not deployed — needs GPU) |
| External operator handoff | Not proven (no real client operator) |
| MFA enforcement | Ready (Authentik integrated, not activated) |
| 90-day operational data | Not available (system is new) |
