# DPA request — OpenAI

**Status:** draft, pre-send. Review with counsel before sending.

**Intended recipients:** OpenAI's DPA self-service flow is the usual path —
Enterprise customers can generate a countersigned DPA from the dashboard at
https://platform.openai.com (Settings → Compliance → Data Processing
Addendum). For non-Enterprise accounts, route via
https://openai.com/form/data-processing-addendum. If bespoke redlines are
needed, escalate via `dpa@openai.com` or the enterprise-sales contact.
Confirm the correct counterparty entity before signing — OpenAI LLC (US) and
OpenAI Ireland Ltd have different signing posture; Ireland is typically the
appropriate counterparty for EU-resident data exporters but **verify with
counsel**.

---

**Subject:** DPA request — Arukai Capital Call (financial services, EU data)

Hello,

I'm Sawan Mahindrakar, founder of Arukai, a financial-services software
vendor building automated capital-call processing for European private-fund
investors. We need to put a Data Processing Agreement in place to cover our
current use of the OpenAI API, and to pre-clear the posture in case our use
expands.

### Company identification and current scope

- **Vendor:** Arukai (legal entity and VAT number provided at signature).
- **Product:** Arukai Capital Call — closed-beta SaaS product.
- **Models in use:** `gpt-4o-mini` and `gpt-4o`, called via `api.openai.com`.
- **Current use case — important:** OpenAI is used **only** for adversarial
  client-persona review. We prompt GPT-4o to act as a paranoid family-office
  COO reviewing our own product's output, as an internal QA gate. **No LP
  personal data or capital-call PDFs are sent to OpenAI in the production
  pipeline today.** If that changes — i.e. if we ever put OpenAI on the
  production data path — we will re-scope this agreement before doing so.
- **Current volume:** small, under 1,000 requests per month, bursty around
  release reviews.

### Data categories sent today

Under the current adversarial-review scope:

- Product output text (structured JSON extracted by our pipeline from
  capital-call PDFs, plus our own UI copy and reasoning traces).
- Synthetic / fixture LP names and amounts used in staging reviews.
- No real LP personal data, no real wire instructions, no production PDFs.

We still want a DPA in place because (a) synthetic data is not a legal
guarantee of non-personal-data, (b) some of our staging fixtures are derived
from real documents with redaction, and (c) our downstream clients will ask.

### Specific asks

1. **Latest DPA.** Please confirm the current DPA version and either send it
   or point me at the self-service flow. Confirm the correct signing
   counterparty (OpenAI LLC, OpenAI Ireland Ltd, or other) for a vendor
   incorporated in <jurisdiction to fill in> processing data of EU-resident
   end users.
2. **EU data-residency.** Please confirm whether our account can be moved to
   the European data-residency option (we understand this is an Enterprise
   feature), and what the path looks like if we want to take it — pricing
   tier, minimum commit, timeline.
3. **Zero data retention (ZDR) via API.** Please confirm in writing that ZDR
   is available for our account, what it covers exactly (prompt, completion,
   embeddings, fine-tuning data, abuse-detection telemetry), and any
   endpoints that are out of scope. We know ZDR exists as a product feature;
   we need it named in the contract.
4. **Sub-processor list.** Current sub-processors with role, region, and DPA
   status, so we can flow them through to downstream clients.
5. **Incident-notification SLA.** Our downstream client contracts require us
   to notify within 24 hours of confirmed incident. Please confirm the
   notification SLA you can commit to and the channel.

Happy to sign an NDA first if needed. Please let me know the right contact on
your side.

Thanks,

Sawan Mahindrakar
Founder, Arukai
<email placeholder — insert before send>
