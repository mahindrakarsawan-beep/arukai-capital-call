# Client Approver Re-Review -- Revised Architecture v0.2.1

**Date:** 2026-04-15
**Reviewers:** Mistral Large (Client Approver 1) + GPT-4o (Client Approver 2)
**Persona:** AI-skeptic family office operator, $500M+ AUM, paranoid about data privacy
**Input:** Revised Architecture Brief v0.2.1 (all 5 showstoppers addressed per Sawan's direction)

---

## Verdict Summary

| Reviewer | Verdict |
|---|---|
| Mistral Large | **CONDITIONALLY APPROVED** |
| GPT-4o | **APPROVED** |

**Combined verdict: CONDITIONALLY APPROVED** -- all 9 showstoppers resolved, 1 remaining condition (SOC 2 / ISO 27001 certification).

---

## Showstopper Resolution Status

| # | Showstopper | Mistral | GPT-4o |
|---|---|---|---|
| 1 | Arukai has full unmonitored access to all data | RESOLVED | RESOLVED |
| 2 | AI providers receive extracted text from financial documents | RESOLVED | RESOLVED |
| 3 | OpenAI fallback sends data to the US | RESOLVED | RESOLVED |
| 4 | No client-side encryption | RESOLVED | RESOLVED |
| 5 | No backup or disaster recovery | RESOLVED | RESOLVED |
| 6 | Dev credentials in production (admin123) | RESOLVED | RESOLVED |
| 7 | No MFA or SSO | RESOLVED | RESOLVED |
| 8 | No DPA or BAA with AI providers | RESOLVED | RESOLVED |
| 9 | No data residency guarantees | RESOLVED | RESOLVED |

**All 9 showstoppers: RESOLVED by both reviewers.**

---

## Serious Concern Resolution Status

| # | Concern | Mistral | GPT-4o |
|---|---|---|---|
| 1 | No SOC 2 or ISO 27001 | STILL OPEN | PARTIALLY RESOLVED |
| 2 | No monitoring or alerting | RESOLVED | RESOLVED |
| 3 | No WAF or DDoS protection | RESOLVED | RESOLVED |
| 4 | JWT tokens not revocable (24h window) | RESOLVED | RESOLVED |
| 5 | No field-level encryption | RESOLVED | RESOLVED |
| 6 | No PDF malware scanning | RESOLVED | RESOLVED |
| 7 | No audit trail for admin actions | RESOLVED | RESOLVED |
| 8 | No automated retention enforcement | RESOLVED | RESOLVED |

**7/8 serious concerns: RESOLVED by both reviewers.**
**1 remaining: SOC 2 / ISO 27001 (governance gap, not technical).**

---

## Conditions for Full Approval (Mistral Large)

1. **Third-party audit:** Arukai must provide SOC 2 Type II report or ISO 27001 certification covering development practices before production deployment
2. **Key rotation policy:** Document and test Cloud KMS key rotation procedures
3. **Incident response plan:** Provide written IR plan for client integration

---

## Mistral Large Full Review

Client owns all infrastructure (GCP, Neon, GitHub, secrets). Post-handoff, Arukai retains zero access. Signed attestation of no data retention is a strong control.

Self-hosted Qwen 2.5 in client's EU GCP project. No third-party APIs in staging/prod. Mistral API used only in dev with synthetic data.

OpenAI fallback removed entirely from non-dev environments. No cross-border data flows.

Field-level (AES-256-GCM) and document-level encryption (PDF bytes) with keys in client's Cloud KMS. Decryption only on authorized access.

Neon PITR (30 days), nightly pg_dump to client-owned GCS, quarterly restore tests. RPO/RTO clearly defined.

All hardcoded credentials removed. Authentication via EU IdP (Zitadel/Keycloak) with MFA.

MFA enforced via EU IdP (OIDC). JWT tokens short-lived (15 min) and revocable.

No third-party AI in staging/prod = no DPA needed. Mistral DPA signed for dev (synthetic data only).

All compute, storage, and AI in EU (GCP europe-west4). Cloudflare WAF with EU routing. Zero cross-border transfers in staging/prod.

**Rationale for Conditional Approval:** The architecture now meets the technical bar for data privacy, residency, and security. The remaining SOC 2/ISO gap is procedural, not architectural, and can be addressed without redesign. The client retains full control over infrastructure and data, mitigating vendor risk.

---

## GPT-4o Full Review

Direct control and ownership of infrastructure by the client, with time-limited, audited Arukai access during development, addresses the data ownership concern.

The use of a self-hosted model for AI processing ensures no financial document text leaves the client's infrastructure. The removal of the OpenAI fallback and the use of a self-hosted AI model within the EU addresses cross-border data transfer.

Implementation of encryption at rest and field-level encryption, managed and owned by the client, resolves encryption concerns. Implementing point-in-time recovery, daily backups, and quarterly restore tests adequately addresses backup and recovery.

Removal of hardcoded dev credentials and the integration of a robust IdP addresses credential management. The use of an EU-hosted identity provider with MFA and session management fulfills requirements for strong authentication.

The shift to self-hosted AI in production means no DPA or BAA is necessary beyond the development phase. Stringent data residency practices with all infrastructure in the EU confirm regional data handling.

**Verdict: APPROVED.** All showstoppers have been resolved. Serious concerns have either been fully resolved or partially addressed to an acceptable degree. The architecture demonstrates a rigorous commitment to data privacy, security, and regulatory compliance.

---

## Delta from Previous Review

| Metric | v0.2 Review | v0.2.1 Re-Review |
|---|---|---|
| Verdict | NOT APPROVED | CONDITIONALLY APPROVED / APPROVED |
| Showstoppers open | 9 | 0 |
| Serious concerns open | 8 | 1 (SOC 2 -- governance, not technical) |
| Reviewer agreement | Both: NOT APPROVED | Both: APPROVED (with/without conditions) |

---

## Next Steps

1. Sawan reviews and approves the showstopper response document
2. Address Mistral's 3 conditions (SOC 2 timeline, key rotation docs, IR plan)
3. Begin Sprint 1 implementation (P0 items: dev creds, OpenAI removal, rate limiting, monitoring)
4. Present revised architecture to client with NDA + data transfer commitment
