# Monitoring Guide — Arukai Capital Call (D2)

**Version:** 1.0.0
**Date:** 2026-04-12
**Handoff items:** H2 (partial), H3 (partial)
**Audience:** Operator admin

---

> **IMPORTANT — H2/H3 GAP:** Cloud Monitoring dashboard and alert policies are NOT YET configured for this deployment. This guide documents what monitoring will look like when configured, and provides manual procedures for the current state. Formal dashboard and alert setup is a known gap — see `KNOWN_ISSUES.md`.

---

## 1. Health Check (Available Now)

The backend exposes a `/health` endpoint for simple liveness verification.

### Manual check

```bash
curl -s https://arukai-capital-call-backend-staging-1035777337524.europe-west4.run.app/health
```

Expected output:
```json
{"status": "ok"}
```

- HTTP 200 = service is up
- Any non-200, connection timeout, or unexpected body = service is unhealthy

### When to run it

- After any deployment or rollback
- After a reported outage
- As a regular manual check (daily or weekly) until automated monitoring is configured

---

## 2. Viewing Cloud Run Logs

### Via GCP Console (recommended for operators)

1. Go to [GCP Console](https://console.cloud.google.com) → **Logging → Logs Explorer**.
2. Select project: `arukai-testbed`.
3. Paste this query to see backend logs:

   ```
   resource.type="cloud_run_revision"
   resource.labels.service_name="arukai-capital-call-backend"
   ```

4. For frontend logs:

   ```
   resource.type="cloud_run_revision"
   resource.labels.service_name="arukai-capital-call-frontend"
   ```

5. Set the time range using the selector at the top right.
6. Filter by severity: click **Severity** and select `ERROR` to focus on failures.

### Via gcloud CLI

```bash
gcloud logging read \
  'resource.type="cloud_run_revision" AND resource.labels.service_name="arukai-capital-call-backend"' \
  --project=arukai-testbed \
  --limit=50 \
  --freshness=1h
```

### What to look for

| Log pattern | Likely cause |
|-------------|-------------|
| `500` response codes | Application error — check stack trace in the log entry |
| `connection refused` | Backend startup failure or crashed instance |
| `jwt` / `auth` errors | Authentication misconfiguration or expired secrets |
| `database` / `neon` errors | DB connectivity issue |
| Repeated cold starts | Instance count set too low; consider min-instances=1 |

---

## 3. Alert Setup Instructions (For When Monitoring Is Configured)

The following alert policies should be configured in GCP Cloud Monitoring once the dashboard is set up. This section documents the intended setup for Arukai or the operator to implement.

### 3.1 Uptime Check Alert (P0 — /health endpoint)

- **Type:** Uptime check
- **Target:** `https://arukai-capital-call-backend-staging-1035777337524.europe-west4.run.app/health`
- **Check interval:** 1 minute
- **Failure threshold:** 2 consecutive failures
- **Alert channel:** email or PagerDuty (configure at setup time)
- **Severity on trigger:** P0 Critical — 30-minute response SLA

### 3.2 Latency Alert (P1 — response time degradation)

- **Metric:** `run.googleapis.com/request_latencies`
- **Filter:** service = `arukai-capital-call-backend`
- **Threshold:** p95 latency > 3000 ms sustained for 5 minutes
- **Severity on trigger:** P1 High — 4-business-hour response SLA

### 3.3 Error Rate Alert (P1 — 5xx spike)

- **Metric:** `run.googleapis.com/request_count`
- **Filter:** response_code_class = `5xx`
- **Threshold:** error rate > 5% of requests over a 5-minute window
- **Severity on trigger:** P1 High

### 3.4 Crash Loop Alert (P0 — repeated container restarts)

- **Metric:** Cloud Run revision restart events
- **Threshold:** > 3 restarts within 10 minutes
- **Severity on trigger:** P0 Critical

### 3.5 Steps to Create Alerts (when dashboard is ready)

1. GCP Console → **Monitoring → Alerting → Create Policy**.
2. Select the metric and configure the threshold as above.
3. Add a notification channel (email, Slack webhook, or PagerDuty integration).
4. Name the policy clearly (e.g., `arukai-d2-backend-health-check`).
5. Save and test by temporarily blocking the health endpoint.

---

## 4. KPIs to Track

These are the key performance indicators for this system. Once the Cloud Monitoring dashboard is configured, these should appear as panels on the dashboard.

| KPI | Target | Measurement |
|-----|--------|-------------|
| Uptime | >= 99.5% | /health check success rate over rolling 30 days |
| Response time (p95) | < 3 seconds | Cloud Run request latency metric |
| Response time (p50) | < 500 ms | Cloud Run request latency metric |
| Error rate (5xx) | < 1% | Cloud Run 5xx response rate |
| Cold start rate | < 10% of requests | Cloud Run cold start metric |
| Document classification latency | < 30 seconds | Application-level log timing (AI call duration) |
| Active sessions | Tracked per day | Application audit log (login events) |
| Documents processed | Tracked per week | Application audit log (upload/classify events) |

---

## 5. Current Monitoring State (Gap Summary)

| Component | Status |
|-----------|--------|
| /health endpoint | Available and functional |
| Cloud Run log access | Available via GCP Console / gcloud |
| Cloud Monitoring dashboard | NOT CONFIGURED — H2 gap |
| Alert policies | NOT CONFIGURED — H3 gap |
| Uptime checks | NOT CONFIGURED |
| SLO / error budget tracking | NOT CONFIGURED |

During the 90-day monitoring window, Arukai will manually check uptime and logs. Formal monitoring setup is planned for Phase 2B or as a follow-on engagement.

---

*Monitoring guide maintained by Arukai squad. For alert configuration or dashboard setup, file a Tier 2 or Tier 3 request.*
