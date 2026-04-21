# Nightly pg_dump → GCS (POR-158 #1)

Cloud Run job that dumps the staging Postgres and writes the gzip into a
CMEK-encrypted GCS bucket with 30-day retention. Triggered daily by Cloud
Scheduler; on failure Cloud Monitoring (POR-158 #2) raises an alert.

## One-off provisioning

### 1. KMS keyring + key

```bash
gcloud kms keyrings create cc-backup \
  --location=europe-west4 --project=arukai-testbed
gcloud kms keys create backup-key \
  --keyring=cc-backup --location=europe-west4 \
  --purpose=encryption --project=arukai-testbed
```

### 2. CMEK-encrypted GCS bucket with 30-day lifecycle

```bash
BUCKET=gs://arukai-testbed-cc-backups
gcloud storage buckets create $BUCKET \
  --location=europe-west4 --project=arukai-testbed \
  --default-encryption-key=projects/arukai-testbed/locations/europe-west4/keyRings/cc-backup/cryptoKeys/backup-key

gcloud storage buckets update $BUCKET --lifecycle-file=- <<'LIFE'
{"lifecycle":{"rule":[{"action":{"type":"Delete"},"condition":{"age":30}}]}}
LIFE
```

### 3. Grant the Cloud Run job SA permission on the CMEK key + bucket

```bash
JOB_SA=cc-backup-job@arukai-testbed.iam.gserviceaccount.com
gcloud iam service-accounts create cc-backup-job \
  --project=arukai-testbed --display-name="CC backup job"

gcloud kms keys add-iam-policy-binding backup-key \
  --keyring=cc-backup --location=europe-west4 \
  --member=serviceAccount:$JOB_SA \
  --role=roles/cloudkms.cryptoKeyEncrypterDecrypter \
  --project=arukai-testbed

gcloud storage buckets add-iam-policy-binding $BUCKET \
  --member=serviceAccount:$JOB_SA --role=roles/storage.objectCreator
```

### 4. Build + push the image

```bash
cd deploy/backup
gcloud builds submit --project=arukai-testbed \
  --tag=europe-west4-docker.pkg.dev/arukai-testbed/capital-call/cc-backup:latest
```

### 5. Create the Cloud Run job

```bash
gcloud run jobs create cc-backup \
  --image=europe-west4-docker.pkg.dev/arukai-testbed/capital-call/cc-backup:latest \
  --region=europe-west4 --project=arukai-testbed \
  --service-account=$JOB_SA \
  --set-secrets=DATABASE_URL=CC_DATABASE_URL:latest \
  --set-env-vars=BACKUP_BUCKET=gs://arukai-testbed-cc-backups,BACKUP_RETENTION_DAYS=30 \
  --max-retries=1 --task-timeout=1800
```

### 6. Create the Cloud Scheduler trigger

```bash
INVOKER_SA=cc-backup-invoker@arukai-testbed.iam.gserviceaccount.com
gcloud iam service-accounts create cc-backup-invoker \
  --project=arukai-testbed --display-name="CC backup invoker"

gcloud run jobs add-iam-policy-binding cc-backup \
  --member=serviceAccount:$INVOKER_SA --role=roles/run.invoker \
  --region=europe-west4 --project=arukai-testbed

gcloud scheduler jobs create http cc-backup-nightly \
  --location=europe-west4 --project=arukai-testbed \
  --schedule="0 2 * * *" \
  --uri="https://europe-west4-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/arukai-testbed/jobs/cc-backup:run" \
  --http-method=POST \
  --oauth-service-account-email=$INVOKER_SA
```

## One-off verification

### Trigger the job manually

```bash
gcloud run jobs execute cc-backup --region=europe-west4 --project=arukai-testbed --wait
gcloud storage ls gs://arukai-testbed-cc-backups
```

Expect one `cc-YYYYMMDD-HHMMSS.sql.gz` object with size > 0.

### Restore to a throwaway Cloud SQL

```bash
gcloud sql instances create cc-restore-test \
  --database-version=POSTGRES_16 --region=europe-west4 \
  --tier=db-f1-micro --project=arukai-testbed
gcloud sql databases create restore_test \
  --instance=cc-restore-test --project=arukai-testbed

FILE=$(gcloud storage ls gs://arukai-testbed-cc-backups/cc-*.sql.gz | tail -1)
gcloud sql import sql cc-restore-test $FILE \
  --database=restore_test --project=arukai-testbed

# Smoke: row counts sane
gcloud sql connect cc-restore-test --database=restore_test --project=arukai-testbed \
  -- -c "SELECT 'packages' AS t, count(*) FROM packages UNION ALL SELECT 'documents', count(*) FROM documents;"

gcloud sql instances delete cc-restore-test --project=arukai-testbed --quiet
```

## Ongoing ops

- **Restore from a specific dump:** `gcloud storage cp gs://arukai-testbed-cc-backups/cc-<stamp>.sql.gz .` then `gunzip | psql $DATABASE_URL`.
- **Force an out-of-cycle run:** `gcloud run jobs execute cc-backup --region=europe-west4 --project=arukai-testbed --wait`.
- **Pause the schedule** (e.g. during a maintenance window): `gcloud scheduler jobs pause cc-backup-nightly --location=europe-west4 --project=arukai-testbed`.
- **Alert channel:** failed job executions surface through the cc-backend Cloud Monitoring alert policy — see `deploy/monitoring/README.md` (A4).
