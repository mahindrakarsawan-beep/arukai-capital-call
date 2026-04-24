# Contracts & DPAs

This directory holds countersigned Data Processing Agreements (DPAs) and related
vendor correspondence for every third-party processor that touches Arukai
Capital Call data. It is the source of truth Sawan (or counsel) should point to
when a prospective client's compliance team asks "who touches our LP data, and
do you have paper on them?"

## What lives here

- Countersigned DPA PDFs from each processor (vendor-side templates, signed by
  both parties).
- Vendor correspondence that materially affects our processing posture (sub-
  processor-change notifications, incident disclosures, retention-policy
  clarifications received in writing).
- Draft outbound requests in `drafts/` — e.g. the initial DPA-request emails
  before the vendor's paper comes back.

This directory is **not** a place to park unsigned vendor redlines or
negotiation drafts with confidential counterparty comments. Keep those in a
private legal workspace; only the final countersigned artifact lands here.

## Third-party processors we touch today

| Vendor | Endpoint / surface | Role | Region | DPA status |
|---|---|---|---|---|
| Mistral AI | `api.mistral.ai` | Classification + extraction of capital-call PDFs. **Primary** model provider — sits on the production data path. | EU (France) | **Required before signed pilot.** See `drafts/dpa-request-mistral.md`. |
| OpenAI | `api.openai.com` | Client-persona adversarial review only (GPT-4o-mini + GPT-4o as paranoid family-office COO). **Not** on the production pipeline today — reviews our product output, not LP data. | US (Ireland entity available for Enterprise) | **Required if we keep it in-loop.** If retired, document retirement here. See `drafts/dpa-request-openai.md`. |
| Google Cloud Platform | Cloud Run, GCE, Secret Manager, Artifact Registry, GCS, KMS | Hosting + infra. Project: `arukai-testbed`, region: `europe-west4`. | EU (NL) | Covered by GCP Terms + Google Cloud DPA. No bespoke signature needed. |
| Neon | `neon.tech` | Managed Postgres for staging environment. | AWS `eu-central-1` (Frankfurt) | Covered by Neon's standard DPA. |
| GitHub | `github.com` | Source hosting, private repo. | US (MS-owned) | Covered by GitHub's standard DPA. |

Vendor-side DPA links (treat these as the canonical text — do not re-host):

- **Google Cloud DPA:** https://cloud.google.com/terms/data-processing-addendum
- **Neon DPA:** https://neon.tech/dpa
- **GitHub DPA:** https://github.com/customer-terms/github-data-protection-agreement

## Policy

Before any signed client pilot (i.e. before the first real LP PDF from a paying
client hits our pipeline), the following must be true:

1. **Mistral DPA countersigned** and stored here. This is non-negotiable —
   Mistral sits on the production data path and processes personal data of LP
   natural persons under GDPR.
2. **OpenAI DPA countersigned** *or* a written decision recorded here that
   OpenAI has been retired from every code path (production and review). If
   retired, the decision note must name the commit that removes the
   integration.
3. **GCP, Neon, GitHub:** rely on vendor-side DPAs linked above. No bespoke
   signature needed unless a client's compliance team specifically asks for a
   pass-through — in which case Arukai can point to the vendor DPA and provide
   evidence of the subscription.

No signed-pilot engagement starts without (1) and (2) satisfied. Holden +
Sawan jointly enforce this gate.

## Filename convention

```
dpa-<vendor>-<YYYY-MM-DD-signed>.pdf
```

Examples:

- `dpa-mistral-2026-05-14-signed.pdf`
- `dpa-openai-2026-06-02-signed.pdf`

One file per countersigned version. If a DPA is amended, drop the new fully-
countersigned PDF alongside the old one — do not overwrite. The newest date
wins.

Never commit:

- Pre-signature drafts containing vendor-side redlines or bracketed counsel
  comments (those belong in a private legal workspace).
- DPAs that are signed by only one party.
- Scans or photos of paper copies without OCR — if we're going to rely on it,
  it must be text-searchable.

## Related

- `docs/contracts/drafts/` — outbound DPA-request email drafts (pre-send).
- `docs/RETENTION_POLICY.md` — our internal retention posture, which must be
  consistent with whatever the vendor DPAs say about their retention.
- `docs/INCIDENT_RESPONSE.md` — incident-notification SLAs we commit to
  downstream, which constrain what we can accept from vendors upstream (we
  need ≤24h from them to meet our downstream obligations).
