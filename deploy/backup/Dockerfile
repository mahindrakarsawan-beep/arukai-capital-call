# POR-158 #1 — nightly pg_dump Cloud Run job.
# Small image: python:3.12-slim + postgresql-client (for pg_dump) + gcloud
# (for gsutil cp into the CMEK bucket).
FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        postgresql-client \
        curl \
        gnupg \
        ca-certificates \
    && echo "deb https://packages.cloud.google.com/apt cloud-sdk main" \
       > /etc/apt/sources.list.d/google-cloud-sdk.list \
    && curl -fsSL https://packages.cloud.google.com/apt/doc/apt-key.gpg \
       | gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg \
    && apt-get update \
    && apt-get install -y --no-install-recommends google-cloud-cli \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY cloud_run_job.py .
ENTRYPOINT ["python", "cloud_run_job.py"]
