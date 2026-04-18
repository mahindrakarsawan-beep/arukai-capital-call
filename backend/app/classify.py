"""Mistral Small classification pipeline v0.2 (POR-151 / POR-147 / ARU-17-B1).

Changes from v0.1 (Haiku):
- Primary provider: Mistral Small (mistral-small-latest) via JSON mode
- Fallback provider: GPT-4o-mini (OpenAI) if Mistral fails
- Final fallback: deterministic heuristic classification
- provider_used field added to ClassificationResult
- tool_use structured extraction kept; adapted to JSON mode (two-pass)
- MISTRAL_API_KEY (primary) + OPENAI_API_KEY (fallback)
"""
import io
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Optional

MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

MISTRAL_MODEL = "mistral-small-latest"
OPENAI_MODEL = "gpt-4o-mini"

MISTRAL_ENDPOINT = "https://api.mistral.ai/v1/chat/completions"
OPENAI_ENDPOINT = "https://api.openai.com/v1/chat/completions"

CLASSIFICATION_TIMEOUT = 15  # seconds

CONFIDENCE_THRESHOLD = 0.5

# ---------------------------------------------------------------------------
# Prompt structure (same semantics as Haiku tool_use version)
# ---------------------------------------------------------------------------

VALID_TYPES = {
    "capital_call_notice",
    "subscription_agreement",
    "side_letter",
    "k1",
    "wire_instructions",
    "other",
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

# JSON schema descriptions used inline in the prompt
CLASSIFY_SCHEMA = json.dumps({
    "document_type": "one of: capital_call_notice | subscription_agreement | side_letter | k1 | wire_instructions | other",
    "confidence": "number 0.0–1.0",
    "key_indicators": ["short phrase 1", "short phrase 2"],
})

EXTRACT_SCHEMA = json.dumps({
    "fund_name": {"value": "string or null", "confidence": 0.95, "source_text": "string or null"},
    "call_number": {"value": "string or null", "confidence": 0.0, "source_text": "string or null"},
    "amount_due": {"value": "string or null", "confidence": 0.0, "source_text": "string or null"},
    "currency": {"value": "string or null", "confidence": 0.0, "source_text": "string or null"},
    "due_date": {"value": "string or null", "confidence": 0.0, "source_text": "string or null"},
    "recipient_entity": {"value": "string or null", "confidence": 0.0, "source_text": "string or null"},
    "wire_instructions_present": {"value": "boolean or null", "confidence": 0.0, "source_text": "string or null"},
    "notice_date": {"value": "string or null", "confidence": 0.0, "source_text": "string or null"},
})

SYSTEM_PROMPT_CLASSIFY = f"""You are a financial document classifier for a capital call management system.

Classify the document into exactly one of these six types:
- capital_call_notice  (capital call / drawdown notices from fund managers)
- subscription_agreement  (LP subscription / commitment agreements)
- side_letter  (side letter agreements modifying LPA terms)
- k1  (Schedule K-1 tax documents)
- wire_instructions  (bank wire / payment instructions)
- other  (anything that does not clearly fit the above)

Respond ONLY with valid JSON matching this schema exactly (no markdown, no prose):
{CLASSIFY_SCHEMA}"""

SYSTEM_PROMPT_EXTRACT = f"""You are a financial document field extractor.

Extract the following fields from the capital call notice. For each field provide:
- value: the extracted value (string, boolean, or null if not found)
- confidence: float 0.0–1.0 (your confidence in the extraction)
- source_text: the exact snippet from the document, or null

Respond ONLY with valid JSON matching this schema exactly (no markdown, no prose):
{EXTRACT_SCHEMA}"""

# ---------------------------------------------------------------------------
# Heuristic fallback
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class ClassificationResult:
    document_type: str = "other"
    confidence: float = 0.0
    key_indicators: list = field(default_factory=list)
    extracted_fields: Optional[dict] = None
    model_version: str = MISTRAL_MODEL
    provider_used: str = "heuristic"
    fallback: bool = False
    classification_error: Optional[str] = None
    duration_ms: int = 0


# ---------------------------------------------------------------------------
# HTTP helpers (urllib — no SDK dependency)
# ---------------------------------------------------------------------------

def _post_json(url: str, headers: dict, payload: dict, timeout: int) -> dict:
    """Synchronous JSON POST via urllib. Raises on HTTP errors."""
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def _chat(
    endpoint: str,
    api_key: str,
    model: str,
    messages: list[dict],
    timeout: int,
    response_format: Optional[dict] = None,
) -> str:
    """Send a chat completion request; return the assistant content string."""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    payload: dict = {"model": model, "messages": messages}
    if response_format:
        payload["response_format"] = response_format

    resp = _post_json(endpoint, headers, payload, timeout)
    return resp["choices"][0]["message"]["content"]


# ---------------------------------------------------------------------------
# Parse helpers
# ---------------------------------------------------------------------------

def _parse_classification(raw: str) -> Optional[dict]:
    """Parse JSON classification response. Returns None on failure."""
    try:
        # Strip markdown fences if present
        text = raw.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        data = json.loads(text)
        if "document_type" not in data:
            return None
        return data
    except (json.JSONDecodeError, KeyError):
        return None


def _parse_extraction(raw: str) -> Optional[dict]:
    """Parse JSON extraction response. Returns None on failure."""
    try:
        text = raw.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        data = json.loads(text)
        if not isinstance(data, dict):
            return None
        return data
    except json.JSONDecodeError:
        return None


# ---------------------------------------------------------------------------
# Provider-level classify (single provider, sync inner calls)
# ---------------------------------------------------------------------------

def _classify_with_provider(
    endpoint: str,
    api_key: str,
    model: str,
    text: str,
    filename: str,
    timeout: int,
) -> tuple[dict, Optional[dict]]:
    """Call one provider; return (clf_data, extract_data_or_None).
    Raises on any error so caller can fall through to next provider.
    """
    truncated = text[:6000] if len(text) > 6000 else text
    user_content = f"Document filename: {filename}\n\nDocument text:\n{truncated}"

    # Pass 1: classify
    clf_raw = _chat(
        endpoint=endpoint,
        api_key=api_key,
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT_CLASSIFY},
            {"role": "user", "content": user_content},
        ],
        timeout=timeout,
        response_format={"type": "json_object"},
    )

    clf_data = _parse_classification(clf_raw)
    if clf_data is None:
        raise ValueError(f"Failed to parse classification JSON from {model}: {clf_raw[:200]}")

    doc_type = clf_data.get("document_type", "other")
    if doc_type not in VALID_TYPES:
        doc_type = "other"
        clf_data["document_type"] = doc_type

    # Pass 2: extract fields only for capital_call_notice
    extract_data: Optional[dict] = None
    if doc_type == "capital_call_notice":
        ext_raw = _chat(
            endpoint=endpoint,
            api_key=api_key,
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_EXTRACT},
                {"role": "user", "content": user_content},
            ],
            timeout=timeout,
            response_format={"type": "json_object"},
        )
        extract_data = _parse_extraction(ext_raw)

    return clf_data, extract_data


# ---------------------------------------------------------------------------
# Build extracted_fields dict from raw parse
# ---------------------------------------------------------------------------

def _build_extracted_fields(extract_data: Optional[dict]) -> Optional[dict]:
    """Normalise extraction response into our internal format."""
    if extract_data is None:
        return _empty_capital_call_fields(backfilled=False, confidence=0.0)

    extracted_fields: dict = {}
    for fname in CAPITAL_CALL_FIELDS:
        fdata = extract_data.get(fname, {})
        if isinstance(fdata, dict):
            extracted_fields[fname] = {
                "value": fdata.get("value"),
                "confidence": float(fdata.get("confidence", 0.0)),
                "source_text": fdata.get("source_text"),
                "backfilled": False,
            }
        else:
            extracted_fields[fname] = {
                "value": None,
                "confidence": 0.0,
                "source_text": None,
                "backfilled": False,
            }
    return extracted_fields


# ---------------------------------------------------------------------------
# Main async entry point
# ---------------------------------------------------------------------------

async def classify_document_text(text: str, filename: str = "") -> ClassificationResult:
    """Classify document text via Mistral Small → OpenAI GPT-4o-mini → heuristic fallback.

    Both AI calls are synchronous HTTP (urllib) wrapped in async function.
    Two passes per provider: classify first, then extract fields for capital_call_notice.
    """
    import asyncio

    start = time.monotonic()

    # Build provider chain
    providers: list[tuple[str, str, str, str]] = []
    if MISTRAL_API_KEY:
        providers.append((MISTRAL_ENDPOINT, MISTRAL_API_KEY, MISTRAL_MODEL, "mistral"))
    if OPENAI_API_KEY:
        providers.append((OPENAI_ENDPOINT, OPENAI_API_KEY, OPENAI_MODEL, "openai"))

    last_error: Optional[str] = None

    for endpoint, api_key, model, provider_name in providers:
        try:
            # Run synchronous HTTP in thread pool to keep async-friendly
            loop = asyncio.get_event_loop()
            clf_data, extract_data = await loop.run_in_executor(
                None,
                _classify_with_provider,
                endpoint,
                api_key,
                model,
                text,
                filename,
                CLASSIFICATION_TIMEOUT,
            )

            doc_type = clf_data.get("document_type", "other")
            confidence = float(clf_data.get("confidence", 0.0))
            indicators = clf_data.get("key_indicators", [])
            duration_ms = int((time.monotonic() - start) * 1000)

            # Build extracted_fields for capital_call_notice
            extracted_fields: Optional[dict] = None
            if doc_type == "capital_call_notice":
                extracted_fields = _build_extracted_fields(extract_data)

            if confidence < CONFIDENCE_THRESHOLD:
                heuristic_type = _heuristic_type(filename, text)
                if heuristic_type == "capital_call_notice" and extracted_fields is None:
                    extracted_fields = _empty_capital_call_fields(backfilled=False, confidence=0.0)
                return ClassificationResult(
                    document_type=heuristic_type,
                    confidence=confidence,
                    key_indicators=indicators,
                    extracted_fields=extracted_fields,
                    model_version=model,
                    provider_used=provider_name,
                    fallback=True,
                    classification_error=f"Low confidence ({confidence:.2f}); heuristic applied",
                    duration_ms=duration_ms,
                )

            return ClassificationResult(
                document_type=doc_type,
                confidence=confidence,
                key_indicators=indicators,
                extracted_fields=extracted_fields,
                model_version=model,
                provider_used=provider_name,
                fallback=False,
                duration_ms=duration_ms,
            )

        except Exception as exc:
            last_error = f"{provider_name}: {exc}"
            continue  # Try next provider

    # All providers failed — heuristic fallback
    duration_ms = int((time.monotonic() - start) * 1000)
    heuristic_type = _heuristic_type(filename, text)
    extracted_fields = None
    if heuristic_type == "capital_call_notice":
        extracted_fields = _empty_capital_call_fields(backfilled=False, confidence=0.0)

    return ClassificationResult(
        document_type=heuristic_type,
        confidence=0.0,
        extracted_fields=extracted_fields,
        model_version="heuristic",
        provider_used="heuristic",
        fallback=True,
        classification_error=last_error,
        duration_ms=duration_ms,
    )


# ---------------------------------------------------------------------------
# PDF text extraction (unchanged)
# ---------------------------------------------------------------------------

def extract_pdf_text(content: bytes) -> str:
    """Extract text layer from PDF bytes using pypdf. Returns empty string on error."""
    try:
        import pypdf

        reader = pypdf.PdfReader(io.BytesIO(content))
        parts = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                parts.append(page_text)
        return "\n".join(parts)
    except Exception:
        return ""
