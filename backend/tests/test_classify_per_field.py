"""TDD: Per-field confidence extraction tests (S3, spec §4).

Tool_use mocked — fallback works.
(POR-147 / ARU-17-B1)
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


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


def _make_tool_use_block(name: str, input_data: dict):
    """Create a mock tool_use content block."""
    block = MagicMock()
    block.type = "tool_use"
    block.name = name
    block.input = input_data
    return block


def _make_message(blocks: list):
    """Create a mock Anthropic message response."""
    msg = MagicMock()
    msg.content = blocks
    return msg


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_classify_capital_call_returns_extracted_fields():
    """capital_call_notice classification returns per-field extracted_fields."""
    clf_block = _make_tool_use_block("classify_document", {
        "document_type": "capital_call_notice",
        "confidence": 0.92,
        "key_indicators": ["capital call", "drawdown"],
    })
    extract_block = _make_tool_use_block("extract_capital_call_fields", {
        "fund_name": {"value": "Fund III", "confidence": 0.95, "source_text": "Fund III"},
        "call_number": {"value": "Q2-2026", "confidence": 0.88, "source_text": "Call #Q2-2026"},
        "amount_due": {"value": "1,500,000", "confidence": 0.91, "source_text": "$1,500,000"},
        "currency": {"value": "USD", "confidence": 0.99, "source_text": "USD"},
        "due_date": {"value": "2026-05-15", "confidence": 0.85, "source_text": "May 15, 2026"},
        "recipient_entity": {"value": "Arukai LP", "confidence": 0.87, "source_text": "Arukai LP"},
        "wire_instructions_present": {"value": True, "confidence": 0.93, "source_text": "Wire to:"},
        "notice_date": {"value": "2026-04-15", "confidence": 0.90, "source_text": "April 15, 2026"},
    })

    mock_msg = _make_message([clf_block, extract_block])

    with patch("app.classify.anthropic_client") as mock_client:
        mock_client.messages.create = AsyncMock(return_value=mock_msg)

        from app.classify import classify_document_text
        result = await classify_document_text(
            text="Capital call notice for Fund III Q2 2026",
            filename="fund3_q2_capital_call.pdf",
        )

    assert result.document_type == "capital_call_notice"
    assert result.confidence == 0.92
    assert result.extracted_fields is not None

    # All 8 required fields present
    for field in CAPITAL_CALL_FIELDS:
        assert field in result.extracted_fields, f"Missing field: {field}"
        assert "value" in result.extracted_fields[field]
        assert "confidence" in result.extracted_fields[field]
        assert "backfilled" in result.extracted_fields[field]
        assert result.extracted_fields[field]["backfilled"] is False


@pytest.mark.asyncio
async def test_classify_non_capital_call_no_extracted_fields():
    """Non-capital_call_notice types should NOT have extracted_fields (S3)."""
    clf_block = _make_tool_use_block("classify_document", {
        "document_type": "k1",
        "confidence": 0.88,
        "key_indicators": ["schedule k-1"],
    })
    mock_msg = _make_message([clf_block])

    with patch("app.classify.anthropic_client") as mock_client:
        mock_client.messages.create = AsyncMock(return_value=mock_msg)

        from app.classify import classify_document_text
        result = await classify_document_text(
            text="Schedule K-1 tax document",
            filename="k1.pdf",
        )

    assert result.document_type == "k1"
    assert result.extracted_fields is None  # No extraction for non-capital-call


@pytest.mark.asyncio
async def test_fallback_populates_zero_confidence_fields():
    """When tool_use fails, extracted_fields has all capital_call fields with confidence=0.0."""
    from app.classify import classify_document_text

    with patch("app.classify.anthropic_client") as mock_client:
        mock_client.messages.create = AsyncMock(
            side_effect=Exception("API timeout")
        )

        result = await classify_document_text(
            text="capital call drawdown notice",
            filename="capital_call.pdf",
        )

    assert result.fallback is True
    # Heuristic detects capital_call_notice from filename
    assert result.document_type == "capital_call_notice"
    assert result.extracted_fields is not None

    for field in CAPITAL_CALL_FIELDS:
        assert field in result.extracted_fields
        assert result.extracted_fields[field]["confidence"] == 0.0
        assert result.extracted_fields[field]["value"] is None


@pytest.mark.asyncio
async def test_low_confidence_triggers_fallback_with_fields():
    """Low confidence classification triggers heuristic fallback but preserves fields."""
    clf_block = _make_tool_use_block("classify_document", {
        "document_type": "capital_call_notice",
        "confidence": 0.3,  # below threshold
        "key_indicators": ["maybe a capital call"],
    })
    extract_block = _make_tool_use_block("extract_capital_call_fields", {
        "fund_name": {"value": None, "confidence": 0.1, "source_text": None},
        "call_number": {"value": None, "confidence": 0.0, "source_text": None},
        "amount_due": {"value": None, "confidence": 0.0, "source_text": None},
        "currency": {"value": None, "confidence": 0.0, "source_text": None},
        "due_date": {"value": None, "confidence": 0.0, "source_text": None},
        "recipient_entity": {"value": None, "confidence": 0.0, "source_text": None},
        "wire_instructions_present": {"value": None, "confidence": 0.0, "source_text": None},
        "notice_date": {"value": None, "confidence": 0.0, "source_text": None},
    })

    mock_msg = _make_message([clf_block, extract_block])

    with patch("app.classify.anthropic_client") as mock_client:
        mock_client.messages.create = AsyncMock(return_value=mock_msg)

        from app.classify import classify_document_text
        result = await classify_document_text(
            text="capital call notice",
            filename="doc.pdf",
        )

    assert result.fallback is True
    assert result.confidence == 0.3


@pytest.mark.asyncio
async def test_missing_extraction_tool_uses_zero_fields():
    """If classify fires but extraction tool is absent, fields are all zero."""
    clf_block = _make_tool_use_block("classify_document", {
        "document_type": "capital_call_notice",
        "confidence": 0.85,
        "key_indicators": ["capital call"],
    })
    # No extract_capital_call_fields block in response
    mock_msg = _make_message([clf_block])

    with patch("app.classify.anthropic_client") as mock_client:
        mock_client.messages.create = AsyncMock(return_value=mock_msg)

        from app.classify import classify_document_text
        result = await classify_document_text(
            text="capital call notice text",
            filename="call.pdf",
        )

    assert result.document_type == "capital_call_notice"
    assert result.extracted_fields is not None
    for field in CAPITAL_CALL_FIELDS:
        assert result.extracted_fields[field]["confidence"] == 0.0
