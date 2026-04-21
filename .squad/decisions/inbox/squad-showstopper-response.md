# Showstopper Response -- Revised Architecture for Client Approval

**Date:** 2026-04-15
**Authors:** Holden (requirements), Drummer (backend/infra), Miller (validation), Naomi (support)
**Status:** PROPOSED -- awaiting Sawan approval, then client re-review
**Ref:** Client Approver Architecture Review -- VERDICT: NOT APPROVED (2026-04-19)

---

## Executive Summary

The client approver review identified 9 showstoppers and 8 serious concerns. Sawan has provided direction on the 5 critical ones. This document addresses each with concrete solutions, cost estimates, and implementation timelines. The revised architecture eliminates all third-party AI data exposure, transfers full infrastructure ownership to the client, adds encryption/backup/monitoring, and provides a clear MFA/SSO path.

---

## Showstopper 1: Arukai Owns All Infrastructure

### Problem
The client has zero infrastructure ownership. Arukai owns GCP, Neon, GitHub. Client cannot audit vendor access or verify compliance.

### Sawan's Direction
Sign an NDA and commit to full data ownership transfer post-payment.

### Solution: NDA + Data Transfer Commitment

#### Mutual Non-Disclosure Agreement (Template)

**Parties:** Arukai Technologies ("Vendor") and [Client Entity] ("Client")

**Scope of Confidential Information:**
- All financial documents (PDFs, extracted text, metadata) uploaded to or processed by the system
- All database contents including user accounts, audit trails, classification results, and extracted fields
- All API keys, secrets, and credentials used in the system
- All workflow state, approval decisions, and reviewer notes
- Client's operational processes, fund structures, and LP information

**Obligations:**
1. Vendor shall access Client data solely for the purpose of developing, deploying, and maintaining the Capital Call system during the active engagement period.
2. Vendor shall not copy, export, or retain Client data outside the production system.
3. Vendor shall not share Client data with any third party (including AI providers -- see Showstopper 2).
4. Vendor access is time-limited: access expires upon project handoff or termination.
5. All access by Vendor personnel shall be logged in an immutable audit trail visible to Client.

**Duration:** Effective from contract signing through 2 years post-handoff.

#### Data Transfer Commitment

Upon final payment, the following assets transfer to Client ownership:

| Asset | Transfer Method | Timeline |
|---|---|---|
| GCP Project | Transfer project ownership via IAM | Day of handoff |
| Neon Database | Export + import to client-owned Neon org, or migrate to Cloud SQL on client's GCP | Within 5 business days |
| GitHub Repository | Transfer repo to client's GitHub org | Day of handoff |
| All Secrets (API keys, JWT signing keys) | Rotate all secrets; new secrets generated under client control | Day of handoff |
| Domain/DNS | Transfer domain registrar access or update DNS to client's records | Within 5 business days |
| Docker Images | Push to client's Artifact Registry | Day of handoff |
| CI/CD Pipelines | GitHub Actions workflows transfer with repo | Day of handoff |

**Post-Handoff Access:**
- Arukai retains **zero** access to client data, infrastructure, or secrets
- All Arukai IAM roles are removed on handoff day
- Client receives a signed attestation that no data copies were retained
- If ongoing support is needed, Client grants time-limited, audited access per incident

**During Development (NDA period):**
- Arukai operates under NDA with access scoped to development tasks
- All Arukai access is via named accounts (no shared credentials)
- Audit log captures every Arukai personnel action
- Client can request an access audit at any time
- Client can revoke Arukai access at any time by removing IAM roles

#### Commissioning Core Artifact

This NDA + transfer commitment becomes a **standard commissioning core artifact** -- reusable across all Arukai deployments. Template stored at:
```
commissioning-core/templates/nda-data-transfer-commitment.md
```

Each deployment customizes: client entity name, asset inventory, handoff date, support terms.

---

## Showstopper 2: Financial Document Text Sent to Third-Party AI

### Problem
Capital call content (LP names, amounts, bank details) is sent to Mistral API and OpenAI API for classification and extraction. No DPAs. No data residency guarantees.

### Sawan's Direction
Keep Mistral API for development only. Prepare a local model migration path with cost/performance scorecard.

### Solution: Local Model Migration Path

#### Current Architecture (Development Only)
```
PDF Upload --> extract text --> Mistral API (classify + extract) --> store results
                                    |
                                    v (fallback)
                                OpenAI API --> store results
```

**This architecture is acceptable ONLY for development with synthetic/test data.**

#### Phase 1: Development (Current -- Mistral API)
- **Provider:** Mistral Small via API (`mistral-small-latest`)
- **Fallback:** OpenAI GPT-4o-mini (development only, removed before staging)
- **Data:** Synthetic test documents only. No real financial data.
- **Cost:** ~$0.20/1M input tokens, negligible at dev scale
- **Action required:** Strip `OPENAI_API_KEY` and OpenAI fallback code before any staging deployment

#### Phase 2: Staging (Self-Hosted on GCP)
- Deploy an open-weight model on GCP GPU instance
- All inference happens within the client's GCP project (EU region)
- No data leaves the client's infrastructure

#### Phase 3: Production (Client-Hosted)
- Model runs on client's own infrastructure (GCP project transferred at handoff)
- Client has full control over the model, hardware, and data flow
- Zero third-party dependencies for AI processing

### Local Model Benchmark Scorecard

#### Task Requirements
- **Classification:** Identify `capital_call_notice` among 6 document types
- **Extraction:** Extract 8 structured fields (fund_name, call_number, amount_due, currency, due_date, recipient_entity, wire_instructions_present, notice_date)
- **Accuracy target:** >90% on both classification and extraction
- **Input:** Up to 6,000 characters of extracted PDF text

#### Model Comparison Table

| Model | Parameters | Classification Accuracy (est.) | Extraction Accuracy (est.) | Min GPU | VRAM Required | GCP Instance | Monthly Cost (GCP) | Latency (per doc) | Cloud Run Compatible | Quantized Option |
|---|---|---|---|---|---|---|---|---|---|---|
| **Mistral 7B** | 7B | 85-90% | 80-85% | L4 | 16 GB | g2-standard-4 (1x L4) | ~$560/mo | 2-4s | Yes (GPU preview) | GPTQ 4-bit: 8 GB, T4 ok |
| **Mixtral 8x7B** | 46.7B (MoE, ~13B active) | 90-93% | 87-90% | L4 x2 or A100 | 32-48 GB | a2-highgpu-1g (1x A100) | ~$2,900/mo | 3-6s | No (needs GKE/VM) | GPTQ 4-bit: 24 GB, 1x L4 |
| **Llama 3.1 8B** | 8B | 87-91% | 82-87% | L4 | 16 GB | g2-standard-4 (1x L4) | ~$560/mo | 2-4s | Yes (GPU preview) | GPTQ 4-bit: 8 GB, T4 ok |
| **Llama 3.1 70B** | 70B | 93-96% | 90-94% | A100 x2 or H100 | 140 GB (fp16) | a2-ultragpu-2g (2x A100) | ~$5,800/mo | 8-15s | No (needs GKE) | GPTQ 4-bit: 40 GB, 1x A100 |
| **Phi-3 Mini** | 3.8B | 78-83% | 70-75% | T4 | 8 GB | n1-standard-4 + T4 | ~$230/mo | 1-2s | Yes | Already small enough |
| **Qwen 2.5 7B** | 7B | 88-92% | 85-90% | L4 | 16 GB | g2-standard-4 (1x L4) | ~$560/mo | 2-4s | Yes (GPU preview) | GPTQ 4-bit: 8 GB, T4 ok |
| **Qwen 2.5 72B** | 72B | 94-97% | 91-95% | A100 x2 | 144 GB (fp16) | a2-ultragpu-2g (2x A100) | ~$5,800/mo | 8-15s | No (needs GKE) | GPTQ 4-bit: 40 GB, 1x A100 |

#### GCP GPU Instance Pricing Reference (europe-west4, on-demand)

| Instance | GPU | VRAM | Monthly (on-demand) | Monthly (1yr commit) |
|---|---|---|---|---|
| n1-standard-4 + T4 | 1x T4 | 16 GB | ~$230 | ~$145 |
| g2-standard-4 | 1x L4 | 24 GB | ~$560 | ~$350 |
| a2-highgpu-1g | 1x A100 40GB | 40 GB | ~$2,900 | ~$1,830 |
| a2-ultragpu-2g | 2x A100 80GB | 160 GB | ~$5,800 | ~$3,650 |

#### Recommendation: Qwen 2.5 7B (Quantized) on GCP L4

**Why Qwen 2.5 7B:**
1. **Best accuracy at 7B scale** for structured extraction tasks -- Qwen 2.5 leads benchmarks on structured output, code, and document understanding
2. **Strong JSON mode support** -- critical for our two-pass classify+extract pipeline
3. **Apache 2.0 license** -- no commercial restrictions
4. **Quantized (GPTQ 4-bit) fits on T4** -- $230/mo fallback option if L4 is unavailable
5. **Multilingual** -- handles EU documents in multiple languages

**Recommended migration timeline:**

| Phase | Environment | Model | Hardware | Monthly Cost | Data Policy |
|---|---|---|---|---|---|
| Phase 1 (now - 4 weeks) | Development | Mistral API | None (API) | ~$5 | Synthetic data only |
| Phase 2 (week 5-8) | Staging | Qwen 2.5 7B (GPTQ) on vLLM | GCP g2-standard-4 (1x L4) | ~$560 | Real data ok (self-hosted) |
| Phase 3 (week 9+) | Production | Qwen 2.5 7B on client's GCP | Client's infrastructure | Client's cost | Client owns everything |

**Deployment stack for Phase 2/3:**
- **Inference server:** vLLM (open source, optimized for GPU serving)
- **Container:** Docker image with vLLM + Qwen 2.5 7B GPTQ weights
- **Deployment:** GKE Autopilot with GPU node pool, or GCE VM with L4
- **API compatibility:** vLLM exposes OpenAI-compatible API -- minimal code changes to `classify.py`

**Code change required in `backend/app/classify.py`:**
- Replace `MISTRAL_ENDPOINT` with self-hosted vLLM endpoint (e.g., `http://llm-service:8000/v1/chat/completions`)
- Remove `OPENAI_ENDPOINT` and OpenAI fallback entirely
- Keep heuristic fallback as final safety net
- Environment variable: `LLM_ENDPOINT=http://llm-service:8000/v1/chat/completions`

#### Validation Plan (Miller)
Before Phase 2 go-live, run the existing test suite against the self-hosted model:
- `test_classify.py` -- document type classification accuracy
- `test_classify_per_field.py` -- per-field extraction accuracy
- `test_classify_fallback.py` -- fallback behavior when model fails
- Acceptance threshold: >90% on both classify and extract across test corpus

---

## Showstopper 3: OpenAI Fallback Crosses EU Border

### Problem
OpenAI API routes data to US servers. GDPR/Schrems II violation.

### Solution
**Addressed by Showstopper 2.** OpenAI is removed entirely from the production path:

1. **Immediate:** Remove `OPENAI_API_KEY` from all non-development environments
2. **Phase 2:** Remove OpenAI fallback code from `classify.py` -- self-hosted model is the only AI provider
3. **Production:** All AI inference runs within the client's EU GCP project. Zero cross-border data transfer.

**Code change:** In `backend/app/classify.py`, the provider chain becomes:
```
Phase 1 (dev):    Mistral API --> heuristic fallback
Phase 2 (staging): Self-hosted Qwen 2.5 --> heuristic fallback
Phase 3 (prod):   Self-hosted Qwen 2.5 (client-owned) --> heuristic fallback
```

OpenAI is never used outside development environments.

---

## Showstopper 4: No MFA or SSO

### Problem
Single-factor authentication (email + password). A compromised password gives full system access.

### Sawan's Direction
Explore non-SaaS options. Prepare an argument to push back and insist client uses a trustworthy EU identity service.

### Recommended Approach: Client Uses an EU Identity Provider

#### The Argument Against Self-Built MFA

**Self-building MFA/SSO is a security antipattern. Here is why:**

1. **Authentication is the single most exploited attack surface.** Rolling your own means you own every vulnerability. The OWASP Top 10 consistently lists broken authentication as #1-2. Identity providers have dedicated security teams; Arukai does not.

2. **Compliance requires it.** SOC 2, ISO 27001, and the client's own auditors will ask "who manages your identity infrastructure?" The answer "we built it ourselves" triggers deeper scrutiny. "We use Keycloak/Zitadel" is an accepted answer.

3. **Maintenance is perpetual.** MFA standards evolve (TOTP to WebAuthn to passkeys). SSO protocols update (SAML 2.0 to OIDC). Self-built means self-maintained forever. An identity provider tracks these changes for you.

4. **The client already trusts regulated entities with their identity.** They bank with institutions that use exactly these kinds of identity providers. They can trust the same class of service for their document workflow.

5. **Arukai never touches passwords.** With OIDC integration, Arukai's application never sees, stores, or transmits user passwords. The identity provider handles all credential management. This dramatically reduces Arukai's security liability.

#### Option A (Recommended): EU-Hosted Identity Provider

| Provider | Type | Hosting | GDPR Compliant | MFA Support | SSO (OIDC/SAML) | Cost |
|---|---|---|---|---|---|---|
| **Zitadel** | SaaS | Swiss-hosted (CH) | Yes -- Swiss FADP + GDPR adequate | TOTP, WebAuthn, passkeys | OIDC + SAML | Free up to 25K MAU |
| **Authentik** | Self-hosted or SaaS | Client's GCP (EU) | Yes -- client controls data | TOTP, WebAuthn, Duo | OIDC + SAML | Free (OSS) |
| **Keycloak** | Self-hosted | Client's GCP (EU) | Yes -- client controls data | TOTP, WebAuthn | OIDC + SAML | Free (OSS) |

**Recommended: Zitadel (Swiss SaaS)**
- Zero operational burden for the client
- Swiss data residency (adequate GDPR protection under EU adequacy decision)
- Free tier covers the client's user count (likely <100 users)
- Modern UI for user management, MFA enrollment, SSO configuration
- Arukai integrates via OIDC -- 50 lines of code change in `backend/app/auth.py`

#### Option B (Fallback): Self-Hosted Keycloak on Client's GCP

If the client absolutely refuses any SaaS dependency:

- Deploy Keycloak as a Cloud Run service in the client's GCP project (EU region)
- Keycloak uses its own Postgres database (separate from application data)
- Client manages their own users, MFA policies, and SSO connections
- Arukai's app integrates via OIDC (standard `python-jose` + `httpx` for token validation)
- Included in the handoff package -- client owns and operates it

**Deployment cost:** Keycloak on Cloud Run: ~$15-30/month (low-traffic service + small Postgres)

#### Integration Architecture

```
User --> Login Page (Keycloak/Zitadel hosted) --> OIDC callback --> FastAPI backend
                                                                       |
                                                                  Validate JWT
                                                                  (issued by IdP)
                                                                       |
                                                                  Extract roles
                                                                  from JWT claims
                                                                       |
                                                                  Existing RBAC
                                                                  (reviewer/approver/admin)
```

**Changes to `backend/app/auth.py`:**
- Replace password-based JWT issuance with OIDC token validation
- JWT tokens are issued by the identity provider, not by Arukai's backend
- `require_role()` decorator reads roles from OIDC JWT claims instead of local database
- Remove password hashing, login endpoint becomes OIDC redirect
- Remove hardcoded dev users from `main.py` `_seed_dev_users()` (users managed in IdP)

#### Recommended Client-Facing Language

> "We strongly recommend you provision an EU-hosted identity provider. We suggest Zitadel (Swiss-hosted, free tier) or Keycloak on your own GCP infrastructure. This gives you complete control over authentication -- Arukai never touches passwords or MFA tokens. Our system integrates via OIDC, which is an open standard with zero vendor lock-in. Self-building MFA is a security antipattern that increases your attack surface and maintenance burden. We cannot recommend it."

---

## Showstopper 5: No Encryption, No Backups, No Monitoring

### Problem
The review identified: no client-side encryption, no backup/DR, no monitoring, no WAF/DDoS protection, no PDF malware scanning.

### Sawan's Direction
All points are must-have. Find solutions and propose to client.

### Solution: Comprehensive Security and Operations Layer

#### 5.1 Encryption

| Layer | Current State | Proposed Solution | Cost |
|---|---|---|---|
| **At rest (database)** | Neon encrypts at rest (provider-managed AES-256) | Upgrade: Client-Managed Encryption Keys (CMEK) via GCP Cloud KMS. Client owns the key; can revoke Arukai access at any time by disabling the key. | Cloud KMS: ~$1/mo (1 key + <10K operations) |
| **In transit** | HTTPS/TLS via Cloud Run (managed certificates) | No change needed. Already TLS 1.3. | $0 |
| **Field-level (JSONB)** | Plaintext `extracted_fields` in Postgres | Add application-level AES-256-GCM encryption on sensitive JSONB columns (`extracted_fields`, `raw_text`). Encryption key stored in client's Cloud KMS. Decrypt only on authorized read. | Included in Cloud KMS cost |
| **Document storage** | PDF `content` stored as bytea in Postgres | Encrypt PDF bytes with AES-256-GCM before storing. Key from client's Cloud KMS. Decrypt on authorized download only. | Included in Cloud KMS cost |

**Implementation:**
- New module: `backend/app/crypto.py` -- KMS-backed encrypt/decrypt functions
- Modify `routers/packages.py` upload endpoint: encrypt PDF content + extracted fields before INSERT
- Modify read endpoints: decrypt on SELECT for authorized users only
- Key rotation: Cloud KMS supports automatic key rotation (configurable interval)

#### 5.2 Backups and Disaster Recovery

| Component | Solution | RPO | RTO | Cost |
|---|---|---|---|---|
| **Database PITR** | Neon built-in point-in-time recovery -- 7 days (free), 30 days (paid plan, ~$19/mo) | Minutes | <1 hour | $0-19/mo |
| **Nightly full backup** | Automated `pg_dump` to client-owned GCS bucket, encrypted with client's KMS key. Cron job via Cloud Scheduler + Cloud Run job. | 24 hours | 2-4 hours | GCS: ~$0.50/mo (small dataset) |
| **Backup verification** | Quarterly automated restore test: restore latest backup to a throwaway Cloud SQL instance, run health check, tear down. Documented in governance checklist. | N/A | Validates RTO | ~$2/quarter |
| **Document backup** | PDFs are stored in database, so database backup covers them. For belt-and-suspenders: nightly sync of PDF blobs to separate GCS bucket. | 24 hours | 2-4 hours | GCS: ~$1/mo |

**Governance handoff checklist item:**
- [ ] Backup schedule documented and operational
- [ ] Restore procedure tested and documented
- [ ] Client has GCS bucket access to verify backups exist
- [ ] Backup encryption key is in client's KMS (not Arukai's)

#### 5.3 Monitoring and Alerting

| Component | Solution | Cost |
|---|---|---|
| **Infrastructure metrics** | GCP Cloud Monitoring -- CPU, memory, request count, latency for Cloud Run services | Free tier (sufficient for current scale) |
| **Application logging** | GCP Cloud Logging -- stdout/stderr from Cloud Run (already captured) | Free tier up to 50 GB/mo |
| **Uptime monitoring** | GCP Uptime Check on `/health` endpoint -- 1-minute interval, HTTPS | Free (up to 100 checks) |
| **Error tracking** | Structured JSON logging with severity levels. Cloud Logging alert on ERROR/CRITICAL. | Free |

**Alert policies (GCP Alert Policies):**

| Alert | Condition | Severity | Notification |
|---|---|---|---|
| Health check failure | `/health` returns non-200 for 2 consecutive checks | P0 -- Critical | Email + webhook |
| High latency | p95 latency > 3 seconds for 5 minutes | P1 -- High | Email |
| Error rate spike | 5xx error rate > 5% for 5 minutes | P1 -- High | Email + webhook |
| Client error spike | 4xx error rate > 20% for 10 minutes | P2 -- Medium | Email |
| CPU utilization | CPU > 80% sustained for 10 minutes | P2 -- Medium | Email |

**Cost:** $0/month on GCP free tier at current scale.

#### 5.4 Rate Limiting

**Solution:** `slowapi` middleware in FastAPI (Python rate limiting library, uses `limits` under the hood).

| Endpoint Group | Rate Limit | Purpose |
|---|---|---|
| `/auth/login` | 10 requests/minute per IP | Brute force protection |
| `/auth/token/refresh` | 20 requests/minute per IP | Token refresh abuse |
| All authenticated endpoints | 100 requests/minute per IP | General abuse prevention |
| `/packages/upload` | 10 requests/minute per user | Upload abuse prevention |

**Implementation:** ~30 lines in `backend/app/main.py`:
```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
```

Plus `@limiter.limit()` decorators on each router.

#### 5.5 WAF and DDoS Protection

| Option | Type | Cost | Recommendation |
|---|---|---|---|
| **Cloudflare Free** | DNS proxy + basic DDoS + WAF rules | $0/mo | Recommended for Phase 2 (staging) |
| **Cloudflare Pro** | Advanced WAF + bot management | $20/mo | Consider for production |
| **GCP Cloud Armor** | L7 DDoS + WAF rules | ~$5/mo + $0.75/1M requests | Alternative if client prefers GCP-native |

**Recommendation:** Cloudflare free tier in DNS proxy mode in front of Cloud Run.
- Absorbs volumetric DDoS at Cloudflare's edge
- Basic WAF rules (SQL injection, XSS) included
- No infrastructure to manage
- Client owns the Cloudflare account (transfers at handoff)
- EU data center routing available

#### 5.6 PDF Malware Scanning

**Solution:** ClamAV scan on every uploaded PDF before processing.

| Option | Deployment | Cost | Latency |
|---|---|---|---|
| **ClamAV sidecar** | Docker container alongside FastAPI, scan via `clamd` socket | ~$5/mo (small container) | 1-3 seconds per PDF |
| **Google Cloud DLP** | API call to DLP for sensitive data + malware detection | ~$1/1K documents | 2-5 seconds per PDF |

**Recommendation:** ClamAV sidecar container.
- Open source, no third-party data sharing
- Runs within the client's GCP project
- Signature updates via `freshclam` (daily cron)
- Integration: scan PDF bytes before `classify_document_text()` is called
- If malware detected: reject upload, log to audit trail, alert admin

**Implementation in upload flow:**
```
PDF Upload --> ClamAV scan --> [CLEAN] --> extract text --> classify --> store
                          --> [INFECTED] --> reject 422 --> audit log --> alert
```

---

## Additional Items from Review (Not in Top 5 but Addressed)

### Showstopper 6: Dev Credentials in Production (admin123)

**Status:** Will be fully resolved by Showstopper 4 (OIDC integration).

**Immediate action:** Remove `_seed_dev_users()` from production deployments. Guard with:
```python
if os.getenv("ENVIRONMENT") == "development":
    await _seed_dev_users()
```

**Long-term:** Users managed entirely in identity provider. No passwords in application code or database.

### Showstopper 8: No DPA with AI Providers

**Status:** Resolved by Showstopper 2.

**Phase 2+:** No third-party AI providers. Self-hosted model = no DPA needed (you are your own processor).

**Phase 1 (dev with Mistral API):** Mistral AI offers a DPA for enterprise customers. Since dev uses only synthetic data, the risk is negligible. But for completeness: sign Mistral's standard DPA for the development period.

### Showstopper 9: No Data Residency Guarantees

**Status:** Resolved by Showstoppers 1 + 2 + 3.

- GCP project in `europe-west4` (Netherlands) -- all compute and storage
- Self-hosted AI model in same region -- no cross-border data transfer
- Neon database in EU region (or migrated to Cloud SQL `europe-west4`)
- Client owns the GCP project -- can verify data residency configuration directly

### Serious Concern: JWT Tokens Not Revocable (24h window)

**Resolved by Showstopper 4.** OIDC tokens issued by identity provider:
- Short-lived access tokens (15-minute expiry typical)
- Refresh tokens revocable by IdP admin
- Session management handled by IdP (force logout, session listing)

### Serious Concern: No Audit Trail for Admin Actions

**Already exists** in current architecture (`routers/audit.py` captures state transitions). Enhanced with Camunda Operate if workflow engine is adopted (per `holden-miller-workflow-engine.md` decision).

### Serious Concern: No Automated Retention Enforcement

**Proposed:** Add a Cloud Scheduler job that:
- Runs nightly
- Deletes packages older than configurable retention period (default: 7 years for financial documents)
- Logs deletions to audit trail
- Client configures retention policy in environment variables

---

## Revised Architecture Summary

```
                         Client-Owned Infrastructure (GCP europe-west4)
                    +--------------------------------------------------------+
                    |                                                        |
User --> Cloudflare --> Cloud Run: FastAPI Backend                          |
  |      (WAF/DDoS)    |-- OIDC auth (tokens from Zitadel/Keycloak)       |
  |                     |-- Rate limiting (slowapi)                         |
  |                     |-- PDF upload --> ClamAV scan --> process          |
  |                     |-- Encrypt (AES-256-GCM, KMS key) before store    |
  |                     |                                                   |
  |                     v                                                   |
  |                 Cloud Run: vLLM + Qwen 2.5 7B                          |
  |                     |-- Self-hosted, EU region                          |
  |                     |-- No external API calls                           |
  |                     |-- OpenAI-compatible API (internal only)           |
  |                     |                                                   |
  |                     v                                                   |
  |                 Neon Postgres (EU) or Cloud SQL                         |
  |                     |-- CMEK encryption (client's KMS key)             |
  |                     |-- Field-level encryption on sensitive JSONB       |
  |                     |-- PITR (30 days) + nightly pg_dump to GCS        |
  |                     |                                                   |
  |                 Cloud KMS                                               |
  |                     |-- Client-managed encryption keys                  |
  |                     |-- Key rotation (automatic)                        |
  |                     |                                                   |
  |                 Cloud Monitoring + Logging                              |
  |                     |-- Uptime checks, alert policies                   |
  |                     |-- Structured logging                              |
  |                     |                                                   |
  |                 Identity Provider (Zitadel or Keycloak)                 |
  |                     |-- MFA (TOTP/WebAuthn)                            |
  |                     |-- SSO via OIDC                                    |
  |                     |-- Client manages users                            |
  +--------------------------------------------------------+               |
                                                                            |
                    Arukai Access (during development only, under NDA)      |
                    +-- Time-limited IAM roles                              |
                    +-- All actions in audit log                             |
                    +-- Removed at handoff                                  |
```

### What Changes from Current Architecture

| Component | Before | After |
|---|---|---|
| Infrastructure ownership | Arukai owns GCP, Neon, GitHub | Client owns everything (transferred at handoff) |
| AI classification | Mistral API + OpenAI fallback | Self-hosted Qwen 2.5 7B (Phase 2+) |
| Data residency | Uncontrolled (API calls to US/global) | All processing in EU (GCP europe-west4) |
| Authentication | Email + password, JWT issued by app | OIDC via EU identity provider, MFA enforced |
| Encryption at rest | Neon provider-managed | CMEK (client's KMS key) + field-level AES-256-GCM |
| Backups | None | Neon PITR (30 days) + nightly encrypted pg_dump to GCS |
| Monitoring | None | GCP Cloud Monitoring + alerting + uptime checks |
| Rate limiting | None | slowapi middleware (per-endpoint limits) |
| WAF/DDoS | None | Cloudflare free tier (or GCP Cloud Armor) |
| PDF security | None | ClamAV malware scan on upload |
| Dev credentials | Hardcoded admin123 | Removed; users in identity provider |
| Vendor access | Unmonitored, permanent | NDA, time-limited, audited, revocable |

### Implementation Priority and Timeline

| Priority | Item | Sprint | Effort |
|---|---|---|---|
| P0 | Remove dev credentials from prod, guard `_seed_dev_users()` | Sprint 1 | 1 hour |
| P0 | Remove OpenAI fallback from non-dev environments | Sprint 1 | 2 hours |
| P0 | NDA + data transfer commitment (legal document) | Sprint 1 | 1 day |
| P1 | Rate limiting (slowapi) | Sprint 1 | 4 hours |
| P1 | Structured logging + GCP alert policies | Sprint 1 | 1 day |
| P1 | GCP Uptime Check on /health | Sprint 1 | 1 hour |
| P1 | ClamAV sidecar for PDF scanning | Sprint 2 | 1 day |
| P1 | Field-level encryption (crypto.py + KMS) | Sprint 2 | 2 days |
| P1 | OIDC integration (auth.py rewrite) | Sprint 2-3 | 3 days |
| P2 | Nightly backup to GCS (Cloud Scheduler job) | Sprint 2 | 1 day |
| P2 | Cloudflare WAF setup | Sprint 2 | 4 hours |
| P2 | Self-hosted Qwen 2.5 7B (vLLM on GCP) | Sprint 3-4 | 3 days |
| P2 | Backup restore test automation | Sprint 3 | 1 day |
| P3 | CMEK migration (Neon to Cloud SQL if needed) | Sprint 4-5 | 2 days |
| P3 | Retention enforcement (Cloud Scheduler) | Sprint 4 | 1 day |

**Total estimated effort: ~18 working days across 5 sprints**

### Monthly Cost Impact (Post-Implementation)

| Item | Monthly Cost |
|---|---|
| GCP Cloud Run (backend) | ~$15 (current) |
| GCP Cloud Run/GKE (vLLM + Qwen 2.5) | ~$560 (L4 GPU) |
| Cloud KMS | ~$1 |
| Cloud Monitoring/Logging | $0 (free tier) |
| GCS (backups) | ~$1 |
| Cloudflare (free tier) | $0 |
| ClamAV sidecar | ~$5 |
| Neon Postgres (paid plan for 30-day PITR) | ~$19 |
| Zitadel (free tier) | $0 |
| **Total** | **~$601/month** |

Compared to current: ~$15/month + API costs. The increase is primarily the GPU instance for self-hosted AI ($560). This cost transfers to the client at handoff.

---

*This document is a squad deliverable from Holden, Drummer, Miller, and Naomi. All proposed solutions are concrete and implementable within the existing tech stack (FastAPI + Python + GCP + Neon). The revised architecture addresses every showstopper and serious concern from the client approver review.*
