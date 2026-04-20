# D2 v0.2.1 -- 3-Stage Implementation Plan

**Date:** 2026-04-15
**Author:** Holden (requirements + architecture)
**Status:** PROPOSED -- awaiting Sawan approval
**Ref:** squad-showstopper-response.md, squad-showstopper-rereview.md

---

## Stage Transition Protocol

After each stage completes:
1. Developer commits + deploys to staging
2. Miller (Opus) runs security validation suite
3. AI approvers (Mistral + OpenAI as paranoid client) review stage deliverables
4. Results posted to Linear with PASS/FAIL per criterion
5. Holden reviews and decides: **PROCEED** / **BLOCK** / **ASK CLIENT**
   - PROCEED: next stage begins
   - BLOCK: specific fixes listed, re-review after fixes
   - ASK CLIENT: Holden formulates question, posts to Linear, waits for Sawan

---

## Stage 1: Security Foundation

**Goal:** Eliminate all must-haves before any client data touches the system.

### S1-T1: Kill Dev Credentials + Guard Seed Users
**Owner:** Drummer (Mistral coding LLM)
**Dependencies:** None
**Hours:** 2

Remove hardcoded `admin123` passwords. Guard `_seed_dev_users()` behind `ENVIRONMENT=development` check. Remove any default credentials from config files.

- **Acceptance:** No hardcoded passwords in codebase; seed function gated by env var; `pytest` passes; grep for "admin123" returns zero hits
- **Files:** `backend/app/main.py`, `backend/app/routers/auth.py`
- **Token budget:** Read only `main.py` seed function + `auth.py` login route. Result: diff only.

### S1-T2: Remove OpenAI from Non-Dev Code Paths
**Owner:** Drummer (Mistral coding LLM)
**Dependencies:** None (parallel with S1-T1)
**Hours:** 3

Strip OpenAI fallback from `classify.py`. Remove `OPENAI_API_KEY` from all non-dev env configs. Provider chain becomes: Mistral API -> heuristic fallback.

- **Acceptance:** No OpenAI imports/calls outside test files; no `OPENAI_API_KEY` in staging/prod configs; classification still works via Mistral; fallback tests pass
- **Files:** `backend/app/classify.py`, `.env.staging`, `.env.production`, `docker-compose*.yml`
- **Token budget:** Read `classify.py` classify function only. Result: diff only.

### S1-T3: Rate Limiting + PDF Malware Scanning
**Owner:** Bobbie (Anthropic Sonnet)
**Dependencies:** None (parallel)
**Hours:** 6

Add `slowapi` middleware with per-endpoint limits (login: 10/min, upload: 10/min/user, general: 100/min). Add ClamAV sidecar container; scan PDFs before processing; reject infected files with 422.

- **Acceptance:** Rate limit returns 429 on excess; ClamAV rejects EICAR test file; clean PDFs process normally; Docker compose includes clamav service
- **Files:** `backend/app/main.py`, `backend/app/routers/packages.py`, `docker-compose.yml`, `requirements.txt`
- **Token budget:** Read `main.py` app setup + `packages.py` upload endpoint. Result: diff + new clamav config.

### S1-T4: Field-Level Encryption + KMS Integration
**Owner:** Drummer (Mistral coding LLM)
**Dependencies:** S1-T1 (clean creds first)
**Hours:** 10

New `backend/app/crypto.py` module: AES-256-GCM encrypt/decrypt backed by GCP Cloud KMS. Encrypt `extracted_fields` JSONB and PDF `content` bytes on write; decrypt on authorized read.

- **Acceptance:** Encrypted data unreadable in raw DB query; decrypt returns original; KMS key configurable via env var; key rotation supported; round-trip test passes
- **Files:** `backend/app/crypto.py` (new), `backend/app/routers/packages.py`, `backend/app/models.py`
- **Token budget:** Read `packages.py` upload/read endpoints + `models.py` Package model. Result: new file + diffs.

### S1-T5: OIDC Endpoint Prep for MFA/SSO
**Owner:** Bobbie (Anthropic Sonnet)
**Dependencies:** S1-T1 (dev creds removed first)
**Hours:** 6

Add OIDC token validation path in `auth.py`. Support both legacy JWT (for dev) and OIDC JWT (for staging/prod). Configure `OIDC_ISSUER_URL` and `OIDC_CLIENT_ID` env vars. Roles extracted from OIDC claims.

- **Acceptance:** OIDC flow validates tokens from test issuer; legacy login still works in dev; role extraction from JWT claims works; env vars documented
- **Files:** `backend/app/auth.py`, `backend/app/routers/auth.py`, `requirements.txt`
- **Token budget:** Read `auth.py` only. Result: diff only.

### Drift Protection Checkpoints (Stage 1)
- **Before S1-T4:** Drummer must confirm KMS key hierarchy design with Holden before writing `crypto.py`
- **Before S1-T5:** Bobbie must confirm OIDC claim mapping (role names, scopes) with Holden before modifying auth

### Client Review Gate
| Criterion | Pass/Fail Test |
|---|---|
| No dev credentials | `grep -r "admin123"` returns empty |
| No OpenAI in prod path | No OpenAI imports in `classify.py` |
| Encryption works | Insert + read round-trip with KMS key |
| Rate limiting active | 11th login attempt in 1 min returns 429 |
| Malware scan works | EICAR test file rejected |

### Questions for Client (Stage 1)
- Confirm preferred IdP: Zitadel (Swiss SaaS) or self-hosted Keycloak?
- Provide GCP project ID for KMS key provisioning

---

## Stage 2: Infrastructure Hardening

**Goal:** Production-grade ops: backups, monitoring, WAF, JWT hardening, audit trail.

### S2-T1: Backup Automation
**Owner:** Drummer (Mistral coding LLM)
**Dependencies:** Stage 1 complete
**Hours:** 6

Nightly `pg_dump` to client-owned GCS bucket, encrypted with client's KMS key. Cloud Scheduler triggers Cloud Run job. Quarterly restore test documented.

- **Acceptance:** Backup runs on schedule; backup file encrypted in GCS; restore to throwaway instance succeeds; backup older than 30 days auto-deleted
- **Files:** `infra/backup-job/` (new), `infra/terraform/scheduler.tf`, Cloud Scheduler config
- **Token budget:** Read current infra configs only. Result: new job + terraform diff.

### S2-T2: Monitoring + Alerting
**Owner:** Alex (Mistral coding LLM)
**Dependencies:** Stage 1 complete
**Hours:** 5

GCP Cloud Monitoring: uptime check on `/health` (1-min interval), alert policies for 5xx spike (>5% for 5min), high latency (p95 >3s), health check failure. Structured JSON logging.

- **Acceptance:** Uptime check configured; alerts fire on simulated failure; structured logs visible in Cloud Logging; alert notification channel configured
- **Files:** `infra/terraform/monitoring.tf`, `backend/app/main.py` (logging config)
- **Token budget:** Read `main.py` logging section only. Result: terraform + diff.

### S2-T3: WAF (Cloudflare Free Tier)
**Owner:** Alex (Mistral coding LLM)
**Dependencies:** S2-T2 (monitoring first, so we can see WAF effects)
**Hours:** 4

Cloudflare DNS proxy in front of Cloud Run. Basic WAF rules enabled. EU routing configured. Document handoff: client owns Cloudflare account.

- **Acceptance:** Traffic routes through Cloudflare; SQL injection test blocked; DDoS protection active; DNS documented for handoff
- **Files:** `infra/cloudflare/` (new), handoff docs
- **Token budget:** No codebase reads needed. Result: config files only.

### S2-T4: JWT Hardening + Audit Trail
**Owner:** Bobbie (Anthropic Sonnet)
**Dependencies:** S1-T5 (OIDC prep done)
**Hours:** 8

Short-lived access tokens (15 min), refresh token flow with revocation list, token rotation on refresh. Admin action audit trail: log all role changes, user management, config changes to immutable audit log.

- **Acceptance:** Access token expires in 15 min; refresh token works; revoked token rejected; admin actions appear in audit log; audit log entries immutable
- **Files:** `backend/app/auth.py`, `backend/app/routers/auth.py`, `backend/app/routers/audit.py`
- **Token budget:** Read `auth.py` token functions + `audit.py`. Result: diffs only.

### S2-T5: NDA + Asset Transfer Template
**Owner:** Holden (Anthropic Opus)
**Dependencies:** None (parallel)
**Hours:** 4

Finalize NDA template and asset transfer agreement from showstopper-response.md. Package as commissioning-core artifact. Include inventory checklist for handoff day.

- **Acceptance:** NDA covers all data categories; transfer table lists every asset; template parameterized for reuse; legal review checklist included
- **Files:** `commissioning-core/templates/nda-data-transfer-commitment.md` (new)
- **Token budget:** Read showstopper-response.md NDA section only. Result: new document.

### Drift Protection Checkpoints (Stage 2)
- **Before S2-T1:** Drummer must confirm GCS bucket naming + retention policy with Holden
- **Before S2-T3:** Alex must confirm Cloudflare account ownership model with Holden (who owns the account during dev?)
- **Before S2-T4:** Bobbie must confirm refresh token storage strategy (DB vs Redis vs in-memory) with Holden

### Client Review Gate
| Criterion | Pass/Fail Test |
|---|---|
| Backup works | Restore latest backup to throwaway instance |
| Monitoring catches incidents | Simulate 5xx spike, verify alert fires |
| WAF blocks attacks | SQL injection payload blocked by Cloudflare |
| JWT hardened | Expired token rejected; revoked token rejected |
| Audit trail complete | Admin action visible in immutable log |

### Questions for Client (Stage 2)
- Preferred GCS bucket region for backups (recommend europe-west4)?
- Alert notification channel: email only, or also webhook/Slack?

---

## Stage 3: AI Sovereignty + Handoff

**Goal:** Self-hosted AI, zero external API calls, full data sovereignty, asset transfer.

### S3-T1: Self-Hosted Qwen 2.5 7B on GCP L4
**Owner:** Drummer (Mistral coding LLM)
**Dependencies:** Stage 2 complete
**Hours:** 10

Deploy Qwen 2.5 7B (GPTQ 4-bit) via vLLM on GCP g2-standard-4 (1x L4). Docker image with vLLM + model weights. OpenAI-compatible API endpoint. Deploy to client's GCP project in europe-west4.

- **Acceptance:** vLLM serves `/v1/chat/completions`; model loads and responds; latency <4s per document; GPU utilization healthy; container restarts cleanly
- **Files:** `infra/llm-service/` (new Dockerfile, deploy config), GKE/GCE config
- **Token budget:** No app code reads. Result: new infra files only.

### S3-T2: Migration -- Swap Mistral API to Self-Hosted
**Owner:** Bobbie (Anthropic Sonnet)
**Dependencies:** S3-T1 (self-hosted running)
**Hours:** 4

Change `LLM_ENDPOINT` env var from Mistral API URL to self-hosted vLLM URL. Remove Mistral API key from staging/prod. Verify classify + extract pipeline works end-to-end.

- **Acceptance:** `classify.py` calls self-hosted endpoint; no external API calls in network logs; classification accuracy matches Mistral baseline; zero code changes beyond env var
- **Files:** `backend/app/classify.py`, `.env.staging`, `.env.production`
- **Token budget:** Read `classify.py` endpoint config section only. Result: env var change.

### S3-T3: Performance Validation
**Owner:** Miller (Anthropic Opus)
**Dependencies:** S3-T2 (migration done)
**Hours:** 6

Run full test suite against self-hosted model. Compare classification + extraction accuracy against Mistral API baseline. Benchmark latency. Document results.

- **Acceptance:** Classification accuracy >90%; extraction accuracy >90%; latency p95 <5s; no accuracy regression >3% vs Mistral; results documented
- **Files:** `tests/test_classify.py`, `tests/test_classify_per_field.py`, benchmark report
- **Token budget:** Read test files for accuracy thresholds. Result: benchmark report (<200 words).

### S3-T4: Asset Transfer Package
**Owner:** Holden (Anthropic Opus)
**Dependencies:** S3-T3 (validation passed)
**Hours:** 6

Compile all H1-H15 governance deliverables. Final inventory: GCP project, Neon DB, GitHub repo, Docker images, CI/CD, DNS, secrets, KMS keys, Cloudflare account. Handoff runbook with day-of checklist.

- **Acceptance:** All assets inventoried; transfer runbook tested; IAM removal script ready; signed attestation template prepared; client can verify completeness
- **Files:** `commissioning-core/handoff/` (new), governance docs
- **Token budget:** Read NDA template from Stage 2. Result: new documents.

### S3-T5: Production Deploy with Self-Hosted AI
**Owner:** Drummer (Mistral coding LLM)
**Dependencies:** S3-T3 + S3-T4 (validation + handoff ready)
**Hours:** 4

Final production deployment. All services on client's GCP. No external API calls. Smoke test full workflow: upload PDF -> scan -> classify -> extract -> approve.

- **Acceptance:** End-to-end workflow completes; zero external API calls in network logs; all data stays in EU; monitoring active; backups running
- **Files:** Production deploy configs, Cloud Run service definitions
- **Token budget:** No code reads. Result: deploy log + smoke test results.

### Drift Protection Checkpoints (Stage 3)
- **Before S3-T1:** Drummer must confirm GPU instance type + region availability with Holden (L4 quota in europe-west4)
- **Before S3-T2:** Bobbie must verify vLLM API compatibility with current `classify.py` prompt format -- ask Holden if any prompt changes needed
- **Before S3-T5:** Drummer must get explicit PROCEED from Holden before production deploy

### Client Review Gate
| Criterion | Pass/Fail Test |
|---|---|
| Self-hosted AI works | Classification + extraction accuracy >90% |
| No external API calls | Network audit shows zero outbound AI API calls |
| Full data sovereignty | All data in EU, client owns all infra |
| Handoff package complete | All assets inventoried, transfer runbook ready |
| Production stable | End-to-end smoke test passes |

### Questions for Client (Stage 3)
- Confirm GCP GPU quota approved for g2-standard-4 in europe-west4
- Preferred handoff date after Stage 3 approval?

---

## Summary

| Stage | Tickets | Total Hours | Key Owners |
|---|---|---|---|
| 1: Security Foundation | 5 | 27 | Drummer, Bobbie |
| 2: Infrastructure Hardening | 5 | 27 | Drummer, Alex, Bobbie, Holden |
| 3: AI Sovereignty + Handoff | 5 | 30 | Drummer, Bobbie, Miller, Holden |
| **Total** | **15** | **84** | |

**Estimated calendar time:** 5-6 weeks (with client review gates between stages).

**Monthly cost post-implementation:** ~$601/month (primarily $560 for GPU instance).
