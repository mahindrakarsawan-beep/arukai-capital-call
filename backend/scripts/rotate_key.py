#!/usr/bin/env python3
"""Re-encrypt all extracted_fields with a new encryption key."""
import argparse
import base64
import json
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("rotate_key")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.security import encrypt_field, decrypt_field


def rotate(old_key_b64: str, new_key_b64: str, dry_run: bool = False):
    old_key = base64.b64decode(old_key_b64)
    new_key = base64.b64decode(new_key_b64)

    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        log.error("DATABASE_URL not set")
        sys.exit(1)

    from sqlalchemy import create_engine, text
    engine = create_engine(db_url.replace("postgresql+psycopg://", "postgresql://")
                               .replace("postgresql+asyncpg://", "postgresql://"))

    with engine.begin() as conn:
        rows = conn.execute(text(
            "SELECT id, extracted_fields FROM classifications WHERE extracted_fields IS NOT NULL"
        )).fetchall()

        total = len(rows)
        log.info("Found %d records to rotate%s", total, " (dry run)" if dry_run else "")

        rotated = 0
        for i, (cid, fields) in enumerate(rows, 1):
            if not isinstance(fields, dict):
                continue

            new_fields = {}
            for fname, fdata in fields.items():
                if isinstance(fdata, dict) and "value" in fdata and isinstance(fdata["value"], str):
                    try:
                        plain = decrypt_field(fdata["value"], old_key)
                        fdata["value"] = encrypt_field(plain, new_key)
                    except Exception:
                        pass  # value might be plaintext, skip
                new_fields[fname] = fdata

            if not dry_run:
                conn.execute(text(
                    "UPDATE classifications SET extracted_fields = :fields WHERE id = :id"
                ), {"fields": json.dumps(new_fields), "id": cid})

            rotated += 1
            if i % 50 == 0 or i == total:
                log.info("Progress: %d/%d", i, total)

        if not dry_run:
            conn.execute(text(
                "INSERT INTO audit_events (id, actor_user_id, action, after_state, created_at) "
                "VALUES (gen_random_uuid(), NULL, 'key_rotation', :state, now())"
            ), {"state": json.dumps({"records_rotated": rotated})})

        log.info("Done. %d records %s.", rotated, "would be rotated" if dry_run else "rotated")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    old = os.environ.get("OLD_ENCRYPTION_KEY", "")
    new = os.environ.get("NEW_ENCRYPTION_KEY", "")
    if not old or not new:
        print("Set OLD_ENCRYPTION_KEY and NEW_ENCRYPTION_KEY (base64)")
        sys.exit(1)

    rotate(old, new, args.dry_run)
