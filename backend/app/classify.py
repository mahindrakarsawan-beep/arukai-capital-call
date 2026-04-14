"""Haiku classification pipeline (POR-141) — classify PDF text via Claude Haiku."""
import io
import json
import os
import time
from dataclasses import dataclass, field
from typing import Optional

import anthropic

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
HAIKU_MODEL = "claude-haiku-4-20250414"
CLASSIFICATION_TIMEOUT = 10  # seconds
CONFIDENCE_THRESHOLD = 0.5

# Initialise client once (module-level)
anthropic_client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else anthropic.AsyncAnthropic()

SYSTEM_PROMPT = """You are a financial document classifier for a capital call management system.

Classify the document into EXACTLY ONE of these six types:
- capital_call_notice  (capital call / drawdown notices from fund managers)
- subscription_agreement  (LP subscription / commitment agreements)
- side_letter  (side letter agreements modifying LPA terms)
- k1  (Schedule K-1 tax documents)
- wire_instructions  (bank wire / payment instructions)
- other  (anything that does not clearly fit the above)

Also identify key indicators that led to your decision.

Respond with STRICT JSON only — no markdown, no prose:
{
  "document_type": "<one of the six types above>",
  "confidence": <float 0.0-1.0>,
  "key_indicators": ["<phrase1>", "<phrase2>", ...]
}"""

VALID_TYPES = {
    "capital_call_notice",
    "subscription_agreement",
    "side_letter",
    "k1",
    "wire_instructions",
    "other",
}

# Filename keyword heuristic fallback
_HEURISTIC_MAP = {
    "capital_call": "capital_call_notice",
    "capital call": "capital_call_notice",
    "drawdown": "capital_call_notice",
    "subscription": "subscription_agreement",
    "sub_doc": "subscription_agreement",
    "side_letter": "side_letter",
    "side letter": "side_letter",
    "k-1": "k1",
    "k1": "k1",
    "schedule k": "k1",
    "wire": "wire_instructions",
    "wiring": "wire_instructions",
    "payment instructions": "wire_instructions",
}


def _heuristic_type(filename: str, text: str) -> str:
    """Best-effort document type from filename + first 200 chars of text."""
    combined = (filename + " " + text[:200]).lower()
    for keyword, doc_type in _HEURISTIC_MAP.items():
        if keyword in combined:
            return doc_type
    return "other"


@dataclass
class ClassificationResult:
    document_type: str = "other"
    confidence: float = 0.0
    key_indicators: list = field(default_factory=list)
    model_version: str = HAIKU_MODEL
    fallback: bool = False
    classification_error: Optional[str] = None
    duration_ms: int = 0


async def classify_document_text(text: str, filename: str = "") -> ClassificationResult:
    """
    Classify document text via Claude Haiku.
    Falls back to heuristic if API fails or confidence is too low.
    """
    start = time.monotonic()

    # Truncate to ~6000 chars per scope spec
    truncated = text[:6000] if len(text) > 6000 else text

    try:
        message = await anthropic_client.messages.create(
            model=HAIKU_MODEL,
            max_tokens=512,
            system=[
                {
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[
                {
                    "role": "user",
                    "content": f"Document filename: {filename}\n\nDocument text:\n{truncated}",
                }
            ],
            timeout=CLASSIFICATION_TIMEOUT,
        )

        raw = message.content[0].text.strip()

        # Strip any accidental markdown fences
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        parsed = json.loads(raw)
        doc_type = parsed.get("document_type", "other")
        confidence = float(parsed.get("confidence", 0.0))
        indicators = parsed.get("key_indicators", [])

        if doc_type not in VALID_TYPES:
            doc_type = "other"
            confidence = 0.0

        duration_ms = int((time.monotonic() - start) * 1000)

        if confidence < CONFIDENCE_THRESHOLD:
            # Low confidence — use heuristic but mark as fallback
            heuristic_type = _heuristic_type(filename, text)
            return ClassificationResult(
                document_type=heuristic_type,
                confidence=confidence,
                key_indicators=indicators,
                model_version=HAIKU_MODEL,
                fallback=True,
                classification_error=f"Low confidence ({confidence:.2f}); heuristic applied",
                duration_ms=duration_ms,
            )

        return ClassificationResult(
            document_type=doc_type,
            confidence=confidence,
            key_indicators=indicators,
            model_version=HAIKU_MODEL,
            fallback=False,
            duration_ms=duration_ms,
        )

    except (json.JSONDecodeError, KeyError, IndexError, AttributeError) as exc:
        duration_ms = int((time.monotonic() - start) * 1000)
        heuristic_type = _heuristic_type(filename, text)
        return ClassificationResult(
            document_type=heuristic_type,
            confidence=0.0,
            fallback=True,
            classification_error=f"Parse error: {exc}",
            duration_ms=duration_ms,
        )

    except Exception as exc:  # API error, timeout, network issue
        duration_ms = int((time.monotonic() - start) * 1000)
        heuristic_type = _heuristic_type(filename, text)
        return ClassificationResult(
            document_type=heuristic_type,
            confidence=0.0,
            fallback=True,
            classification_error=str(exc),
            duration_ms=duration_ms,
        )


def extract_pdf_text(content: bytes) -> str:
    """Extract text layer from PDF bytes using pypdf. Returns empty string on error."""
    try:
        import pypdf

        reader = pypdf.PdfReader(io.BytesIO(content))
        parts = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                parts.append(text)
        return "\n".join(parts)
    except Exception:
        return ""
