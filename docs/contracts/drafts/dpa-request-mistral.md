# DPA request — Mistral AI

**Status:** draft, pre-send. Review with counsel before sending.

**Intended recipients:** `security@mistral.ai`, `support@mistral.ai`, or via
Mistral's enterprise-sales contact form at https://mistral.ai/contact. Prefer
`security@` if it resolves; otherwise route through enterprise sales and ask
them to forward. Confirm the correct DPA contact before sending — the
addresses above are best-guess and have not been verified against a Mistral
compliance directory.

---

**Subject:** DPA request — Arukai Capital Call (financial services, EU data)

Hello,

I'm reaching out on behalf of Arukai, a financial-services software vendor
building an automated capital-call-processing product for European private-
fund investors. We are currently using Mistral's inference API in a pre-pilot
staging environment and need to put a Data Processing Agreement in place
before our first signed client engagement.

### Company identification

- **Vendor:** Arukai (legal entity details and VAT number provided on
  request / at signature).
- **Product:** Arukai Capital Call — a closed-beta SaaS product that ingests
  capital-call PDFs and extracts structured data for LP back-offices.
- **Models in use:** `mistral-small-latest` (classification) and
  `mistral-large-latest` (extraction), called via `api.mistral.ai`.
- **Region:** Mistral EU endpoints only. We have no US-egress tolerance — see
  below.
- **Current volume:** small pilot, under 10,000 requests per month.
- **Production target volume:** unknown until our first signed pilot lands;
  we expect low-millions of requests per year at steady state across all
  clients, but will share firmer numbers once the first client is live.

### Data categories ingested

Our product sends capital-call PDFs to Mistral for classification and field
extraction. These documents routinely contain:

- Fund and share-class names.
- Dollar / euro amounts and due dates.
- **Investor (LP) names** — in the majority of cases these are natural
  persons or family-office entities where a natural person is identifiable.
- **Wire instructions** — bank account numbers, SWIFT/BIC codes, beneficiary
  names.

We classify this as **personal data** under GDPR Articles 4(1) and 9 (for the
LP natural persons) and as **sensitive financial data** under MiFID-adjacent
regulatory frameworks that apply to our clients. This classification drives
the asks below.

### Specific asks

1. **Latest DPA template.** Please send your most recent DPA template, ideally
   the post-2024 version that reflects both the GDPR Standard Contractual
   Clauses and any EU AI Act alignment Mistral has adopted.
2. **EU-only processing.** Please confirm in writing that inference on the
   models we use is performed exclusively on EU infrastructure with no US
   sub-processor in the hot path. Our clients are EU-resident family offices
   and funds that will not accept US egress of LP data under any circumstances
   — this is a hard gate on our ability to sign them.
3. **Retention on the inference endpoint.** We understand Mistral's default
   posture for the API is zero retention of prompt and completion content
   beyond transient processing. Please confirm this in writing, reference the
   specific product/endpoint it applies to, and note any logging that does
   persist (metadata, request counts, abuse-detection hashes, etc.) with
   retention windows.
4. **Sub-processor list.** Please share your current sub-processor list with
   each entity's role, region, and DPA status. We will need to flow these
   through to our clients.
5. **Incident-notification SLA.** Our downstream client contracts require us
   to notify within 24 hours of confirmed incident. Please confirm Mistral
   can meet a ≤24-hour notification SLA from the point of confirmation, and
   describe the notification channel (email address, webhook, customer-portal
   alert).
6. **EU AI Act Article 28 / Annex XI readiness.** If and when any of the
   Mistral models we use is classified as a general-purpose AI model with
   systemic risk under the EU AI Act, we may request the Annex XI data-
   governance, training-data-summary, and cybersecurity evidence required of
   providers of such models. We are flagging this now so it does not come as
   a surprise at contract time.

We're happy to sign an NDA before you share anything beyond the public DPA
template. Please let me know what the right path is on your side — whether
that's enterprise sales, legal, or a dedicated compliance contact — and I'll
route accordingly.

Thanks,

Sawan Mahindrakar
Founder, Arukai
<email placeholder — insert before send>
