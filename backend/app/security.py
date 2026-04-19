"""Security utilities — PDF validation, field encryption."""
import base64
import logging
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

logger = logging.getLogger(__name__)

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


def _get_key(key: bytes | None) -> bytes | None:
    """Resolve encryption key: explicit arg > env var > None (skip encryption)."""
    if key is not None:
        return key
    key_b64 = os.environ.get("FIELD_ENCRYPTION_KEY")
    if key_b64:
        return base64.b64decode(key_b64)
    return None


def encrypt_field(value: str, key: bytes | None = None) -> str:
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


def decrypt_field(ciphertext_b64: str, key: bytes | None = None) -> str:
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
