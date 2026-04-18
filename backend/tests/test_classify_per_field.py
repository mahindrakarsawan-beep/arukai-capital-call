"""TDD: Per-field confidence extraction tests (S3, spec §4).

Mistral provider mocked via _classify_with_provider — fallback works.
(POR-151 / POR-147 / ARU-17-B1)
"""
import pytest
from unittest.mock import patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


def _make_clf_data(doc_type="capital_call_notice", confidence=0.92, indicators=None):
    return {
        "document_type": doc_type,
        "confidence": confidence,
        "key_indicators": indicators or ["capital call", "drawdown"],
    }


def _full_extract_data():
    return {
        "fund_name": {"value": "Fund III", "confidence": 0.95, "source_text": "Fund III"},
        "call_number": {"value": "Q2-2026", "confidence": 0.88, "source_text": "Call #Q2-2026"},
        "amount_due": {"value": "1,500,000", "confidence": 0.91, "source_text": "$1,500,000"},
        "currency": {"value": "USD", "confidence": 0.99, "source_text": "USD"},
        "due_date": {"value": "2026-05-15", "confidence": 0.85, "source_text": "May 15, 2026"},
        "recipient_entity": {"value": "Arukai LP", "confidence": 0.87, "source_text": "Arukai LP"},
        "wire_instructions_present": {"value": True, "confidence": 0.93, "source_text": "Wire to:"},
        "notice_date": {"value": "2026-04-15", "confidence": 0.90, "source_text": "April 15, 2026"},
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_classify_capital_call_returns_extracted_fields():
    """capital_call_notice classification returns per-field extracted_fields."""
    clf_data = _make_clf_data()
    extract_data = _full_extract_data()

    with patch("app.classify.MISTRAL_API_KEY", "test-key"):
        with patch("app.classify._classify_with_provider", return_value=(clf_data, extract_data)):
            from app.classify import classify_document_text
            result = await classify_document_text(
                text="Capital call notice for Fund III Q2 2026",
                filename="fund3_q2_capital_call.pdf",
            )

    assert result.document_type == "capital_call_notice"
    assert result.confidence == 0.92
    assert result.extracted_fields is not None

    # All 8 required fields present
    for f in CAPITAL_CALL_FIELDS:
        assert f in result.extracted_fields, f"Missing field: {f}"
        assert "value" in result.extracted_fields[f]
        assert "confidence" in result.extracted_fields[f]
        assert "backfilled" in result.extracted_fields[f]
        assert result.extracted_fields[f]["backfilled"] is False


@pytest.mark.asyncio
async def test_classify_non_capital_call_no_extracted_fields():
    """Non-capital_call_notice types should NOT have extracted_fields (S3)."""
    clf_data = _make_clf_data(doc_type="k1", confidence=0.88, indicators=["schedule k-1"])

    with patch("app.classify.MISTRAL_API_KEY", "test-key"):
        with patch("app.classify._classify_with_provider", return_value=(clf_data, None)):
            from app.classify import classify_document_text
            result = await classify_document_text(
                text="Schedule K-1 tax document",
                filename="k1.pdf",
            )

    assert result.document_type == "k1"
    assert result.extracted_fields is None  # No extraction for non-capital-call


@pytest.mark.asyncio
async def test_fallback_populates_zero_confidence_fields():
    """When all providers fail, extracted_fields has capital_call fields with confidence=0.0."""
    from app.classify import classify_document_text

    with patch("app.classify.MISTRAL_API_KEY", "test-key"):
        with patch("app.classify.OPENAI_API_KEY", ""):
            with patch("app.classify._classify_with_provider",
                       side_effect=Exception("API timeout")):
                result = await classify_document_text(
                    text="capital call drawdown notice",
                    filename="capital_call.pdf",
                )

    assert result.fallback is True
    # Heuristic detects capital_call_notice from filename
    assert result.document_type == "capital_call_notice"
    assert result.extracted_fields is not None

    for f in CAPITAL_CALL_FIELDS:
        assert f in result.extracted_fields
        assert result.extracted_fields[f]["confidence"] == 0.0
        assert result.extracted_fields[f]["value"] is None


@pytest.mark.asyncio
async def test_low_confidence_triggers_fallback_with_fields():
    """Low confidence classification triggers heuristic fallback but preserves fields."""
    clf_data = _make_clf_data(
        doc_type="capital_call_notice",
        confidence=0.3,  # below threshold
        indicators=["maybe a capital call"],
    )
    # Extract data with all-zero fields
    extract_data = {
        f: {"value": None, "confidence": 0.0, "source_text": None}
        for f in CAPITAL_CALL_FIELDS
    }

    with patch("app.classify.MISTRAL_API_KEY", "test-key"):
        with patch("app.classify._classify_with_provider", return_value=(clf_data, extract_data)):
            from app.classify import classify_document_text
            result = await classify_document_text(
                text="capital call notice",
                filename="doc.pdf",
            )

    assert result.fallback is True
    assert result.confidence == 0.3


@pytest.mark.asyncio
async def test_missing_extraction_data_uses_zero_fields():
    """If classify succeeds but extraction returns None, fields are all zero."""
    clf_data = _make_clf_data(confidence=0.85, indicators=["capital call"])

    with patch("app.classify.MISTRAL_API_KEY", "test-key"):
        # extract_data is None — simulates provider returning None for extraction
        with patch("app.classify._classify_with_provider", return_value=(clf_data, None)):
            from app.classify import classify_document_text
            result = await classify_document_text(
                text="capital call notice text",
                filename="call.pdf",
            )

    assert result.document_type == "capital_call_notice"
    assert result.extracted_fields is not None
    for f in CAPITAL_CALL_FIELDS:
        assert result.extracted_fields[f]["confidence"] == 0.0
