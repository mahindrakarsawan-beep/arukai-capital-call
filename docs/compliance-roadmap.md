# Compliance roadmap — SOC 2 and ISO 27001

**Status:** roadmap, not attestation. No certification claim is made in this document.
**Owner:** Arukai engineering lead. Sign-off required from the client commissioning the
product before it is relied on for procurement due diligence.
**Last updated:** 2026-04-21 (POR-158 B2).

## Why this exists

GPT-4o client-persona re-review (2026-04-21) listed "No SOC 2 / ISO 27001 progress" as
one of the active showstoppers. This document closes the "no plan" gap by committing to
a sequenced audit path and documenting what we already control. Real certification
remains a ~12-18 month effort and depends on signed pilot revenue to fund auditor fees
and a continuous-monitoring platform.

## Current controls — mapped to SOC 2 CC series

The mappings below are our best-effort alignment of existing code and ops to the SOC 2
Common Criteria. They are not auditor-blessed — a real Type I audit will re-scope these
against the actual Trust Services Criteria in effect at audit time.

| Control | SOC 2 CC | Evidence |
|---|---|---|
| Role-based access (admin / approver / reviewer / uploader) | CC6.1 | `backend/app/auth.py` `require_role`; `backend/tests/test_auth.py` |
| Password policy (length, complexity, rotation) + session revocation | CC6.1 / CC6.2 | `backend/app/auth.py` `check_password_policy`; `backend/alembic/versions/0002_add_sessions_refresh_columns.py` |
| JWT + refresh session store | CC6.1 | `backend/app/models.py` Session model; `backend/app/auth.py` |
| Hash-chained audit ledger (SHA-256, tamper-evident) | CC7.3 | `backend/app/audit_chain.py`; `backend/tests/test_audit_hash_chain.py`; `GET /audit/verify` in `backend/app/routers/audit.py` |
| Append-only audit trigger (Postgres) | CC7.3 | `backend/alembic/versions/0001_v02_state_machine.py` trigger; `backend/alembic/versions/0003_audit_hash_chain.py` |
| Global audit log API (filtered, paginated, CSV export, admin+approver only) | CC7.2 / CC7.3 | `backend/app/routers/audit.py` (`GET /audit`, `GET /audit/export.csv`) |
| Nightly encrypted backups + 30-day lifecycle + CMEK | CC7.5 / A1.2 | `deploy/backup/README.md` (keyring `cc-backup`) |
| Input sanitization (filenames + headers) | CC6.6 | `backend/app/sanitizers.py`; `backend/tests/test_input_sanitization.py` |
| Operational runbook (staging) | CC7.1 / CC7.4 | `docs/runbook-gce-staging.md`; `docs/OPERATIONAL_RUNBOOK.md` |
| Incident response playbook (initial) | CC7.4 | `docs/INCIDENT_RESPONSE.md` (to be refined — see gaps) |
| Data retention policy | CC6.5 / C1.2 | `docs/RETENTION_POLICY.md` |
| Vendor-to-client infra transfer plan | CC9.2 | `docs/INFRASTRUCTURE_TRANSFER_PLAN.md` |

Structured application logging to Cloud Logging is planned but not yet implemented as a
dedicated module — current logging is via FastAPI defaults plus ad-hoc records in
`backend/app/classify.py`. Once a `backend/app/logging_config.py` (or equivalent) lands,
it will be added to this table under CC7.2.

## Gaps — and who closes them

| Gap | Description | Owner | Target |
|---|---|---|---|
| Risk assessment document | Written assessment of data-loss, availability, privacy, and provider-lockin risks with likelihood × impact scoring | Holden + product | Q3 2026 |
| Vendor management matrix | Per-vendor: DPA status, data categories exposed, sub-processor list, exit plan | Holden | Q2 2026 (blocks any pilot sign) |
| Incident response runbook (formal) | On-call rotation, severity definitions, comms templates, post-mortem format — extends `docs/INCIDENT_RESPONSE.md` | Drummer | Q3 2026 |
| Change management policy | PR review gates, deploy approvals, rollback SLAs. Most of this is already in-practice; needs write-up | Miller | Q2 2026 |
| Quarterly access review cadence | Checklist and log for reviewing who has prod access each quarter; tied to `require_role` assignments and Session rows | Holden | Q3 2026 |
| Centralized structured logging module | `logging_config.py` (or equivalent) emitting JSON to Cloud Logging, replacing ad-hoc loggers | Drummer | Q3 2026 |
| WAF + HTTPS termination | Cloudflare tunnel for VM endpoints, managed ruleset in front of Cloud Run | Drummer | POR-158 §C — blocked on client Cloudflare account |
| DPAs with AI providers | Mistral (FR), OpenAI (US) — countersigned PDFs in `docs/contracts/` | Holden | POR-158 #5 — blocked on vendor response |
| Continuous monitoring platform | Vanta, Drata, or Secureframe selection + connector rollout | Holden | 2026-Q4 (once pilot signed) |

## Sequenced audit path

| Phase | Timeline | Scope | Estimated spend |
|---|---|---|---|
| 0. Internal readiness | 2026-Q2 → 2027-Q1 | Close gaps above; adopt Vanta/Drata/Secureframe for continuous monitoring | $8-15k/yr platform + ~30% of one engineer's quarter in internal time |
| 1. SOC 2 Type I | 2027-Q3 | Point-in-time attestation over the CC6 / CC7 / CC8 / CC9 controls above | $15-25k auditor fees |
| 2. SOC 2 Type II | 2028-Q3 (12 months after Type I) | 12-month operating-effectiveness attestation, same scope | $25-40k auditor fees |
| 3. ISO 27001 (optional, client-driven) | 2028+ | Separate track; different auditor; EU-leaning clients will ask for this | $30-60k first year (Stage 1 + Stage 2), then ~$10-15k/yr surveillance |

HIPAA and PCI are intentionally out of scope — we do not process protected health
information or payment card data.

## Non-goals

- This roadmap does not commit to being "SOC 2 ready" before the first signed pilot.
  The controls above are what we have today; closing the gaps and paying for the audit
  is scoped once we have committed pilot revenue to fund it.
- We will not advertise certification status we do not hold. If a prospect asks "are
  you SOC 2 certified?" the honest answer is "not yet — we are at the roadmap stage
  described in `docs/compliance-roadmap.md`, and here is what we can show you today."
- This document is not a substitute for a real Trust Services Criteria gap analysis
  performed by a licensed CPA firm. It is a pre-readiness artifact.

## Risk-framing evidence already on file

- `.squad/decisions/inbox/client-approver-mistral-por159.md` — Mistral-Large-as-reviewer verdict (POR-159)
- `.squad/decisions/inbox/client-approver-openai-por159.md` — GPT-4o-as-reviewer verdict (POR-159)
- `docs/runbook-gce-staging.md` — current staging operational runbook
- `docs/OPERATIONAL_RUNBOOK.md` — broader operational runbook
- `docs/INCIDENT_RESPONSE.md` — initial incident response notes (to be hardened per gaps table)
- `docs/INFRASTRUCTURE_TRANSFER_PLAN.md` — tenant transfer plan (POR-158 #6)
- `docs/RETENTION_POLICY.md` — data retention policy
- `docs/superpowers/plans/2026-04-21-por158-replan.md` — sprint plan under superpowers methodology

## Revision discipline

This document is re-opened and updated:

1. Whenever a gap in the gaps table is closed (move the row up into the controls table
   with evidence paths).
2. Whenever a client-persona review (Mistral or GPT-4o) flags a new compliance concern
   — the concern lands as a new gap row with an owner.
3. Quarterly, as a scheduled review item on the engineering lead's calendar, even if
   nothing has changed — to confirm the timeline and cost estimates still hold.
