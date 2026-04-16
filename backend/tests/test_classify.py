"""TDD: Classification pipeline tests v0.2 — mock Anthropic tool_use, fallback."""
import io
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.classify import classify_document_text, ClassificationResult


def _make_tool_use_block(name: str, input_data: dict):
    """Create a mock tool_use content block."""
    block = MagicMock()
    block.type = "tool_use"
    block.name = name
    block.input = input_data
    return block


def _make_message(blocks: list):
    msg = MagicMock()
    msg.content = blocks
    return msg


# ---------------------------------------------------------------------------
# Unit tests for classify_document_text()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_classify_happy_path():
    """Tool_use returns valid result → classification populated."""
    clf_block = _make_tool_use_block("classify_document", {
        "document_type": "capital_call_notice",
        "confidence": 0.94,
        "key_indicators": ["capital call", "Q2 2026"],
    })
    extract_block = _make_tool_use_block("extract_capital_call_fields", {
        "fund_name": {"value": "Fund III", "confidence": 0.95, "source_text": "Fund III"},
        "call_number": {"value": "Q2-2026", "confidence": 0.88, "source_text": "Q2-2026"},
        "amount_due": {"value": None, "confidence": 0.0, "source_text": None},
        "currency": {"value": "USD", "confidence": 0.99, "source_text": "USD"},
        "due_date": {"value": None, "confidence": 0.0, "source_text": None},
        "recipient_entity": {"value": None, "confidence": 0.0, "source_text": None},
        "wire_instructions_present": {"value": False, "confidence": 0.7, "source_text": None},
        "notice_date": {"value": None, "confidence": 0.0, "source_text": None},
    })

    mock_msg = _make_message([clf_block, extract_block])

    with patch("app.classify.anthropic_client") as mock_client:
        mock_client.messages.create = AsyncMock(return_value=mock_msg)

        result = await classify_document_text(
            text="Capital Call Notice Q2 2026 from Meridian Fund III",
            filename="capital_call.pdf",
        )

    assert result.document_type == "capital_call_notice"
    assert result.confidence == pytest.approx(0.94)
    assert result.fallback is False
    assert result.classification_error is None


@pytest.mark.asyncio
async def test_classify_fallback_on_api_error():
    """If Anthropic raises, fallback fires — no crash."""
    with patch("app.classify.anthropic_client") as mock_client:
        mock_client.messages.create = AsyncMock(side_effect=Exception("API unavailable"))

        result = await classify_document_text(
            text="Some document text",
            filename="unknown.pdf",
        )

    assert result.fallback is True
    assert result.document_type == "other"
    assert result.confidence == 0.0
    assert result.classification_error is not None


@pytest.mark.asyncio
async def test_classify_fallback_on_invalid_json():
    """If tool_use returns no classify_document block, fallback fires."""
    # Return a message with no tool_use blocks
    mock_msg = _make_message([])

    with patch("app.classify.anthropic_client") as mock_client:
        mock_client.messages.create = AsyncMock(return_value=mock_msg)

        result = await classify_document_text(
            text="Some document text",
            filename="doc.pdf",
        )

    assert result.fallback is True
    assert result.document_type in (
        "other", "capital_call_notice", "subscription_agreement",
        "side_letter", "k1", "wire_instructions",
    )


@pytest.mark.asyncio
async def test_classify_low_confidence_uses_heuristic():
    """Low confidence (<0.5) triggers heuristic fallback."""
    clf_block = _make_tool_use_block("classify_document", {
        "document_type": "other",
        "confidence": 0.3,
        "key_indicators": [],
    })
    mock_msg = _make_message([clf_block])

    with patch("app.classify.anthropic_client") as mock_client:
        mock_client.messages.create = AsyncMock(return_value=mock_msg)

        result = await classify_document_text(
            text="capital call notice fund investment",
            filename="capital_call_q2.pdf",
        )

    assert result is not None
    assert result.fallback is True


@pytest.mark.asyncio
async def test_classify_subscription_document():
    """Correctly identifies subscription agreement."""
    clf_block = _make_tool_use_block("classify_document", {
        "document_type": "subscription_agreement",
        "confidence": 0.88,
        "key_indicators": ["subscription", "investor", "limited partnership"],
    })
    mock_msg = _make_message([clf_block])

    with patch("app.classify.anthropic_client") as mock_client:
        mock_client.messages.create = AsyncMock(return_value=mock_msg)

        result = await classify_document_text(
            text="Subscription Agreement for Meridian Fund III LP",
            filename="subscription.pdf",
        )

    assert result.document_type == "subscription_agreement"
    assert result.confidence > 0.5
    # Non-capital_call_notice types don't get extracted_fields
    assert result.extracted_fields is None


# ---------------------------------------------------------------------------
# Integration: upload triggers classification (mocked)
# ---------------------------------------------------------------------------

def _login(client: TestClient, email: str, password: str) -> str:
    resp = client.post("/auth/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


def _make_pdf_bytes() -> bytes:
    return (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
        b"4 0 obj\n<< /Length 44 >>\nstream\nBT /F1 12 Tf 100 700 Td "
        b"(Capital Call Notice Q2 2026) Tj ET\nendstream\nendobj\n"
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
        b"xref\n0 6\n0000000000 65535 f \n"
        b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n9\n%%EOF\n"
    )


def test_upload_stores_classification(client: TestClient):
    """After upload, classification is attached to the package."""
    token = _login(client, "admin@arukai.example", "admin123")

    clf_block = _make_tool_use_block("classify_document", {
        "document_type": "capital_call_notice",
        "confidence": 0.91,
        "key_indicators": ["capital call"],
    })
    extract_block = _make_tool_use_block("extract_capital_call_fields", {
        "fund_name": {"value": "Fund X", "confidence": 0.9, "source_text": "Fund X"},
        "call_number": {"value": "Q1", "confidence": 0.8, "source_text": "Q1"},
        "amount_due": {"value": None, "confidence": 0.0, "source_text": None},
        "currency": {"value": "USD", "confidence": 1.0, "source_text": "USD"},
        "due_date": {"value": None, "confidence": 0.0, "source_text": None},
        "recipient_entity": {"value": None, "confidence": 0.0, "source_text": None},
        "wire_instructions_present": {"value": False, "confidence": 0.7, "source_text": None},
        "notice_date": {"value": None, "confidence": 0.0, "source_text": None},
    })
    mock_msg = _make_message([clf_block, extract_block])

    with patch("app.classify.anthropic_client") as mock_client:
        mock_client.messages.create = AsyncMock(return_value=mock_msg)

        pdf = io.BytesIO(_make_pdf_bytes())
        resp = client.post(
            "/documents/upload",
            data={"title": "Classify Integration Test"},
            files={"file": ("capital.pdf", pdf, "application/pdf")},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 201
    pkg_id = resp.json()["id"]

    detail = client.get(f"/documents/{pkg_id}", headers={"Authorization": f"Bearer {token}"})
    assert detail.status_code == 200
    detail_data = detail.json()
    docs = detail_data.get("documents", [])
    assert len(docs) > 0
    doc = docs[0]
    assert "classification" in doc
    clf = doc["classification"]
    assert clf is not None
    assert clf["document_type"] == "capital_call_notice"
