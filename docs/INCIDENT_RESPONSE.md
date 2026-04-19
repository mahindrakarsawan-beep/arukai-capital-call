# Incident Response Runbook

## Severity levels

| Level | Definition | Response time | Examples |
|-------|-----------|--------------|---------|
| P0 | System down or data breach | 30 minutes | Health endpoint failing, unauthorized data access |
| P1 | Major feature broken | 4 hours | Classification pipeline down, auth failures |
| P2 | Minor issue | 1 business day | Slow responses, UI glitch |

## P0: Suspected data breach

### Immediate (within 30 minutes)

1. **Revoke all sessions**
```bash
# Connect to DB and revoke everything
psql $DATABASE_URL -c "UPDATE sessions SET revoked_at = now() WHERE revoked_at IS NULL"
```

2. **Rotate JWT secret**
```bash
# Generate new secret
NEW_SECRET=$(openssl rand -base64 48)
gcloud run services update arukai-capital-call-backend-staging \
  --update-secrets=JWT_SECRET=CC_JWT_SECRET:latest
# Update the secret in Secret Manager first
echo -n "$NEW_SECRET" | gcloud secrets versions add CC_JWT_SECRET --data-file=-
```

3. **Rotate encryption keys**
```bash
# Generate new key, run rotation
NEW_KEY=$(openssl rand -base64 32)
OLD_ENCRYPTION_KEY=$CURRENT_KEY NEW_ENCRYPTION_KEY=$NEW_KEY \
  python3 scripts/rotate_key.py
# Update Secret Manager
echo -n "$NEW_KEY" | gcloud secrets versions add FIELD_ENCRYPTION_KEY --data-file=-
```

4. **Check audit trail**
```bash
# Last 100 events
psql $DATABASE_URL -c "SELECT created_at, action, actor_user_id FROM audit_events ORDER BY created_at DESC LIMIT 100"
```

5. **Notify stakeholders**
- Client contact (from NDA)
- Arukai lead (Holden)
- Legal counsel (if PII exposed)

### Within 24 hours

6. **Root cause analysis** — check Cloud Run logs, audit events, access patterns
7. **Scope assessment** — what data was exposed, which users affected
8. **Remediation** — patch vulnerability, update WAF rules
9. **Document** — write incident report in `.squad/decisions/inbox/`

## P0: System down

1. **Check health:** `curl https://<backend>/health`
2. **Check Cloud Run:** `gcloud run services describe arukai-capital-call-backend-staging --region=europe-west4`
3. **Check logs:** `gcloud logging read "resource.type=cloud_run_revision" --limit=50`
4. **Rollback:** `gcloud run services update-traffic --to-revisions=<previous-revision>=100`
5. **Check DB:** `psql $DATABASE_URL -c "SELECT 1"`
6. **Check GPU (if self-hosted AI):** `gcloud compute ssh arukai-llm -- nvidia-smi`

## P1: Classification pipeline down

1. System auto-falls back to heuristic classifier (no AI needed)
2. Check Mistral API status (dev only): `curl -s https://api.mistral.ai/v1/models`
3. Check local LLM (prod): `curl http://<gpu-vm>:8080/health`
4. If GPU VM down: restart it or let Mistral fallback handle it (dev env)

## Credential rotation schedule

| Credential | Rotation frequency | How |
|-----------|-------------------|-----|
| JWT_SECRET | On breach or quarterly | Secret Manager + redeploy |
| FIELD_ENCRYPTION_KEY | On breach | scripts/rotate_key.py |
| User passwords | On breach (forced) | Change-password endpoint + revoke-all |
| Mistral API key | Annually | Mistral dashboard + Secret Manager |
| DB password | On breach or annually | Neon dashboard + Secret Manager |

## Post-incident checklist

- [ ] All sessions revoked
- [ ] Compromised keys rotated
- [ ] Root cause identified
- [ ] Fix deployed
- [ ] Stakeholders notified
- [ ] Incident report written
- [ ] Runbook updated if new failure mode discovered
