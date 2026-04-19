"""Security utilities — PDF validation, field encryption, KMS key resolution."""
import base64
import logging
import os
from typing import Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

try:
    from google.cloud import kms
except ImportError:
    kms = None  # GCP KMS not installed — local/dev mode

logger = logging.getLogger(__name__)

_encryption_key_cache: Optional[bytes] = None
_cache_resolved: bool = False

MAX_PDF_SIZE = 20 * 1024 * 1024  # 20MB


def validate_pdf(content: bytes, filename: str) -> tuple[bool, str]:
    """Validate uploaded file is a real PDF within size limits."""
    if len(content) > MAX_PDF_SIZE:
        return False, f"File exceeds {MAX_PDF_SIZE // (1024*1024)}MB limit"

    if not content.startswith(b"%PDF"):
        return False, "File does not contain a valid PDF header"

    if len(content) < 20:
        return False, "File is too small to be a valid PDF"

    # Check for suspicious embedded content
    content_lower = content[:10000].lower()
    if b"/javascript" in content_lower or b"/js " in content_lower:
        logger.warning("PDF contains JavaScript — rejected: %s", filename)
        return False, "PDF contains embedded JavaScript (rejected for security)"

    return True, ""


def get_encryption_key() -> Optional[bytes]:
    """Resolve key: GCP KMS > FIELD_ENCRYPTION_KEY env > None. Cached after first call."""
    global _encryption_key_cache, _cache_resolved

    if _cache_resolved:
        return _encryption_key_cache

    # Priority 1: GCP KMS
    kms_resource = os.environ.get("KMS_KEY_RESOURCE_NAME")
    kms_wrapped = os.environ.get("KMS_WRAPPED_KEY")
    if kms_resource and kms_wrapped and kms is not None:
        client = kms.KeyManagementServiceClient()
        response = client.decrypt(request={
            "name": kms_resource,
            "ciphertext": base64.b64decode(kms_wrapped),
        })
        _encryption_key_cache = response.plaintext
        _cache_resolved = True
        logger.info("Encryption key resolved from GCP KMS")
        return _encryption_key_cache

    # Priority 2: Local env var
    key_b64 = os.environ.get("FIELD_ENCRYPTION_KEY")
    if key_b64:
        _encryption_key_cache = base64.b64decode(key_b64)
        _cache_resolved = True
        return _encryption_key_cache

    # Priority 3: No key — plaintext mode
    _encryption_key_cache = None
    _cache_resolved = True
    return None


def _get_key(key: Optional[bytes] = None) -> Optional[bytes]:
    """Resolve encryption key: explicit arg > cached resolution > None."""
    if key is not None:
        return key
    return get_encryption_key()


def encrypt_field(value: str, key: Optional[bytes] = None) -> str:
    """AES-256-GCM encrypt. Returns base64(nonce + ciphertext_with_tag). No key = plaintext."""
    if not isinstance(value, str):
        raise TypeError("Value must be a string")

    resolved = _get_key(key)
    if resolved is None:
        return value

    if len(resolved) != 32:
        raise ValueError("Encryption key must be 32 bytes (256 bits)")

    nonce = os.urandom(12)
    aesgcm = AESGCM(resolved)
    ct = aesgcm.encrypt(nonce, value.encode(), None)
    return base64.b64encode(nonce + ct).decode()


def decrypt_field(ciphertext_b64: str, key: Optional[bytes] = None) -> str:
    """AES-256-GCM decrypt. No key = return as-is (plaintext passthrough)."""
    if not isinstance(ciphertext_b64, str):
        raise TypeError("Ciphertext must be a string")

    resolved = _get_key(key)
    if resolved is None:
        return ciphertext_b64

    if len(resolved) != 32:
        raise ValueError("Encryption key must be 32 bytes (256 bits)")

    try:
        raw = base64.b64decode(ciphertext_b64)
        nonce = raw[:12]
        ct = raw[12:]
        plaintext = AESGCM(resolved).decrypt(nonce, ct, None)
        return plaintext.decode()
    except Exception as e:
        raise ValueError("Decryption failed — tampered data or wrong key") from e
