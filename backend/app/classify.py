"""Haiku classification pipeline v0.2 (POR-147 / ARU-17-B1).

Changes from v0.1:
- tool_use structured output for per-field confidence (S3, spec §4)
- Per-doc-type schema: only capital_call_notice gets field extraction
- Fallback: all fields populated with confidence 0.0 if tool_use fails
- ClassificationResult now carries extracted_fields dict
"""
import io
import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import anthropic

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
HAIKU_MODEL = "claude-haiku-4-5-20251001"
CLASSIFICATION_TIMEOUT = 15  # seconds (increased for tool_use)
CONFIDENCE_THRESHOLD = 0.5

# Initialise client once (module-level)
anthropic_client = (
    anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    if ANTHROPIC_API_KEY
    else anthropic.AsyncAnthropic()
)

# ---------------------------------------------------------------------------
# Tool definitions for structured extraction
# ---------------------------------------------------------------------------

CLASSIFY_TOOL = {
    "name": "classify_document",
    "description": (
        "Classify a financial document and extract key fields with per-field confidence scores."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "document_type": {
                "type": "string",
                "enum": [
                    "capital_call_notice",
                    "subscription_agreement",
                    "side_letter",
                    "k1",
                    "wire_instructions",
                    "other",
                ],
                "description": "The classified document type.",
            },
            "confidence": {
                "type": "number",
                "description": "Overall classification confidence score 0.0–1.0.",
            },
            "key_indicators": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Short phrases that led to the classification decision.",
            },
        },
        "required": ["document_type", "confidence", "key_indicators"],
    },
}

# v0.2 capital_call_notice field extraction tool (S3)
CAPITAL_CALL_EXTRACT_TOOL = {
    "name": "extract_capital_call_fields",
    "description": (
        "Extract structured fields from a capital call notice with per-field confidence."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "fund_name": {
                "type": "object",
                "properties": {
                    "value": {"type": ["string", "null"]},
                    "confidence": {"type": "number"},
                    "source_text": {"type": ["string", "null"]},
                },
                "required": ["value", "confidence", "source_text"],
            },
            "call_number": {
                "type": "object",
                "properties": {
                    "value": {"type": ["string", "null"]},
                    "confidence": {"type": "number"},
                    "source_text": {"type": ["string", "null"]},
                },
                "required": ["value", "confidence", "source_text"],
            },
            "amount_due": {
                "type": "object",
                "properties": {
                    "value": {"type": ["string", "null"]},
                    "confidence": {"type": "number"},
                    "source_text": {"type": ["string", "null"]},
                },
                "required": ["value", "confidence", "source_text"],
            },
            "currency": {
                "type": "object",
                "properties": {
                    "value": {"type": ["string", "null"]},
                    "confidence": {"type": "number"},
                    "source_text": {"type": ["string", "null"]},
                },
                "required": ["value", "confidence", "source_text"],
            },
            "due_date": {
                "type": "object",
                "properties": {
                    "value": {"type": ["string", "null"]},
                    "confidence": {"type": "number"},
                    "source_text": {"type": ["string", "null"]},
                },
                "required": ["value", "confidence", "source_text"],
            },
            "recipient_entity": {
                "type": "object",
                "properties": {
                    "value": {"type": ["string", "null"]},
                    "confidence": {"type": "number"},
                    "source_text": {"type": ["string", "null"]},
                },
                "required": ["value", "confidence", "source_text"],
            },
            "wire_instructions_present": {
                "type": "object",
                "properties": {
                    "value": {"type": ["boolean", "null"]},
                    "confidence": {"type": "number"},
                    "source_text": {"type": ["string", "null"]},
                },
                "required": ["value", "confidence", "source_text"],
            },
            "notice_date": {
                "type": "object",
                "properties": {
                    "value": {"type": ["string", "null"]},
                    "confidence": {"type": "number"},
                    "source_text": {"type": ["string", "null"]},
                },
                "required": ["value", "confidence", "source_text"],
            },
        },
        "required": [
            "fund_name",
            "call_number",
            "amount_due",
            "currency",
            "due_date",
            "recipient_entity",
            "wire_instructions_present",
            "notice_date",
        ],
    },
}

CAPITAL_CALL_FIELDS = [
    "fund_name",
    "call_number",
    "amount_due",
    "currency",
    "due_date",
    "recipient_entity",
    "wire_instructions_present",
    "notice_date",
]

SYSTEM_PROMPT = """You are a financial document classifier for a capital call management system.

Classify the document into exactly one of these six types:
- capital_call_notice  (capital call / drawdown notices from fund managers)
- subscription_agreement  (LP subscription / commitment agreements)
- side_letter  (side letter agreements modifying LPA terms)
- k1  (Schedule K-1 tax documents)
- wire_instructions  (bank wire / payment instructions)
- other  (anything that does not clearly fit the above)

Use the classify_document tool to return your result.
If the document type is capital_call_notice, also use extract_capital_call_fields."""

VALID_TYPES = {
    "capital_call_notice",
    "subscription_agreement",
    "side_letter",
    "k1",
    "wire_instructions",
    "other",
}

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


def _empty_capital_call_fields(backfilled: bool = True, confidence: float = 0.0) -> dict[str, Any]:
    """Return all capital_call_notice fields with null values and given confidence."""
    return {
        f: {"value": None, "confidence": confidence, "source_text": None, "backfilled": backfilled}
        for f in CAPITAL_CALL_FIELDS
    }


@dataclass
class ClassificationResult:
    document_type: str = "other"
    confidence: float = 0.0
    key_indicators: list = field(default_factory=list)
    extracted_fields: Optional[dict] = None
    model_version: str = HAIKU_MODEL
    fallback: bool = False
    classification_error: Optional[str] = None
    duration_ms: int = 0


async def classify_document_text(text: str, filename: str = "") -> ClassificationResult:
    """Classify document text via Claude Haiku with tool_use for structured output.

    Per S3: field extraction only runs for capital_call_notice.
    Fallback: all fields populated with confidence 0.0 if tool_use fails.
    """
    start = time.monotonic()
    truncated = text[:6000] if len(text) > 6000 else text

    try:
        # Single tool_use call: classify + conditionally extract fields
        tools = [CLASSIFY_TOOL, CAPITAL_CALL_EXTRACT_TOOL]

        message = await anthropic_client.messages.create(
            model=HAIKU_MODEL,
            max_tokens=1024,
            system=[
                {
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            tools=tools,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Document filename: {filename}\n\nDocument text:\n{truncated}"
                    ),
                }
            ],
            timeout=CLASSIFICATION_TIMEOUT,
        )

        # Extract tool_use results
        clf_result = None
        extract_result = None

        for block in message.content:
            if block.type == "tool_use":
                if block.name == "classify_document":
                    clf_result = block.input
                elif block.name == "extract_capital_call_fields":
                    extract_result = block.input

        if clf_result is None:
            # Tool_use did not fire — try text fallback
            raise ValueError("No classify_document tool call in response")

        doc_type = clf_result.get("document_type", "other")
        confidence = float(clf_result.get("confidence", 0.0))
        indicators = clf_result.get("key_indicators", [])

        if doc_type not in VALID_TYPES:
            doc_type = "other"
            confidence = 0.0

        duration_ms = int((time.monotonic() - start) * 1000)

        # Build extracted_fields only for capital_call_notice (S3)
        extracted_fields: Optional[dict] = None
        if doc_type == "capital_call_notice":
            if extract_result:
                # Attach backfilled=False to each field
                extracted_fields = {
                    fname: {
                        "value": fdata.get("value"),
                        "confidence": float(fdata.get("confidence", 0.0)),
                        "source_text": fdata.get("source_text"),
                        "backfilled": False,
                    }
                    for fname, fdata in extract_result.items()
                    if fname in CAPITAL_CALL_FIELDS
                }
                # Ensure all required fields present
                for fname in CAPITAL_CALL_FIELDS:
                    if fname not in extracted_fields:
                        extracted_fields[fname] = {
                            "value": None,
                            "confidence": 0.0,
                            "source_text": None,
                            "backfilled": False,
                        }
            else:
                # Extraction tool did not fire — populate with zeros
                extracted_fields = _empty_capital_call_fields(backfilled=False, confidence=0.0)

        if confidence < CONFIDENCE_THRESHOLD:
            heuristic_type = _heuristic_type(filename, text)
            # If heuristic suggests capital_call_notice, keep extracted_fields (with zeros)
            if heuristic_type == "capital_call_notice" and extracted_fields is None:
                extracted_fields = _empty_capital_call_fields(backfilled=False, confidence=0.0)
            return ClassificationResult(
                document_type=heuristic_type,
                confidence=confidence,
                key_indicators=indicators,
                extracted_fields=extracted_fields,
                model_version=HAIKU_MODEL,
                fallback=True,
                classification_error=f"Low confidence ({confidence:.2f}); heuristic applied",
                duration_ms=duration_ms,
            )

        return ClassificationResult(
            document_type=doc_type,
            confidence=confidence,
            key_indicators=indicators,
            extracted_fields=extracted_fields,
            model_version=HAIKU_MODEL,
            fallback=False,
            duration_ms=duration_ms,
        )

    except Exception as exc:
        duration_ms = int((time.monotonic() - start) * 1000)
        heuristic_type = _heuristic_type(filename, text)
        # Fallback: all fields with confidence 0.0 for capital_call_notice
        extracted_fields = None
        if heuristic_type == "capital_call_notice":
            extracted_fields = _empty_capital_call_fields(backfilled=False, confidence=0.0)
        return ClassificationResult(
            document_type=heuristic_type,
            confidence=0.0,
            extracted_fields=extracted_fields,
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
