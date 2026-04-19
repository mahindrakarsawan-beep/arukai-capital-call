#!/usr/bin/env python3
"""Neon Postgres backup — dump, encrypt, upload to GCS."""
import argparse
import io
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("backup")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def dump_database(database_url: str) -> bytes:
    result = subprocess.run(
        ["pg_dump", "--no-owner", "--no-acl", database_url],
        capture_output=True, check=True,
    )
    return result.stdout


def encrypt_dump(data: bytes) -> bytes:
    from app.security import get_encryption_key, encrypt_field
    key = get_encryption_key()
    if key is None:
        logger.warning("No encryption key — backup will be unencrypted")
        return data
    return encrypt_field(data.decode("utf-8", errors="replace"), key).encode()


def upload_to_gcs(bucket_name: str, blob_name: str, data: bytes) -> bool:
    try:
        from google.cloud import storage
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        blob.upload_from_file(io.BytesIO(data), content_type="application/octet-stream")
        return blob.exists()
    except ImportError:
        logger.error("google-cloud-storage not installed")
        return False
    except Exception as e:
        logger.error("Upload failed: %s", e)
        return False


def delete_old_backups(bucket_name: str, retention_days: int) -> int:
    try:
        from google.cloud import storage
        from datetime import timedelta
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        deleted = 0
        for blob in bucket.list_blobs(prefix="backup-"):
            if blob.time_created < cutoff:
                blob.delete()
                deleted += 1
        return deleted
    except Exception as e:
        logger.error("Retention cleanup failed: %s", e)
        return 0


def main():
    parser = argparse.ArgumentParser(description="Backup Neon Postgres to GCS")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--retention-days", type=int, default=30)
    args = parser.parse_args()

    db_url = os.environ.get("DATABASE_URL")
    bucket = os.environ.get("BACKUP_GCS_BUCKET")

    if not db_url:
        logger.error("DATABASE_URL not set")
        sys.exit(1)

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H%M%S")
    blob_name = f"backup-{ts}.sql.enc"

    if args.dry_run:
        print(f"Would dump: {db_url[:30]}...")
        print(f"Would encrypt with KMS/env key")
        print(f"Would upload to: gs://{bucket}/{blob_name}")
        print(f"Would delete backups older than {args.retention_days} days")
        return

    logger.info("Starting backup")
    t0 = time.time()

    logger.info("Dumping database...")
    data = dump_database(db_url)
    logger.info("Dump: %d bytes (%.1fs)", len(data), time.time() - t0)

    t1 = time.time()
    logger.info("Encrypting...")
    encrypted = encrypt_dump(data)
    logger.info("Encrypted: %d bytes (%.1fs)", len(encrypted), time.time() - t1)

    if bucket:
        t2 = time.time()
        logger.info("Uploading to gs://%s/%s...", bucket, blob_name)
        ok = upload_to_gcs(bucket, blob_name, encrypted)
        if not ok:
            logger.error("Upload verification failed")
            sys.exit(1)
        logger.info("Uploaded (%.1fs)", time.time() - t2)

        deleted = delete_old_backups(bucket, args.retention_days)
        if deleted:
            logger.info("Deleted %d old backups", deleted)
    else:
        out_path = f"/tmp/{blob_name}"
        with open(out_path, "wb") as f:
            f.write(encrypted)
        logger.info("No GCS bucket — saved locally: %s", out_path)

    logger.info("Backup complete (%.1fs total)", time.time() - t0)


if __name__ == "__main__":
    main()
