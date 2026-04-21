# POR-158 #1 — nightly pg_dump Cloud Run job.
#
# Bookworm (Debian 12) is pinned explicitly because:
#   - postgresql-client-17 from the PGDG repo needs a stable distro codename
#     path (`bookworm-pgdg`); trixie paths moved in Debian 13.
#   - Google Cloud's apt repo `cloud-sdk main` is distro-agnostic but its
#     keyring handling is smoothest on bookworm.
# Staging Neon runs Postgres 17.8 — Debian's stock pg15 client dumps fail with
# server-version-mismatch, so we pull pg17 from PGDG.
FROM python:3.12-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl gnupg ca-certificates lsb-release \
    && install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc \
       -o /etc/apt/keyrings/pgdg.asc \
    && echo "deb [signed-by=/etc/apt/keyrings/pgdg.asc] https://apt.postgresql.org/pub/repos/apt bookworm-pgdg main" \
       > /etc/apt/sources.list.d/pgdg.list \
    && curl -fsSL https://packages.cloud.google.com/apt/doc/apt-key.gpg \
       -o /etc/apt/keyrings/gcloud.asc \
    && echo "deb [signed-by=/etc/apt/keyrings/gcloud.asc] https://packages.cloud.google.com/apt cloud-sdk main" \
       > /etc/apt/sources.list.d/gcloud.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client-17 google-cloud-cli \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY cloud_run_job.py .
ENTRYPOINT ["python3", "cloud_run_job.py"]
