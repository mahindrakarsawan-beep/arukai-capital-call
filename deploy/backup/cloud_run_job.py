"""Cloud Run job — nightly pg_dump of the staging Postgres into a
KMS-encrypted GCS bucket. POR-158 #1.

Environment:
  DATABASE_URL           — full postgres://... URL (from Secret Manager)
  BACKUP_BUCKET          — gs://<bucket>, CMEK-enabled
  BACKUP_RETENTION_DAYS  — integer, defaults to 30 (applied via bucket lifecycle;
                           the job itself does not prune)

Exit codes:
  0 on success; non-zero on dump or upload failure. Cloud Run treats non-zero
  as a job-execution failure which surfaces to Cloud Monitoring (A4) for
  alerting.

The job writes to /tmp/<stamp>.sql.gz (pg_dump -Fc is compressed binary,
we use plain-format + gzip here to keep restore simple via `gunzip | psql`).
"""
from __future__ import annotations

import datetime as _dt
import gzip
import os
import shutil
import subprocess
import sys


def _redact_url(url: str) -> str:
    """Best-effort redaction for logs — strip password from postgres URL."""
    # postgres://user:pass@host:port/db  →  postgres://user:***@host:port/db
    if "://" not in url or "@" not in url:
        return url
    scheme, rest = url.split("://", 1)
    creds, hostpart = rest.split("@", 1)
    if ":" in creds:
        user, _pw = creds.split(":", 1)
        creds = f"{user}:***"
    return f"{scheme}://{creds}@{hostpart}"


def main() -> int:
    db_url = os.environ["DATABASE_URL"]
    bucket = os.environ["BACKUP_BUCKET"].rstrip("/")
    stamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%d-%H%M%S")
    dump_path = f"/tmp/cc-{stamp}.sql"
    gz_path = f"{dump_path}.gz"
    dest = f"{bucket}/cc-{stamp}.sql.gz"

    dump_cmd = [
        "pg_dump", "--no-owner", "--no-privileges",
        "--format=plain", "--file", dump_path, db_url,
    ]
    print(f"[backup] dumping {_redact_url(db_url)} -> {dump_path}", flush=True)
    r = subprocess.run(dump_cmd, check=False)
    if r.returncode != 0:
        print(f"[backup] pg_dump failed (exit {r.returncode})", flush=True)
        return r.returncode

    print(f"[backup] gzipping {dump_path} -> {gz_path}", flush=True)
    with open(dump_path, "rb") as src, gzip.open(gz_path, "wb") as dst:
        shutil.copyfileobj(src, dst)

    print(f"[backup] uploading {gz_path} -> {dest}", flush=True)
    r = subprocess.run(["gsutil", "cp", gz_path, dest], check=False)
    if r.returncode != 0:
        print(f"[backup] gsutil cp failed (exit {r.returncode})", flush=True)
        return r.returncode

    print(f"[backup] done: {dest}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
