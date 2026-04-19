"""Security utilities — PDF validation, rate limiting setup."""
import logging

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
